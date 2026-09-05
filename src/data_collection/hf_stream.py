"""Resumable line-by-line streaming of HuggingFace-hosted jsonl files.

Uses HTTP Range requests + a byte-offset checkpoint file, so a 22 GB stream
survives disconnects: rerunning continues from the last checkpoint. Checkpoints
are only advanced on whole processed lines.
"""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Callable, Iterator

BASE = "https://huggingface.co/datasets/McAuley-Lab/Amazon-Reviews-2023/resolve/main/"
UA = {"User-Agent": "capstone-academic-research"}
CHUNK = 1 << 20  # 1 MiB


def _open_at(url: str, offset: int):
    headers = dict(UA)
    if offset:
        headers["Range"] = f"bytes={offset}-"
    req = urllib.request.Request(url, headers=headers)
    return urllib.request.urlopen(req, timeout=60)


def stream_jsonl(relpath: str, checkpoint: Path,
                 max_bytes: int | None = None,
                 progress_every: int = 500_000) -> Iterator[dict]:
    """Yield parsed JSON objects; persist byte offset to `checkpoint` as we go.

    On resume from a mid-line offset the first partial line is discarded —
    callers must be idempotent per line (dedup by uid), which all ours are.
    """
    url = BASE + relpath
    offset = 0
    if checkpoint.exists():
        offset = json.loads(checkpoint.read_text()).get("offset", 0)
        print(f"  resuming {relpath} at byte {offset:,}")
    checkpoint.parent.mkdir(parents=True, exist_ok=True)

    n_lines, bytes_read_session, t0 = 0, 0, time.time()
    retries = 0
    while True:
        try:
            resp = _open_at(url, offset)
        except urllib.error.HTTPError as exc:
            if exc.code == 416:  # requested range beyond EOF -> done
                break
            raise
        except (urllib.error.URLError, TimeoutError, ConnectionError, OSError) as exc:
            # connection establishment failed (handshake timeout, reset, DNS...)
            retries += 1
            if retries > 12:
                checkpoint.write_text(json.dumps({"offset": offset}))
                raise RuntimeError(f"Too many connect failures on {relpath}: {exc}")
            wait = min(2 ** retries, 180)
            print(f"  connect error ({exc}); retrying in {wait}s from byte {offset:,}")
            time.sleep(wait)
            continue
        buf = b""
        first = offset > 0  # discard potential partial first line on resume
        try:
            while True:
                chunk = resp.read(CHUNK)
                if not chunk:
                    # EOF: process remaining buffer as final line
                    if buf and not first:
                        try:
                            yield json.loads(buf)
                        except json.JSONDecodeError:
                            pass
                    offset += len(buf)
                    checkpoint.write_text(json.dumps({"offset": offset, "done": True}))
                    return
                buf += chunk
                bytes_read_session += len(chunk)
                while True:
                    nl = buf.find(b"\n")
                    if nl < 0:
                        break
                    line, buf = buf[:nl], buf[nl + 1:]
                    offset += nl + 1
                    if first:
                        first = False
                    else:
                        if line.strip():
                            try:
                                yield json.loads(line)
                            except json.JSONDecodeError:
                                pass
                        n_lines += 1
                        if n_lines % progress_every == 0:
                            mb = bytes_read_session / 1e6
                            rate = mb / max(time.time() - t0, 1e-9)
                            print(f"  {relpath}: {n_lines:,} lines, "
                                  f"{mb:,.0f} MB this session ({rate:.1f} MB/s)", flush=True)
                            checkpoint.write_text(json.dumps({"offset": offset}))
                if max_bytes and bytes_read_session >= max_bytes:
                    checkpoint.write_text(json.dumps({"offset": offset}))
                    print(f"  stopped at --max-bytes cap ({bytes_read_session/1e6:.0f} MB)")
                    return
                retries = 0
        except (urllib.error.URLError, TimeoutError, ConnectionError, OSError) as exc:
            retries += 1
            if retries > 8:
                checkpoint.write_text(json.dumps({"offset": offset}))
                raise RuntimeError(f"Too many stream failures on {relpath}: {exc}")
            wait = min(2 ** retries, 120)
            print(f"  stream error ({exc}); reconnecting in {wait}s from byte {offset:,}")
            checkpoint.write_text(json.dumps({"offset": offset}))
            time.sleep(wait)
        finally:
            try:
                resp.close()
            except Exception:
                pass


def is_done(checkpoint: Path) -> bool:
    return checkpoint.exists() and json.loads(checkpoint.read_text()).get("done", False)

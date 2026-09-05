"""Multi-provider LLM pool for Stage B extraction and Stage G bridging.

Providers in priority order:
  1. gemini_flash  (google-generativeai, model gemini-3-flash; free tier ~10 RPM / 1500 RPD per key)
  2. groq_llama70b (groq sdk, model llama-3.3-70b-versatile; 30 RPM / 1000 RPD per key)
  3. ollama_gemma  (local, model gemma3:4b; unlimited but slow)
  4. mock          (deterministic keyword scorer; no network — used by tests and dry runs)

Keys live in config/llm_providers.yaml (gitignored). Multiple keys per provider are
round-robined; per-key RPM and RPD are tracked in-process. When every cloud key is
rate-limited the pool sleeps until the earliest key frees up, and when all cloud keys
are exhausted for the day it falls through to ollama.

SDK imports are lazy so the mock provider (and any single provider) works without
installing the others.
"""

from __future__ import annotations

import hashlib
import json
import re
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path

DEFAULT_CONFIG_PATH = Path("config/llm_providers.yaml")

# provider name -> (RPM limit, RPD limit) per key.
# Quotas are PER MODEL on the same key, so each model is its own provider with its
# own quota pool — that's how a fixed key set multiplies daily capacity.
# RPM values are token-derived where TPM binds (~1.2k tokens per extraction).
CLOUD_LIMITS = {
    "gemini_flash": (10, 250),        # gemini-3.5-flash: best quality, small RPD
    "gemini_flash_lite": (12, 1000),  # gemini-3.1-flash-lite: bigger free RPD
    "groq_llama70b": (8, 1000),       # 12k TPM -> ~8 effective RPM; TPD binds first
    "groq_llama8b": (5, 400),         # llama-3.1-8b-instant: 6k TPM, 500k TPD
    "cerebras_llama70b": (25, 800),   # 30 RPM, 1M tokens/day -> ~800 extractions
    "sambanova_llama70b": (15, 1500), # 10-30 RPM free tier; RPD conservative guess
    "mistral_small": (2, 2500),       # 2 RPM but ~1B tokens/month — RPM binds
    "nvidia_llama70b": (30, 900),     # NIM free tier: 40 RPM; credits bound overall
    "github_llama70b": (10, 140),     # GitHub Models: ~15 RPM / 150 RPD low tier
}
# ollama_gemma removed from the default chain 2026-07-12: audit showed 75.6%
# all-null rows (vs ~3% for cloud) — it dilutes mention_rate features. The cloud
# fleet (33 keys, 7 pools) carries the batch; gemma remains available only by
# explicit --provider ollama_gemma.
# groq_llama8b (llama-3.1-8b-instant) removed 2026-09: Groq decommissioned the
# model (404 model_not_found). Its definition is kept below but it is out of the
# default rotation; re-add only with a currently-served Groq model id.
PROVIDER_ORDER = ["gemini_flash", "gemini_flash_lite", "groq_llama70b",
                  "cerebras_llama70b", "sambanova_llama70b", "nvidia_llama70b",
                  "mistral_small", "github_llama70b"]
PROVIDER_MODELS = {
    "gemini_flash": "gemini-3.5-flash",
    "gemini_flash_lite": "gemini-3.1-flash-lite",
    "groq_llama70b": "llama-3.3-70b-versatile",
    "groq_llama8b": "llama-3.1-8b-instant",
    "cerebras_llama70b": "gpt-oss-120b",  # largest/best on Cerebras' 2026 free lineup
    "sambanova_llama70b": "Meta-Llama-3.3-70B-Instruct",
    "mistral_small": "mistral-small-latest",
    "nvidia_llama70b": "meta/llama-3.3-70b-instruct",
    "github_llama70b": "meta/Llama-3.3-70B-Instruct",
}
# OpenAI-compatible providers: one client implementation covers all three
OPENAI_COMPAT_BASE = {
    "cerebras_llama70b": "https://api.cerebras.ai/v1",
    "sambanova_llama70b": "https://api.sambanova.ai/v1",
    "mistral_small": "https://api.mistral.ai/v1",
    "nvidia_llama70b": "https://integrate.api.nvidia.com/v1",
    "github_llama70b": "https://models.github.ai/inference",
}
# providers whose API rejects response_format json_object (send plain, strip_json handles)
NO_JSON_MODE = {"sambanova_llama70b"}


class ProviderError(RuntimeError):
    """A provider failed to produce any text (network, auth, empty response)."""


@dataclass
class _KeyState:
    key: str
    minute_stamps: list[float] = field(default_factory=list)
    day_count: int = 0
    day_start: float = field(default_factory=time.time)
    cooldown_until: float = 0.0  # set on 429s the local counters didn't predict

    def _roll(self) -> None:
        now = time.time()
        self.minute_stamps = [t for t in self.minute_stamps if now - t < 60]
        if now - self.day_start > 86400:
            self.day_count = 0
            self.day_start = now

    def available_at(self, rpm: int, rpd: int) -> float:
        """Return the earliest time this key can serve a request (0 = now)."""
        self._roll()
        if time.time() < self.cooldown_until:
            return self.cooldown_until
        if self.day_count >= rpd:
            return self.day_start + 86400
        if len(self.minute_stamps) >= rpm:
            return self.minute_stamps[0] + 60
        return 0.0

    def record(self) -> None:
        self.minute_stamps.append(time.time())
        self.day_count += 1


def _load_config(config_path: Path) -> dict:
    import yaml  # local import: not needed for mock-only usage via explicit config

    if not config_path.exists():
        # Cloud deployments (e.g. Streamlit Cloud) have no yaml — read keys from
        # env vars instead: GEMINI_API_KEYS / GROQ_API_KEYS (comma-separated).
        env_cfg = _config_from_env()
        if env_cfg:
            return env_cfg
        raise FileNotFoundError(
            f"{config_path} not found and no GEMINI_API_KEYS/GROQ_API_KEYS env vars set. "
            "Copy config/llm_providers.yaml.template and add keys."
        )
    with open(config_path, encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def _config_from_env() -> dict:
    import os

    cfg: dict = {}
    for env_name, provider in (("GEMINI_API_KEYS", "gemini"), ("GROQ_API_KEYS", "groq")):
        raw = os.environ.get(env_name) or os.environ.get(env_name.rstrip("S"))  # singular too
        keys = [k.strip() for k in raw.split(",") if k.strip()] if raw else []
        if keys:
            cfg[provider] = {"keys": keys}
    return cfg


def strip_json(text: str) -> str:
    """Strip markdown fences / prose around the first JSON object in the text."""
    text = text.strip()
    fence = re.match(r"^```(?:json)?\s*(.*?)\s*```$", text, re.DOTALL)
    if fence:
        return fence.group(1).strip()
    start = text.find("{")
    if start > 0:
        depth = 0
        for i, ch in enumerate(text[start:], start):
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    return text[start : i + 1]
    return text


class ProviderPool:
    """Round-robin key pool with rate limiting and provider fallthrough."""

    def __init__(self, config: dict | None = None,
                 config_path: Path = DEFAULT_CONFIG_PATH,
                 providers: list[str] | None = None):
        cfg = config if config is not None else _load_config(config_path)
        self.providers = providers or list(PROVIDER_ORDER)
        gemini_keys = [k for k in cfg.get("gemini", {}).get("keys", [])
                       if k and not k.startswith("YOUR_")]
        groq_keys = [k for k in cfg.get("groq", {}).get("keys", [])
                     if k and not k.startswith("YOUR_")]
        def _sect(name: str) -> list[str]:
            return [k for k in (cfg.get(name, {}) or {}).get("keys", [])
                    if k and not k.startswith("YOUR_")]

        # separate _KeyState per provider: per-model quotas are independent
        self.keys: dict[str, list[_KeyState]] = {
            "gemini_flash": [_KeyState(k) for k in gemini_keys],
            "gemini_flash_lite": [_KeyState(k) for k in gemini_keys],
            "groq_llama70b": [_KeyState(k) for k in groq_keys],
            "groq_llama8b": [_KeyState(k) for k in groq_keys],
            "cerebras_llama70b": [_KeyState(k) for k in _sect("cerebras")],
            "sambanova_llama70b": [_KeyState(k) for k in _sect("sambanova")],
            "mistral_small": [_KeyState(k) for k in _sect("mistral")],
            "nvidia_llama70b": [_KeyState(k) for k in _sect("nvidia")],
            "github_llama70b": [_KeyState(k) for k in _sect("github")],
        }
        ollama_cfg = cfg.get("ollama", {}) or {}
        self.ollama_model = ollama_cfg.get("model", "gemma3:4b")
        self.ollama_base_url = ollama_cfg.get("base_url", "http://localhost:11434")
        self._rr: dict[str, int] = {}
        self._lock = threading.Lock()  # guards key selection/reservation across workers
        # remove cloud providers with no usable keys
        self.providers = [p for p in self.providers
                          if p in ("ollama_gemma", "mock") or self.keys.get(p)]
        if not self.providers:
            raise RuntimeError("No usable providers: add keys to config/llm_providers.yaml "
                               "or ensure ollama is configured.")

    # -- key selection ---------------------------------------------------

    def _pick_key(self, provider: str, max_wait: float = 90.0) -> _KeyState | None:
        """Pick and RESERVE the next available key (thread-safe), sleeping up to
        max_wait if all are limited. Reservation = the RPM/RPD slot is consumed
        at pick time so concurrent workers cannot double-book a key."""
        states = self.keys.get(provider, [])
        if not states:
            return None
        rpm, rpd = CLOUD_LIMITS[provider]
        deadline = time.time() + max_wait
        while True:
            with self._lock:
                start = self._rr.get(provider, 0)
                best_at = float("inf")
                for i in range(len(states)):
                    st = states[(start + i) % len(states)]
                    at = st.available_at(rpm, rpd)
                    if at == 0.0:
                        self._rr[provider] = (start + i + 1) % len(states)
                        st.record()  # reserve the slot under the lock
                        return st
                    best_at = min(best_at, at)
            wait = best_at - time.time()
            if time.time() + max(wait, 0.5) > deadline:
                return None  # limited for too long -> caller falls through
            time.sleep(min(max(wait, 0.5) + 0.2, max_wait))

    # -- provider backends ------------------------------------------------

    def _call_gemini(self, prompt: str, key: str, json_mode: bool,
                     model_name: str) -> str:
        import google.generativeai as genai

        genai.configure(api_key=key)
        gen_cfg = {"temperature": 0.1}
        if json_mode:
            gen_cfg["response_mime_type"] = "application/json"
        # pinned model names (not "-latest" aliases): extraction scores must come
        # from fixed model versions for the whole batch
        model = genai.GenerativeModel(model_name, generation_config=gen_cfg)
        resp = model.generate_content(prompt)
        if not getattr(resp, "text", None):
            raise ProviderError("gemini returned empty response")
        return resp.text

    def _call_groq(self, prompt: str, key: str, json_mode: bool,
                   model_name: str) -> str:
        from groq import Groq

        client = Groq(api_key=key)
        kwargs = {"response_format": {"type": "json_object"}} if json_mode else {}
        resp = client.chat.completions.create(
            model=model_name,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1,
            **kwargs,
        )
        text = resp.choices[0].message.content
        if not text:
            raise ProviderError("groq returned empty response")
        return text

    _ollama_sem = threading.Semaphore(2)  # a laptop can't serve 6 parallel gemma runs

    def _call_openai_compat(self, prompt: str, key: str, json_mode: bool,
                            provider: str) -> str:
        from openai import OpenAI

        client = OpenAI(api_key=key, base_url=OPENAI_COMPAT_BASE[provider],
                        timeout=60, max_retries=0)
        kwargs = ({"response_format": {"type": "json_object"}}
                  if json_mode and provider not in NO_JSON_MODE else {})
        resp = client.chat.completions.create(
            model=PROVIDER_MODELS[provider],
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1,
            **kwargs,
        )
        text = resp.choices[0].message.content
        if not text:
            raise ProviderError(f"{provider} returned empty response")
        return text

    def _call_ollama(self, prompt: str) -> str:
        import ollama

        if not self._ollama_sem.acquire(timeout=45):
            # queue for the local model rather than erroring into 30s+ backoffs —
            # when cloud is day-capped, ollama is the only engine and idle time is waste
            raise ProviderError("ollama busy (2 concurrent inferences max)")
        try:
            # small local models drift from the nested schema without reinforcement
            prompt = prompt + (
                '\n\nCRITICAL FORMAT RULE: every aspect value must be either null or '
                'an object of the exact form {"score": <number 0-10>, "evidence": '
                '"<short verbatim quote>"}. Never output a bare number. Include ALL '
                'listed aspects as keys.'
            )
            client = ollama.Client(host=self.ollama_base_url)
            resp = client.generate(model=self.ollama_model, prompt=prompt,
                                   format="json", options={"temperature": 0.1})
        finally:
            self._ollama_sem.release()
        text = resp.get("response", "")
        if not text:
            raise ProviderError("ollama returned empty response")
        return text

    def _call_mock(self, prompt: str) -> str:
        return mock_llm_response(prompt)

    # -- public API --------------------------------------------------------

    def generate(self, prompt: str, provider: str | None = None,
                 json_mode: bool = True) -> tuple[str, str]:
        """Generate text. Returns (text, provider_used). Raises ProviderError if
        the chosen provider (or, with provider=None, every provider) fails."""
        chain = [provider] if provider else list(self.providers)
        last_err: Exception | None = None
        for prov in chain:
            try:
                if prov == "mock":
                    return self._call_mock(prompt), "mock"
                if prov == "ollama_gemma":
                    return self._call_ollama(prompt), "ollama_gemma"
                # pinned provider: wait out rate limits; chain mode: probe briefly
                # for a cloud slot, then overflow so the local model stays fed
                key = self._pick_key(prov, max_wait=90.0 if provider else 5.0)
                if key is None:
                    continue
                try:
                    model_name = PROVIDER_MODELS[prov]
                    if prov in OPENAI_COMPAT_BASE:
                        text = self._call_openai_compat(prompt, key.key, json_mode, prov)
                    elif prov.startswith("gemini"):
                        text = self._call_gemini(prompt, key.key, json_mode, model_name)
                    elif prov.startswith("groq"):
                        text = self._call_groq(prompt, key.key, json_mode, model_name)
                    else:
                        raise ValueError(f"Unknown provider {prov!r}")
                except Exception as exc:
                    msg = str(exc)
                    low = msg.lower()
                    if "429" in msg or "quota" in low or "rate limit" in low:
                        # provider-side limit our local counters missed: bench the key.
                        # Daily-quota 429s bench long; per-minute (TPM) ones bench short.
                        long_term = "day" in low or "daily" in low
                        key.cooldown_until = time.time() + (3600 if long_term else 90)
                    raise
                return text, prov  # slot was reserved at pick time
            except ProviderError as exc:
                last_err = exc
            except Exception as exc:  # SDK/network errors count as provider failure
                last_err = exc
        raise ProviderError(f"All providers failed. Last error: {last_err}")

    def earliest_available(self) -> float:
        """Earliest epoch time any cloud key can serve a request (inf if no cloud keys)."""
        best = float("inf")
        for prov, states in self.keys.items():
            rpm, rpd = CLOUD_LIMITS[prov]
            for st in states:
                best = min(best, st.available_at(rpm, rpd))
        return best

    def next_provider_after(self, provider: str) -> str | None:
        """The provider to switch to after `provider` fails twice (retry policy)."""
        try:
            i = self.providers.index(provider)
        except ValueError:
            return self.providers[0] if self.providers else None
        return self.providers[i + 1] if i + 1 < len(self.providers) else None


# --------------------------------------------------------------------------
# Mock provider: deterministic keyword-based extraction, used for tests,
# smoke runs, and the hand-validation dry run. NEVER use for real extraction.
# --------------------------------------------------------------------------

_MOCK_KEYWORDS = {
    "value_for_money": ["price", "worth", "value", "cheap", "expensive", "money", "cost",
                        "subscription", "iap"],
    "utility": ["works", "sound", "function", "feature", "useful", "does the job", "purpose",
                "tracking", "accurate"],
    "ease_of_use": ["easy", "simple", "intuitive", "setup", "comfortable", "learning curve",
                    "navigation", "confusing"],
    "reliability": ["reliable", "consistent", "disconnect", "malfunction", "sync", "always",
                    "never fails", "stopped working"],
    "design_appeal": ["design", "look", "beautiful", "sleek", "ugly", "aesthetic", "stylish"],
    "after_sales": ["support", "warranty", "customer service", "replacement", "refund",
                    "developer responded"],
    "build_quality": ["build", "material", "solid", "plastic", "sturdy", "flimsy", "premium feel"],
    "durability": ["durable", "lasted", "broke", "wear", "months", "years", "still going"],
    "repairability": ["repair", "spare", "fix", "serviceable", "replaceable battery"],
    "performance": ["fast", "slow", "smooth", "lag", "battery drain", "load", "snappy"],
    "stability": ["crash", "bug", "freeze", "glitch", "stable"],
    "ad_experience": ["ads", "advert", "ad-free", "popup"],
    "update_support": ["update", "new version", "abandoned", "changelog"],
    "privacy_trust": ["privacy", "permission", "data", "trust", "tracking me"],
}
_NEGATIVE = ["not", "bad", "poor", "terrible", "broke", "crash", "slow", "ugly", "flimsy",
             "expensive", "disconnect", "drain", "abandoned", "worst", "awful", "stopped",
             "confusing", "lag", "glitch", "intrusive"]
_POSITIVE = ["great", "excellent", "love", "amazing", "perfect", "solid", "easy", "fast",
             "smooth", "beautiful", "worth", "sturdy", "reliable", "best", "premium",
             "snappy", "stable"]


def _mock_aspect_keys(prompt: str) -> list[str]:
    keys = []
    for line in prompt.splitlines():
        m = re.match(r"^- (\w+):", line.strip())
        if m and m.group(1) in _MOCK_KEYWORDS:
            keys.append(m.group(1))
    return keys


def mock_llm_response(prompt: str) -> str:
    """Deterministic pseudo-extraction: keyword presence -> score, evidence = matched window."""
    m = re.search(r'"""(.*?)"""', prompt, re.DOTALL)
    review = (m.group(1) if m else prompt).lower()
    keys = _mock_aspect_keys(prompt)
    if not keys:  # bridging-style prompt: score everything 4-8 deterministically
        keys = _mock_aspect_keys(prompt) or list(_MOCK_KEYWORDS)
    scores: dict = {}
    for k in keys:
        hit = next((w for w in _MOCK_KEYWORDS[k] if w in review), None)
        if hit is None:
            scores[k] = None
            continue
        idx = review.find(hit)
        window = review[max(0, idx - 30): idx + 40]
        neg = sum(w in window for w in _NEGATIVE)
        pos = sum(w in window for w in _POSITIVE)
        h = int(hashlib.md5((k + review[:80]).encode()).hexdigest(), 16) % 20 / 10.0
        score = 5.0 + (pos - neg) * 2.0 + h - 1.0
        score = max(0.0, min(10.0, round(score, 1)))
        words = review[idx: idx + 60].split()
        evidence = " ".join(words[:6])[:60] or hit
        scores[k] = {"score": score, "evidence": evidence}
    n_scored = sum(1 for v in scores.values() if v)
    confidence = round(min(1.0, 0.4 + 0.1 * n_scored), 2)
    return json.dumps({"scores": scores, "confidence": confidence})

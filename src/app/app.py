"""Streamlit UI for the Hybrid AI Product Success Predictor.

Run: streamlit run src/app/app.py
Requires: trained models (Stage E), category profiles (Stage F), and gemini keys
in config/llm_providers.yaml (or check "mock mode" for an offline demo).
"""

from __future__ import annotations

import gc
import json
import sys
import time
import threading
from pathlib import Path

# Detect if running under Streamlit
is_streamlit = any('streamlit' in arg for arg in sys.argv) or 'streamlit' in sys.modules

if not is_streamlit:
    import uvicorn
    import webbrowser
    # Ensure the project root is importable so uvicorn can resolve "src.app.api"
    # regardless of the directory the script was launched from.
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    print("Starting premium React + FastAPI application on http://127.0.0.1:8000 ...")
    try:
        webbrowser.open("http://127.0.0.1:8000")
    except Exception:
        pass
    uvicorn.run("src.app.api:app", host="127.0.0.1", port=8000, reload=False)
    sys.exit(0)

# Running under Streamlit
import streamlit as st
import streamlit.components.v1 as components
import tornado.web
import tornado.httpclient
from tornado.routing import Rule, PathMatches

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

PHYSICAL_CATEGORIES = ["wireless_headphones", "bluetooth_speakers", "ice_makers",
                       "smartwatches", "power_banks"]
APP_CATEGORIES: list[str] = []  # apps removed from the system

# -- 1. Background FastAPI Service ----------------------------------------------
def run_backend():
    from src.app.api import app as fastapi_app
    import uvicorn
    uvicorn.run(fastapi_app, host="127.0.0.1", port=8000, log_level="warning")

if not any(t.name == "fastapi-backend" for t in threading.enumerate()):
    backend_thread = threading.Thread(target=run_backend, name="fastapi-backend", daemon=True)
    backend_thread.start()
    # Wait until uvicorn actually accepts connections — a fixed sleep loses the
    # race on cloud cold starts (xgboost/pandas/shap imports take several
    # seconds), and the React UI fires /api/categories immediately on load.
    import socket
    for _ in range(60):  # up to 30s
        try:
            with socket.create_connection(("127.0.0.1", 8000), timeout=0.5):
                break
        except OSError:
            time.sleep(0.5)

# -- 2. Tornado Reverse Proxy Setup ----------------------------------------------
class PremiumHtmlHandler(tornado.web.RequestHandler):
    def get(self):
        index_path = Path(__file__).resolve().parent / "frontend/dist/index.html"
        if not index_path.exists():
            self.set_status(404)
            self.write("React build assets not found. Make sure 'npm run build' was run before deploying.")
            return
        self.set_header("Content-Type", "text/html")
        self.write(index_path.read_text(encoding="utf-8"))

class TornadoProxyHandler(tornado.web.RequestHandler):
    async def get(self, path=None):
        await self._proxy(path)

    async def post(self, path=None):
        await self._proxy(path)

    async def _proxy(self, path):
        client = tornado.httpclient.AsyncHTTPClient()
        url = f"http://127.0.0.1:8000{self.request.path}"
        headers = dict(self.request.headers)
        headers.pop("Host", None)
        
        req = tornado.httpclient.HTTPRequest(
            url=url,
            method=self.request.method,
            headers=headers,
            body=self.request.body if self.request.body else None,
            allow_nonstandard_methods=True,
            request_timeout=60.0
        )
        try:
            resp = await client.fetch(req)
            self.set_status(resp.code)
            for k, v in resp.headers.get_all():
                if k not in ("Content-Encoding", "Transfer-Encoding"):
                    self.set_header(k, v)
            self.write(resp.body)
        except tornado.httpclient.HTTPClientError as e:
            self.set_status(e.code)
            if e.response:
                self.write(e.response.body)
            else:
                self.write(str(e))
        except Exception as e:
            self.set_status(500)
            self.write(str(e))

@st.cache_resource
def setup_tornado_routing():
    try:
        from tornado.web import Application
        tornado_app = next(o for o in gc.get_referrers(Application) if o.__class__ is Application)
        
        existing_rules = [r.target for r in tornado_app.wildcard_router.rules]
        if PremiumHtmlHandler not in existing_rules:
            # We inject our rules at index 0 so they match before Streamlit core
            tornado_app.wildcard_router.rules.insert(0, Rule(PathMatches(r"/app-premium"), PremiumHtmlHandler))
            tornado_app.wildcard_router.rules.insert(0, Rule(PathMatches(r"/assets/(.*)"), TornadoProxyHandler))
            tornado_app.wildcard_router.rules.insert(0, Rule(PathMatches(r"/api/(.*)"), TornadoProxyHandler))
            tornado_app.wildcard_router.rules.insert(0, Rule(PathMatches(r"/favicon.svg"), TornadoProxyHandler))
    except Exception as e:
        st.error(f"Failed to initialize premium routing tunnel: {e}")

setup_tornado_routing()

# -- 3. Premium App Layout serving ---------------------------------------------
st.set_page_config(page_title="Product Success Predictor", layout="wide", initial_sidebar_state="collapsed")

# Hide standard Streamlit header, footer, margins, and configure full page viewport
st.markdown("""
    <style>
        #MainMenu {visibility: hidden;}
        header {visibility: hidden;}
        footer {visibility: hidden;}
        .block-container {
            padding-top: 0rem !important;
            padding-bottom: 0rem !important;
            padding-left: 0rem !important;
            padding-right: 0rem !important;
        }
        iframe {
            border: none;
            width: 100vw;
            height: 98vh;
        }
    </style>
""", unsafe_allow_html=True)

# Render the React Premium Interface inside the proxy container
components.iframe("/app-premium", height=900)

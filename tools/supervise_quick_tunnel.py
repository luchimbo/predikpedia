"""Run the loopback relay + Cloudflare Quick Tunnel and sync its URL to Render.

All credentials are read from the process environment or an ignored dotenv file.
"""

from __future__ import annotations

import json
import os
import re
import signal
import subprocess
import sys
import time
from pathlib import Path
from urllib.parse import urlparse
from urllib.error import HTTPError
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
LOG_DIR = ROOT / ".runtime-logs"
TUNNEL_URL_RE = re.compile(r"https://[a-z0-9-]+\.trycloudflare\.com", re.IGNORECASE)
RENDER_API = "https://api.render.com/v1"


def load_dotenv_file(path: Path) -> None:
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def render_request(method: str, path: str, payload: dict | None = None):
    token = os.environ["RENDER_API_KEY"]
    data = json.dumps(payload).encode() if payload is not None else None
    request = Request(
        f"{RENDER_API}{path}", data=data, method=method,
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json", "Accept": "application/json"},
    )
    try:
        with urlopen(request, timeout=30) as response:
            raw = response.read()
            return json.loads(raw) if raw else None
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Render API {method} falló con HTTP {exc.code}: {detail}") from exc


def render_service_id() -> str:
    """Extract a plain srv- ID, tolerating an accidentally pasted URL/query."""
    raw = os.environ["RENDER_SERVICE_ID"].strip()
    parsed = urlparse(raw)
    value = parsed.path if parsed.scheme else raw
    value = value.split("?", 1)[0].rstrip("/")
    if "/" in value:
        value = value.rsplit("/", 1)[-1]
    if not value.startswith("srv-"):
        raise RuntimeError("RENDER_SERVICE_ID debe contener solamente un identificador srv-...")
    return value


def sync_render(tunnel_url: str) -> bool:
    service_id = render_service_id()
    desired = {
        "LLM_PROVIDER": "schedule",
        "LLM_SCHEDULE_TIMEZONE": "America/Argentina/Buenos_Aires",
        "LLM_LOCAL_START": "09:30",
        "LLM_LOCAL_END": "17:30",
        "LLM_LOCAL_BASE_URL": f"{tunnel_url}/v1",
        "LLM_LOCAL_API_KEY": os.environ["LLM_RELAY_BEARER_TOKEN"],
        "LLM_LOCAL_MODEL": os.getenv("LLM_LOCAL_MODEL", "qwen2.5:32b"),
        "OPENROUTER_MODEL": os.environ["OPENROUTER_MODEL"],
    }
    # Render's env-var list response can be unavailable or redacted depending
    # on account/API version. Track the last successfully applied Quick Tunnel
    # locally instead; every new Quick Tunnel URL is necessarily a new target.
    state_file = LOG_DIR / "last_render_tunnel_url.txt"
    previous_url = state_file.read_text(encoding="utf-8").strip() if state_file.exists() else ""
    base_url_changed = previous_url != desired["LLM_LOCAL_BASE_URL"]
    for key, value in desired.items():
        render_request("PUT", f"/services/{service_id}/env-vars/{key}", {"value": value})
    if base_url_changed:
        render_request("POST", f"/services/{service_id}/deploys", {"clearCache": "do_not_clear"})
        state_file.write_text(desired["LLM_LOCAL_BASE_URL"] + "\n", encoding="utf-8")
        print("Render actualizado y redeploy iniciado para la nueva URL del túnel.", flush=True)
    else:
        print("URL de túnel sin cambios; no se inicia redeploy.", flush=True)
    return base_url_changed


def require_environment() -> None:
    missing = [key for key in ("LLM_RELAY_BEARER_TOKEN", "RENDER_API_KEY", "RENDER_SERVICE_ID", "OPENROUTER_MODEL") if not os.getenv(key)]
    if missing:
        raise RuntimeError("Faltan variables requeridas: " + ", ".join(missing))


def main() -> None:
    load_dotenv_file(ROOT / ".env.relay.local")
    require_environment()
    LOG_DIR.mkdir(exist_ok=True)
    relay_log = (LOG_DIR / "ollama-relay.log").open("a", encoding="utf-8")
    relay = subprocess.Popen([sys.executable, str(ROOT / "tools" / "ollama_relay.py")], cwd=ROOT, stdout=relay_log, stderr=relay_log)
    cloudflared = os.getenv("CLOUDFLARED_BIN", "cloudflared")
    try:
        while True:
            tunnel_log = (LOG_DIR / "cloudflared.log").open("a", encoding="utf-8")
            tunnel = subprocess.Popen(
                [cloudflared, "tunnel", "--url", "http://127.0.0.1:3100"], cwd=ROOT,
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding="utf-8",
            )
            url = None
            assert tunnel.stdout is not None
            for line in tunnel.stdout:
                tunnel_log.write(line)
                tunnel_log.flush()
                match = TUNNEL_URL_RE.search(line)
                if match and url is None:
                    url = match.group(0)
                    print(f"Quick Tunnel disponible: {url}", flush=True)
                    sync_render(url)
            tunnel_log.close()
            if tunnel.returncode is None:
                tunnel.wait()
            print("cloudflared terminó; reiniciando en 5 segundos.", flush=True)
            time.sleep(5)
    except KeyboardInterrupt:
        print("Deteniendo procesos creados por el supervisor.", flush=True)
    finally:
        for process in (locals().get("tunnel"), relay):
            if process and process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    process.kill()
        relay_log.close()


if __name__ == "__main__":
    main()

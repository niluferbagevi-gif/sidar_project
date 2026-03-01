"""
Sidar Project - Web Arayüzü Sunucusu
FastAPI + SSE (Server-Sent Events) ile asenkron (async) akış destekli chat arayüzü.

Başlatmak için:
    python web_server.py
    python web_server.py --host 0.0.0.0 --port 7860
"""

import argparse
import asyncio
import json
import logging
import subprocess
import time
from collections import defaultdict
from pathlib import Path

import uvicorn
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse, Response

from config import Config
from agent.sidar_agent import SidarAgent

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────
#  UYGULAMA BAŞLATMA
# ─────────────────────────────────────────────

cfg = Config()
_agent: SidarAgent | None = None
_agent_lock = asyncio.Lock()


async def get_agent() -> SidarAgent:
    """Singleton ajan — ilk async çağrıda başlatılır (asyncio.Lock ile korunur)."""
    global _agent
    if _agent is None:
        async with _agent_lock:
            if _agent is None:
                _agent = SidarAgent(cfg)
    return _agent


# ─────────────────────────────────────────────
#  FASTAPI UYGULAMASI
# ─────────────────────────────────────────────

app = FastAPI(title="Sidar Web UI", docs_url=None, redoc_url=None)

# CORS: Yalnızca localhost'tan gelen isteklere izin ver
_ALLOWED_ORIGINS = [
    "http://localhost:7860",
    "http://127.0.0.1:7860",
    "http://0.0.0.0:7860",
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_ALLOWED_ORIGINS,
    allow_methods=["GET", "POST", "DELETE"],
    allow_headers=["Content-Type"],
)

# ─────────────────────────────────────────────
#  RATE LIMITING (basit in-memory)
# ─────────────────────────────────────────────

_rate_data: dict[str, list[float]] = defaultdict(list)
_RATE_LIMIT  = 20   # maksimum istek sayısı
_RATE_WINDOW = 60   # saniye cinsinden pencere


def _is_rate_limited(ip: str) -> bool:
    now = time.monotonic()
    window_start = now - _RATE_WINDOW
    calls = _rate_data[ip]
    # Pencere dışındakileri temizle
    _rate_data[ip] = [t for t in calls if t > window_start]
    if len(_rate_data[ip]) >= _RATE_LIMIT:
        return True
    _rate_data[ip].append(now)
    return False


@app.middleware("http")
async def rate_limit_middleware(request: Request, call_next):
    if request.url.path == "/chat":
        client_ip = request.client.host if request.client else "unknown"
        if _is_rate_limited(client_ip):
            return JSONResponse(
                {"error": "Çok fazla istek. Lütfen bir dakika bekleyin."},
                status_code=429,
            )
    return await call_next(request)

WEB_DIR = Path(__file__).parent / "web_ui"


# ─────────────────────────────────────────────
#  ROTALAR
# ─────────────────────────────────────────────

@app.get("/favicon.ico", include_in_schema=False)
async def favicon():
    """Tarayıcının favicon isteğini 404 hatası vermeden sessizce (204) geçiştirir."""
    return Response(status_code=204)


@app.get("/", response_class=HTMLResponse)
async def index():
    """Ana sayfa — chat arayüzü."""
    html_file = WEB_DIR / "index.html"
    if not html_file.exists():
        return HTMLResponse("<h1>Hata: web_ui/index.html bulunamadı.</h1>", status_code=500)
    return html_file.read_text(encoding="utf-8")


@app.post("/chat")
async def chat(request: Request):
    """
    Kullanıcı mesajını SSE akışı olarak işler.
    Agent artık asenkron (AsyncIterator) olduğu için doğrudan await edilebilir.
    (Eski Thread/Queue yapısı tamamen kaldırılmıştır).
    """
    body = await request.json()
    user_message = body.get("message", "").strip()

    if not user_message:
        return JSONResponse({"error": "Mesaj boş olamaz."}, status_code=400)

    async def sse_generator():
        """Asenkron SSE akışı: Ajan yanıtlarını dinler ve yayar."""
        try:
            agent = await get_agent()
            
            # Eğer aktif bir başlık yoksa ve bu ilk mesajsa, basit bir başlık üretelim
            if len(agent.memory) == 0:
                title = user_message[:30] + "..." if len(user_message) > 30 else user_message
                agent.memory.update_title(title)

            # Ajanın asenkron stream yanıtını bekle ve akıt
            async for chunk in agent.respond(user_message):
                if await request.is_disconnected():
                    logger.info("İstemci bağlantıyı kesti, stream durduruluyor.")
                    return
                yield f"data: {json.dumps({'chunk': chunk})}\n\n"

            # Akış başarıyla tamamlandı
            yield f"data: {json.dumps({'done': True})}\n\n"

        except Exception as exc:
            logger.exception("Agent respond hatası: %s", exc)
            err_chunk = json.dumps({"chunk": f"\n[Sistem Hatası] {exc}"})
            yield f"data: {err_chunk}\n\n"
            yield f"data: {json.dumps({'done': True})}\n\n"

    return StreamingResponse(
        sse_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",   # Nginx proxy'de buffering'i kapat
        },
    )


@app.get("/status")
async def status():
    """Ajan durum bilgisini JSON olarak döndür."""
    a = await get_agent()
    gpu_info = a.health.get_gpu_info()
    return JSONResponse({
        "version": a.VERSION,
        "provider": a.cfg.AI_PROVIDER,
        "model": a.cfg.CODING_MODEL,
        "access_level": a.cfg.ACCESS_LEVEL,
        "memory_count": len(a.memory),
        "github": a.github.is_available(),
        "web_search": a.web.is_available(),
        "rag_status": a.docs.status(),
        "pkg_status": a.pkg.status(),
        # GPU bilgisi
        "gpu_enabled": a.cfg.USE_GPU,
        "gpu_info": a.cfg.GPU_INFO,
        "gpu_count": getattr(a.cfg, "GPU_COUNT", 0),
        "cuda_version": getattr(a.cfg, "CUDA_VERSION", "N/A"),
        "gpu_devices": gpu_info.get("devices", []),
    })

# ─────────────────────────────────────────────
#  ÇOKLU SOHBET (SESSIONS) ROTALARI
# ─────────────────────────────────────────────

@app.get("/sessions")
async def get_sessions():
    """Tüm oturumların listesini döndürür."""
    agent = await get_agent()
    return JSONResponse({
        "active_session": agent.memory.active_session_id,
        "sessions": agent.memory.get_all_sessions()
    })

@app.get("/sessions/{session_id}")
async def load_session(session_id: str):
    """Belirli bir oturumu yükler ve geçmişini döndürür."""
    agent = await get_agent()
    if agent.memory.load_session(session_id):
        return JSONResponse({"success": True, "history": agent.memory.get_history()})
    return JSONResponse({"success": False, "error": "Oturum bulunamadı."}, status_code=404)

@app.post("/sessions/new")
async def new_session():
    """Yeni bir oturum oluşturur."""
    agent = await get_agent()
    session_id = agent.memory.create_session("Yeni Sohbet")
    return JSONResponse({"success": True, "session_id": session_id})

@app.delete("/sessions/{session_id}")
async def delete_session(session_id: str):
    """Belirli bir oturumu siler."""
    agent = await get_agent()
    if agent.memory.delete_session(session_id):
        return JSONResponse({
            "success": True, 
            "active_session": agent.memory.active_session_id
        })
    return JSONResponse({"success": False, "error": "Silinemedi."}, status_code=500)

@app.get("/git-info")
async def git_info():
    """Git deposu bilgilerini (dal adı, repo adı) döndürür."""
    _root = Path(__file__).parent

    def _run(cmd):
        try:
            return subprocess.check_output(
                cmd, cwd=str(_root), stderr=subprocess.DEVNULL
            ).decode().strip()
        except Exception:
            return ""

    branch  = _run(["git", "rev-parse", "--abbrev-ref", "HEAD"]) or "main"
    remote  = _run(["git", "remote", "get-url", "origin"]) or ""

    # GitHub URL'sini "owner/repo" biçimine çevir
    repo = ""
    if remote:
        # https://github.com/owner/repo.git  →  owner/repo
        # git@github.com:owner/repo.git      →  owner/repo
        repo = remote.rstrip(".git")
        repo = repo.split("github.com/")[-1].split("github.com:")[-1]

    return JSONResponse({"branch": branch, "repo": repo or "sidar_project"})


@app.get("/git-branches")
async def git_branches():
    """Yerel git dallarını listeler."""
    _root = Path(__file__).parent

    def _run(cmd):
        try:
            return subprocess.check_output(
                cmd, cwd=str(_root), stderr=subprocess.DEVNULL
            ).decode().strip()
        except Exception:
            return ""

    branches_raw = _run(["git", "branch", "--format=%(refname:short)"])
    branches = [b.strip() for b in branches_raw.split("\n") if b.strip()]
    current = _run(["git", "rev-parse", "--abbrev-ref", "HEAD"]) or "main"

    return JSONResponse({"branches": branches or ["main"], "current": current})


@app.post("/set-repo")
async def set_repo(request: Request):
    """GitHub deposunu çalışma zamanında değiştirir."""
    body = await request.json()
    repo_name = body.get("repo", "").strip()
    if not repo_name:
        return JSONResponse({"success": False, "error": "Depo adı boş."}, status_code=400)

    agent = await get_agent()
    ok, msg = agent.github.set_repo(repo_name)
    if ok:
        cfg.GITHUB_REPO = repo_name
    return JSONResponse({"success": ok, "message": msg})


@app.post("/clear")
async def clear():
    """Aktif konuşma belleğini temizle."""
    agent = await get_agent()
    agent.memory.clear()
    return JSONResponse({"result": True})


# ─────────────────────────────────────────────
#  BAŞLATMA
# ─────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="Sidar Web Arayüzü")
    parser.add_argument(
        "--host", default=cfg.WEB_HOST,
        help=f"Sunucu adresi (varsayılan: {cfg.WEB_HOST})"
    )
    parser.add_argument(
        "--port", type=int, default=cfg.WEB_PORT,
        help=f"Port numarası (varsayılan: {cfg.WEB_PORT})"
    )
    parser.add_argument(
        "--level", choices=["restricted", "sandbox", "full"],
        help="Erişim seviyesi (varsayılan: .env'deki değer)"
    )
    parser.add_argument(
        "--provider", choices=["ollama", "gemini"],
        help="AI sağlayıcısı (varsayılan: .env'deki değer)"
    )
    parser.add_argument(
        "--log", default="info",
        help="Log seviyesi (debug/info/warning)"
    )
    args = parser.parse_args()

    # Dinamik config override
    if args.level:
        cfg.ACCESS_LEVEL = args.level
    if args.provider:
        cfg.AI_PROVIDER = args.provider

    # Ajan önceden başlat (ilk istekte gecikme olmasın).
    # SidarAgent.__init__ senkrondur; asyncio.run() gerekmez.
    global _agent
    _agent = SidarAgent(cfg)

    display_host = "localhost" if args.host in ("0.0.0.0", "") else args.host
    print(f"\n  ╔══════════════════════════════════════╗")
    print(f"  ║  SİDAR Web Arayüzü — v{_agent.VERSION}          ║")
    print(f"  ║  http://{display_host}:{args.port:<27}║")
    print(f"  ╚══════════════════════════════════════╝\n")

    uvicorn.run(
        app,
        host=args.host,
        port=args.port,
        log_level=args.log,
    )


if __name__ == "__main__":
    main()
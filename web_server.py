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
from pathlib import Path

import uvicorn
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse

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

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

WEB_DIR = Path(__file__).parent / "web_ui"


# ─────────────────────────────────────────────
#  ROTALAR
# ─────────────────────────────────────────────

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
            # Ajanın asenkron stream yanıtını bekle ve akıt
            async for chunk in agent.respond(user_message):
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


@app.post("/clear")
async def clear():
    """Konuşma belleğini temizle."""
    agent = await get_agent()
    result = agent.clear_memory()
    return JSONResponse({"result": result})


@app.get("/github/info")
async def github_info():
    """GitHub bağlantı durumu, kullanıcı depo listesi ve mevcut depo."""
    agent = await get_agent()
    gh = agent.github
    if not gh.is_available():
        return JSONResponse({"available": False, "repos": [], "current_repo": ""})
    repos = []
    try:
        user_repos = list(gh._gh.get_user().get_repos(sort="updated", type="all"))[:30]
        repos = [
            {
                "name": r.full_name,
                "description": r.description or "",
                "language": r.language or "",
                "private": r.private,
            }
            for r in user_repos
        ]
    except Exception as exc:
        logger.warning("Repo listesi alınamadı: %s", exc)
    return JSONResponse({
        "available": True,
        "repos": repos,
        "current_repo": gh.repo_name,
    })


@app.get("/github/branches")
async def github_branches():
    """Mevcut deponun branch listesini döndür."""
    agent = await get_agent()
    gh = agent.github
    if not gh.is_available() or not gh._repo:
        return JSONResponse({"available": False, "branches": ["main"], "default": "main"})
    try:
        branch_objs = list(gh._repo.get_branches())
        branches = [b.name for b in branch_objs]
        default = gh._repo.default_branch
        return JSONResponse({"available": True, "branches": branches, "default": default})
    except Exception as exc:
        logger.warning("Branch listesi alınamadı: %s", exc)
        return JSONResponse({"available": False, "branches": ["main"], "default": "main"})


@app.post("/github/repo")
async def set_github_repo(request: Request):
    """Aktif depoyu değiştir."""
    body = await request.json()
    repo_name = body.get("repo", "").strip()
    if not repo_name:
        return JSONResponse({"error": "Depo adı boş olamaz."}, status_code=400)
    agent = await get_agent()
    ok, msg = agent.github.set_repo(repo_name)
    return JSONResponse({"ok": ok, "message": msg})


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
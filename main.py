"""
Sidar Project - Giriş Noktası
Yazılım Mühendisi AI Asistanı — CLI Arayüzü

Kullanım:
    python main.py                  # interaktif mod
    python main.py --status         # sistem durumunu göster
    python main.py -c "komut"       # tek komut çalıştır
    python main.py --level full     # erişim seviyesini geçici olarak ayarla
"""

import argparse
import asyncio
import logging
import os
import sys

# Proje kökünü sys.path'e ekle
sys.path.insert(0, os.path.dirname(__file__))

from config import Config
from agent.sidar_agent import SidarAgent


# ─────────────────────────────────────────────
#  LOGLAMA
# ─────────────────────────────────────────────

def _setup_logging(level: str) -> None:
    """
    config.py zaten logging.basicConfig'i RotatingFileHandler ile kurmuştur.
    Burada yalnızca CLI --log argümanına göre kök logger seviyesini güncelliyoruz.
    """
    log_level = getattr(logging, level.upper(), logging.INFO)
    logging.getLogger().setLevel(log_level)


# ─────────────────────────────────────────────
#  BANNER
# ─────────────────────────────────────────────

BANNER = r"""
 ╔══════════════════════════════════════════════╗
 ║  ███████╗██╗██████╗  █████╗ ██████╗          ║
 ║  ██╔════╝██║██╔══██╗██╔══██╗██╔══██╗         ║
 ║  ███████╗██║██║  ██║███████║██████╔╝         ║
 ║  ╚════██║██║██║  ██║██╔══██║██╔══██╗         ║
 ║  ███████║██║██████╔╝██║  ██║██║  ██║         ║
 ║  ╚══════╝╚═╝╚═════╝ ╚═╝  ╚═╝╚═╝  ╚═╝         ║
 ║  Yazılım Mimarı & Baş Mühendis AI  v2.6.0   ║
 ╚══════════════════════════════════════════════╝
"""

HELP_TEXT = """
Komutlar:
  .status     — Sistem durumunu göster
  .clear      — Konuşma belleğini temizle
  .audit      — Proje denetimini çalıştır
  .health     — Sistem sağlık raporu
  .gpu        — GPU belleğini optimize et
  .github     — GitHub bağlantı durumu
  .level      — Mevcut erişim seviyesini göster
  .web        — Web arama durumu
  .docs       — Belge deposunu listele
  .help       — Bu yardım mesajını göster
  .exit / .q  — Çıkış

Doğrudan Komutlar (serbest metin):
  web'de ara: <sorgu>              → DuckDuckGo web araması
  pypi: <paket>                    → PyPI paket bilgisi
  npm: <paket>                     → npm paket bilgisi
  github releases: <owner/repo>    → GitHub release listesi
  docs ara: <sorgu>                → Belge deposunda ara
  belge ekle <url>                 → URL'den belge ekle
  stackoverflow: <sorgu>           → Stack Overflow araması
"""


# ─────────────────────────────────────────────
#  İNTERAKTİF DÖNGÜ
# ─────────────────────────────────────────────

def interactive_loop(agent: SidarAgent) -> None:
    print(BANNER)
    print(f"  Erişim Seviyesi : {agent.cfg.ACCESS_LEVEL.upper()}")
    print(f"  AI Sağlayıcı    : {agent.cfg.AI_PROVIDER} ({agent.cfg.CODING_MODEL})")
    # GPU bilgisi
    if agent.cfg.USE_GPU:
        gpu_line = f"✓ {agent.cfg.GPU_INFO}"
        if getattr(agent.cfg, "CUDA_VERSION", "N/A") != "N/A":
            gpu_line += f"  (CUDA {agent.cfg.CUDA_VERSION}"
            if getattr(agent.cfg, "GPU_COUNT", 1) > 1:
                gpu_line += f", {agent.cfg.GPU_COUNT} GPU"
            gpu_line += ")"
        print(f"  GPU             : {gpu_line}")
    else:
        print(f"  GPU             : ✗ CPU Modu  ({agent.cfg.GPU_INFO})")
    print(f"  GitHub          : {'Bağlı' if agent.github.is_available() else 'Bağlı değil'}")
    print(f"  Web Arama       : {'Aktif' if agent.web.is_available() else 'duckduckgo-search kurulu değil'}")
    print(f"  Paket Bilgi     : {agent.pkg.status()}")
    print(f"  Belge Deposu    : {agent.docs.status()}")
    print(f"\n  '.help' yazarak komut listesini görebilirsiniz.\n")

    while True:
        try:
            user_input = input("Sen  > ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nSidar > Görüşürüz. ✓")
            break

        if not user_input:
            continue

        # Dahili komutlar
        if user_input.lower() in (".exit", ".q", "exit", "quit", "çıkış"):
            print("Sidar > Görüşürüz. ✓")
            break
        elif user_input.lower() == ".help":
            print(HELP_TEXT)
            continue
        elif user_input.lower() == ".status":
            print(agent.status())
            continue
        elif user_input.lower() == ".clear":
            print(agent.clear_memory())
            continue
        elif user_input.lower() == ".audit":
            print(agent.code.audit_project("."))
            continue
        elif user_input.lower() == ".health":
            print(agent.health.full_report())
            continue
        elif user_input.lower() == ".gpu":
            print(agent.health.optimize_gpu_memory())
            continue
        elif user_input.lower() == ".github":
            print(agent.github.status())
            continue
        elif user_input.lower() == ".level":
            print(agent.security.status_report())
            continue
        elif user_input.lower() == ".web":
            print(agent.web.status())
            continue
        elif user_input.lower() == ".docs":
            print(agent.docs.list_documents())
            continue

        # Ajan yanıtı — respond() async generator olduğu için asyncio.run() gerekli
        try:
            print("Sidar > ", end="", flush=True)

            async def _stream(msg: str) -> None:
                async for chunk in agent.respond(msg):
                    print(chunk, end="", flush=True)
                print("\n")

            asyncio.run(_stream(user_input))

        except Exception as exc:
            print(f"\nSidar > ✗ Hata: {exc}\n")
            logging.exception("Ajan yanıt hatası")


# ─────────────────────────────────────────────
#  GİRİŞ NOKTASI
# ─────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Sidar — Yazılım Mühendisi AI Asistanı",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("-c", "--command", help="Tek komut çalıştır ve çık")
    parser.add_argument("--status", action="store_true", help="Sistem durumunu göster ve çık")
    parser.add_argument(
        "--level",
        choices=["restricted", "sandbox", "full"],
        help="Erişim seviyesini geçici olarak ayarla",
    )
    parser.add_argument("--provider", choices=["ollama", "gemini"], help="AI sağlayıcısı")
    parser.add_argument("--model", help="Ollama model adı")
    parser.add_argument("--log", default="INFO", help="Log seviyesi (DEBUG/INFO/WARNING)")
    args = parser.parse_args()

    _setup_logging(args.log)

    # Config nesnesini oluştur; CLI flag'leri instance attribute olarak
    # doğrudan override et. os.environ üzerinden override ÇALIŞMAZ çünkü
    # Config sınıf attribute'ları module import anında bir kez değerlendirilir.
    cfg = Config()
    if args.level:
        cfg.ACCESS_LEVEL = args.level
    if args.provider:
        cfg.AI_PROVIDER = args.provider
    if args.model:
        cfg.CODING_MODEL = args.model

    agent = SidarAgent(cfg)

    if args.status:
        print(agent.status())
        return

    if args.command:
        # respond() async generator olduğu için asyncio.run() ile çalıştırılır
        async def _run_command() -> None:
            print("Sidar > ", end="", flush=True)
            async for chunk in agent.respond(args.command):
                print(chunk, end="", flush=True)
            print()

        asyncio.run(_run_command())
        return

    interactive_loop(agent)


if __name__ == "__main__":
    main()
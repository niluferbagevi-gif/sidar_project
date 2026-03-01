"""
Sidar Project — Merkezi Yapılandırma Modülü
Sürüm: 2.6.0 (GPU & Donanım Hızlandırma Desteği)
Açıklama: Sistem ayarları, donanım tespiti, dizin yönetimi ve loglama altyapısı.
"""

import os
import sys
import logging
import warnings
from logging.handlers import RotatingFileHandler
from pathlib import Path
from dotenv import load_dotenv
from typing import Dict, Any, Optional, List
from dataclasses import dataclass

# ═══════════════════════════════════════════════════════════════
# UYARI FİLTRELERİ
# ═══════════════════════════════════════════════════════════════
warnings.filterwarnings("ignore", category=FutureWarning, module="torch")
warnings.filterwarnings("ignore", category=UserWarning, module="torch")
warnings.filterwarnings("ignore", category=UserWarning, message=".*pkg_resources is deprecated.*")

# ═══════════════════════════════════════════════════════════════
# TEMEL DİZİN VE .ENV YÜKLEMESİ  (diğer her şeyden ÖNCE)
# ═══════════════════════════════════════════════════════════════
BASE_DIR = Path(__file__).resolve().parent
ENV_PATH = BASE_DIR / ".env"

if not ENV_PATH.exists():
    print("⚠️  '.env' dosyası bulunamadı! Varsayılan ayarlar kullanılacak.")
else:
    load_dotenv(dotenv_path=ENV_PATH)

# ═══════════════════════════════════════════════════════════════
# YARDIMCI FONKSİYONLAR
# ═══════════════════════════════════════════════════════════════

def get_bool_env(key: str, default: bool = False) -> bool:
    val = os.getenv(key, str(default)).lower()
    return val in ("true", "1", "yes", "on")


def get_int_env(key: str, default: int = 0) -> int:
    try:
        return int(os.getenv(key, str(default)))
    except (ValueError, TypeError):
        return default


def get_float_env(key: str, default: float = 0.0) -> float:
    try:
        return float(os.getenv(key, str(default)))
    except (ValueError, TypeError):
        return default


def get_list_env(key: str, default: Optional[List[str]] = None,
                 separator: str = ",") -> List[str]:
    if default is None:
        default = []
    value = os.getenv(key, "")
    if not value:
        return default
    return [item.strip() for item in value.split(separator) if item.strip()]


# ═══════════════════════════════════════════════════════════════
# LOGLAMA SİSTEMİ  (dinamik, RotatingFileHandler)
# ═══════════════════════════════════════════════════════════════
_LOG_DIR = BASE_DIR / "logs"
_LOG_DIR.mkdir(parents=True, exist_ok=True)

_LOG_LEVEL_STR  = os.getenv("LOG_LEVEL", "INFO").upper()
_LOG_FILE_PATH  = BASE_DIR / os.getenv("LOG_FILE", "logs/sidar_system.log")
_LOG_MAX_BYTES  = get_int_env("LOG_MAX_BYTES", 10_485_760)   # 10 MB
_LOG_BACKUP_CNT = get_int_env("LOG_BACKUP_COUNT", 5)

_LOG_FILE_PATH.parent.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=getattr(logging, _LOG_LEVEL_STR, logging.INFO),
    format="%(asctime)s - [%(levelname)s] - %(name)s - (%(filename)s:%(lineno)d) - %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        RotatingFileHandler(
            _LOG_FILE_PATH,
            maxBytes=_LOG_MAX_BYTES,
            backupCount=_LOG_BACKUP_CNT,
            encoding="utf-8",
        ),
    ],
)
logger = logging.getLogger("Sidar.Config")

if ENV_PATH.exists():
    logger.info("✅ Ortam değişkenleri yüklendi: %s", ENV_PATH)

# ═══════════════════════════════════════════════════════════════
# DONANIM TESPİTİ
# ═══════════════════════════════════════════════════════════════

@dataclass
class HardwareInfo:
    """Başlangıçta tespit edilen donanım bilgilerini tutar."""
    has_cuda: bool
    gpu_name: str
    gpu_count: int = 0
    cpu_count: int = 0
    cuda_version: str = "N/A"
    driver_version: str = "N/A"


def _is_wsl2() -> bool:
    """WSL2 ortamını tespit eder (/proc/sys/kernel/osrelease içinde 'microsoft' arar)."""
    try:
        return "microsoft" in Path("/proc/sys/kernel/osrelease").read_text().lower()
    except Exception:
        return False


def check_hardware() -> HardwareInfo:
    """GPU/CPU donanımını tespit eder; PyTorch yoksa sessizce devam eder."""
    info = HardwareInfo(has_cuda=False, gpu_name="N/A")

    wsl2 = _is_wsl2()
    if wsl2:
        logger.info("ℹ️  WSL2 ortamı tespit edildi — CUDA, Windows sürücüsü üzerinden erişilecek.")

    if not get_bool_env("USE_GPU", True):
        logger.info("ℹ️  GPU kullanımı .env ile devre dışı bırakıldı.")
        info.gpu_name = "Devre Dışı (Kullanıcı)"
        return info

    try:
        import torch
        if torch.cuda.is_available():
            info.has_cuda     = True
            info.gpu_count    = torch.cuda.device_count()
            info.gpu_name     = torch.cuda.get_device_name(0)
            info.cuda_version = torch.version.cuda or "N/A"
            logger.info(
                "🚀 GPU Hızlandırma Aktif: %s  (%d GPU tespit edildi, CUDA %s)",
                info.gpu_name, info.gpu_count, info.cuda_version,
            )
            # VRAM fraksiyonunu hemen uygula (GPU_MEMORY_FRACTION env'den okunur)
            frac = get_float_env("GPU_MEMORY_FRACTION", 0.8)
            if not (0.1 <= frac < 1.0):
                logger.warning(
                    "GPU_MEMORY_FRACTION=%.2f geçersiz aralık (0.1–1.0 bekleniyor) "
                    "— varsayılan 0.8 kullanılıyor.",
                    frac,
                )
                frac = 0.8
            try:
                torch.cuda.set_per_process_memory_fraction(frac, device=0)
                logger.info("🔧 VRAM fraksiyonu ayarlandı: %.0f%%", frac * 100)
            except Exception as exc:
                logger.debug("VRAM fraksiyon ayarı atlandı: %s", exc)
        else:
            if wsl2:
                logger.warning(
                    "⚠️  WSL2 — CUDA bulunamadı. Kontrol: "
                    "Windows NVIDIA sürücüsü güncel mi? "
                    "PyTorch CUDA 12.x wheel ile kuruldu mu? "
                    "(pip install torch --index-url https://download.pytorch.org/whl/cu121)"
                )
            else:
                logger.info("ℹ️  CUDA bulunamadı — CPU modunda çalışılacak.")
            info.gpu_name = "CUDA Bulunamadı"
    except ImportError:
        logger.warning("⚠️  PyTorch kurulu değil; GPU kontrolü atlanıyor.")
        info.gpu_name = "PyTorch Yok"
    except Exception as exc:
        logger.warning("⚠️  Donanım kontrolü hatası: %s", exc)
        info.gpu_name = "Tespit Edilemedi"

    # sürücü sürümü — nvidia-ml-py varsa al
    try:
        import pynvml
        pynvml.nvmlInit()
        info.driver_version = pynvml.nvmlSystemGetDriverVersion()
        pynvml.nvmlShutdown()
    except Exception:
        pass  # opsiyonel bağımlılık; WSL2'de NVML erişimi kısıtlı olabilir

    try:
        import multiprocessing
        info.cpu_count = multiprocessing.cpu_count()
    except Exception:
        info.cpu_count = 1

    return info


# Modül yüklendiğinde bir kez çalışır
HARDWARE = check_hardware()


# ═══════════════════════════════════════════════════════════════
# ANA YAPILANDIRMA SINIFI
# ═══════════════════════════════════════════════════════════════

class Config:
    """
    Sidar Merkezi Yapılandırma Sınıfı
    Sürüm: 2.6.0
    """

    # ─── Genel ───────────────────────────────────────────────
    PROJECT_NAME: str = "Sidar"
    VERSION: str      = "2.6.1"
    DEBUG_MODE: bool  = get_bool_env("DEBUG_MODE", False)

    # ─── Dizinler ────────────────────────────────────────────
    BASE_DIR:    Path = BASE_DIR
    TEMP_DIR:    Path = BASE_DIR / "temp"
    LOGS_DIR:    Path = BASE_DIR / "logs"
    DATA_DIR:    Path = BASE_DIR / "data"
    MEMORY_FILE: Path = DATA_DIR / "memory.json"

    REQUIRED_DIRS: List[Path] = [BASE_DIR / "temp", BASE_DIR / "logs", BASE_DIR / "data"]

    # ─── AI Sağlayıcı ────────────────────────────────────────
    AI_PROVIDER:    str = os.getenv("AI_PROVIDER", "ollama")   # "ollama" | "gemini"
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
    GEMINI_MODEL:   str = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")

    # ─── Ollama ──────────────────────────────────────────────
    OLLAMA_URL:     str = os.getenv("OLLAMA_URL", "http://localhost:11434/api")
    OLLAMA_TIMEOUT: int = get_int_env("OLLAMA_TIMEOUT", 30)
    CODING_MODEL:   str = os.getenv("CODING_MODEL", "qwen2.5-coder:7b")
    TEXT_MODEL:     str = os.getenv("TEXT_MODEL", "gemma2:9b")

    # ─── Erişim Seviyesi (OpenClaw) ──────────────────────────
    ACCESS_LEVEL: str = os.getenv("ACCESS_LEVEL", "full")

    # ─── GitHub ──────────────────────────────────────────────
    GITHUB_TOKEN: str = os.getenv("GITHUB_TOKEN", "")
    GITHUB_REPO:  str = os.getenv("GITHUB_REPO", "")

    # ─── Donanım & GPU ───────────────────────────────────────
    USE_GPU:       bool  = HARDWARE.has_cuda
    GPU_INFO:      str   = HARDWARE.gpu_name
    GPU_COUNT:     int   = HARDWARE.gpu_count
    CPU_COUNT:     int   = HARDWARE.cpu_count
    CUDA_VERSION:  str   = HARDWARE.cuda_version
    DRIVER_VERSION: str  = HARDWARE.driver_version

    # Birden fazla GPU varsa hangi device kullanılsın (0-indexed)
    GPU_DEVICE: int = get_int_env("GPU_DEVICE", 0)

    # Çoklu GPU dağıtık mod
    MULTI_GPU: bool = get_bool_env("MULTI_GPU", False)

    # Embedding ve model yüklemeleri için VRAM fraksiyonu (0.1–1.0)
    GPU_MEMORY_FRACTION: float = get_float_env("GPU_MEMORY_FRACTION", 0.8)

    # FP16 / mixed precision  →  embedding modellerinde bellek tasarrufu
    GPU_MIXED_PRECISION: bool = get_bool_env("GPU_MIXED_PRECISION", False)

    # ─── Uygulama ────────────────────────────────────────────
    MAX_MEMORY_TURNS:  int = get_int_env("MAX_MEMORY_TURNS", 20)
    LOG_LEVEL:         str = os.getenv("LOG_LEVEL", "INFO")
    RESPONSE_LANGUAGE: str = os.getenv("RESPONSE_LANGUAGE", "tr")

    # ─── Loglama ─────────────────────────────────────────────
    LOG_FILE:         Path = _LOG_FILE_PATH
    LOG_MAX_BYTES:     int = _LOG_MAX_BYTES
    LOG_BACKUP_COUNT:  int = _LOG_BACKUP_CNT

    # ─── ReAct Döngüsü ───────────────────────────────────────
    MAX_REACT_STEPS: int = get_int_env("MAX_REACT_STEPS", 10)
    REACT_TIMEOUT:   int = get_int_env("REACT_TIMEOUT", 60)

    # ─── Web Arama ───────────────────────────────────────────
    SEARCH_ENGINE:        str = os.getenv("SEARCH_ENGINE", "auto")
    TAVILY_API_KEY:       str = os.getenv("TAVILY_API_KEY", "")
    GOOGLE_SEARCH_API_KEY: str = os.getenv("GOOGLE_SEARCH_API_KEY", "")
    GOOGLE_SEARCH_CX:     str = os.getenv("GOOGLE_SEARCH_CX", "")
    WEB_SEARCH_MAX_RESULTS: int = get_int_env("WEB_SEARCH_MAX_RESULTS", 5)
    WEB_FETCH_TIMEOUT:     int = get_int_env("WEB_FETCH_TIMEOUT", 15)
    WEB_FETCH_MAX_CHARS:   int = get_int_env("WEB_FETCH_MAX_CHARS", 4000)

    # ─── Paket Bilgi ─────────────────────────────────────────
    PACKAGE_INFO_TIMEOUT: int = get_int_env("PACKAGE_INFO_TIMEOUT", 12)

    # ─── RAG — Belge Deposu ──────────────────────────────────
    RAG_DIR:          Path = BASE_DIR / os.getenv("RAG_DIR", "data/rag")
    RAG_TOP_K:         int = get_int_env("RAG_TOP_K", 3)
    RAG_CHUNK_SIZE:    int = get_int_env("RAG_CHUNK_SIZE", 1000)
    RAG_CHUNK_OVERLAP: int = get_int_env("RAG_CHUNK_OVERLAP", 200)

    # ─── Docker REPL Sandbox ─────────────────────────────────
    DOCKER_PYTHON_IMAGE: str = os.getenv("DOCKER_PYTHON_IMAGE", "python:3.11-alpine")

    # ─── Web Arayüzü ─────────────────────────────────────────
    WEB_HOST: str = os.getenv("WEB_HOST", "0.0.0.0")
    WEB_PORT: int = get_int_env("WEB_PORT", 7860)

    # ─────────────────────────────────────────────────────────
    #  METOTLAR
    # ─────────────────────────────────────────────────────────

    @classmethod
    def initialize_directories(cls) -> bool:
        """Gerekli tüm dizinleri oluşturur."""
        success = True
        for folder in cls.REQUIRED_DIRS:
            try:
                folder.mkdir(parents=True, exist_ok=True)
                logger.debug("✅ Dizin hazır: %s", folder.name)
            except Exception as exc:
                logger.error("❌ Dizin oluşturulamadı (%s): %s", folder.name, exc)
                success = False
        return success

    @classmethod
    def set_provider_mode(cls, mode: str) -> None:
        """AI sağlayıcı modunu çalışma zamanında değiştirir."""
        mode_map = {
            "online": "gemini", "gemini": "gemini",
            "local":  "ollama", "ollama": "ollama",
        }
        m_lower = mode.lower()
        if m_lower in mode_map:
            cls.AI_PROVIDER = mode_map[m_lower]
            logger.info("✅ AI Sağlayıcı güncellendi: %s", cls.AI_PROVIDER.upper())
        else:
            logger.error(
                "❌ Geçersiz sağlayıcı modu: %s  Geçerliler: %s",
                mode, list(mode_map.keys()),
            )

    @classmethod
    def validate_critical_settings(cls) -> bool:
        """Kritik yapılandırmaları doğrular; uyarıları loglar."""
        is_valid = True
        cls.initialize_directories()

        if cls.AI_PROVIDER == "gemini" and not cls.GEMINI_API_KEY:
            logger.error(
                "❌ Gemini modu seçili ama GEMINI_API_KEY ayarlanmamış!\n"
                "   .env dosyasını kontrol edin."
            )
            is_valid = False

        if cls.AI_PROVIDER == "ollama":
            try:
                import httpx
                base = cls.OLLAMA_URL.rstrip("/")
                if base.endswith("/api"):
                    tags_url = base + "/tags"
                else:
                    tags_url = base + "/api/tags"
                with httpx.Client(timeout=2) as client:
                    r = client.get(tags_url)
                if r.status_code == 200:
                    logger.info("✅ Ollama bağlantısı başarılı.")
                else:
                    logger.warning("⚠️  Ollama yanıt kodu: %d", r.status_code)
            except Exception:
                logger.warning(
                    "⚠️  Ollama'ya ulaşılamadı (%s)\n"
                    "    'ollama serve' çalıştırıldığından emin olun.",
                    cls.OLLAMA_URL,
                )

        return is_valid

    @classmethod
    def get_system_info(cls) -> Dict[str, Any]:
        """Özet sistem bilgisini sözlük olarak döndürür."""
        return {
            "project":            cls.PROJECT_NAME,
            "version":            cls.VERSION,
            "provider":           cls.AI_PROVIDER,
            "access_level":       cls.ACCESS_LEVEL,
            "gpu_enabled":        cls.USE_GPU,
            "gpu_info":           cls.GPU_INFO,
            "gpu_count":          cls.GPU_COUNT,
            "gpu_device":         cls.GPU_DEVICE,
            "cuda_version":       cls.CUDA_VERSION,
            "driver_version":     cls.DRIVER_VERSION,
            "multi_gpu":          cls.MULTI_GPU,
            "gpu_mixed_precision": cls.GPU_MIXED_PRECISION,
            "cpu_count":          cls.CPU_COUNT,
            "debug_mode":         cls.DEBUG_MODE,
        }

    @classmethod
    def print_config_summary(cls) -> None:
        """Konsola yapılandırma özetini yazdırır."""
        print("\n" + "═" * 62)
        print(f"  {cls.PROJECT_NAME} v{cls.VERSION} — Yapılandırma Özeti")
        print("═" * 62)
        print(f"  AI Sağlayıcı     : {cls.AI_PROVIDER.upper()}")
        if cls.USE_GPU:
            print(f"  GPU              : ✓ {cls.GPU_INFO}  (CUDA {cls.CUDA_VERSION})")
            print(f"  GPU Sayısı       : {cls.GPU_COUNT}")
            print(f"  Hedef Cihaz      : cuda:{cls.GPU_DEVICE}")
            print(f"  Mixed Precision  : {'Açık' if cls.GPU_MIXED_PRECISION else 'Kapalı'}")
            if cls.DRIVER_VERSION != "N/A":
                print(f"  Sürücü Sürümü    : {cls.DRIVER_VERSION}")
        else:
            print(f"  GPU              : ✗ CPU Modu  ({cls.GPU_INFO})")
        print(f"  CPU Çekirdek     : {cls.CPU_COUNT}")
        print(f"  Erişim Seviyesi  : {cls.ACCESS_LEVEL.upper()}")
        print(f"  Debug Modu       : {'Açık' if cls.DEBUG_MODE else 'Kapalı'}")
        if cls.AI_PROVIDER == "ollama":
            print(f"  CODING Modeli    : {cls.CODING_MODEL}")
            print(f"  TEXT Modeli      : {cls.TEXT_MODEL}")
        else:
            print(f"  Gemini Modeli    : {cls.GEMINI_MODEL}")
        print(f"  RAG Dizini       : {cls.RAG_DIR.relative_to(BASE_DIR)}")
        print("═" * 62 + "\n")


# ═══════════════════════════════════════════════════════════════
# BAŞLANGIÇ  —  dizinler & özet
# ═══════════════════════════════════════════════════════════════
Config.initialize_directories()
logger.info("✅ %s v%s yapılandırması yüklendi.", Config.PROJECT_NAME, Config.VERSION)

if Config.DEBUG_MODE:
    Config.print_config_summary()
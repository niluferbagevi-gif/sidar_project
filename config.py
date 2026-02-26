"""
Sidar Project - Konfigürasyon Modülü
Yazılım Mühendisi AI Asistanı
"""

import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# ─────────────────────────────────────────────
#  PROJE KÖK DİZİNİ
# ─────────────────────────────────────────────
BASE_DIR = Path(__file__).resolve().parent
TEMP_DIR = BASE_DIR / "temp"
LOGS_DIR = BASE_DIR / "logs"
DATA_DIR = BASE_DIR / "data"  # Veri klasörü eklendi

TEMP_DIR.mkdir(exist_ok=True)
LOGS_DIR.mkdir(exist_ok=True)
DATA_DIR.mkdir(exist_ok=True)


class Config:
    # ─────────────────────────────────────────────
    #  AI SAĞLAYICI
    # ─────────────────────────────────────────────
    AI_PROVIDER: str = os.getenv("AI_PROVIDER", "ollama")   # "ollama" | "gemini"
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
    GEMINI_MODEL: str = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")

    # ─────────────────────────────────────────────
    #  OLLAMA
    # ─────────────────────────────────────────────
    OLLAMA_URL: str = os.getenv("OLLAMA_URL", "http://localhost:11434/api")
    CODING_MODEL: str = os.getenv("CODING_MODEL", "qwen2.5-coder:7b")
    TEXT_MODEL: str = os.getenv("TEXT_MODEL", "gemma2:9b")

    # ─────────────────────────────────────────────
    #  ERİŞİM SEVİYESİ (OpenClaw Sistemi)
    # ─────────────────────────────────────────────
    ACCESS_LEVEL: str = os.getenv("ACCESS_LEVEL", "sandbox")

    # ─────────────────────────────────────────────
    #  GITHUB
    # ─────────────────────────────────────────────
    GITHUB_TOKEN: str = os.getenv("GITHUB_TOKEN", "")
    GITHUB_REPO: str = os.getenv("GITHUB_REPO", "")

    # ─────────────────────────────────────────────
    #  DONANIM
    # ─────────────────────────────────────────────
    USE_GPU: bool = os.getenv("USE_GPU", "true").lower() == "true"

    # ─────────────────────────────────────────────
    #  UYGULAMA
    # ─────────────────────────────────────────────
    MAX_MEMORY_TURNS: int = int(os.getenv("MAX_MEMORY_TURNS", "20"))
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    RESPONSE_LANGUAGE: str = os.getenv("RESPONSE_LANGUAGE", "tr")

    # ─────────────────────────────────────────────
    #  DOSYA YOLLARI
    # ─────────────────────────────────────────────
    BASE_DIR: Path = BASE_DIR
    TEMP_DIR: Path = TEMP_DIR
    LOGS_DIR: Path = LOGS_DIR
    DATA_DIR: Path = DATA_DIR

    # Kalıcı bellek dosyası
    MEMORY_FILE: Path = DATA_DIR / "memory.json"

    # ─────────────────────────────────────────────
    #  ReAct DÖNGÜSÜ
    # ─────────────────────────────────────────────
    MAX_REACT_STEPS: int = int(os.getenv("MAX_REACT_STEPS", "10"))
    REACT_TIMEOUT: int = int(os.getenv("REACT_TIMEOUT", "60"))

    # ─────────────────────────────────────────────
    #  WEB ARAMA
    # ─────────────────────────────────────────────
    SEARCH_ENGINE: str = os.getenv("SEARCH_ENGINE", "auto") # auto, duckduckgo, tavily, google
    TAVILY_API_KEY: str = os.getenv("TAVILY_API_KEY", "")
    GOOGLE_SEARCH_API_KEY: str = os.getenv("GOOGLE_SEARCH_API_KEY", "")
    GOOGLE_SEARCH_CX: str = os.getenv("GOOGLE_SEARCH_CX", "")

    WEB_SEARCH_MAX_RESULTS: int = int(os.getenv("WEB_SEARCH_MAX_RESULTS", "5"))
    WEB_FETCH_TIMEOUT: int = int(os.getenv("WEB_FETCH_TIMEOUT", "15"))
    WEB_FETCH_MAX_CHARS: int = int(os.getenv("WEB_FETCH_MAX_CHARS", "4000"))

    # ─────────────────────────────────────────────
    #  PAKET BİLGİ
    # ─────────────────────────────────────────────
    PACKAGE_INFO_TIMEOUT: int = int(os.getenv("PACKAGE_INFO_TIMEOUT", "12"))

    # ─────────────────────────────────────────────
    #  RAG — Belge Deposu
    # ─────────────────────────────────────────────
    RAG_DIR: Path = BASE_DIR / os.getenv("RAG_DIR", "data/rag")
    RAG_TOP_K: int = int(os.getenv("RAG_TOP_K", "3"))

    # ─────────────────────────────────────────────
    #  WEB ARAYÜZÜ
    # ─────────────────────────────────────────────
    WEB_HOST: str = os.getenv("WEB_HOST", "0.0.0.0")
    WEB_PORT: int = int(os.getenv("WEB_PORT", "7860"))
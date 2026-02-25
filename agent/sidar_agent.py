"""
Sidar Project - Ana Ajan
ReAct (Reason + Act) döngüsü ile çalışan yazılım mühendisi AI asistanı.
"""

import logging
import threading
from typing import Optional

from config import Config
from core.memory import ConversationMemory
from core.llm_client import LLMClient
from core.rag import DocumentStore
from managers.code_manager import CodeManager
from managers.system_health import SystemHealthManager
from managers.github_manager import GitHubManager
from managers.security import SecurityManager
from managers.web_search import WebSearchManager
from managers.package_info import PackageInfoManager
from agent.auto_handle import AutoHandle
from agent.definitions import SIDAR_SYSTEM_PROMPT

logger = logging.getLogger(__name__)


class SidarAgent:
    """
    Sidar — Yazılım Mimarı ve Baş Mühendis AI Asistanı.

    Mimari:
    1. Kullanıcı girdisi → AutoHandle (hızlı örüntü eşleme)
    2. Eşleşme yoksa → ReAct döngüsü (LLM + araç çağrısı)
    3. LLM yanıtı → Hafızaya kaydet → Kullanıcıya sun
    """

    VERSION = "2.0.0"

    def __init__(self, cfg: Config = None) -> None:
        self.cfg = cfg or Config()
        self._lock = threading.RLock()

        # Alt sistemler — temel
        self.security = SecurityManager(self.cfg.ACCESS_LEVEL, self.cfg.BASE_DIR)
        self.code = CodeManager(self.security, self.cfg.BASE_DIR)
        self.health = SystemHealthManager(self.cfg.USE_GPU)
        self.github = GitHubManager(self.cfg.GITHUB_TOKEN, self.cfg.GITHUB_REPO)
        self.memory = ConversationMemory(self.cfg.MAX_MEMORY_TURNS)
        self.llm = LLMClient(self.cfg.AI_PROVIDER, self.cfg)

        # Alt sistemler — yeni
        self.web = WebSearchManager()
        self.pkg = PackageInfoManager()
        self.docs = DocumentStore(self.cfg.RAG_DIR)

        self.auto = AutoHandle(
            self.code, self.health, self.github, self.memory,
            self.web, self.pkg, self.docs,
        )

        logger.info(
            "SidarAgent v%s başlatıldı — sağlayıcı=%s model=%s erişim=%s web=%s",
            self.VERSION,
            self.cfg.AI_PROVIDER,
            self.cfg.CODING_MODEL,
            self.cfg.ACCESS_LEVEL,
            "aktif" if self.web.is_available() else "devre dışı",
        )

    # ─────────────────────────────────────────────
    #  ANA YANIT METODU
    # ─────────────────────────────────────────────

    def respond(self, user_input: str) -> str:
        """
        Kullanıcı girdisini işle ve yanıt üret.

        1. AutoHandle → hızlı yol
        2. ReAct loop → LLM ile araç çağrısı
        """
        user_input = user_input.strip()
        if not user_input:
            return "⚠ Boş girdi."

        with self._lock:
            self.memory.add("user", user_input)

            handled, quick_response = self.auto.handle(user_input)
            if handled:
                self.memory.add("assistant", quick_response)
                return quick_response

            response = self._react_loop(user_input)
            self.memory.add("assistant", response)
            return response

    # ─────────────────────────────────────────────
    #  ReAct DÖNGÜSÜ
    # ─────────────────────────────────────────────

    def _react_loop(self, user_input: str) -> str:
        """
        LLM'e araç talimatları içeren bir sistem talimatıyla istek gönder.
        LLM, gerekirse araç çağrısı yapar; bu döngü sonuçları toplayıp son yanıtı üretir.
        """
        messages = self.memory.get_messages_for_llm()
        context = self._build_context()
        full_system = SIDAR_SYSTEM_PROMPT + "\n\n" + context

        for step in range(self.cfg.MAX_REACT_STEPS):
            response = self.llm.chat(
                messages=messages,
                model=self.cfg.CODING_MODEL,
                system_prompt=full_system,
                temperature=0.3,
            )

            tool_result = self._check_and_execute_tools(response)
            if tool_result is None:
                return response

            messages = messages + [
                {"role": "assistant", "content": response},
                {"role": "user", "content": f"[Araç Sonucu]\n{tool_result}"},
            ]

        return response

    def _check_and_execute_tools(self, llm_response: str) -> Optional[str]:
        """
        LLM yanıtında araç çağrısı direktifi var mı kontrol et ve çalıştır.

        Temel direktifler:
            TOOL:list_dir:<path>
            TOOL:read_file:<path>
            TOOL:audit
            TOOL:health
            TOOL:gpu_optimize
            TOOL:github_commits:<n>
            TOOL:github_info

        Web / Paket / RAG direktifleri:
            TOOL:web_search:<query>
            TOOL:fetch_url:<url>
            TOOL:search_docs:<lib> <topic>
            TOOL:search_stackoverflow:<query>
            TOOL:pypi:<package>
            TOOL:pypi_compare:<package>|<version>
            TOOL:npm:<package>
            TOOL:gh_releases:<owner/repo>
            TOOL:gh_latest:<owner/repo>
            TOOL:docs_search:<query>
            TOOL:docs_add:<title>|<url>
            TOOL:docs_list
            TOOL:docs_delete:<id>
        """
        import re

        m = re.search(r"TOOL:(\w+)(?::(.+))?", llm_response)
        if not m:
            return None

        tool_name = m.group(1)
        tool_arg = (m.group(2) or "").strip()

        # ── Temel araçlar ──────────────────────────
        if tool_name == "list_dir":
            _, result = self.code.list_directory(tool_arg or ".")
            return result

        if tool_name == "read_file":
            if not tool_arg:
                return "Dosya yolu belirtilmedi."
            ok, result = self.code.read_file(tool_arg)
            if ok:
                self.memory.set_last_file(tool_arg)
            return result

        if tool_name == "audit":
            return self.code.audit_project(tool_arg or ".")

        if tool_name == "health":
            return self.health.full_report()

        if tool_name == "gpu_optimize":
            return self.health.optimize_gpu_memory()

        if tool_name == "github_commits":
            try:
                n = int(tool_arg) if tool_arg else 10
            except ValueError:
                n = 10
            _, result = self.github.list_commits(n=n)
            return result

        if tool_name == "github_info":
            _, result = self.github.get_repo_info()
            return result

        # ── Web Arama araçları ─────────────────────
        if tool_name == "web_search":
            if not tool_arg:
                return "⚠ Arama sorgusu belirtilmedi."
            _, result = self.web.search(tool_arg)
            return result

        if tool_name == "fetch_url":
            if not tool_arg:
                return "⚠ URL belirtilmedi."
            _, result = self.web.fetch_url(tool_arg)
            return result

        if tool_name == "search_docs":
            parts = tool_arg.split(" ", 1)
            lib = parts[0] if parts else ""
            topic = parts[1] if len(parts) > 1 else ""
            if not lib:
                return "⚠ Kütüphane adı belirtilmedi."
            _, result = self.web.search_docs(lib, topic)
            return result

        if tool_name == "search_stackoverflow":
            if not tool_arg:
                return "⚠ Arama sorgusu belirtilmedi."
            _, result = self.web.search_stackoverflow(tool_arg)
            return result

        # ── Paket Bilgi araçları ───────────────────
        if tool_name == "pypi":
            if not tool_arg:
                return "⚠ Paket adı belirtilmedi."
            _, result = self.pkg.pypi_info(tool_arg)
            return result

        if tool_name == "pypi_compare":
            parts = tool_arg.split("|", 1)
            if len(parts) < 2:
                return "⚠ Kullanım: TOOL:pypi_compare:<paket>|<mevcut_sürüm>"
            _, result = self.pkg.pypi_compare(parts[0].strip(), parts[1].strip())
            return result

        if tool_name == "npm":
            if not tool_arg:
                return "⚠ Paket adı belirtilmedi."
            _, result = self.pkg.npm_info(tool_arg)
            return result

        if tool_name == "gh_releases":
            if not tool_arg:
                return "⚠ Depo adı belirtilmedi (format: owner/repo)."
            _, result = self.pkg.github_releases(tool_arg)
            return result

        if tool_name == "gh_latest":
            if not tool_arg:
                return "⚠ Depo adı belirtilmedi (format: owner/repo)."
            _, result = self.pkg.github_latest_release(tool_arg)
            return result

        # ── RAG / Belge Deposu araçları ────────────
        if tool_name == "docs_search":
            if not tool_arg:
                return "⚠ Arama sorgusu belirtilmedi."
            _, result = self.docs.search(tool_arg)
            return result

        if tool_name == "docs_add":
            parts = tool_arg.split("|", 1)
            if len(parts) < 2:
                return "⚠ Kullanım: TOOL:docs_add:<başlık>|<url>"
            title, url = parts[0].strip(), parts[1].strip()
            _, result = self.docs.add_document_from_url(url, title=title)
            return result

        if tool_name == "docs_list":
            return self.docs.list_documents()

        if tool_name == "docs_delete":
            if not tool_arg:
                return "⚠ Belge ID'si belirtilmedi."
            return self.docs.delete_document(tool_arg)

        return None

    # ─────────────────────────────────────────────
    #  BAĞLAM OLUŞTURMA
    # ─────────────────────────────────────────────

    def _build_context(self) -> str:
        """Tüm alt sistem durumlarını özetleyen bağlam dizesi."""
        lines = ["[Araç Durumu]"]
        lines.append(f"  Güvenlik   : {self.security.level_name.upper()}")
        lines.append(f"  GitHub     : {'Bağlı' if self.github.is_available() else 'Bağlı değil'}")
        lines.append(f"  GPU        : {'Mevcut' if self.health._gpu_available else 'Yok'}")
        lines.append(f"  WebSearch  : {'Aktif' if self.web.is_available() else 'Kurulu değil'}")
        lines.append(f"  PackageInfo: Aktif (PyPI + npm + GitHub)")
        lines.append(f"  RAG        : {self.docs.status()}")

        m = self.code.get_metrics()
        lines.append(f"  Okunan     : {m['files_read']} dosya | Yazılan: {m['files_written']}")

        last_file = self.memory.get_last_file()
        if last_file:
            lines.append(f"  Son dosya  : {last_file}")

        return "\n".join(lines)

    # ─────────────────────────────────────────────
    #  YARDIMCI METODLAR
    # ─────────────────────────────────────────────

    def clear_memory(self) -> str:
        self.memory.clear()
        return "Konuşma belleği temizlendi. ✓"

    def status(self) -> str:
        lines = [
            f"[SidarAgent v{self.VERSION}]",
            f"  Sağlayıcı    : {self.cfg.AI_PROVIDER}",
            f"  Model        : {self.cfg.CODING_MODEL}",
            f"  Erişim       : {self.cfg.ACCESS_LEVEL}",
            f"  Bellek       : {len(self.memory)} mesaj",
            f"  {self.github.status()}",
            f"  {self.web.status()}",
            f"  {self.pkg.status()}",
            f"  {self.docs.status()}",
            self.health.full_report(),
        ]
        return "\n".join(lines)

    def __repr__(self) -> str:
        return f"<SidarAgent v{self.VERSION} provider={self.cfg.AI_PROVIDER}>"
"""
Sidar Project - Ana Ajan
ReAct (Reason + Act) döngüsü ile çalışan yazılım mühendisi AI asistanı.
"""

import logging
import threading
from typing import Optional, Iterator

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
    """

    VERSION = "2.2.0"  # Streaming Update

    def __init__(self, cfg: Config = None) -> None:
        self.cfg = cfg or Config()
        self._lock = threading.RLock()

        # Alt sistemler — temel
        self.security = SecurityManager(self.cfg.ACCESS_LEVEL, self.cfg.BASE_DIR)
        self.code = CodeManager(self.security, self.cfg.BASE_DIR)
        self.health = SystemHealthManager(self.cfg.USE_GPU)
        self.github = GitHubManager(self.cfg.GITHUB_TOKEN, self.cfg.GITHUB_REPO)
        
        self.memory = ConversationMemory(
            file_path=self.cfg.MEMORY_FILE,
            max_turns=self.cfg.MAX_MEMORY_TURNS
        )
        
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
            "SidarAgent v%s başlatıldı — sağlayıcı=%s model=%s erişim=%s bellek=%s",
            self.VERSION,
            self.cfg.AI_PROVIDER,
            self.cfg.CODING_MODEL,
            self.cfg.ACCESS_LEVEL,
            "kalıcı" if self.cfg.MEMORY_FILE else "geçici",
        )

    # ─────────────────────────────────────────────
    #  ANA YANIT METODU (STREAMING)
    # ─────────────────────────────────────────────

    def respond(self, user_input: str) -> Iterator[str]:
        """
        Kullanıcı girdisini işle ve yanıtı STREAM olarak döndür.
        """
        user_input = user_input.strip()
        if not user_input:
            yield "⚠ Boş girdi."
            return

        with self._lock:
            self.memory.add("user", user_input)

            handled, quick_response = self.auto.handle(user_input)
            if handled:
                self.memory.add("assistant", quick_response)
                yield quick_response
                return

            # ReAct döngüsünden gelen akışı kullanıcıya ilet
            full_response = ""
            for chunk in self._react_loop(user_input):
                full_response += chunk  # Bellek için biriktir
                yield chunk             # Kullanıcıya gönder

            # Döngü bitince son hali hafızaya kaydet
            # Not: _react_loop içinde ara adımlar hafızaya eklenmiyor,
            # sadece en son LLM yanıtı veya araç sonucu ekleniyor.
            # Basitlik adına burada son birikmiş yanıtı kaydediyoruz.
            # ReAct mantığı gereği son "full_response" her zaman son adımın çıktısıdır.
            pass 

    # ─────────────────────────────────────────────
    #  ReAct DÖNGÜSÜ (STREAMING)
    # ─────────────────────────────────────────────

    def _react_loop(self, user_input: str) -> Iterator[str]:
        """
        LLM ile araç çağrısı döngüsü. Yanıtları yield eder.
        """
        messages = self.memory.get_messages_for_llm()
        context = self._build_context()
        full_system = SIDAR_SYSTEM_PROMPT + "\n\n" + context

        for step in range(self.cfg.MAX_REACT_STEPS):
            # 1. LLM Çağrısı (Stream)
            response_generator = self.llm.chat(
                messages=messages,
                model=self.cfg.CODING_MODEL,
                system_prompt=full_system,
                temperature=0.3,
                stream=True
            )

            # LLM yanıtını hem biriktir hem yield et
            llm_response_accumulated = ""
            for chunk in response_generator:
                llm_response_accumulated += chunk
                yield chunk

            # 2. Araç Kontrolü
            tool_result = self._check_and_execute_tools(llm_response_accumulated)
            
            # Eğer araç çağrılmadıysa, bu son yanıttır.
            if tool_result is None:
                self.memory.add("assistant", llm_response_accumulated)
                return

            # Araç çağrıldıysa, sonucu göster ve döngüye devam et
            # Kullanıcıya aracın çalıştığını gösteren bir mesaj akıtıyoruz
            tool_msg = f"\n\n[Sistem] Araç Çıktısı:\n{tool_result}\n\n"
            yield tool_msg

            # Hafızayı güncelle (Araç öncesi düşünce + Araç sonucu)
            messages = messages + [
                {"role": "assistant", "content": llm_response_accumulated},
                {"role": "user", "content": f"[Araç Sonucu]\n{tool_result}"},
            ]
            
            # Araç sonucunu hafızaya kalıcı olarak da ekleyelim ki context kopmasın
            # (Basitleştirilmiş yaklaşım: sadece en son turu eklemiyoruz, adımları tutuyoruz)
            # Ancak ana memory.add metodunu kirletmemek için buradaki messages listesini güncel tutuyoruz.
            
        # Döngü biterse
        yield "\n[Sistem] Maksimum adım sayısına ulaşıldı."

    def _check_and_execute_tools(self, llm_response: str) -> Optional[str]:
        """
        LLM yanıtında araç çağrısı direktifi var mı kontrol et ve çalıştır.
        (Buradaki kod orijinaliyle aynıdır)
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
        return "Konuşma belleği temizlendi (dosya silindi). ✓"

    def status(self) -> str:
        lines = [
            f"[SidarAgent v{self.VERSION}]",
            f"  Sağlayıcı    : {self.cfg.AI_PROVIDER}",
            f"  Model        : {self.cfg.CODING_MODEL}",
            f"  Erişim       : {self.cfg.ACCESS_LEVEL}",
            f"  Bellek       : {len(self.memory)} mesaj (Kalıcı)",
            f"  {self.github.status()}",
            f"  {self.web.status()}",
            f"  {self.pkg.status()}",
            f"  {self.docs.status()}",
            self.health.full_report(),
        ]
        return "\n".join(lines)

    def __repr__(self) -> str:
        return f"<SidarAgent v{self.VERSION} provider={self.cfg.AI_PROVIDER}>"
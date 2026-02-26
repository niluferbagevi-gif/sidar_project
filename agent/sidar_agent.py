"""
Sidar Project - Ana Ajan
ReAct (Reason + Act) döngüsü ile çalışan yazılım mühendisi AI asistanı.
"""

import logging
import threading
import json
import re
from typing import Optional, Iterator, Dict

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

    VERSION = "2.3.2"  # REPL Feature Update

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
        self.web = WebSearchManager(self.cfg)
        self.pkg = PackageInfoManager(self.cfg)
        self.docs = DocumentStore(self.cfg.RAG_DIR, top_k=self.cfg.RAG_TOP_K)

        self.auto = AutoHandle(
            self.code, self.health, self.github, self.memory,
            self.web, self.pkg, self.docs,
        )

        logger.info(
            "SidarAgent v%s başlatıldı — sağlayıcı=%s model=%s erişim=%s (JSON MODE)",
            self.VERSION,
            self.cfg.AI_PROVIDER,
            self.cfg.CODING_MODEL,
            self.cfg.ACCESS_LEVEL,
        )

    # ─────────────────────────────────────────────
    #  ANA YANIT METODU (STREAMING)
    # ─────────────────────────────────────────────

    def respond(self, user_input: str) -> Iterator[str]:
        """
        Kullanıcı girdisini işle ve yanıtı STREAM olarak döndür.
        Lock yalnızca bellek/auto-handle kontrolü için kısa tutulur;
        generator tüketimi lock dışında gerçekleşir.
        """
        user_input = user_input.strip()
        if not user_input:
            yield "⚠ Boş girdi."
            return

        # Bellek yazma ve hızlı eşleme kilitli bölgede yapılır
        with self._lock:
            self.memory.add("user", user_input)
            handled, quick_response = self.auto.handle(user_input)
            if handled:
                self.memory.add("assistant", quick_response)

        # Lock serbest bırakıldı — yield ve generator lock dışında
        if handled:
            yield quick_response
            return

        # Bellek eşiği dolmak üzereyse özetleme tetikle
        if self.memory.needs_summarization():
            yield "\n[Sistem] Konuşma belleği sıkıştırılıyor...\n"
            self._summarize_memory()

        # ReAct döngüsünü akıştır
        for chunk in self._react_loop(user_input):
            yield chunk

    # ─────────────────────────────────────────────
    #  ReAct DÖNGÜSÜ (JSON PARSING)
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

            # LLM yanıtını biriktir
            llm_response_accumulated = ""
            for chunk in response_generator:
                llm_response_accumulated += chunk
                yield chunk

            # 2. JSON Ayrıştırma ve Araç Kontrolü
            try:
                # Markdown temizliği
                clean_json = llm_response_accumulated.strip()
                if clean_json.startswith("```"):
                    clean_json = re.sub(r"^```(json)?|```$", "", clean_json, flags=re.MULTILINE).strip()

                action_data = json.loads(clean_json)
                
                tool_name = action_data.get("tool")
                tool_arg = action_data.get("argument", "")

                if tool_name == "final_answer":
                    self.memory.add("assistant", tool_arg)
                    return

                # Aracı çalıştır
                tool_result = self._execute_tool(tool_name, tool_arg)
                
                if tool_result is None:
                    yield f"\n\n[Sistem] Geçersiz araç çağrısı: {tool_name}\n"
                    messages = messages + [
                         {"role": "assistant", "content": llm_response_accumulated},
                         {"role": "user", "content": f"[Sistem Hatası] '{tool_name}' adında bir araç yok veya JSON hatalı."}
                    ]
                    continue

                yield f"\n\n[Sistem] Araç Çıktısı ({tool_name}):\n{tool_result}\n\n"

                messages = messages + [
                    {"role": "assistant", "content": llm_response_accumulated},
                    {"role": "user", "content": f"[Araç Sonucu]\n{tool_result}"},
                ]
            
            except json.JSONDecodeError as je:
                yield "\n\n[Sistem Hatası] Model geçersiz JSON üretti. Tekrar deneniyor...\n"
                error_feedback = (
                    f"[Sistem Hatası] Yanıtın geçerli bir JSON değil.\n"
                    f"Hata: {je.msg} (satır {je.lineno})\n\n"
                    f"Ürettiğin yanıt (ilk 300 karakter):\n{llm_response_accumulated[:300]}\n\n"
                    f'Beklenen format: {{"thought": "...", "tool": "araç_adı", "argument": "argüman"}}'
                )
                messages = messages + [
                    {"role": "assistant", "content": llm_response_accumulated},
                    {"role": "user", "content": error_feedback},
                ]
            except Exception as exc:
                 yield f"\n\n[Sistem Hatası] Beklenmeyen hata: {exc}\n"
                 return
            
        yield "\n[Sistem] Maksimum adım sayısına ulaşıldı."

    def _execute_tool(self, tool_name: str, tool_arg: str) -> Optional[str]:
        """
        Ayrıştırılmış araç adı ve argümanını kullanarak ilgili metodu çağırır.
        """
        tool_arg = str(tool_arg).strip()

        # ── Temel araçlar ──────────────────────────
        if tool_name == "list_dir":
            _, result = self.code.list_directory(tool_arg or ".")
            return result

        if tool_name == "read_file":
            if not tool_arg: return "Dosya yolu belirtilmedi."
            ok, result = self.code.read_file(tool_arg)
            if ok: self.memory.set_last_file(tool_arg)
            return result
        
        if tool_name == "write_file":
            parts = tool_arg.split("|||", 1)
            if len(parts) < 2: return "⚠ Hatalı format. Kullanım: path|||content"
            path, content = parts[0].strip(), parts[1]
            _, result = self.code.write_file(path, content)
            return result

        if tool_name == "patch_file":
            parts = tool_arg.split("|||")
            if len(parts) < 3:
                return "⚠ Hatalı patch formatı. Kullanım: path|||eski_kod|||yeni_kod"
            path = parts[0].strip()
            old_code = parts[1]
            new_code = parts[2]
            _, result = self.code.patch_file(path, old_code, new_code)
            return result

        if tool_name == "execute_code":
            if not tool_arg: return "⚠ Çalıştırılacak kod belirtilmedi."
            _, result = self.code.execute_code(tool_arg)
            return result

        if tool_name == "audit":
            return self.code.audit_project(tool_arg or ".")

        if tool_name == "health":
            return self.health.full_report()

        if tool_name == "gpu_optimize":
            return self.health.optimize_gpu_memory()

        if tool_name == "github_commits":
            try: n = int(tool_arg)
            except: n = 10
            _, result = self.github.list_commits(n=n)
            return result

        if tool_name == "github_info":
            _, result = self.github.get_repo_info()
            return result

        if tool_name == "github_read":
            if not tool_arg: return "⚠ Okunacak GitHub dosya yolu belirtilmedi."
            _, result = self.github.read_remote_file(tool_arg)
            return result

        # ── Web Arama araçları ─────────────────────
        if tool_name == "web_search":
            if not tool_arg: return "⚠ Arama sorgusu belirtilmedi."
            _, result = self.web.search(tool_arg)
            return result

        if tool_name == "fetch_url":
            if not tool_arg: return "⚠ URL belirtilmedi."
            _, result = self.web.fetch_url(tool_arg)
            return result

        if tool_name == "search_docs":
            parts = tool_arg.split(" ", 1)
            lib = parts[0]
            topic = parts[1] if len(parts) > 1 else ""
            _, result = self.web.search_docs(lib, topic)
            return result

        if tool_name == "search_stackoverflow":
            _, result = self.web.search_stackoverflow(tool_arg)
            return result

        # ── Paket Bilgi araçları ───────────────────
        if tool_name == "pypi":
            _, result = self.pkg.pypi_info(tool_arg)
            return result

        if tool_name == "pypi_compare":
            parts = tool_arg.split("|", 1)
            if len(parts) < 2: return "⚠ Kullanım: paket|mevcut_sürüm"
            _, result = self.pkg.pypi_compare(parts[0].strip(), parts[1].strip())
            return result

        if tool_name == "npm":
            _, result = self.pkg.npm_info(tool_arg)
            return result

        if tool_name == "gh_releases":
            _, result = self.pkg.github_releases(tool_arg)
            return result

        if tool_name == "gh_latest":
            _, result = self.pkg.github_latest_release(tool_arg)
            return result

        # ── RAG / Belge Deposu araçları ────────────
        if tool_name == "docs_search":
            _, result = self.docs.search(tool_arg)
            return result

        if tool_name == "docs_add":
            parts = tool_arg.split("|", 1)
            if len(parts) < 2: return "⚠ Kullanım: başlık|url"
            _, result = self.docs.add_document_from_url(parts[1].strip(), title=parts[0].strip())
            return result

        if tool_name == "docs_list":
            return self.docs.list_documents()

        if tool_name == "docs_delete":
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
        lines.append(f"  RAG        : {self.docs.status()}")

        m = self.code.get_metrics()
        lines.append(f"  Okunan     : {m['files_read']} dosya | Yazılan: {m['files_written']}")

        last_file = self.memory.get_last_file()
        if last_file:
            lines.append(f"  Son dosya  : {last_file}")

        return "\n".join(lines)

    # ─────────────────────────────────────────────
    #  BELLEK ÖZETLEME
    # ─────────────────────────────────────────────

    def _summarize_memory(self) -> None:
        """
        Konuşma geçmişini LLM ile özetler ve belleği sıkıştırır.
        Başarısız olursa sessizce geçer; bellek mevcut haliyle sürer.
        """
        history = self.memory.get_history()
        if len(history) < 4:
            return

        turns_text = "\n".join(
            f"{t['role'].upper()}: {t['content'][:400]}"
            for t in history
        )
        summarize_prompt = (
            "Aşağıdaki konuşmayı kısa ve bilgilendirici şekilde özetle. "
            "Teknik detayları, dosya adlarını ve kod kararlarını koru:\n\n"
            + turns_text
        )
        try:
            summary = self.llm.chat(
                messages=[{"role": "user", "content": summarize_prompt}],
                model=self.cfg.CODING_MODEL,
                temperature=0.1,
                stream=False,
                json_mode=False,   # Özet düz metin olmalı, JSON değil
            )
            self.memory.apply_summary(str(summary))
            logger.info("Bellek özetlendi (%d → 2 mesaj).", len(history))
        except Exception as exc:
            logger.warning("Bellek özetleme başarısız: %s", exc)

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
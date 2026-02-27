"""
Sidar Project - Ana Ajan
ReAct (Reason + Act) döngüsü ile çalışan yazılım mühendisi AI asistanı (Asenkron + Pydantic Uyumlu).
"""

import logging
import json
import re
import asyncio
import time
from typing import Optional, AsyncIterator, Dict

from pydantic import BaseModel, Field, ValidationError

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

# ─────────────────────────────────────────────
#  PYDANTIC VERİ MODELİ (YAPISAL ÇIKTI)
# ─────────────────────────────────────────────
class ToolCall(BaseModel):
    """LLM'in ReAct döngüsünde üretmesi gereken JSON şeması."""
    thought: str = Field(description="Ajanın mevcut adımdaki analizi ve planı.")
    tool: str = Field(description="Çalıştırılacak aracın tam adı (örn: final_answer, web_search).")
    argument: str = Field(default="", description="Araca geçirilecek parametre (opsiyonel).")


class SidarAgent:
    """
    Sidar — Yazılım Mimarı ve Baş Mühendis AI Asistanı.
    Tamamen asenkron ağ istekleri, stream, yapısal veri ve sonsuz vektör hafıza uyumlu yapı.
    """

    VERSION = "2.5.0"  # Vector Memory (Infinite Recall) Update

    def __init__(self, cfg: Config = None) -> None:
        self.cfg = cfg or Config()
        self._lock = None  # Asenkron Lock, respond çağrıldığında yaratılacak

        # Alt sistemler — temel (Senkron/Yerel)
        self.security = SecurityManager(self.cfg.ACCESS_LEVEL, self.cfg.BASE_DIR)
        self.code = CodeManager(self.security, self.cfg.BASE_DIR)
        self.health = SystemHealthManager(self.cfg.USE_GPU)
        self.github = GitHubManager(self.cfg.GITHUB_TOKEN, self.cfg.GITHUB_REPO)
        
        self.memory = ConversationMemory(
            file_path=self.cfg.MEMORY_FILE,
            max_turns=self.cfg.MAX_MEMORY_TURNS
        )
        
        self.llm = LLMClient(self.cfg.AI_PROVIDER, self.cfg)

        # Alt sistemler — yeni (Asenkron)
        self.web = WebSearchManager(self.cfg)
        self.pkg = PackageInfoManager(self.cfg)
        self.docs = DocumentStore(self.cfg.RAG_DIR, top_k=self.cfg.RAG_TOP_K)

        self.auto = AutoHandle(
            self.code, self.health, self.github, self.memory,
            self.web, self.pkg, self.docs,
        )

        logger.info(
            "SidarAgent v%s başlatıldı — sağlayıcı=%s model=%s erişim=%s (VECTOR MEMORY + ASYNC)",
            self.VERSION,
            self.cfg.AI_PROVIDER,
            self.cfg.CODING_MODEL,
            self.cfg.ACCESS_LEVEL,
        )

    # ─────────────────────────────────────────────
    #  ANA YANIT METODU (ASYNC STREAMING)
    # ─────────────────────────────────────────────

    async def respond(self, user_input: str) -> AsyncIterator[str]:
        """
        Kullanıcı girdisini asenkron işle ve yanıtı STREAM olarak döndür.
        """
        user_input = user_input.strip()
        if not user_input:
            yield "⚠ Boş girdi."
            return

        # Event loop içinde güvenli Lock oluşturma
        if self._lock is None:
            self._lock = asyncio.Lock()

        # Bellek yazma ve hızlı eşleme kilitli bölgede yapılır
        async with self._lock:
            self.memory.add("user", user_input)
            handled, quick_response = await self.auto.handle(user_input)
            if handled:
                self.memory.add("assistant", quick_response)

        # Lock serbest bırakıldı
        if handled:
            yield quick_response
            return

        # Bellek eşiği dolmak üzereyse özetleme ve arşivleme tetikle
        if self.memory.needs_summarization():
            yield "\n[Sistem] Konuşma belleği arşivleniyor ve sıkıştırılıyor...\n"
            await self._summarize_memory()

        # ReAct döngüsünü akıştır
        async for chunk in self._react_loop(user_input):
            yield chunk

    # ─────────────────────────────────────────────
    #  ReAct DÖNGÜSÜ (PYDANTIC PARSING)
    # ─────────────────────────────────────────────

    async def _react_loop(self, user_input: str) -> AsyncIterator[str]:
        """
        LLM ile araç çağrısı döngüsü (Asenkron).
        Kullanıcıya yalnızca nihai yanıt metni döndürülür; ara JSON/araç
        çıktıları arka planda işlenir.
        """
        messages = self.memory.get_messages_for_llm()
        context = self._build_context()
        full_system = SIDAR_SYSTEM_PROMPT + "\n\n" + context

        for step in range(self.cfg.MAX_REACT_STEPS):
            # 1. LLM Çağrısı (Async Stream)
            response_generator = await self.llm.chat(
                messages=messages,
                model=self.cfg.CODING_MODEL,
                system_prompt=full_system,
                temperature=0.3,
                stream=True
            )

            # LLM yanıtını biriktir
            llm_response_accumulated = ""
            async for chunk in response_generator:
                llm_response_accumulated += chunk

            # 2. JSON Ayrıştırma ve Yapısal Doğrulama (Pydantic)
            try:
                raw_text = llm_response_accumulated.strip()
                
                # Modelin fazladan ürettiği Markdown veya metinleri atlayıp sadece JSON kısmını al
                json_match = re.search(r'\{.*\}', raw_text, re.DOTALL)
                
                if not json_match:
                    raise ValueError("Yanıtın içerisinde süslü parantezlerle ( { ... } ) çevrili bir JSON objesi bulunamadı.")
                    
                clean_json = json_match.group(0)

                # Pydantic ile doğrulama (Eksik veya hatalı tip varsa ValidationError fırlatır)
                action_data = ToolCall.model_validate_json(clean_json)
                
                tool_name = action_data.tool
                tool_arg = action_data.argument

                if tool_name == "final_answer":
                    self.memory.add("assistant", tool_arg)
                    yield str(tool_arg)
                    return

                # Aracı asenkron çalıştır
                tool_result = await self._execute_tool(tool_name, tool_arg)
                
                if tool_result is None:
                    messages = messages + [
                         {"role": "assistant", "content": llm_response_accumulated},
                         {"role": "user", "content": f"[Sistem Hatası] '{tool_name}' adında bir araç yok veya geçersiz bir işlem seçildi."}
                    ]
                    continue

                messages = messages + [
                    {"role": "assistant", "content": llm_response_accumulated},
                    {"role": "user", "content": f"[Araç Sonucu]\n{tool_result}"},
                ]
            
            except ValidationError as ve:
                logger.warning("Pydantic doğrulama hatası:\n%s", ve)
                error_feedback = (
                    f"[Sistem Hatası] Ürettiğin JSON yapısı beklentilere uymuyor.\n"
                    f"Eksik veya hatalı alanlar:\n{ve}\n\n"
                    f"Lütfen sadece şu formata uyan BİR TANE JSON döndür:\n"
                    f'{{"thought": "düşüncen", "tool": "araç_adı", "argument": "argüman"}}'
                )
                messages = messages + [
                    {"role": "assistant", "content": llm_response_accumulated},
                    {"role": "user", "content": error_feedback},
                ]
            except (ValueError, json.JSONDecodeError) as e:
                logger.warning("JSON ayrıştırma hatası: %s", e)
                error_feedback = (
                    f"[Sistem Hatası] Yanıtın geçerli bir JSON formatında değil veya bozuk: {e}\n\n"
                    f"Lütfen yanıtını herhangi bir markdown (```json) bloğuna almadan, sadece düz geçerli bir JSON objesi olarak ver."
                )
                messages = messages + [
                    {"role": "assistant", "content": llm_response_accumulated},
                    {"role": "user", "content": error_feedback},
                ]
            except Exception as exc:
                 logger.exception("ReAct döngüsünde beklenmeyen hata: %s", exc)
                 yield "Üzgünüm, yanıt üretirken beklenmeyen bir hata oluştu."
                 return
            
        yield "Üzgünüm, bu istek için güvenilir bir sonuca ulaşamadım (Maksimum adım sayısına ulaşıldı)."

    async def _execute_tool(self, tool_name: str, tool_arg: str) -> Optional[str]:
        """
        Ayrıştırılmış araç adı ve argümanını kullanarak ilgili metodu asenkron çağırır.
        """
        tool_arg = str(tool_arg).strip()

        # ── Temel araçlar (Senkron çalışanlar) ─────
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

        # ── Web Arama araçları (ASENKRON) ──────────
        if tool_name == "web_search":
            if not tool_arg: return "⚠ Arama sorgusu belirtilmedi."
            _, result = await self.web.search(tool_arg)
            return result

        if tool_name == "fetch_url":
            if not tool_arg: return "⚠ URL belirtilmedi."
            _, result = await self.web.fetch_url(tool_arg)
            return result

        if tool_name == "search_docs":
            parts = tool_arg.split(" ", 1)
            lib = parts[0]
            topic = parts[1] if len(parts) > 1 else ""
            _, result = await self.web.search_docs(lib, topic)
            return result

        if tool_name == "search_stackoverflow":
            _, result = await self.web.search_stackoverflow(tool_arg)
            return result

        # ── Paket Bilgi araçları (ASENKRON) ────────
        if tool_name == "pypi":
            _, result = await self.pkg.pypi_info(tool_arg)
            return result

        if tool_name == "pypi_compare":
            parts = tool_arg.split("|", 1)
            if len(parts) < 2: return "⚠ Kullanım: paket|mevcut_sürüm"
            _, result = await self.pkg.pypi_compare(parts[0].strip(), parts[1].strip())
            return result

        if tool_name == "npm":
            _, result = await self.pkg.npm_info(tool_arg)
            return result

        if tool_name == "gh_releases":
            _, result = await self.pkg.github_releases(tool_arg)
            return result

        if tool_name == "gh_latest":
            _, result = await self.pkg.github_latest_release(tool_arg)
            return result

        # ── RAG / Belge Deposu araçları ────────────
        if tool_name == "docs_search":
            _, result = self.docs.search(tool_arg)
            return result

        if tool_name == "docs_add":
            parts = tool_arg.split("|", 1)
            if len(parts) < 2: return "⚠ Kullanım: başlık|url"
            _, result = await self.docs.add_document_from_url(parts[1].strip(), title=parts[0].strip())
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
    #  BELLEK ÖZETLEME VE VEKTÖR ARŞİVLEME (ASYNC)
    # ─────────────────────────────────────────────

    async def _summarize_memory(self) -> None:
        """
        Konuşma geçmişini LLM ile özetler ve belleği sıkıştırır.
        AYRICA: Eski konuşmaları 'Sonsuz Hafıza' için Vektör DB'ye (ChromaDB) gömer.
        """
        history = self.memory.get_history()
        if len(history) < 4:
            return

        # 1. VEKTÖR BELLEK (SONSUZ HAFIZA) KAYDI
        # Kısa özetlemeye geçmeden önce, tüm detayları RAG sistemine kaydediyoruz
        full_turns_text = "\n\n".join(
            f"[{time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(t.get('timestamp', time.time())))}] {t['role'].upper()}:\n{t['content']}"
            for t in history
        )
        
        try:
            self.docs.add_document(
                title=f"Sohbet Geçmişi Arşivi ({time.strftime('%Y-%m-%d %H:%M')})",
                content=full_turns_text,
                source="memory_archive",
                tags=["memory", "archive", "conversation"]
            )
            logger.info("Eski konuşmalar RAG (Vektör) belleğine arşivlendi.")
        except Exception as exc:
            logger.warning("Vektör belleğe kayıt başarısız: %s", exc)

        # 2. KISA SÜRELİ BELLEK ÖZETLEMESİ
        # LLM token tasarrufu için sadece ilk 400 karakterlik kısımları gönderiyoruz
        turns_text_short = "\n".join(
            f"{t['role'].upper()}: {t['content'][:400]}"
            for t in history
        )
        summarize_prompt = (
            "Aşağıdaki konuşmayı kısa ve bilgilendirici şekilde özetle. "
            "Teknik detayları, dosya adlarını ve kod kararlarını koru:\n\n"
            + turns_text_short
        )
        try:
            summary = await self.llm.chat(
                messages=[{"role": "user", "content": summarize_prompt}],
                model=self.cfg.CODING_MODEL,
                temperature=0.1,
                stream=False,
                json_mode=False,
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
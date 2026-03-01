"""
Sidar Project - Otomatik Komut İşleyici
Kullanıcı girdisindeki ortak kalıpları otomatik olarak tanır ve işler (Asenkron Uyumlu).
"""

import re
from typing import Optional, Tuple

from managers.code_manager import CodeManager
from managers.system_health import SystemHealthManager
from managers.github_manager import GitHubManager
from managers.web_search import WebSearchManager
from managers.package_info import PackageInfoManager
from core.memory import ConversationMemory
from core.rag import DocumentStore


class AutoHandle:
    """
    Kullanıcı mesajlarını anahtar kelime örüntülerine göre analiz eder
    ve uygun manager metodunu çağırır.

    Dönen değer: (işlendi_mi: bool, yanıt: str)
    """

    def __init__(
        self,
        code: CodeManager,
        health: SystemHealthManager,
        github: GitHubManager,
        memory: ConversationMemory,
        web: WebSearchManager,
        pkg: PackageInfoManager,
        docs: DocumentStore,
    ) -> None:
        self.code = code
        self.health = health
        self.github = github
        self.memory = memory
        self.web = web
        self.pkg = pkg
        self.docs = docs

    # ─────────────────────────────────────────────
    #  ANA GİRİŞ NOKTASI (ASYNC)
    # ─────────────────────────────────────────────

    async def handle(self, text: str) -> Tuple[bool, str]:
        """
        text: kullanıcı mesajı

        Returns:
            (True, yanıt)  — otomatik işlendiyse
            (False, "")    — LLM'e ilet
        """
        t = text.lower().strip()

        # ── Temel araçlar (Senkron) ──────────────────────────
        result = self._try_list_directory(t, text)
        if result[0]: return result

        result = self._try_read_file(t, text)
        if result[0]: return result

        result = self._try_audit(t)
        if result[0]: return result

        result = self._try_health(t)
        if result[0]: return result

        result = self._try_gpu_optimize(t)
        if result[0]: return result

        result = self._try_validate_file(t, text)
        if result[0]: return result

        result = self._try_github_commits(t)
        if result[0]: return result

        result = self._try_github_info(t)
        if result[0]: return result

        result = self._try_github_read(t, text)
        if result[0]: return result

        result = self._try_security_status(t)
        if result[0]: return result

        # ── Web Arama araçları (ASENKRON) ─────────────────────
        result = await self._try_web_search(t, text)
        if result[0]: return result

        result = await self._try_fetch_url(t, text)
        if result[0]: return result

        result = await self._try_search_docs(t, text)
        if result[0]: return result

        result = await self._try_search_stackoverflow(t, text)
        if result[0]: return result

        # ── Paket Bilgi araçları (ASENKRON) ───────────────────
        result = await self._try_pypi(t, text)
        if result[0]: return result

        result = await self._try_npm(t, text)
        if result[0]: return result

        result = await self._try_gh_releases(t, text)
        if result[0]: return result

        # ── RAG / Belge Deposu ────────────────────────────────
        result = self._try_docs_search(t, text)
        if result[0]: return result

        result = self._try_docs_list(t, text)
        if result[0]: return result

        result = await self._try_docs_add(t, text)
        if result[0]: return result

        return False, ""

    # ─────────────────────────────────────────────
    #  TEMEL ARAÇ İŞLEYİCİLERİ (SENKRON)
    # ─────────────────────────────────────────────

    def _try_list_directory(self, t: str, raw: str) -> Tuple[bool, str]:
        if re.search(r"listele|dosyaları\s+göster|klasör.*içer|dizin.*listele|ls\b", t):
            path = self._extract_path(raw) or "."
            _, result = self.code.list_directory(path)
            return True, result
        return False, ""

    def _try_read_file(self, t: str, raw: str) -> Tuple[bool, str]:
        if re.search(r"(dosyayı?\s+oku|incele|göster|içeriğ|cat\b)", t):
            path = self._extract_path(raw) or self.memory.get_last_file()
            if not path:
                return True, "⚠ Hangi dosyayı okumamı istiyorsunuz? Lütfen dosya yolunu belirtin."
            ok, content = self.code.read_file(path)
            if ok:
                self.memory.set_last_file(path)
                lines = content.splitlines()
                preview = "\n".join(lines[:80])
                suffix = f"\n... ({len(lines) - 80} satır daha)" if len(lines) > 80 else ""
                return True, f"[{path}]\n```\n{preview}{suffix}\n```"
            return True, f"✗ {content}"
        return False, ""

    def _try_audit(self, t: str) -> Tuple[bool, str]:
        if re.search(r"denetle|sistemi\s+tara|audit|teknik\s+rapor|kod.*kontrol", t):
            return True, self.code.audit_project(".")
        return False, ""

    def _try_health(self, t: str) -> Tuple[bool, str]:
        if re.search(r"sistem.*sağlık|donanım|hardware|cpu|ram|memory.*report|sağlık.*rapor", t):
            if not self.health:
                return True, "⚠ Sistem sağlık monitörü başlatılamadı."
            return True, self.health.full_report()
        return False, ""

    def _try_gpu_optimize(self, t: str) -> Tuple[bool, str]:
        if re.search(r"gpu.*(optimize|temizle|boşalt|clear)|vram", t):
            if not self.health:
                return True, "⚠ Sistem sağlık monitörü başlatılamadı."
            return True, self.health.optimize_gpu_memory()
        return False, ""

    def _try_validate_file(self, t: str, raw: str) -> Tuple[bool, str]:
        if re.search(r"sözdizimi|syntax|doğrula|validate|kontrol\s+et", t):
            path = self._extract_path(raw) or self.memory.get_last_file()
            if not path:
                return True, "⚠ Doğrulanacak dosya yolunu belirtin."
            ok, content = self.code.read_file(path)
            if not ok:
                return True, f"✗ Dosya okunamadı: {content}"
            if path.endswith(".py"):
                ok, msg = self.code.validate_python_syntax(content)
            elif path.endswith(".json"):
                ok, msg = self.code.validate_json(content)
            else:
                return True, f"⚠ {path} için sözdizimi doğrulama desteklenmiyor."
            icon = "✓" if ok else "✗"
            return True, f"{icon} {msg}"
        return False, ""

    def _try_github_commits(self, t: str) -> Tuple[bool, str]:
        if re.search(r"(github|commit).*(listele|göster|son|last)", t) or re.search(r"son.*commit", t):
            if not self.github.is_available():
                return True, "⚠ GitHub token ayarlanmamış."
            m = re.search(r"(\d+)\s*commit", t)
            n = int(m.group(1)) if m else 10
            _, result = self.github.list_commits(n=n)
            return True, result
        return False, ""

    def _try_github_info(self, t: str) -> Tuple[bool, str]:
        if re.search(r"github.*(bilgi|info|repo|depo)|(depo|repo).*(bilgi|info)", t):
            if not self.github.is_available():
                return True, "⚠ GitHub token ayarlanmamış."
            _, result = self.github.get_repo_info()
            return True, result
        return False, ""

    def _try_github_read(self, t: str, raw: str) -> Tuple[bool, str]:
        if re.search(r"github.*(oku|dosya|file)|uzak.*dosya", t):
            if not self.github.is_available():
                return True, "⚠ GitHub token ayarlanmamış."
            path = self._extract_path(raw)
            if not path:
                return True, "⚠ Okunacak GitHub dosya yolunu belirtin."
            ok, content = self.github.read_remote_file(path)
            return True, content if ok else f"✗ {content}"
        return False, ""

    def _try_security_status(self, t: str) -> Tuple[bool, str]:
        if re.search(r"erişim|güvenlik|openclaw|access.*level|yetki", t):
            return True, self.code.security.status_report()
        return False, ""

    # ─────────────────────────────────────────────
    #  WEB ARAMA İŞLEYİCİLERİ (ASENKRON)
    # ─────────────────────────────────────────────

    async def _try_web_search(self, t: str, raw: str) -> Tuple[bool, str]:
        """Web araması — 'web'de ara', 'internette ara', 'google:' vb."""
        m = re.search(
            r"(?:web.?de\s+ara|internette\s+ara|google\s*:|search\s*:)\s*(.+)",
            t,
        )
        if m:
            query = m.group(1).strip()
            if not query:
                return True, "⚠ Arama sorgusu belirtilmedi."
            _, result = await self.web.search(query)
            return True, result
        return False, ""

    async def _try_fetch_url(self, t: str, raw: str) -> Tuple[bool, str]:
        """URL içerik çekme — 'url oku', 'fetch url' vb."""
        if re.search(r"url.*(oku|çek|getir|fetch)|fetch.*url", t):
            url = self._extract_url(raw)
            if not url:
                return True, "⚠ Geçerli bir URL bulunamadı."
            _, result = await self.web.fetch_url(url)
            return True, result
        return False, ""

    async def _try_search_docs(self, t: str, raw: str) -> Tuple[bool, str]:
        """Dokümantasyon araması — 'docs ara fastapi', 'dokümantasyon' vb."""
        m = re.search(
            r"(?:docs?\s+ara|dokümantasyon\s+ara|resmi\s+docs?)\s*[:\-]?\s*(.+)",
            t,
        )
        if m:
            parts = m.group(1).strip().split(" ", 1)
            lib = parts[0]
            topic = parts[1] if len(parts) > 1 else ""
            _, result = await self.web.search_docs(lib, topic)
            return True, result
        return False, ""

    async def _try_search_stackoverflow(self, t: str, raw: str) -> Tuple[bool, str]:
        """Stack Overflow araması — 'stackoverflow: python async' vb."""
        m = re.search(r"(?:stackoverflow|so)\s*[:\-]\s*(.+)", t)
        if m:
            query = m.group(1).strip()
            _, result = await self.web.search_stackoverflow(query)
            return True, result
        return False, ""

    # ─────────────────────────────────────────────
    #  PAKET BİLGİ İŞLEYİCİLERİ (ASENKRON)
    # ─────────────────────────────────────────────

    async def _try_pypi(self, t: str, raw: str) -> Tuple[bool, str]:
        """PyPI paket sorgusu — 'pypi requests', 'paket bilgisi fastapi' vb."""
        m = re.search(
            r"(?:pypi|pip\s+show|paket\s+bilgisi?|python\s+paketi?)\s*[:\-]?\s*([\w\-_.]+)",
            t,
        )
        if m:
            package = m.group(1).strip()
            # Sürüm karşılaştırma: "pypi requests 2.31.0"
            ver_m = re.search(
                r"(?:pypi|pip\s+show|paket\s+bilgisi?)\s+[\w\-_.]+\s+([\d.]+)", t
            )
            if ver_m:
                _, result = await self.pkg.pypi_compare(package, ver_m.group(1))
            else:
                _, result = await self.pkg.pypi_info(package)
            return True, result
        return False, ""

    async def _try_npm(self, t: str, raw: str) -> Tuple[bool, str]:
        """npm paket sorgusu — 'npm react', 'node paketi axios' vb."""
        m = re.search(
            r"(?:npm|node\s+paketi?|js\s+paketi?)\s*[:\-]?\s*([@\w\-_./]+)",
            t,
        )
        if m:
            package = m.group(1).strip()
            _, result = await self.pkg.npm_info(package)
            return True, result
        return False, ""

    async def _try_gh_releases(self, t: str, raw: str) -> Tuple[bool, str]:
        """GitHub releases sorgusu — 'github releases tiangolo/fastapi' vb."""
        m = re.search(
            r"(?:github\s+releases?|gh\s+releases?|sürümler)\s*[:\-]?\s*([\w\-_.]+/[\w\-_.]+)",
            t,
        )
        if m:
            repo = m.group(1).strip()
            _, result = await self.pkg.github_releases(repo)
            return True, result
        return False, ""

    # ─────────────────────────────────────────────
    #  RAG / BELGE DEPOSU İŞLEYİCİLERİ (SENKRON)
    # ─────────────────────────────────────────────

    def _try_docs_search(self, t: str, raw: str) -> Tuple[bool, str]:
        """Belge deposunda arama — 'depoda ara', 'bilgi bankası' vb."""
        m = re.search(
            r"(?:depoda\s+ara|bilgi\s+bankası|rag\s+ara|belgeler.*ara)\s*[:\-]?\s*(.+)",
            t,
        )
        if m:
            query = m.group(1).strip()
            _, result = self.docs.search(query)
            return True, result
        return False, ""

    def _try_docs_list(self, t: str, raw: str) -> Tuple[bool, str]:
        """Belge deposunu listele."""
        if re.search(r"belge.*listele|belge\s+deposu|rag.*listele|döküman.*listele", t):
            return True, self.docs.list_documents()
        return False, ""

    async def _try_docs_add(self, t: str, raw: str) -> Tuple[bool, str]:
        """URL'den belge deposuna ekle — 'belge ekle https://...' vb."""
        m = re.search(r"(?:belge\s+ekle|dokümana\s+ekle|rag.*ekle)\s+(https?://\S+)", raw, re.IGNORECASE)
        if m:
            url = m.group(1).strip()
            title_m = re.search(r'"([^"]+)"', raw)
            title = title_m.group(1) if title_m else ""
            _, result = await self.docs.add_document_from_url(url, title=title)
            return True, result
        return False, ""

    # ─────────────────────────────────────────────
    #  YARDIMCILAR
    # ─────────────────────────────────────────────

    def _extract_path(self, text: str) -> Optional[str]:
        """Metinden dosya/dizin yolu çıkar."""
        m = re.search(r'["\']([^"\']+\.[a-zA-Z]{1,6})["\']', text)
        if m:
            return m.group(1)
        m = re.search(
            r'\b([\w/\\.\-]+\.(?:py|json|md|txt|yaml|yml|js|ts|sh|toml|cfg|ini))\b',
            text,
        )
        if m:
            return m.group(1)
        return None

    def _extract_url(self, text: str) -> Optional[str]:
        """Metinden URL çıkar."""
        m = re.search(r'https?://[^\s"\'<>]+', text)
        return m.group(0) if m else None
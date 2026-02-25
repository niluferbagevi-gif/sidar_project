"""
Sidar Project - Web Arama Yöneticisi
DuckDuckGo arama motoru ve URL içerik çekme.
"""

import logging
import re
from typing import Tuple, Optional

import requests

logger = logging.getLogger(__name__)


class WebSearchManager:
    """
    DuckDuckGo ile gerçek zamanlı web araması ve URL içerik çekme.

    Gereksinim: pip install duckduckgo-search
    """

    MAX_RESULTS = 5
    FETCH_TIMEOUT = 15  # saniye
    FETCH_MAX_CHARS = 4000

    def __init__(self) -> None:
        self._available = self._check_availability()

    # ─────────────────────────────────────────────
    #  DURUM
    # ─────────────────────────────────────────────

    def _check_availability(self) -> bool:
        try:
            from duckduckgo_search import DDGS  # noqa: F401
            return True
        except ImportError:
            logger.warning(
                "duckduckgo-search kurulu değil. "
                "Kurmak için: pip install duckduckgo-search"
            )
            return False

    def is_available(self) -> bool:
        return self._available

    def status(self) -> str:
        state = "Aktif" if self._available else "duckduckgo-search kurulu değil"
        return f"WebSearch: {state}"

    # ─────────────────────────────────────────────
    #  WEB ARAMA
    # ─────────────────────────────────────────────

    def search(self, query: str, max_results: int = None) -> Tuple[bool, str]:
        """
        DuckDuckGo'da metin araması yap.

        Args:
            query      : Arama sorgusu
            max_results: Maksimum sonuç sayısı (varsayılan MAX_RESULTS)

        Returns:
            (başarı, biçimlendirilmiş_sonuç)
        """
        if not self._available:
            return False, (
                "⚠ Web arama mevcut değil. "
                "Kurmak için: pip install duckduckgo-search"
            )

        n = max_results or self.MAX_RESULTS
        try:
            from duckduckgo_search import DDGS

            with DDGS() as ddgs:
                results = list(ddgs.text(query, max_results=n))

            if not results:
                return True, f"'{query}' için sonuç bulunamadı."

            lines = [f"[Web Arama: {query}]", ""]
            for i, r in enumerate(results, 1):
                title = r.get("title", "Başlıksız")
                body = (r.get("body") or "")[:250].rstrip()
                href = r.get("href", "")
                lines.append(f"{i}. **{title}**")
                if body:
                    lines.append(f"   {body}")
                lines.append(f"   → {href}")
                lines.append("")

            return True, "\n".join(lines)

        except Exception as exc:
            logger.error("Web arama hatası: %s", exc)
            return False, f"[HATA] Web arama: {exc}"

    # ─────────────────────────────────────────────
    #  URL İÇERİĞİ ÇEKME
    # ─────────────────────────────────────────────

    def fetch_url(self, url: str) -> Tuple[bool, str]:
        """
        Belirtilen URL'nin içeriğini çek ve temiz metin olarak döndür.

        Args:
            url: Çekilecek URL

        Returns:
            (başarı, içerik)
        """
        try:
            resp = requests.get(
                url,
                timeout=self.FETCH_TIMEOUT,
                headers={"User-Agent": "Mozilla/5.0 (compatible; SidarBot/1.0)"},
            )
            resp.raise_for_status()
            text = self._clean_html(resp.text)
            truncated = text[: self.FETCH_MAX_CHARS]
            suffix = f"\n... ({len(text) - self.FETCH_MAX_CHARS} karakter daha)" if len(text) > self.FETCH_MAX_CHARS else ""
            return True, f"[URL: {url}]\n\n{truncated}{suffix}"
        except requests.exceptions.Timeout:
            return False, f"[HATA] URL zaman aşımı: {url}"
        except requests.exceptions.ConnectionError:
            return False, f"[HATA] URL bağlantı hatası: {url}"
        except Exception as exc:
            logger.error("URL çekme hatası: %s", exc)
            return False, f"[HATA] URL çekme: {exc}"

    @staticmethod
    def _clean_html(html: str) -> str:
        """HTML etiketlerini temizleyerek düz metin üret."""
        # Script/style bloklarını kaldır
        clean = re.sub(
            r"<(script|style)[^>]*>.*?</(script|style)>",
            "",
            html,
            flags=re.DOTALL | re.IGNORECASE,
        )
        # HTML etiketlerini kaldır
        clean = re.sub(r"<[^>]+>", " ", clean)
        # HTML entity'lerini çöz
        clean = clean.replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">")
        clean = clean.replace("&nbsp;", " ").replace("&quot;", '"')
        # Fazla boşlukları temizle
        clean = re.sub(r"\s+", " ", clean)
        return clean.strip()

    # ─────────────────────────────────────────────
    #  DOKÜMANTASYON ARAMALARI
    # ─────────────────────────────────────────────

    def search_docs(self, library: str, topic: str = "") -> Tuple[bool, str]:
        """
        Belirli bir kütüphanenin dokümantasyonunu ara.

        Args:
            library: Kütüphane adı (örn: "fastapi", "pandas")
            topic  : Opsiyonel konu (örn: "routing", "dataframe")
        """
        q = f"{library} documentation {topic}".strip()
        q += " site:docs.python.org OR site:pypi.org OR site:readthedocs.io OR site:github.com"
        return self.search(q, max_results=5)

    def search_stackoverflow(self, query: str) -> Tuple[bool, str]:
        """Stack Overflow'da soru ara."""
        q = f"site:stackoverflow.com {query}"
        return self.search(q, max_results=5)

    def search_github(self, query: str) -> Tuple[bool, str]:
        """GitHub'da depo veya kod ara."""
        q = f"site:github.com {query}"
        return self.search(q, max_results=5)

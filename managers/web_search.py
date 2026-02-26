"""
Sidar Project - Web Arama Yöneticisi
DuckDuckGo arama motoru ve URL içerik çekme (Asenkron).
"""

import logging
import re
import asyncio
from typing import Tuple, Optional

import httpx

logger = logging.getLogger(__name__)


class WebSearchManager:
    """
    DuckDuckGo ile gerçek zamanlı web araması ve URL içerik çekme.
    Tamamen asenkron (async/await) mimariye uyumludur.

    Gereksinim: pip install duckduckgo-search httpx
    """

    # Varsayılan değerler (Config verilmezse kullanılır)
    MAX_RESULTS = 5
    FETCH_TIMEOUT = 15  # saniye
    FETCH_MAX_CHARS = 4000

    def __init__(self, config=None) -> None:
        if config is not None:
            self.MAX_RESULTS = getattr(config, "WEB_SEARCH_MAX_RESULTS", self.MAX_RESULTS)
            self.FETCH_TIMEOUT = getattr(config, "WEB_FETCH_TIMEOUT", self.FETCH_TIMEOUT)
            self.FETCH_MAX_CHARS = getattr(config, "WEB_FETCH_MAX_CHARS", self.FETCH_MAX_CHARS)
        self._available = self._check_availability()

    # ─────────────────────────────────────────────
    #  DURUM
    # ─────────────────────────────────────────────

    def _check_availability(self) -> bool:
        try:
            from duckduckgo_search import AsyncDDGS  # noqa: F401
            return True
        except ImportError:
            logger.warning(
                "duckduckgo-search kurulu değil veya sürümü eski. "
                "Kurmak/Güncellemek için: pip install -U duckduckgo-search httpx"
            )
            return False

    def is_available(self) -> bool:
        return self._available

    def status(self) -> str:
        state = "Aktif (Asenkron)" if self._available else "duckduckgo-search kurulu değil"
        return f"WebSearch: {state}"

    # ─────────────────────────────────────────────
    #  WEB ARAMA (ASYNC)
    # ─────────────────────────────────────────────

    async def search(self, query: str, max_results: int = None) -> Tuple[bool, str]:
        """
        DuckDuckGo'da asenkron metin araması yap.

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
            from duckduckgo_search import AsyncDDGS

            async with AsyncDDGS() as ddgs:
                # AsyncDDGS kütüphanesinde arama işlemi için text metodunu await ediyoruz
                results = await ddgs.text(query, max_results=n)

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
    #  URL İÇERİĞİ ÇEKME (ASYNC)
    # ─────────────────────────────────────────────

    async def fetch_url(self, url: str) -> Tuple[bool, str]:
        """
        Belirtilen URL'nin içeriğini asenkron olarak çek ve temiz metin olarak döndür.

        Args:
            url: Çekilecek URL

        Returns:
            (başarı, içerik)
        """
        try:
            async with httpx.AsyncClient(timeout=self.FETCH_TIMEOUT, follow_redirects=True) as client:
                resp = await client.get(
                    url,
                    headers={"User-Agent": "Mozilla/5.0 (compatible; SidarBot/1.0)"}
                )
                resp.raise_for_status()
                
                text = self._clean_html(resp.text)
                truncated = text[: self.FETCH_MAX_CHARS]
                suffix = f"\n... ({len(text) - self.FETCH_MAX_CHARS} karakter daha)" if len(text) > self.FETCH_MAX_CHARS else ""
                
                return True, f"[URL: {url}]\n\n{truncated}{suffix}"
                
        except httpx.TimeoutException:
            return False, f"[HATA] URL zaman aşımı: {url}"
        except httpx.RequestError as exc:
            return False, f"[HATA] URL bağlantı/istek hatası: {url} - {exc}"
        except httpx.HTTPStatusError as exc:
            return False, f"[HATA] HTTP Hata Kodu {exc.response.status_code}: {url}"
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
    #  DOKÜMANTASYON ARAMALARI (ASYNC)
    # ─────────────────────────────────────────────

    async def search_docs(self, library: str, topic: str = "") -> Tuple[bool, str]:
        """
        Belirli bir kütüphanenin dokümantasyonunu ara.
        """
        q = f"{library} documentation {topic}".strip()
        q += " site:docs.python.org OR site:pypi.org OR site:readthedocs.io OR site:github.com"
        return await self.search(q, max_results=5)

    async def search_stackoverflow(self, query: str) -> Tuple[bool, str]:
        """Stack Overflow'da soru ara."""
        q = f"site:stackoverflow.com {query}"
        return await self.search(q, max_results=5)
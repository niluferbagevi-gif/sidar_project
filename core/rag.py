"""
Sidar Project - Belge Deposu ve Arama (RAG)
BM25 tabanlı hafif Retrieval-Augmented Generation sistemi.

Belgeler disk'te saklanır; arama için rank-bm25 kullanılır.
rank-bm25 yoksa anahtar kelime eşleme ile devam edilir.
"""

import hashlib
import json
import logging
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


class DocumentStore:
    """
    Yerel belge deposu — BM25 ile semantik arama.

    Kullanım:
        store = DocumentStore(Path("data/rag"))
        doc_id = store.add_document("FastAPI Giriş", content, source="https://...")
        ok, result = store.search("dependency injection")
    """

    def __init__(self, store_dir: Path) -> None:
        self.store_dir = Path(store_dir)
        self.store_dir.mkdir(parents=True, exist_ok=True)
        self.index_file = self.store_dir / "index.json"
        self._index: Dict[str, Dict] = self._load_index()
        self._bm25_available = self._check_bm25()

    # ─────────────────────────────────────────────
    #  BAŞLANGIÇ
    # ─────────────────────────────────────────────

    def _check_bm25(self) -> bool:
        try:
            import rank_bm25  # noqa: F401
            return True
        except ImportError:
            logger.debug("rank-bm25 kurulu değil; anahtar kelime araması kullanılacak.")
            return False

    def _load_index(self) -> Dict[str, Dict]:
        if self.index_file.exists():
            try:
                return json.loads(self.index_file.read_text(encoding="utf-8"))
            except Exception as exc:
                logger.warning("RAG index okunamadı: %s", exc)
        return {}

    def _save_index(self) -> None:
        self.index_file.write_text(
            json.dumps(self._index, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    # ─────────────────────────────────────────────
    #  BELGE YÖNETİMİ
    # ─────────────────────────────────────────────

    def add_document(
        self,
        title: str,
        content: str,
        source: str = "",
        tags: Optional[List[str]] = None,
    ) -> str:
        """
        Belge ekle veya güncelle.

        Args:
            title  : Belge başlığı
            content: Belge içeriği
            source : Kaynak URL veya yol (opsiyonel)
            tags   : Etiketler (opsiyonel)

        Returns:
            Belge ID'si (12 karakter hex)
        """
        doc_id = hashlib.md5(f"{title}{source}".encode()).hexdigest()[:12]
        doc_file = self.store_dir / f"{doc_id}.txt"
        doc_file.write_text(content, encoding="utf-8")

        self._index[doc_id] = {
            "title": title,
            "source": source,
            "tags": tags or [],
            "size": len(content),
            "preview": content[:250],
        }
        self._save_index()
        logger.info("RAG belge eklendi: [%s] %s (%d karakter)", doc_id, title, len(content))
        return doc_id

    def add_document_from_url(self, url: str, title: str = "", tags: Optional[List[str]] = None) -> Tuple[bool, str]:
        """
        URL'den içerik çekerek belge ekle.

        Args:
            url  : İçerik çekilecek URL
            title: Belge başlığı (boşsa URL'den türetilir)
            tags : Etiketler

        Returns:
            (başarı, mesaj_veya_doc_id)
        """
        import requests

        try:
            resp = requests.get(
                url,
                timeout=15,
                headers={"User-Agent": "Mozilla/5.0 (compatible; SidarBot/1.0)"},
            )
            resp.raise_for_status()
            content = self._clean_html(resp.text)

            if not title:
                # URL'den başlık türet
                m = re.search(r"<title[^>]*>([^<]+)</title>", resp.text, re.IGNORECASE)
                title = m.group(1).strip() if m else url.split("/")[-1] or url

            doc_id = self.add_document(title, content, source=url, tags=tags)
            return True, f"✓ Belge eklendi: [{doc_id}] {title} ({len(content)} karakter)"

        except Exception as exc:
            logger.error("URL belge çekme hatası: %s", exc)
            return False, f"[HATA] URL belge eklenemedi: {exc}"

    def delete_document(self, doc_id: str) -> str:
        """Belge sil."""
        if doc_id not in self._index:
            return f"✗ Belge bulunamadı: {doc_id}"
        doc_file = self.store_dir / f"{doc_id}.txt"
        if doc_file.exists():
            doc_file.unlink()
        title = self._index[doc_id].get("title", doc_id)
        del self._index[doc_id]
        self._save_index()
        return f"✓ Belge silindi: [{doc_id}] {title}"

    def get_document(self, doc_id: str) -> Tuple[bool, str]:
        """Belge ID ile tam içerik getir."""
        if doc_id not in self._index:
            return False, f"✗ Belge bulunamadı: {doc_id}"
        doc_file = self.store_dir / f"{doc_id}.txt"
        if not doc_file.exists():
            return False, f"✗ Belge dosyası eksik: {doc_id}"
        content = doc_file.read_text(encoding="utf-8")
        meta = self._index[doc_id]
        return True, f"[{doc_id}] {meta['title']}\nKaynak: {meta.get('source', '-')}\n\n{content}"

    # ─────────────────────────────────────────────
    #  ARAMA
    # ─────────────────────────────────────────────

    def search(self, query: str, top_k: int = 3) -> Tuple[bool, str]:
        """
        Sorguya göre en ilgili belgeleri bul.

        BM25 (rank-bm25 kuruluysa) veya anahtar kelime eşleme kullanır.

        Args:
            query : Arama sorgusu
            top_k : Döndürülecek maksimum sonuç sayısı

        Returns:
            (başarı, biçimlendirilmiş_sonuçlar)
        """
        if not self._index:
            return False, (
                "⚠ Belge deposu boş. "
                "Belge eklemek için: TOOL:docs_add:<başlık>|<url>"
            )

        if self._bm25_available:
            return self._bm25_search(query, top_k)
        return self._keyword_search(query, top_k)

    def _bm25_search(self, query: str, top_k: int) -> Tuple[bool, str]:
        from rank_bm25 import BM25Okapi

        doc_ids = list(self._index.keys())
        corpus = []
        for doc_id in doc_ids:
            doc_file = self.store_dir / f"{doc_id}.txt"
            text = doc_file.read_text(encoding="utf-8") if doc_file.exists() else ""
            corpus.append(text.lower().split())

        bm25 = BM25Okapi(corpus)
        scores = bm25.get_scores(query.lower().split())
        ranked = sorted(zip(doc_ids, scores), key=lambda x: x[1], reverse=True)
        ranked = [(d, s) for d, s in ranked if s > 0][:top_k]
        return self._format_results(ranked, query)

    def _keyword_search(self, query: str, top_k: int) -> Tuple[bool, str]:
        keywords = query.lower().split()
        scored = []

        for doc_id, meta in self._index.items():
            doc_file = self.store_dir / f"{doc_id}.txt"
            text = (
                doc_file.read_text(encoding="utf-8") if doc_file.exists() else ""
            ).lower()
            title_lower = meta["title"].lower()
            tags_lower = " ".join(meta.get("tags", [])).lower()

            score = sum(
                text.count(kw) + title_lower.count(kw) * 5 + tags_lower.count(kw) * 3
                for kw in keywords
            )
            if score > 0:
                scored.append((doc_id, score))

        ranked = sorted(scored, key=lambda x: x[1], reverse=True)[:top_k]
        return self._format_results(ranked, query)

    def _format_results(self, ranked: list, query: str) -> Tuple[bool, str]:
        if not ranked:
            return False, f"'{query}' için belge deposunda ilgili sonuç bulunamadı."

        lines = [f"[Belge Deposu Arama: {query}]", ""]
        for doc_id, score in ranked:
            meta = self._index.get(doc_id, {})
            doc_file = self.store_dir / f"{doc_id}.txt"
            content = doc_file.read_text(encoding="utf-8") if doc_file.exists() else ""

            # Sorgudaki kelimelerin geçtiği paragrafı bul
            snippet = self._extract_snippet(content, query)

            lines.append(f"**[{doc_id}] {meta.get('title', '?')}**")
            if meta.get("source"):
                lines.append(f"  Kaynak: {meta['source']}")
            lines.append(f"  {snippet}")
            lines.append("")

        return True, "\n".join(lines)

    @staticmethod
    def _extract_snippet(content: str, query: str, window: int = 400) -> str:
        """Sorgudaki ilk anahtar kelimenin etrafındaki metni çıkar."""
        keywords = query.lower().split()
        content_lower = content.lower()
        for kw in keywords:
            idx = content_lower.find(kw)
            if idx != -1:
                start = max(0, idx - 100)
                end = min(len(content), idx + window)
                snippet = content[start:end].strip()
                return f"...{snippet}..." if start > 0 else snippet
        return content[:window]

    # ─────────────────────────────────────────────
    #  LİSTELEME
    # ─────────────────────────────────────────────

    def list_documents(self) -> str:
        if not self._index:
            return "Belge deposu boş."

        lines = [f"[Belge Deposu — {len(self._index)} belge]", ""]
        for doc_id, meta in self._index.items():
            tags = ", ".join(meta.get("tags", [])) or "-"
            size_kb = meta.get("size", 0) / 1024
            lines.append(f"  [{doc_id}] {meta['title']}")
            lines.append(
                f"    Kaynak: {meta.get('source', '-')} | "
                f"Boyut: {size_kb:.1f} KB | Etiketler: {tags}"
            )
        return "\n".join(lines)

    # ─────────────────────────────────────────────
    #  YARDIMCILAR
    # ─────────────────────────────────────────────

    @staticmethod
    def _clean_html(html: str) -> str:
        """HTML'yi temiz metne dönüştür."""
        clean = re.sub(
            r"<(script|style)[^>]*>.*?</(script|style)>",
            "",
            html,
            flags=re.DOTALL | re.IGNORECASE,
        )
        clean = re.sub(r"<[^>]+>", " ", clean)
        clean = clean.replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">")
        clean = clean.replace("&nbsp;", " ").replace("&quot;", '"')
        clean = re.sub(r"\s+", " ", clean)
        return clean.strip()

    def status(self) -> str:
        engine = "BM25 (rank-bm25)" if self._bm25_available else "Anahtar Kelime"
        return f"RAG: {len(self._index)} belge | Motor: {engine} | Dizin: {self.store_dir}"

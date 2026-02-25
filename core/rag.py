"""
Sidar Project - Belge Deposu ve Arama (RAG)
ChromaDB tabanlı Vektör Arama + BM25 Hibrit Sistemi.

Özellikler:
1. Vektör Arama (ChromaDB): Anlamsal yakınlık (Semantic Search)
2. BM25 (rank_bm25): Kelime sıklığı ve nadirlik tabanlı arama
3. Fallback: Basit anahtar kelime eşleşmesi
"""

import hashlib
import json
import logging
import re
import shutil
from pathlib import Path
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


class DocumentStore:
    """
    Yerel belge deposu — ChromaDB ile semantik arama.

    Kullanım:
        store = DocumentStore(Path("data/rag"))
        doc_id = store.add_document("FastAPI Giriş", content, source="https://...")
        ok, result = store.search("dependency injection")
    """

    def __init__(self, store_dir: Path) -> None:
        self.store_dir = Path(store_dir)
        self.store_dir.mkdir(parents=True, exist_ok=True)
        self.index_file = self.store_dir / "index.json"
        
        # Meta verileri yükle
        self._index: Dict[str, Dict] = self._load_index()
        
        # Arama motorlarını başlat
        self._bm25_available = self._check_import("rank_bm25")
        self._chroma_available = self._check_import("chromadb")
        
        self.chroma_client = None
        self.collection = None

        if self._chroma_available:
            self._init_chroma()

    # ─────────────────────────────────────────────
    #  BAŞLANGIÇ & AYARLAR
    # ─────────────────────────────────────────────

    def _check_import(self, module_name: str) -> bool:
        import importlib
        try:
            importlib.import_module(module_name)
            return True
        except ImportError:
            return False

    def _init_chroma(self) -> None:
        """ChromaDB istemcisini ve koleksiyonunu başlat."""
        try:
            import chromadb
            from chromadb.config import Settings
            
            # Veritabanını data/rag/chroma_db içinde tut
            db_path = self.store_dir / "chroma_db"
            
            self.chroma_client = chromadb.PersistentClient(path=str(db_path))
            
            # Varsayılan embedding fonksiyonu (all-MiniLM-L6-v2) otomatik kullanılır
            self.collection = self.chroma_client.get_or_create_collection(
                name="sidar_knowledge_base",
                metadata={"hnsw:space": "cosine"}
            )
            logger.info("ChromaDB vektör veritabanı başlatıldı.")
        except Exception as exc:
            logger.error("ChromaDB başlatma hatası: %s", exc)
            self._chroma_available = False

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
        Belge ekle veya güncelle (Hem JSON hem ChromaDB).
        """
        # ID oluştur
        doc_id = hashlib.md5(f"{title}{source}".encode()).hexdigest()[:12]
        tags = tags or []

        # 1. Dosya sistemine kaydet (Yedek ve tam okuma için)
        doc_file = self.store_dir / f"{doc_id}.txt"
        doc_file.write_text(content, encoding="utf-8")

        # 2. JSON Index güncelle
        self._index[doc_id] = {
            "title": title,
            "source": source,
            "tags": tags,
            "size": len(content),
            "preview": content[:300],
        }
        self._save_index()

        # 3. ChromaDB'ye vektör olarak ekle
        if self._chroma_available and self.collection:
            try:
                # Meta verileri hazırla
                metadata = {
                    "source": source,
                    "title": title,
                    "tags": ",".join(tags)
                }
                # Büyük dokümanları parçalamak (chunking) daha iyidir ama
                # şimdilik basitçe ilk 2000 karakteri veya tamamını gömelim.
                # Chroma varsayılan modeli token limitine sahip olabilir.
                self.collection.upsert(
                    ids=[doc_id],
                    documents=[content],
                    metadatas=[metadata]
                )
            except Exception as exc:
                logger.error("ChromaDB belge ekleme hatası: %s", exc)

        logger.info("RAG belge eklendi: [%s] %s (%d karakter)", doc_id, title, len(content))
        return doc_id

    def add_document_from_url(self, url: str, title: str = "", tags: Optional[List[str]] = None) -> Tuple[bool, str]:
        """URL'den içerik çekerek belge ekle."""
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
        """Belgeyi tüm depolardan sil."""
        if doc_id not in self._index:
            return f"✗ Belge bulunamadı: {doc_id}"

        # 1. Dosya sil
        doc_file = self.store_dir / f"{doc_id}.txt"
        if doc_file.exists():
            doc_file.unlink()

        # 2. ChromaDB'den sil
        if self._chroma_available and self.collection:
            try:
                self.collection.delete(ids=[doc_id])
            except Exception as exc:
                logger.error("ChromaDB silme hatası: %s", exc)

        # 3. Index'ten sil
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
    #  ARAMA (HİBRİT)
    # ─────────────────────────────────────────────

    def search(self, query: str, top_k: int = 3) -> Tuple[bool, str]:
        """
        Sorguya göre en ilgili belgeleri bul.
        Öncelik: ChromaDB (Vektör) -> BM25 -> Keyword
        """
        if not self._index:
            return False, (
                "⚠ Belge deposu boş. "
                "Belge eklemek için: TOOL:docs_add:<başlık>|<url>"
            )

        # 1. Vektör Arama (En iyi sonuçlar)
        if self._chroma_available and self.collection:
            try:
                return self._chroma_search(query, top_k)
            except Exception as exc:
                logger.warning("ChromaDB arama hatası (BM25'e düşülüyor): %s", exc)

        # 2. BM25 Arama
        if self._bm25_available:
            return self._bm25_search(query, top_k)
        
        # 3. Basit Kelime Araması
        return self._keyword_search(query, top_k)

    def _chroma_search(self, query: str, top_k: int) -> Tuple[bool, str]:
        results = self.collection.query(
            query_texts=[query],
            n_results=top_k
        )
        
        if not results["ids"] or not results["ids"][0]:
            return False, f"'{query}' için anlamsal sonuç bulunamadı."

        # Chroma sonuçlarını biçimlendir
        ranked_ids = results["ids"][0]
        # distances = results["distances"][0] if "distances" in results else []
        
        # Biçimlendirme için ortak fonksiyonu kullan, ancak snippet'ı vektör sonucundan alabiliriz
        # fakat tam metin için yine dosyaya gitmek daha güvenli.
        
        # Chroma'dan gelen ID'leri, DocumentStore formatında döndür
        # Skoru yapay olarak sıralamaya göre veriyoruz (Chroma zaten sıralı döner)
        ranked_with_score = [(doc_id, 1.0) for doc_id in ranked_ids]
        
        return self._format_results(ranked_with_score, query, source_name="Vektör Arama (ChromaDB)")

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
        return self._format_results(ranked, query, source_name="BM25")

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
        return self._format_results(ranked, query, source_name="Kelime Eşleşmesi")

    def _format_results(self, ranked: list, query: str, source_name: str) -> Tuple[bool, str]:
        if not ranked:
            return False, f"'{query}' için belge deposunda ilgili sonuç bulunamadı."

        lines = [f"[RAG Arama: {query}] (Motor: {source_name})", ""]
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
        
        # Önce tam eşleşme ara
        for kw in keywords:
            idx = content_lower.find(kw)
            if idx != -1:
                start = max(0, idx - 100)
                end = min(len(content), idx + window)
                snippet = content[start:end].strip()
                return f"...{snippet}..." if start > 0 else snippet
        
        # Bulunamazsa baş tarafı döndür
        return content[:window] + ("..." if len(content) > window else "")

    # ─────────────────────────────────────────────
    #  LİSTELEME & STATÜ
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
        engines = []
        if self._chroma_available: engines.append("ChromaDB (Vektör)")
        if self._bm25_available: engines.append("BM25")
        if not engines: engines.append("Anahtar Kelime")
        
        return f"RAG: {len(self._index)} belge | Motorlar: {', '.join(engines)}"
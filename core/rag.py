"""
Sidar Project - Belge Deposu ve Arama (RAG)
ChromaDB tabanlı Vektör Arama + BM25 Hibrit Sistemi.

Özellikler:
1. Vektör Arama (ChromaDB): Anlamsal yakınlık (Semantic Search) - Chunking destekli
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
    
    Güncelleme: Recursive Character Chunking stratejisi ile büyük belgeleri
    mantıksal parçalara ayırarak vektörleştirir.
    """

    def __init__(self, store_dir: Path, top_k: int = 3,
                 chunk_size: int = 1000, chunk_overlap: int = 200) -> None:
        self.store_dir = Path(store_dir)
        self.store_dir.mkdir(parents=True, exist_ok=True)
        self.index_file = self.store_dir / "index.json"
        self.default_top_k = top_k
        self._chunk_size = chunk_size
        self._chunk_overlap = chunk_overlap

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
    #  BELGE YÖNETİMİ & CHUNKING
    # ─────────────────────────────────────────────

    def _recursive_chunk_text(self, text: str) -> List[str]:
        """
        Metni kod yapısına uygun ayırıcılarla (separators) mantıksal parçalara böler.
        LangChain'in RecursiveCharacterTextSplitter mantığını simüle eder.
        """
        if not text:
            return []

        # Öncelik sırasına göre ayırıcılar (Python ve genel metin için optimize)
        separators = ["\nclass ", "\ndef ", "\n\n", "\n", " ", ""]
        
        final_chunks = []
        
        # Eğer metin zaten limitin altındaysa direkt döndür
        if len(text) <= self._chunk_size:
            return [text]

        def _split(text_part: str, sep_idx: int) -> List[str]:
            """Recursive bölme fonksiyonu"""
            if len(text_part) <= self._chunk_size:
                return [text_part]
            
            if sep_idx >= len(separators):
                # Hiçbir ayırıcı ile bölünemiyorsa zorla böl (character limit)
                return [text_part[i:i+self._chunk_size] for i in range(0, len(text_part), self._chunk_size - self._chunk_overlap)]

            sep = separators[sep_idx]
            # Ayırıcıya göre böl (ayırıcı başta kalsın diye lookahead simülasyonu yapılabilir ama basit split yeterli)
            # Not: Python split ayırıcıyı yutar, tekrar eklemek gerekebilir.
            # Burada basit split kullanıyoruz, bağlam kaybı olmaması için overlap önemli.
            if sep == "":
                parts = list(text_part) # Karakter karakter
            else:
                parts = text_part.split(sep)
                # Ayırıcıyı parçalara geri ekleyelim (özellikle class/def için önemli)
                parts = [parts[0]] + [sep + p for p in parts[1:]] if parts else []

            new_chunks = []
            current_chunk = ""

            for part in parts:
                # Eğer parça tek başına bile çok büyükse, bir sonraki ayırıcı ile böl
                if len(part) > self._chunk_size:
                    if current_chunk:
                        new_chunks.append(current_chunk)
                        current_chunk = ""
                    sub_chunks = _split(part, sep_idx + 1)
                    new_chunks.extend(sub_chunks)
                    continue

                # Mevcut parça ile limiti aşıyor mu?
                if len(current_chunk) + len(part) > self._chunk_size:
                    new_chunks.append(current_chunk)
                    # Overlap mekanizması: Bir önceki chunk'ın sonundan biraz al
                    overlap_len = min(len(current_chunk), self._chunk_overlap)
                    current_chunk = current_chunk[-overlap_len:] + part
                else:
                    current_chunk += part
            
            if current_chunk:
                new_chunks.append(current_chunk)
            
            return new_chunks

        return _split(text, 0)

    def add_document(
        self,
        title: str,
        content: str,
        source: str = "",
        tags: Optional[List[str]] = None,
    ) -> str:
        """
        Belge ekle veya güncelle.
        İçeriği parçalara (chunks) ayırarak ChromaDB'ye kaydeder.
        """
        # Ana Belge ID oluştur
        doc_id = hashlib.md5(f"{title}{source}".encode()).hexdigest()[:12]
        tags = tags or []

        # 1. Dosya sistemine TAM metni kaydet (Okuma ve BM25 için referans)
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

        # 3. ChromaDB'ye parçalayarak (Chunking) ekle
        if self._chroma_available and self.collection:
            try:
                # Önce eski parçaları temizle (Update senaryosu)
                self.collection.delete(where={"parent_id": doc_id})

                # Metni parçala
                chunks = self._recursive_chunk_text(content)
                
                # Vektör verilerini hazırla
                ids = [f"{doc_id}_{i}" for i in range(len(chunks))]
                metadatas = [
                    {
                        "source": source,
                        "title": title,
                        "tags": ",".join(tags),
                        "parent_id": doc_id,
                        "chunk_index": i
                    } 
                    for i in range(len(chunks))
                ]

                if chunks:
                    self.collection.upsert(
                        ids=ids,
                        documents=chunks,
                        metadatas=metadatas
                    )
                    logger.info("ChromaDB: %s belgesi %d parçaya ayrılarak eklendi.", doc_id, len(chunks))
            except Exception as exc:
                logger.error("ChromaDB belge ekleme hatası: %s", exc)

        logger.info("RAG belge eklendi: [%s] %s (%d karakter)", doc_id, title, len(content))
        return doc_id

    async def add_document_from_url(self, url: str, title: str = "", tags: Optional[List[str]] = None) -> Tuple[bool, str]:
        """URL'den içerik çekerek belge ekle (Asenkron — event loop bloklanmaz)."""
        import httpx

        try:
            async with httpx.AsyncClient(
                timeout=15,
                follow_redirects=True,
                headers={"User-Agent": "Mozilla/5.0 (compatible; SidarBot/1.0)"},
            ) as client:
                resp = await client.get(url)
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

        # 2. ChromaDB'den sil (Tüm parçaları)
        if self._chroma_available and self.collection:
            try:
                # Parent ID'ye göre silme (Where filtresi)
                self.collection.delete(where={"parent_id": doc_id})
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

    def search(self, query: str, top_k: int = None) -> Tuple[bool, str]:
        """
        Sorguya göre en ilgili belgeleri bul.
        Öncelik: ChromaDB (Vektör) -> BM25 -> Keyword
        top_k verilmezse __init__'teki default_top_k kullanılır.
        """
        if top_k is None:
            top_k = self.default_top_k
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
        # Chunking nedeniyle top_k'yı biraz artıralım, aynı dokümanın farklı parçaları gelebilir
        results = self.collection.query(
            query_texts=[query],
            n_results=top_k * 2 
        )
        
        if not results["ids"] or not results["ids"][0]:
            return False, f"'{query}' için anlamsal sonuç bulunamadı."

        # Sonuçları işle
        found_docs = []
        seen_parents = set()
        
        # results["documents"][0] -> bulunan chunk içeriği
        # results["metadatas"][0] -> metadata
        for i, chunk_content in enumerate(results["documents"][0]):
            meta = results["metadatas"][0][i]
            parent_id = meta.get("parent_id")
            
            # Aynı dokümanın birden fazla parçası gelebilir, çeşitlilik için filtrele
            # (veya en alakalı parçayı göster)
            unique_key = parent_id
            if unique_key in seen_parents and len(seen_parents) >= top_k:
                continue
            
            seen_parents.add(unique_key)
            
            # Chunk içeriğini snippet olarak kullan
            found_docs.append({
                "id": parent_id,
                "title": meta.get("title", "?"),
                "source": meta.get("source", ""),
                "snippet": chunk_content, # Chunk'ın kendisi en iyi snippet'tir
                "score": 1.0 # Chroma sıralı döndürür
            })
            
            if len(found_docs) >= top_k:
                break
        
        return self._format_results_from_struct(found_docs, query, source_name="Vektör Arama (ChromaDB + Chunking)")

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
        
        # BM25 sonuçlarını yapıya çevir
        results = []
        for doc_id, score in ranked:
            doc_file = self.store_dir / f"{doc_id}.txt"
            content = doc_file.read_text(encoding="utf-8") if doc_file.exists() else ""
            meta = self._index.get(doc_id, {})
            snippet = self._extract_snippet(content, query)
            
            results.append({
                "id": doc_id,
                "title": meta.get("title", "?"),
                "source": meta.get("source", ""),
                "snippet": snippet,
                "score": score
            })

        return self._format_results_from_struct(results, query, source_name="BM25")

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
        
        results = []
        for doc_id, score in ranked:
            doc_file = self.store_dir / f"{doc_id}.txt"
            content = doc_file.read_text(encoding="utf-8") if doc_file.exists() else ""
            meta = self._index.get(doc_id, {})
            snippet = self._extract_snippet(content, query)
            
            results.append({
                "id": doc_id,
                "title": meta.get("title", "?"),
                "source": meta.get("source", ""),
                "snippet": snippet,
                "score": score
            })

        return self._format_results_from_struct(results, query, source_name="Kelime Eşleşmesi")

    def _format_results_from_struct(self, results: list, query: str, source_name: str) -> Tuple[bool, str]:
        """Ortak sonuç biçimlendirici."""
        if not results:
            return False, f"'{query}' için belge deposunda ilgili sonuç bulunamadı."

        lines = [f"[RAG Arama: {query}] (Motor: {source_name})", ""]
        for res in results:
            lines.append(f"**[{res['id']}] {res['title']}**")
            if res['source']:
                lines.append(f"  Kaynak: {res['source']}")
            
            # Snippet temizliği (çok uzun boşlukları al)
            snippet = res['snippet'].replace("\n", " ").strip()
            if len(snippet) > 400:
                snippet = snippet[:400] + "..."
            
            lines.append(f"  {snippet}")
            lines.append("")

        return True, "\n".join(lines)

    @staticmethod
    def _extract_snippet(content: str, query: str, window: int = 400) -> str:
        """Sorgudaki ilk anahtar kelimenin etrafındaki metni çıkar (BM25 ve Keyword için)."""
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
        if self._chroma_available: engines.append("ChromaDB (Chunking Destekli)")
        if self._bm25_available: engines.append("BM25")
        if not engines: engines.append("Anahtar Kelime")
        
        return f"RAG: {len(self._index)} belge | Motorlar: {', '.join(engines)}"
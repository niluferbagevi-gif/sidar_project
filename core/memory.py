"""
Sidar Project - Konuşma Belleği (Kalıcı)
Çoklu tur konuşma geçmişini yönetir ve diske kaydeder.
"""

import json
import time
import threading
import logging
from pathlib import Path
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)

class ConversationMemory:
    """
    Thread-safe ve kalıcı (persistent) konuşma belleği yöneticisi.
    Verileri JSON dosyasında saklar.
    """

    def __init__(self, file_path: Path, max_turns: int = 20) -> None:
        self.file_path = file_path
        self.max_turns = max_turns
        self._lock = threading.RLock()
        
        # Varsayılan değerler
        self._turns: List[Dict] = []
        self._last_file: Optional[str] = None
        
        # Başlangıçta belleği yükle
        self._load()

    # ─────────────────────────────────────────────
    #  PERSISTENCE (Kalıcılık)
    # ─────────────────────────────────────────────

    def _load(self) -> None:
        """Belleği diskten yükle."""
        if not self.file_path.exists():
            return

        try:
            with self._lock:
                data = json.loads(self.file_path.read_text(encoding="utf-8"))
                self._turns = data.get("turns", [])
                self._last_file = data.get("last_file")
                logger.info(f"Bellek yüklendi: {len(self._turns)} mesaj.")
        except Exception as exc:
            logger.error(f"Bellek yükleme hatası: {exc}")
            # Hata durumunda boş başlat
            self._turns = []
            self._last_file = None

    def _save(self) -> None:
        """Belleği diske kaydet."""
        try:
            data = {
                "last_file": self._last_file,
                "turns": self._turns
            }
            with self._lock:
                # Dizin yoksa oluştur
                self.file_path.parent.mkdir(parents=True, exist_ok=True)
                self.file_path.write_text(
                    json.dumps(data, ensure_ascii=False, indent=2),
                    encoding="utf-8"
                )
        except Exception as exc:
            logger.error(f"Bellek kaydetme hatası: {exc}")

    # ─────────────────────────────────────────────
    #  EKLEME & OKUMA
    # ─────────────────────────────────────────────

    def add(self, role: str, content: str) -> None:
        """Yeni bir mesaj turu ekle ve kaydet."""
        with self._lock:
            self._turns.append({
                "role": role,
                "content": content,
                "timestamp": time.time(),
            })
            # Pencere boyutunu koru
            if len(self._turns) > self.max_turns * 2:
                self._turns = self._turns[-(self.max_turns * 2):]
            
            self._save()

    def get_history(self, n_last: Optional[int] = None) -> List[Dict]:
        """Son n_last turu döndür."""
        with self._lock:
            turns = list(self._turns)
        return turns if n_last is None else turns[-n_last:]

    def get_messages_for_llm(self) -> List[Dict[str, str]]:
        """LLM API çağrısı için mesaj listesi döndür."""
        with self._lock:
            return [{"role": t["role"], "content": t["content"]} for t in self._turns]

    # ─────────────────────────────────────────────
    #  DOSYA TAKİBİ
    # ─────────────────────────────────────────────

    def set_last_file(self, path: str) -> None:
        with self._lock:
            self._last_file = path
            self._save()

    def get_last_file(self) -> Optional[str]:
        with self._lock:
            return self._last_file

    # ─────────────────────────────────────────────
    #  YARDIMCILAR
    # ─────────────────────────────────────────────

    def clear(self) -> None:
        """Belleği hem RAM'den hem diskten temizle."""
        with self._lock:
            self._turns.clear()
            self._last_file = None
            
            # Dosyayı da sıfırla veya sil
            if self.file_path.exists():
                try:
                    self.file_path.unlink()
                except OSError:
                    self._save() # Silinemezse boş kaydet

    def __len__(self) -> int:
        with self._lock:
            return len(self._turns)

    def __repr__(self) -> str:
        return f"<ConversationMemory turns={len(self._turns)} file={self.file_path.name}>"
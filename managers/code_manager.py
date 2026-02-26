"""
Sidar Project - Kod Yöneticisi
Dosya okuma, yazma, sözdizimi doğrulama ve kod analizi.
"""

import ast
import json
import logging
import os
import sys
import subprocess
import threading
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from .security import SecurityManager

logger = logging.getLogger(__name__)


class CodeManager:
    """
    PEP 8 uyumlu dosya işlemleri ve sözdizimi doğrulama.
    Thread-safe RLock ile korunur.
    """

    SUPPORTED_EXTENSIONS = {".py", ".js", ".ts", ".json", ".yaml", ".yml", ".md", ".txt", ".sh"}

    def __init__(self, security: SecurityManager, base_dir: Path) -> None:
        self.security = security
        self.base_dir = base_dir
        self._lock = threading.RLock()
        # Metrikler
        self._files_read = 0
        self._files_written = 0
        self._syntax_checks = 0
        self._audits_done = 0

    # ─────────────────────────────────────────────
    #  DOSYA OKUMA
    # ─────────────────────────────────────────────

    def read_file(self, path: str) -> Tuple[bool, str]:
        """
        Dosya içeriğini oku.

        Returns:
            (başarı, içerik_veya_hata_mesajı)
        """
        if not self.security.can_read():
            return False, "[OpenClaw] Okuma yetkisi yok."

        try:
            target = Path(path)
            if not target.exists():
                return False, f"Dosya bulunamadı: {path}"
            if target.is_dir():
                return False, f"Belirtilen yol bir dizin: {path}"

            with self._lock:
                content = target.read_text(encoding="utf-8", errors="replace")
                self._files_read += 1

            logger.debug("Dosya okundu: %s (%d karakter)", path, len(content))
            return True, content

        except PermissionError:
            return False, f"[OpenClaw] Erişim reddedildi: {path}"
        except Exception as exc:
            return False, f"Okuma hatası: {exc}"

    # ─────────────────────────────────────────────
    #  DOSYA YAZMA
    # ─────────────────────────────────────────────

    def write_file(self, path: str, content: str, validate: bool = True) -> Tuple[bool, str]:
        """
        Dosyaya içerik yaz (Tam üzerine yazma).

        Returns:
            (başarı, mesaj)
        """
        if not self.security.can_write(path):
            safe = str(self.security.get_safe_write_path(Path(path).name))
            return False, (
                f"[OpenClaw] Yazma yetkisi yok: {path}\n"
                f"  Güvenli alternatif: {safe}"
            )

        # Python dosyaları için sözdizimi kontrolü
        if validate and path.endswith(".py"):
            ok, msg = self.validate_python_syntax(content)
            if not ok:
                return False, f"Sözdizimi hatası, dosya kaydedilmedi:\n{msg}"

        try:
            target = Path(path)
            target.parent.mkdir(parents=True, exist_ok=True)

            with self._lock:
                target.write_text(content, encoding="utf-8")
                self._files_written += 1

            logger.info("Dosya yazıldı: %s", path)
            return True, f"Dosya başarıyla kaydedildi: {path}"

        except PermissionError:
            return False, f"[OpenClaw] Yazma erişimi reddedildi: {path}"
        except Exception as exc:
            return False, f"Yazma hatası: {exc}"

    # ─────────────────────────────────────────────
    #  AKILLI YAMA (PATCH)
    # ─────────────────────────────────────────────

    def patch_file(self, path: str, target_block: str, replacement_block: str) -> Tuple[bool, str]:
        """
        Dosyadaki belirli bir kod bloğunu yenisiyle değiştirir.
        """
        ok, content = self.read_file(path)
        if not ok:
            return False, content

        count = content.count(target_block)
        
        if count == 0:
            return False, (
                "⚠ Yama uygulanamadı: 'Hedef kod bloğu' dosyada bulunamadı.\n"
                "Lütfen boşluklara ve girintilere (indentation) dikkat ederek, "
                "dosyada var olan kodu birebir kopyaladığından emin ol."
            )
        
        if count > 1:
            return False, (
                f"⚠ Yama uygulanamadı: Hedef kod bloğu dosyada {count} kez geçiyor.\n"
                "Hangi bloğun değiştirileceği belirsiz. Lütfen daha fazla bağlam (context) ekle."
            )

        new_content = content.replace(target_block, replacement_block)
        return self.write_file(path, new_content, validate=True)

    # ─────────────────────────────────────────────
    #  GÜVENLİ KOD ÇALIŞTIRMA (REPL) - YENİ
    # ─────────────────────────────────────────────

    def execute_code(self, code: str) -> Tuple[bool, str]:
        """
        Kodu izole bir alt süreçte çalıştırır.
        
        Özellikler:
        - 10 saniye zaman aşımı (Timeout)
        - Geçici dosya üzerinde çalışma (/temp/repl_session.py)
        - Stdout ve Stderr yakalama
        """
        if not self.security.can_execute():
            return False, "[OpenClaw] Kod çalıştırma yetkisi yok (Restricted Mod)."

        try:
            # Geçici çalışma dizini ve dosya
            temp_dir = self.base_dir / "temp"
            temp_dir.mkdir(exist_ok=True)
            runner_path = temp_dir / "repl_session.py"
            
            # Kodu dosyaya yaz
            runner_path.write_text(code, encoding="utf-8")
            
            # Subprocess ile çalıştır
            # sys.executable: O anki Python yorumlayıcısını kullanır (Docker içindeyse onu)
            result = subprocess.run(
                [sys.executable, str(runner_path)],
                capture_output=True,
                text=True,
                timeout=10,  # 10 saniye sınır
                cwd=str(temp_dir)  # Çalışma dizini temp olsun
            )
            
            output = result.stdout + result.stderr
            if result.returncode == 0:
                final_out = output.strip() or "(Kod başarıyla çalıştı ancak çıktı üretmedi)"
                return True, f"REPL Çıktısı:\n{final_out}"
            else:
                return False, f"Çalışma Zamanı Hatası (Exit {result.returncode}):\n{output}"

        except subprocess.TimeoutExpired:
            return False, "⚠ Zaman aşımı! Kod 10 saniyeden uzun sürdü ve durduruldu."
        except Exception as exc:
            return False, f"Çalıştırma hatası: {exc}"

    # ─────────────────────────────────────────────
    #  DİZİN LİSTELEME
    # ─────────────────────────────────────────────

    def list_directory(self, path: str = ".") -> Tuple[bool, str]:
        """Dizin içeriğini listele."""
        try:
            target = Path(path).resolve()
            if not target.exists():
                return False, f"Dizin bulunamadı: {path}"
            if not target.is_dir():
                return False, f"Belirtilen yol bir dizin değil: {path}"

            items = sorted(target.iterdir(), key=lambda p: (p.is_file(), p.name.lower()))
            lines = [f"📁 {path}/"]
            for item in items:
                if item.is_dir():
                    lines.append(f"  📂 {item.name}/")
                else:
                    size_kb = item.stat().st_size / 1024
                    lines.append(f"  📄 {item.name}  ({size_kb:.1f} KB)")

            return True, "\n".join(lines)

        except Exception as exc:
            return False, f"Dizin listeleme hatası: {exc}"

    # ─────────────────────────────────────────────
    #  SÖZDİZİMİ DOĞRULAMA
    # ─────────────────────────────────────────────

    def validate_python_syntax(self, code: str) -> Tuple[bool, str]:
        """Python sözdizimini doğrula."""
        with self._lock:
            self._syntax_checks += 1
        try:
            ast.parse(code)
            return True, "Sözdizimi geçerli."
        except SyntaxError as exc:
            return False, f"Sözdizimi hatası — Satır {exc.lineno}: {exc.msg}"

    def validate_json(self, content: str) -> Tuple[bool, str]:
        """JSON sözdizimini doğrula."""
        try:
            json.loads(content)
            return True, "Geçerli JSON."
        except json.JSONDecodeError as exc:
            return False, f"JSON hatası — Satır {exc.lineno}: {exc.msg}"

    # ─────────────────────────────────────────────
    #  KOD DENETİMİ
    # ─────────────────────────────────────────────

    def audit_project(self, root: str = ".") -> str:
        with self._lock:
            self._audits_done += 1

        target = Path(root).resolve()
        py_files: List[Path] = list(target.rglob("*.py"))
        errors: List[str] = []
        ok_count = 0

        for fp in py_files:
            try:
                content = fp.read_text(encoding="utf-8", errors="replace")
                ok, msg = self.validate_python_syntax(content)
                if ok:
                    ok_count += 1
                else:
                    errors.append(f"  {fp.relative_to(target)}: {msg}")
            except Exception as exc:
                errors.append(f"  {fp}: Okunamadı — {exc}")

        report_lines = [
            f"[Sidar Denetim Raporu] — {root}",
            f"  Toplam Python dosyası : {len(py_files)}",
            f"  Geçerli             : {ok_count}",
            f"  Hatalı              : {len(errors)}",
        ]
        if errors:
            report_lines.append("\n  Hatalar:")
            report_lines.extend(errors)
        else:
            report_lines.append("  Tüm dosyalar sözdizimi açısından temiz. ✓")

        return "\n".join(report_lines)

    # ─────────────────────────────────────────────
    #  METRİKLER
    # ─────────────────────────────────────────────

    def get_metrics(self) -> Dict[str, int]:
        with self._lock:
            return {
                "files_read": self._files_read,
                "files_written": self._files_written,
                "syntax_checks": self._syntax_checks,
                "audits_done": self._audits_done,
            }

    def __repr__(self) -> str:
        m = self.get_metrics()
        return (
            f"<CodeManager reads={m['files_read']} "
            f"writes={m['files_written']} "
            f"checks={m['syntax_checks']}>"
        )
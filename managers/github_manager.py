"""
Sidar Project - GitHub Yöneticisi
Depo analizi, commit geçmişi ve uzak dosya okuma (Binary Korumalı).
"""

import logging
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


class GitHubManager:
    """
    GitHub API üzerinden depo analizi yapar.
    PyGithub kütüphanesi kullanır.
    """

    # Okunmasına izin verilen, metin tabanlı (text-based) güvenli dosya uzantıları
    SAFE_TEXT_EXTENSIONS = {
        ".py", ".txt", ".md", ".json", ".yaml", ".yml", ".ini", ".cfg", ".toml",
        ".csv", ".xml", ".html", ".css", ".js", ".ts", ".sh", ".bash", ".bat",
        ".sql", ".env", ".example", ".gitignore", ".dockerignore"
    }

    # Uzantısız ama güvenli olduğu bilinen dosyalar (küçük harf karşılaştırma)
    SAFE_EXTENSIONLESS = {
        "makefile", "dockerfile", "procfile", "vagrantfile",
        "rakefile", "brewfile", "jenkinsfile", "gemfile",
    }

    def __init__(self, token: str, repo_name: str = "") -> None:
        self.token = token
        self.repo_name = repo_name
        self._gh = None
        self._repo = None
        self._available = False
        self._init_client()

    # ─────────────────────────────────────────────
    #  BAŞLATMA
    # ─────────────────────────────────────────────

    def _init_client(self) -> None:
        if not self.token:
            logger.warning("GitHub token ayarlanmamış. GitHub özellikleri devre dışı.")
            return
        try:
            from github import Github  # type: ignore
            self._gh = Github(self.token)
            # Token doğrulama
            _ = self._gh.get_user().login
            self._available = True
            logger.info("GitHub bağlantısı kuruldu.")
            if self.repo_name:
                self._load_repo(self.repo_name)
        except ImportError:
            logger.error("'PyGithub' paketi kurulu değil. pip install PyGithub")
        except Exception as exc:
            logger.error("GitHub bağlantı hatası: %s", exc)

    def _load_repo(self, repo_name: str) -> bool:
        """Depo nesnesini yükle."""
        if not self._gh:
            return False
        try:
            self._repo = self._gh.get_repo(repo_name)
            self.repo_name = repo_name
            logger.info("Depo yüklendi: %s", repo_name)
            return True
        except Exception as exc:
            logger.error("Depo yükleme hatası (%s): %s", repo_name, exc)
            return False

    # ─────────────────────────────────────────────
    #  DEPO İŞLEMLERİ
    # ─────────────────────────────────────────────

    def set_repo(self, repo_name: str) -> Tuple[bool, str]:
        """Aktif depoyu değiştir."""
        if not self._available:
            return False, "GitHub bağlantısı yok."
        ok = self._load_repo(repo_name)
        if ok:
            return True, f"Depo değiştirildi: {repo_name}"
        return False, f"Depo bulunamadı veya erişim reddedildi: {repo_name}"

    def get_repo_info(self) -> Tuple[bool, str]:
        """Depo bilgilerini döndür."""
        if not self._repo:
            return False, "Aktif depo yok. Önce bir depo belirtin."
        try:
            r = self._repo
            return True, (
                f"[Depo Bilgisi] {r.full_name}\n"
                f"  Açıklama  : {r.description or 'Yok'}\n"
                f"  Dil       : {r.language or 'Bilinmiyor'}\n"
                f"  Yıldız    : {r.stargazers_count}\n"
                f"  Fork      : {r.forks_count}\n"
                f"  Açık PR   : {r.get_pulls(state='open').totalCount}\n"
                f"  Açık Issue: {r.get_issues(state='open').totalCount}\n"
                f"  Varsayılan branch: {r.default_branch}"
            )
        except Exception as exc:
            return False, f"Depo bilgisi alınamadı: {exc}"

    def list_commits(self, n: int = 10, branch: Optional[str] = None) -> Tuple[bool, str]:
        """Son n commit'i listele."""
        if not self._repo:
            return False, "Aktif depo yok."
        try:
            kwargs = {}
            if branch:
                kwargs["sha"] = branch
            commits = list(self._repo.get_commits(**kwargs)[:n])
            lines = [f"[Son {len(commits)} Commit — {self._repo.full_name}]"]
            for c in commits:
                sha = c.sha[:7]
                msg = c.commit.message.splitlines()[0][:72]
                author = c.commit.author.name
                date = c.commit.author.date.strftime("%Y-%m-%d %H:%M")
                lines.append(f"  {sha}  {date}  {author}  {msg}")
            return True, "\n".join(lines)
        except Exception as exc:
            return False, f"Commit listesi alınamadı: {exc}"

    def read_remote_file(self, file_path: str, ref: Optional[str] = None) -> Tuple[bool, str]:
        """Uzak depodaki bir dosyayı okur (Binary korumalı)."""
        if not self._repo:
            return False, "Aktif depo yok."
        try:
            kwargs = {}
            if ref:
                kwargs["ref"] = ref
            
            content_file = self._repo.get_contents(file_path, **kwargs)
            
            # Eğer dönen veri bir liste ise, bu bir dizindir
            if isinstance(content_file, list):
                lines = [f"[Dizin: {file_path}]"]
                for item in content_file:
                    icon = "📂" if item.type == "dir" else "📄"
                    lines.append(f"  {icon} {item.name}")
                return True, "\n".join(lines)
            
            # Eğer bu bir dosyaysa, içeriği UTF-8 mi yoksa Binary mi diye kontrol et
            file_name = content_file.name.lower()

            # Uzantıyı çıkar (varsa)
            extension = ""
            if "." in file_name:
                extension = "." + file_name.split(".")[-1]

            # Uzantısız dosyalar: yalnızca bilinen-güvenli adlar whitelist'te kabul edilir
            if not extension and file_name not in self.SAFE_EXTENSIONLESS:
                return False, (
                    f"⚠ Güvenlik: '{content_file.name}' uzantısız dosya whitelist'te değil. "
                    "Binary (ELF, PE vb.) içerebilir; okuma iptal edildi."
                )

            # Uzantılı dosyalar: yalnızca bilinen metin uzantıları kabul edilir
            if extension and extension not in self.SAFE_TEXT_EXTENSIONS:
                return False, (
                    f"⚠ Güvenlik/Hata Koruması: '{content_file.name}' dosyasının binary (ikili) "
                    "veya desteklenmeyen bir veri formatı (.png, .zip, vb.) olduğu varsayılarak "
                    "okuma işlemi iptal edildi. Yalnızca metin tabanlı dosyalar okunabilir."
                )

            # Güvenli olduğuna ikna olduysak, decode et
            decoded = content_file.decoded_content.decode("utf-8", errors="replace")
            return True, decoded
            
        except UnicodeDecodeError:
            # Yine de decode hatası alırsak (örneğin uzantısı .txt ama içi binary bozuk bir dosya)
             return False, f"⚠ Hata: '{file_path}' dosyası UTF-8 formatında okunamadı. Dosya binary (ikili veri) içeriyor olabilir."
        except Exception as exc:
            return False, f"Uzak dosya okunamadı ({file_path}): {exc}"

    def list_branches(self) -> Tuple[bool, str]:
        """Depo dallarını listele."""
        if not self._repo:
            return False, "Aktif depo yok."
        try:
            branches = list(self._repo.get_branches())
            lines = [f"[Branch Listesi — {self._repo.full_name}]"]
            for b in branches:
                prefix = "* " if b.name == self._repo.default_branch else "  "
                lines.append(f"{prefix}{b.name}")
            return True, "\n".join(lines)
        except Exception as exc:
            return False, f"Branch listesi alınamadı: {exc}"

    def search_code(self, query: str) -> Tuple[bool, str]:
        """Depoda kod araması yap."""
        if not self._gh or not self._repo:
            return False, "GitHub bağlantısı veya aktif depo yok."
        try:
            full_query = f"{query} repo:{self._repo.full_name}"
            results = list(self._gh.search_code(full_query)[:10])
            if not results:
                return True, f"'{query}' için sonuç bulunamadı."
            lines = [f"[Kod Arama: '{query}']"]
            for item in results:
                lines.append(f"  📄 {item.path}")
            return True, "\n".join(lines)
        except Exception as exc:
            return False, f"Kod arama hatası: {exc}"

    # ─────────────────────────────────────────────
    #  DURUM
    # ─────────────────────────────────────────────

    def is_available(self) -> bool:
        return self._available

    def status(self) -> str:
        if not self._available:
            return "GitHub: Bağlı değil (token eksik veya hatalı)"
        repo_info = f" | Depo: {self.repo_name}" if self.repo_name else " | Depo: ayarlanmamış"
        return f"GitHub: Bağlı{repo_info}"

    def __repr__(self) -> str:
        return (
            f"<GitHubManager available={self._available} "
            f"repo={self.repo_name or 'None'}>"
        )
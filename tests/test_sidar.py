"""
Sidar Project - Birim Testleri
pytest ile çalıştır: cd sidar_project && pytest tests/ -v
"""

import os
import sys
import textwrap
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest
import requests

# Proje kökünü yola ekle
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config import Config
from managers.security import SecurityManager, RESTRICTED, SANDBOX, FULL
from managers.code_manager import CodeManager
from managers.system_health import SystemHealthManager
from managers.web_search import WebSearchManager
from managers.package_info import PackageInfoManager
from core.memory import ConversationMemory
from core.rag import DocumentStore
from core.llm_client import LLMClient


# ─────────────────────────────────────────────
#  FIXTURES
# ─────────────────────────────────────────────

@pytest.fixture
def tmp_base(tmp_path):
    """Geçici proje kökü oluştur."""
    (tmp_path / "temp").mkdir()
    return tmp_path


@pytest.fixture
def security_sandbox(tmp_base):
    return SecurityManager("sandbox", tmp_base)


@pytest.fixture
def security_full(tmp_base):
    return SecurityManager("full", tmp_base)


@pytest.fixture
def security_restricted(tmp_base):
    return SecurityManager("restricted", tmp_base)


@pytest.fixture
def code_manager_sandbox(security_sandbox, tmp_base):
    return CodeManager(security_sandbox, tmp_base)


@pytest.fixture
def code_manager_full(security_full, tmp_base):
    return CodeManager(security_full, tmp_base)


# ─────────────────────────────────────────────
#  GÜVENLİK TESTLERİ
# ─────────────────────────────────────────────

class TestSecurityManager:
    def test_restricted_cannot_write(self, security_restricted):
        assert security_restricted.can_write("/tmp/test.py") is False

    def test_restricted_can_read(self, security_restricted):
        assert security_restricted.can_read() is True

    def test_restricted_cannot_execute(self, security_restricted):
        assert security_restricted.can_execute() is False

    def test_sandbox_can_write_to_temp(self, security_sandbox, tmp_base):
        safe_path = str(tmp_base / "temp" / "test.py")
        assert security_sandbox.can_write(safe_path) is True

    def test_sandbox_cannot_write_outside_temp(self, security_sandbox, tmp_base):
        outside = str(tmp_base / "outside.py")
        assert security_sandbox.can_write(outside) is False

    def test_sandbox_can_execute(self, security_sandbox):
        # sandbox seviyesi SANDBOX >= SANDBOX → True (yalnızca /temp üzerinde çalışır)
        assert security_sandbox.can_execute() is True

    def test_full_can_write_anywhere(self, security_full, tmp_base):
        assert security_full.can_write(str(tmp_base / "anything.py")) is True

    def test_full_can_execute(self, security_full):
        assert security_full.can_execute() is True

    def test_level_values(self, tmp_base):
        assert SecurityManager("restricted", tmp_base).level == RESTRICTED
        assert SecurityManager("sandbox", tmp_base).level == SANDBOX
        assert SecurityManager("full", tmp_base).level == FULL


# ─────────────────────────────────────────────
#  KOD YÖNETİCİSİ TESTLERİ
# ─────────────────────────────────────────────

class TestCodeManager:
    def test_read_existing_file(self, code_manager_sandbox, tmp_base):
        test_file = tmp_base / "hello.py"
        test_file.write_text("print('hello')", encoding="utf-8")
        ok, content = code_manager_sandbox.read_file(str(test_file))
        assert ok is True
        assert "print" in content

    def test_read_nonexistent_file(self, code_manager_sandbox):
        ok, msg = code_manager_sandbox.read_file("/nonexistent/path/file.py")
        assert ok is False
        assert "bulunamadı" in msg.lower()

    def test_write_to_temp_sandbox(self, code_manager_sandbox, tmp_base):
        path = str(tmp_base / "temp" / "test_output.py")
        ok, msg = code_manager_sandbox.write_file(path, "x = 1\n", validate=True)
        assert ok is True
        assert Path(path).exists()

    def test_write_rejected_outside_temp_sandbox(self, code_manager_sandbox, tmp_base):
        path = str(tmp_base / "not_allowed.py")
        ok, msg = code_manager_sandbox.write_file(path, "x = 1\n")
        assert ok is False
        assert "openclaw" in msg.lower() or "yetki" in msg.lower()

    def test_valid_python_syntax(self, code_manager_sandbox):
        ok, msg = code_manager_sandbox.validate_python_syntax("def foo(): return 42")
        assert ok is True

    def test_invalid_python_syntax(self, code_manager_sandbox):
        ok, msg = code_manager_sandbox.validate_python_syntax("def foo( return 42")
        assert ok is False
        assert "sözdizimi" in msg.lower() or "syntax" in msg.lower()

    def test_valid_json(self, code_manager_sandbox):
        ok, msg = code_manager_sandbox.validate_json('{"key": "value"}')
        assert ok is True

    def test_invalid_json(self, code_manager_sandbox):
        ok, msg = code_manager_sandbox.validate_json('{key: value}')
        assert ok is False

    def test_list_directory(self, code_manager_sandbox, tmp_base):
        ok, listing = code_manager_sandbox.list_directory(str(tmp_base))
        assert ok is True
        assert "temp" in listing

    def test_audit_project(self, code_manager_full, tmp_base):
        # Geçerli python dosyası oluştur
        (tmp_base / "sample.py").write_text("x = 1\n", encoding="utf-8")
        report = code_manager_full.audit_project(str(tmp_base))
        assert "Denetim Raporu" in report

    def test_metrics_increment(self, code_manager_sandbox, tmp_base):
        test_file = tmp_base / "metric_test.py"
        test_file.write_text("pass\n", encoding="utf-8")
        code_manager_sandbox.read_file(str(test_file))
        code_manager_sandbox.validate_python_syntax("x = 1")
        m = code_manager_sandbox.get_metrics()
        assert m["files_read"] >= 1
        assert m["syntax_checks"] >= 1

    def test_no_write_on_syntax_error(self, code_manager_full, tmp_base):
        path = str(tmp_base / "bad.py")
        ok, msg = code_manager_full.write_file(path, "def bad( pass", validate=True)
        assert ok is False
        assert not Path(path).exists()


# ─────────────────────────────────────────────
#  SİSTEM SAĞLIĞI TESTLERİ
# ─────────────────────────────────────────────

class TestSystemHealthManager:
    def test_full_report_runs(self):
        health = SystemHealthManager(use_gpu=False)
        report = health.full_report()
        assert "Sistem Sağlık Raporu" in report

    def test_gpu_optimize_no_crash(self):
        health = SystemHealthManager(use_gpu=False)
        result = health.optimize_gpu_memory()
        assert "GC" in result or "temizlendi" in result.lower()

    def test_memory_info(self):
        health = SystemHealthManager(use_gpu=False)
        mem = health.get_memory_info()
        # psutil kuruluysa dolu, değilse boş dict
        if mem:
            assert "total_gb" in mem
            assert mem["total_gb"] > 0


# ─────────────────────────────────────────────
#  BELLEK TESTLERİ
# ─────────────────────────────────────────────

class TestConversationMemory:
    def test_add_and_retrieve(self, tmp_path):
        mem = ConversationMemory(file_path=tmp_path / "mem.json", max_turns=5)
        mem.add("user", "Merhaba")
        mem.add("assistant", "Selam!")
        history = mem.get_history()
        assert len(history) == 2

    def test_max_turns_window(self, tmp_path):
        mem = ConversationMemory(file_path=tmp_path / "mem.json", max_turns=2)
        for i in range(10):
            mem.add("user", f"mesaj {i}")
            mem.add("assistant", f"yanıt {i}")
        # max_turns * 2 = 4 mesaj tutulmalı
        assert len(mem) <= 4

    def test_last_file_tracking(self, tmp_path):
        mem = ConversationMemory(file_path=tmp_path / "mem.json")
        assert mem.get_last_file() is None
        mem.set_last_file("/path/to/file.py")
        assert mem.get_last_file() == "/path/to/file.py"

    def test_clear(self, tmp_path):
        mem = ConversationMemory(file_path=tmp_path / "mem.json")
        mem.add("user", "test")
        mem.set_last_file("test.py")
        mem.clear()
        assert len(mem) == 0
        assert mem.get_last_file() is None

    def test_messages_for_llm(self, tmp_path):
        mem = ConversationMemory(file_path=tmp_path / "mem.json")
        mem.add("user", "soru")
        mem.add("assistant", "yanıt")
        msgs = mem.get_messages_for_llm()
        assert msgs[0]["role"] == "user"
        assert msgs[1]["role"] == "assistant"
        assert "timestamp" not in msgs[0]

    def test_needs_summarization_false(self, tmp_path):
        mem = ConversationMemory(file_path=tmp_path / "mem.json", max_turns=10)
        mem.add("user", "merhaba")
        mem.add("assistant", "selam")
        assert mem.needs_summarization() is False

    def test_needs_summarization_true(self, tmp_path):
        mem = ConversationMemory(file_path=tmp_path / "mem.json", max_turns=2)
        for i in range(4):
            mem.add("user", f"mesaj {i}")
            mem.add("assistant", f"yanıt {i}")
        # 8 mesaj ≥ eşik (2 * 2 * 0.8 = 3.2 → 3)
        assert mem.needs_summarization() is True

    def test_apply_summary(self, tmp_path):
        mem = ConversationMemory(file_path=tmp_path / "mem.json", max_turns=10)
        for i in range(5):
            mem.add("user", f"mesaj {i}")
            mem.add("assistant", f"yanıt {i}")
        mem.apply_summary("Test özet içeriği.")
        # Özetleme sonrası yalnızca 2 mesaj kalır
        assert len(mem) == 2
        history = mem.get_history()
        assert history[1]["role"] == "assistant"
        assert "Test özet içeriği." in history[1]["content"]


# ─────────────────────────────────────────────
#  BELGE DEPOSU TESTLERİ (RAG)
# ─────────────────────────────────────────────

class TestDocumentStore:
    def test_search_empty_store(self, tmp_path):
        store = DocumentStore(tmp_path / "rag")
        ok, msg = store.search("python test")
        assert ok is False
        assert "boş" in msg.lower()

    def test_list_documents_empty(self, tmp_path):
        store = DocumentStore(tmp_path / "rag")
        result = store.list_documents()
        assert "boş" in result.lower() or "belge yok" in result.lower()

    def test_delete_nonexistent(self, tmp_path):
        store = DocumentStore(tmp_path / "rag")
        result = store.delete_document("nonexistent_id_xyz")
        assert "bulunamadı" in result.lower()

    def test_default_top_k(self, tmp_path):
        store = DocumentStore(tmp_path / "rag", top_k=7)
        assert store.default_top_k == 7

    def test_status_empty(self, tmp_path):
        store = DocumentStore(tmp_path / "rag")
        status = store.status()
        assert "0" in status or "boş" in status.lower()


# ─────────────────────────────────────────────
#  WEB ARAMA TESTLERİ
# ─────────────────────────────────────────────

class TestWebSearchManager:
    def test_unavailable_returns_error(self):
        with patch.object(WebSearchManager, "_check_availability", return_value=False):
            ws = WebSearchManager()
        ok, msg = ws.search("test")
        assert ok is False
        assert "kurulu değil" in msg or "mevcut değil" in msg

    def test_config_values_applied(self):
        cfg = MagicMock()
        cfg.WEB_SEARCH_MAX_RESULTS = 10
        cfg.WEB_FETCH_TIMEOUT = 30
        cfg.WEB_FETCH_MAX_CHARS = 8000
        with patch.object(WebSearchManager, "_check_availability", return_value=True):
            ws = WebSearchManager(config=cfg)
        assert ws.MAX_RESULTS == 10
        assert ws.FETCH_TIMEOUT == 30
        assert ws.FETCH_MAX_CHARS == 8000

    def test_fetch_url_timeout(self):
        with patch("requests.get", side_effect=requests.exceptions.Timeout()):
            ws = WebSearchManager()
            ok, msg = ws.fetch_url("http://example.com")
        assert ok is False
        assert "zaman aşımı" in msg.lower()

    def test_fetch_url_connection_error(self):
        with patch("requests.get", side_effect=requests.exceptions.ConnectionError()):
            ws = WebSearchManager()
            ok, msg = ws.fetch_url("http://example.com")
        assert ok is False
        assert "bağlantı" in msg.lower()

    def test_status_available(self):
        with patch.object(WebSearchManager, "_check_availability", return_value=True):
            ws = WebSearchManager()
        assert ws.is_available() is True
        assert "Aktif" in ws.status()

    def test_status_unavailable(self):
        with patch.object(WebSearchManager, "_check_availability", return_value=False):
            ws = WebSearchManager()
        assert ws.is_available() is False
        assert "Aktif" not in ws.status()


# ─────────────────────────────────────────────
#  PAKET BİLGİ TESTLERİ
# ─────────────────────────────────────────────

class TestPackageInfoManager:
    def _mock_pypi_response(self):
        mock = MagicMock()
        mock.raise_for_status = MagicMock()
        mock.json.return_value = {
            "info": {
                "name": "requests",
                "version": "2.31.0",
                "author": "Kenneth Reitz",
                "license": "Apache 2.0",
                "summary": "Python HTTP library",
                "home_page": "https://requests.readthedocs.io",
                "requires_dist": ["certifi", "charset-normalizer"],
            },
            "releases": {"2.31.0": [{}], "2.30.0": [{}]},
        }
        return mock

    def test_pypi_info_success(self):
        with patch("requests.get", return_value=self._mock_pypi_response()):
            pkg = PackageInfoManager()
            ok, msg = pkg.pypi_info("requests")
        assert ok is True
        assert "requests" in msg.lower()
        assert "2.31.0" in msg

    def test_pypi_info_not_found(self):
        # status_code=404 → package_info.py 404 erken dönüş dalını test eder
        mock = MagicMock()
        mock.status_code = 404
        mock.raise_for_status = MagicMock()
        with patch("requests.get", return_value=mock):
            pkg = PackageInfoManager()
            ok, msg = pkg.pypi_info("nonexistent_pkg_xyz_123")
        assert ok is False
        assert "bulunamadı" in msg

    def test_npm_info_success(self):
        mock = MagicMock()
        mock.raise_for_status = MagicMock()
        mock.json.return_value = {
            "name": "react",
            "version": "18.2.0",
            "description": "A JavaScript library for building UIs.",
            "license": "MIT",
            "homepage": "https://reactjs.org/",
            "dist-tags": {"latest": "18.2.0"},
        }
        with patch("requests.get", return_value=mock):
            pkg = PackageInfoManager()
            ok, msg = pkg.npm_info("react")
        assert ok is True
        assert "react" in msg.lower()

    def test_config_timeout_applied(self):
        cfg = MagicMock()
        cfg.PACKAGE_INFO_TIMEOUT = 30
        pkg = PackageInfoManager(config=cfg)
        assert pkg.TIMEOUT == 30


# ─────────────────────────────────────────────
#  LLM İSTEMCİSİ TESTLERİ
# ─────────────────────────────────────────────

class TestLLMClient:
    def test_provider_stored(self):
        cfg = Config()
        client = LLMClient("ollama", cfg)
        assert client.provider == "ollama"

    def test_unknown_provider_raises(self):
        cfg = Config()
        client = LLMClient("unknown_provider", cfg)
        with pytest.raises(ValueError, match="Bilinmeyen"):
            client.chat(messages=[{"role": "user", "content": "test"}])

    def test_ollama_connection_error_non_stream(self):
        cfg = Config()
        client = LLMClient("ollama", cfg)
        with patch("requests.post", side_effect=requests.exceptions.ConnectionError()):
            result = client.chat(
                messages=[{"role": "user", "content": "test"}],
                stream=False,
            )
        assert "HATA" in result

    def test_ollama_connection_error_stream(self):
        cfg = Config()
        client = LLMClient("ollama", cfg)
        with patch("requests.post", side_effect=requests.exceptions.ConnectionError()):
            result = list(client.chat(
                messages=[{"role": "user", "content": "test"}],
                stream=True,
            ))
        assert any("HATA" in chunk for chunk in result)

    def test_gemini_missing_api_key(self):
        cfg = Config()
        cfg.GEMINI_API_KEY = ""
        client = LLMClient("gemini", cfg)
        result = client.chat(
            messages=[{"role": "user", "content": "test"}],
            stream=False,
        )
        assert "HATA" in result

    def test_is_ollama_available_false(self):
        cfg = Config()
        client = LLMClient("ollama", cfg)
        with patch("requests.get", side_effect=requests.exceptions.ConnectionError()):
            assert client.is_ollama_available() is False
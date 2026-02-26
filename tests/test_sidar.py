"""
Sidar Project - Temel Test ve Entegrasyon Suiti
Çalıştırmak için kök dizinde: pytest tests/
"""

import asyncio
import os
from pathlib import Path

import pytest
from pydantic import ValidationError

from config import Config
from agent.sidar_agent import SidarAgent, ToolCall
from managers.web_search import WebSearchManager
from core.rag import DocumentStore


@pytest.fixture
def test_config(tmp_path):
    """Her test için izole edilmiş geçici bir yapılandırma oluşturur."""
    cfg = Config()
    cfg.BASE_DIR = tmp_path
    cfg.TEMP_DIR = tmp_path / "temp"
    cfg.DATA_DIR = tmp_path / "data"
    cfg.RAG_DIR = tmp_path / "rag"
    cfg.MEMORY_FILE = cfg.DATA_DIR / "memory.json"
    
    cfg.TEMP_DIR.mkdir()
    cfg.DATA_DIR.mkdir()
    cfg.RAG_DIR.mkdir()
    
    # Testleri hızlandırmak için API'leri devre dışı bırak
    cfg.TAVILY_API_KEY = ""
    cfg.GOOGLE_SEARCH_API_KEY = ""
    cfg.SEARCH_ENGINE = "auto"
    
    return cfg


@pytest.fixture
def agent(test_config):
    """Testler için SidarAgent nesnesi üretir."""
    return SidarAgent(cfg=test_config)


# ─────────────────────────────────────────────
# 1. TEMEL YÖNETİCİ TESTLERİ
# ─────────────────────────────────────────────

def test_code_manager_read_write(agent):
    """CodeManager: Dosya yazma ve okuma yetkisini test eder."""
    test_file = agent.cfg.TEMP_DIR / "test_hello.py"
    
    # Yazma
    ok, msg = agent.code.write_file(str(test_file), "print('Hello')", validate=False)
    assert ok is True
    assert test_file.exists()

    # Okuma
    ok, content = agent.code.read_file(str(test_file))
    assert ok is True
    assert "print('Hello')" in content


def test_code_manager_validation(agent):
    """CodeManager: Python sözdizimi doğrulamasını test eder."""
    # Bozuk kod
    ok, msg = agent.code.validate_python_syntax("def broken_func() print('hi')")
    assert ok is False
    assert "Sözdizimi hatası" in msg

    # Geçerli kod
    ok, msg = agent.code.validate_python_syntax("def clean_func():\n    pass")
    assert ok is True


# ─────────────────────────────────────────────
# 2. YAPISAL ÇIKTI (PYDANTIC) TESTLERİ
# ─────────────────────────────────────────────

def test_toolcall_pydantic_validation():
    """Pydantic şemasının doğru JSON'ları kabul edip hatalıları reddettiğini test eder."""
    
    # Başarılı JSON
    valid_json = '{"thought": "Webde arama yapmalıyım", "tool": "web_search", "argument": "python fastapi"}'
    parsed = ToolCall.model_validate_json(valid_json)
    assert parsed.tool == "web_search"
    assert parsed.argument == "python fastapi"
    
    # Hatalı/Eksik JSON (tool alanı eksik)
    invalid_json = '{"thought": "düşünüyorum", "argument": "sadece argüman"}'
    with pytest.raises(ValidationError):
         ToolCall.model_validate_json(invalid_json)


# ─────────────────────────────────────────────
# 3. ASENKRON WEB ARAMA (FALLBACK) TESTİ
# ─────────────────────────────────────────────

@pytest.mark.asyncio
async def test_web_search_fallback(test_config):
    """WebSearchManager'ın API anahtarı yokken otomatik olarak düşüş yaşadığını test eder."""
    web = WebSearchManager(test_config)
    
    # Tavily ve Google key bilerek boş bırakıldı, DuckDuckGo veya uyarı dönmeli
    assert web.tavily_key == ""
    assert web.google_key == ""
    
    status = web.status()
    # DDg kuruluysa DuckDuckGo yazmalı, değilse motor yok uyarısı vermeli
    assert "DuckDuckGo" in status or "motor yok" in status.lower()


# ─────────────────────────────────────────────
# 4. RAG VE VEKTÖR BELLEK TESTLERİ
# ─────────────────────────────────────────────

def test_rag_document_chunking(test_config):
    """DocumentStore'un büyük metinleri chunking mantığıyla böldüğünü test eder."""
    docs = DocumentStore(test_config.RAG_DIR)
    
    # Uzun ve yapısal bir metin oluşturalım
    long_text = "Metin baslangici.\n\n"
    for i in range(50):
        long_text += f"def func_{i}():\n    return {i}\n\n"
        
    doc_id = docs.add_document(title="Test Kodu", content=long_text, source="test_source")
    
    assert doc_id is not None
    # Index'e tam boyutla eklenmiş olmalı
    assert docs._index[doc_id]["size"] == len(long_text)
    
    # Metin parçalanıp kaydedildiyse, get_document ile tamamını geri okuyabilmeliyiz
    ok, retrieved = docs.get_document(doc_id)
    assert ok is True
    assert "func_49()" in retrieved


# ─────────────────────────────────────────────
# 5. AJAN BAŞLATMA TESTİ
# ─────────────────────────────────────────────

@pytest.mark.asyncio
async def test_agent_initialization(agent):
    """Ajanın ve alt modüllerinin başarıyla ayağa kalktığını test eder."""
    status_report = agent.status()
    
    assert agent.VERSION is not None
    assert agent.cfg.AI_PROVIDER in ("ollama", "gemini")
    assert "Bellek" in status_report
    assert "Güvenlik" in agent._build_context()




# """
# Sidar Project - Birim ve Entegrasyon Testleri (Güncel Async + Pydantic Sürümü)
# pytest ile çalıştır: cd sidar_project && pytest tests/ -v
# """

# import os
# import sys
# import asyncio
# from pathlib import Path
# from unittest.mock import patch, AsyncMock, MagicMock

# import pytest
# import httpx
# from pydantic import ValidationError

# # Proje kökünü yola ekle
# sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# from config import Config
# from managers.security import SecurityManager, RESTRICTED, SANDBOX, FULL
# from managers.code_manager import CodeManager
# from managers.system_health import SystemHealthManager
# from managers.web_search import WebSearchManager
# from managers.package_info import PackageInfoManager
# from core.memory import ConversationMemory
# from core.rag import DocumentStore
# from core.llm_client import LLMClient
# from agent.sidar_agent import SidarAgent, ToolCall


# # ─────────────────────────────────────────────
# #  FIXTURES
# # ─────────────────────────────────────────────

# @pytest.fixture
# def tmp_base(tmp_path):
#     """Geçici proje kökü oluştur."""
#     (tmp_path / "temp").mkdir()
#     (tmp_path / "data").mkdir()
#     (tmp_path / "rag").mkdir()
#     return tmp_path

# @pytest.fixture
# def test_config(tmp_base):
#     cfg = Config()
#     cfg.BASE_DIR = tmp_base
#     cfg.TEMP_DIR = tmp_base / "temp"
#     cfg.DATA_DIR = tmp_base / "data"
#     cfg.RAG_DIR = tmp_base / "rag"
#     cfg.MEMORY_FILE = cfg.DATA_DIR / "memory.json"
#     cfg.TAVILY_API_KEY = ""
#     cfg.GOOGLE_SEARCH_API_KEY = ""
#     cfg.SEARCH_ENGINE = "auto"
#     return cfg

# @pytest.fixture
# def security_sandbox(tmp_base):
#     return SecurityManager("sandbox", tmp_base)

# @pytest.fixture
# def code_manager_sandbox(security_sandbox, tmp_base):
#     return CodeManager(security_sandbox, tmp_base)


# # ─────────────────────────────────────────────
# #  1. YENİ YAPISAL ÇIKTI (PYDANTIC) TESTLERİ
# # ─────────────────────────────────────────────

# def test_toolcall_pydantic_validation():
#     """Pydantic şemasının doğru JSON'ları kabul edip hatalıları reddettiğini test eder."""
#     # Başarılı JSON
#     valid_json = '{"thought": "Webde arama yapmalıyım", "tool": "web_search", "argument": "python fastapi"}'
#     parsed = ToolCall.model_validate_json(valid_json)
#     assert parsed.tool == "web_search"
#     assert parsed.argument == "python fastapi"
    
#     # Hatalı/Eksik JSON (tool alanı eksik)
#     invalid_json = '{"thought": "düşünüyorum", "argument": "sadece argüman"}'
#     with pytest.raises(ValidationError):
#          ToolCall.model_validate_json(invalid_json)


# # ─────────────────────────────────────────────
# #  2. GÜVENLİK VE KOD YÖNETİCİSİ TESTLERİ
# # ─────────────────────────────────────────────

# class TestSecurityAndCode:
#     def test_sandbox_can_write_to_temp(self, security_sandbox, tmp_base):
#         safe_path = str(tmp_base / "temp" / "test.py")
#         assert security_sandbox.can_write(safe_path) is True

#     def test_sandbox_cannot_write_outside_temp(self, security_sandbox, tmp_base):
#         outside = str(tmp_base / "outside.py")
#         assert security_sandbox.can_write(outside) is False

#     def test_read_existing_file(self, code_manager_sandbox, tmp_base):
#         test_file = tmp_base / "hello.py"
#         test_file.write_text("print('hello')", encoding="utf-8")
#         ok, content = code_manager_sandbox.read_file(str(test_file))
#         assert ok is True
#         assert "print" in content

#     def test_valid_python_syntax(self, code_manager_sandbox):
#         ok, msg = code_manager_sandbox.validate_python_syntax("def foo(): return 42")
#         assert ok is True

#     def test_invalid_python_syntax(self, code_manager_sandbox):
#         ok, msg = code_manager_sandbox.validate_python_syntax("def foo( return 42")
#         assert ok is False


# # ─────────────────────────────────────────────
# #  3. BELLEK VE RAG (CHUNKING) TESTLERİ
# # ─────────────────────────────────────────────

# class TestMemoryAndRAG:
#     def test_memory_add_and_summarize(self, tmp_path):
#         mem = ConversationMemory(file_path=tmp_path / "mem.json", max_turns=2)
#         for i in range(4):
#             mem.add("user", f"mesaj {i}")
#             mem.add("assistant", f"yanıt {i}")
#         assert mem.needs_summarization() is True
        
#         mem.apply_summary("Test özet içeriği.")
#         assert len(mem) == 2
#         history = mem.get_history()
#         assert "Test özet içeriği." in history[1]["content"]

#     def test_rag_document_chunking(self, test_config):
#         docs = DocumentStore(test_config.RAG_DIR)
#         long_text = "Metin baslangici.\n\n"
#         for i in range(50):
#             long_text += f"def func_{i}():\n    return {i}\n\n"
            
#         doc_id = docs.add_document(title="Test Kodu", content=long_text, source="test_source")
#         assert doc_id is not None
#         assert docs._index[doc_id]["size"] == len(long_text)
        
#         ok, retrieved = docs.get_document(doc_id)
#         assert ok is True
#         assert "func_49()" in retrieved


# # ─────────────────────────────────────────────
# #  4. ASENKRON ARAMA VE PAKET BİLGİ TESTLERİ
# # ─────────────────────────────────────────────

# @pytest.mark.asyncio
# class TestAsyncManagers:
#     async def test_web_search_fallback(self, test_config):
#         web = WebSearchManager(test_config)
#         assert web.tavily_key == ""
#         assert web.google_key == ""
#         status = web.status()
#         assert "DuckDuckGo" in status or "motor yok" in status.lower()

#     @patch("httpx.AsyncClient.get", new_callable=AsyncMock)
#     async def test_pypi_info_success(self, mock_get):
#         mock_resp = MagicMock()
#         mock_resp.status_code = 200
#         mock_resp.json.return_value = {
#             "info": {"name": "requests", "version": "2.31.0"},
#             "releases": {"2.31.0": []}
#         }
#         mock_resp.raise_for_status = MagicMock()
#         mock_get.return_value = mock_resp

#         pkg = PackageInfoManager()
#         ok, msg = await pkg.pypi_info("requests")
#         assert ok is True
#         assert "requests" in msg.lower()
#         assert "2.31.0" in msg

#     @patch("httpx.AsyncClient.post", new_callable=AsyncMock)
#     async def test_ollama_client_async(self, mock_post):
#         mock_resp = MagicMock()
#         mock_resp.json.return_value = {"message": {"content": "Test yanıtı"}}
#         mock_resp.raise_for_status = MagicMock()
#         mock_post.return_value = mock_resp

#         cfg = Config()
#         client = LLMClient("ollama", cfg)
#         result = await client.chat([{"role": "user", "content": "selam"}], stream=False)
#         assert result == "Test yanıtı"







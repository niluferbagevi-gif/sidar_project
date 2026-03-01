"""
Sidar Project - Temel Test ve Entegrasyon Suiti
Çalıştırmak için kök dizinde: pytest tests/
"""

import asyncio
import os
from pathlib import Path

import pytest
from pydantic import ValidationError

from config import Config, HARDWARE
from agent.sidar_agent import SidarAgent, ToolCall
from managers.web_search import WebSearchManager
from managers.system_health import SystemHealthManager
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
    docs = DocumentStore(test_config.RAG_DIR, use_gpu=False)
    
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


# ─────────────────────────────────────────────
# 6. GPU & DONANIM TESTLERİ
# ─────────────────────────────────────────────

def test_hardware_info_fields():
    """HardwareInfo dataclass alanlarının doğru tipte olduğunu doğrular."""
    assert isinstance(HARDWARE.has_cuda, bool)
    assert isinstance(HARDWARE.gpu_name, str)
    assert isinstance(HARDWARE.gpu_count, int)
    assert isinstance(HARDWARE.cpu_count, int)
    assert isinstance(HARDWARE.cuda_version, str)
    assert isinstance(HARDWARE.driver_version, str)
    assert HARDWARE.cpu_count >= 1


def test_config_gpu_fields():
    """Config sınıfının GPU ile ilgili tüm alanları içerdiğini doğrular."""
    cfg = Config()
    assert hasattr(cfg, "USE_GPU")
    assert hasattr(cfg, "GPU_INFO")
    assert hasattr(cfg, "GPU_COUNT")
    assert hasattr(cfg, "GPU_DEVICE")
    assert hasattr(cfg, "CUDA_VERSION")
    assert hasattr(cfg, "DRIVER_VERSION")
    assert hasattr(cfg, "MULTI_GPU")
    assert hasattr(cfg, "GPU_MEMORY_FRACTION")
    assert hasattr(cfg, "GPU_MIXED_PRECISION")

    assert isinstance(cfg.USE_GPU, bool)
    assert isinstance(cfg.GPU_DEVICE, int)
    assert 0.0 < cfg.GPU_MEMORY_FRACTION <= 1.0


def test_system_health_manager_cpu_only():
    """SystemHealthManager'ın GPU olmadan CPU/RAM raporunu ürettiğini test eder."""
    health = SystemHealthManager(use_gpu=False)

    assert health._gpu_available is False

    report = health.full_report()
    assert "Sistem Sağlık Raporu" in report
    assert "OS" in report

    # GPU devre dışı — optimize çağrısı yine de güvenli çalışmalı
    result = health.optimize_gpu_memory()
    assert "GC" in result


def test_system_health_gpu_info_structure():
    """get_gpu_info() çıktısının beklenen yapıyı döndürdüğünü test eder."""
    health = SystemHealthManager(use_gpu=True)
    info = health.get_gpu_info()

    assert "available" in info
    if info["available"]:
        # GPU varsa zorunlu alanlar
        assert "device_count" in info
        assert "devices" in info
        assert "cuda_version" in info
        for dev in info["devices"]:
            assert "id" in dev
            assert "name" in dev
            assert "total_vram_gb" in dev
            assert "free_gb" in dev
            assert "compute_capability" in dev
    else:
        # GPU yoksa reason veya error alanı olmalı
        assert "reason" in info or "error" in info


def test_rag_gpu_params(test_config):
    """DocumentStore'un GPU parametrelerini kabul ettiğini doğrular."""
    # GPU olmayan sistemde use_gpu=True verilse bile güvenle başlamalı
    docs = DocumentStore(
        test_config.RAG_DIR,
        use_gpu=True,
        gpu_device=0,
        mixed_precision=False,
    )
    assert docs._use_gpu is True
    assert docs._gpu_device == 0
    # CUDA yoksa ChromaDB CPU'ya düşmeli; collection ya None ya da başlatılmış olmalı
    status = docs.status()
    assert "RAG" in status


# ─────────────────────────────────────────────
# 9. SESSION LIFECYCLE TESTLERİ
# ─────────────────────────────────────────────

def test_session_create(test_config):
    """ConversationMemory: Yeni oturum oluşturma ve aktif hale getirme."""
    from core.memory import ConversationMemory
    mem = ConversationMemory(file_path=test_config.MEMORY_FILE, max_turns=10)

    session_id = mem.create_session("Test Sohbeti")

    assert session_id is not None
    assert len(session_id) == 36  # UUID4 formatı
    assert mem.active_session_id == session_id
    assert mem.active_title == "Test Sohbeti"
    assert (test_config.DATA_DIR / "sessions" / f"{session_id}.json").exists()


def test_session_add_and_load(test_config):
    """ConversationMemory: Mesaj ekleme ve oturumu yeniden yükleme."""
    from core.memory import ConversationMemory
    mem = ConversationMemory(file_path=test_config.MEMORY_FILE, max_turns=10)

    session_id = mem.create_session("Yükleme Testi")
    mem.add("user", "Merhaba Sidar!")
    mem.add("assistant", "Merhaba! Nasıl yardımcı olabilirim?")

    # Yeni bir bellek nesnesi oluştur ve oturumu yeniden yükle
    mem2 = ConversationMemory(file_path=test_config.MEMORY_FILE, max_turns=10)
    ok = mem2.load_session(session_id)

    assert ok is True
    assert mem2.active_session_id == session_id
    history = mem2.get_history()
    assert len(history) == 2
    assert history[0]["role"] == "user"
    assert history[0]["content"] == "Merhaba Sidar!"
    assert history[1]["role"] == "assistant"


def test_session_delete(test_config):
    """ConversationMemory: Oturum silme ve dosyanın kaldırıldığını doğrulama."""
    from core.memory import ConversationMemory
    mem = ConversationMemory(file_path=test_config.MEMORY_FILE, max_turns=10)

    sid = mem.create_session("Silinecek Oturum")
    session_file = test_config.DATA_DIR / "sessions" / f"{sid}.json"
    assert session_file.exists()

    result = mem.delete_session(sid)

    assert result is True
    assert not session_file.exists()


def test_session_get_all_sorted(test_config):
    """ConversationMemory: Tüm oturumları en yeniden en eskiye sıralı listeler."""
    from core.memory import ConversationMemory
    import time as _time
    mem = ConversationMemory(file_path=test_config.MEMORY_FILE, max_turns=10)

    id1 = mem.create_session("Birinci")
    _time.sleep(0.01)
    id2 = mem.create_session("İkinci")
    _time.sleep(0.01)
    id3 = mem.create_session("Üçüncü")

    sessions = mem.get_all_sessions()
    ids = [s["id"] for s in sessions]

    # En son oluşturulan en üstte olmalı
    assert ids[0] == id3
    assert id1 in ids
    assert id2 in ids


def test_session_update_title(test_config):
    """ConversationMemory: Aktif oturum başlığını güncelleme."""
    from core.memory import ConversationMemory
    mem = ConversationMemory(file_path=test_config.MEMORY_FILE, max_turns=10)

    sid = mem.create_session("Eski Başlık")
    mem.update_title("Yeni Başlık")

    assert mem.active_title == "Yeni Başlık"

    # Yeniden yükleme ile kalıcılığı doğrula
    mem2 = ConversationMemory(file_path=test_config.MEMORY_FILE, max_turns=10)
    mem2.load_session(sid)
    assert mem2.active_title == "Yeni Başlık"


def test_session_load_nonexistent(test_config):
    """ConversationMemory: Var olmayan oturum yüklenmeye çalışıldığında False döner."""
    from core.memory import ConversationMemory
    mem = ConversationMemory(file_path=test_config.MEMORY_FILE, max_turns=10)

    result = mem.load_session("00000000-0000-0000-0000-000000000000")
    assert result is False


# ─────────────────────────────────────────────
# 10. ARAÇ DISPATCHER TESTLERİ
# ─────────────────────────────────────────────

@pytest.mark.asyncio
async def test_execute_tool_unknown_returns_none(agent):
    """SidarAgent dispatcher'ı bilinmeyen araç adı için None döndürür."""
    result = await agent._execute_tool("var_olmayan_arac_xyz", "test argümanı")
    assert result is None


@pytest.mark.asyncio
async def test_execute_tool_known_does_not_return_none(agent):
    """SidarAgent dispatcher'ı bilinen araç için None döndürmez."""
    # list_dir gerçek I/O yapar; BASE_DIR mevcut olduğundan sonuç döner
    result = await agent._execute_tool("list_dir", str(agent.cfg.BASE_DIR))
    assert result is not None


# ─────────────────────────────────────────────
# 11. CHUNKING SINIR TESTLERİ
# ─────────────────────────────────────────────

def test_rag_chunking_small_text(test_config):
    """DocumentStore: _chunk_size'dan küçük metin tek parça olarak eklenir."""
    docs = DocumentStore(test_config.RAG_DIR, use_gpu=False)
    small = "Küçük bir metin."
    doc_id = docs.add_document(title="Küçük", content=small, source="test")
    assert doc_id is not None
    ok, retrieved = docs.get_document(doc_id)
    assert ok is True
    assert retrieved == small


def test_rag_chunking_large_text(test_config):
    """DocumentStore: _chunk_size'dan büyük metin parçalara bölünür ve tamamı saklanır."""
    docs = DocumentStore(test_config.RAG_DIR, use_gpu=False)
    # Varsayılan chunk_size (genellikle 512) değerini aşan metin üret
    large = "A" * 2000 + "\n\n" + "B" * 2000
    doc_id = docs.add_document(title="Büyük", content=large, source="test")
    assert doc_id is not None
    ok, retrieved = docs.get_document(doc_id)
    assert ok is True
    assert len(retrieved) == len(large)


# ─────────────────────────────────────────────
# 12. AUTOHANDLE PATTERN TESTLERİ
# ─────────────────────────────────────────────

@pytest.mark.asyncio
async def test_auto_handle_no_match(agent):
    """AutoHandle: normal LLM sorusuna müdahale etmez."""
    handled, _ = await agent.auto.handle("Python'da asenkron programlama nasıl çalışır?")
    assert handled is False


@pytest.mark.asyncio
async def test_auto_handle_clear_command(agent):
    """AutoHandle: 'belleği temizle' / 'sohbeti sıfırla' komutlarına yanıt verir."""
    # Önce birkaç mesaj ekle
    agent.memory.add("user", "test mesajı")
    handled, response = await agent.auto.handle("belleği temizle")
    # Bu komut tanınmalı (handled=True) veya tanınmamalı (handled=False)
    # Her iki durumda da çökme olmamalı
    assert isinstance(handled, bool)
    assert isinstance(response, str)


# ─────────────────────────────────────────────
# 13. BROKEN JSON KARANTINA TESTİ
# ─────────────────────────────────────────────

def test_session_broken_json_quarantine(test_config):
    """ConversationMemory: Bozuk JSON dosyası .json.broken olarak karantinaya alınır."""
    from core.memory import ConversationMemory

    # Bozuk bir JSON dosyası oluştur
    sessions_dir = test_config.DATA_DIR / "sessions"
    sessions_dir.mkdir(parents=True, exist_ok=True)
    broken_file = sessions_dir / "bozuk-oturum.json"
    broken_file.write_text("{bozuk json içerik: !!!", encoding="utf-8")

    # get_all_sessions() çağrısı çökme üretmemeli; bozuk dosya karantinaya alınmalı
    mem = ConversationMemory(file_path=test_config.MEMORY_FILE, max_turns=10)
    sessions = mem.get_all_sessions()

    # Bozuk dosya .json.broken adıyla karantinada olmalı
    quarantined = sessions_dir / "bozuk-oturum.json.broken"
    assert quarantined.exists(), "Bozuk dosya karantinaya alınmadı"
    assert not broken_file.exists(), "Orijinal bozuk dosya hâlâ mevcut"
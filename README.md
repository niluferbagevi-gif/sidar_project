# SİDAR — Yazılım Mühendisi AI Asistanı

> **v2.6.1** — ReAct mimarisi üzerine kurulu, Türkçe dilli, tam async yazılım mühendisi AI projesi.

```
 ╔══════════════════════════════════════════════╗
 ║  ███████╗██╗██████╗  █████╗ ██████╗          ║
 ║  ██╔════╝██║██╔══██╗██╔══██╗██╔══██╗         ║
 ║  ███████╗██║██║  ██║███████║██████╔╝         ║
 ║  ╚════██║██║██║  ██║██╔══██║██╔══██╗         ║
 ║  ███████║██║██████╔╝██║  ██║██║  ██║         ║
 ║  ╚══════╝╚═╝╚═════╝ ╚═╝  ╚═╝╚═╝  ╚═╝         ║
 ║  Yazılım Mimarı & Baş Mühendis AI  v2.6.1  ║
 ╚══════════════════════════════════════════════╝
```

---

## Proje Hakkında

**Sidar**, kod yönetimi, sistem izleme, GitHub entegrasyonu, web araştırması ve güvenli dosya işlemleri konularında uzmanlaşmış bir AI asistanıdır. ReAct (Reason + Act) döngüsü ile çalışır; 25 araç üzerinden LLM destekli kararlar alır.

### Karakter Profili

| Özellik | Değer |
|---------|-------|
| Ad | SİDAR |
| Rol | Yazılım Mimarı & Baş Mühendis |
| Kişilik | Analitik, disiplinli, geek ruhu |
| İletişim | Minimal ve öz; gereksiz söz yok |
| Karar verme | Veri tabanlı, duygusal değil |
| Birincil Model | `qwen2.5-coder:7b` (Ollama, yerel) |
| Yedek Model | Google Gemini 2.0 Flash (bulut) |

---

## Özellikler

### Kod Yönetimi (CodeManager)
- PEP 8 uyumlu Python dosyası okuma/yazma
- Yazılımdan önce otomatik sözdizimi doğrulama (AST)
- JSON doğrulama
- Dosya yamalama (`patch_file` — sadece değişen satırlar)
- Dizin listeleme ve proje denetimi (`audit`)
- **Docker REPL Sandbox**: `python:3.11-alpine` içinde ağ/RAM/CPU kısıtlı izole kod çalıştırma (10 sn timeout)
- Metrik takibi (okunan/yazılan/doğrulanan)

### OpenClaw Güvenlik Sistemi (SecurityManager)

| Seviye | Okuma | Yazma | Kod Çalıştırma | Terminal (Shell) |
|--------|-------|-------|----------------|-----------------|
| `restricted` | ✓ | ✗ | ✗ | ✗ |
| `sandbox` | ✓ | Yalnızca `/temp` | ✓ | ✗ |
| `full` | ✓ | Her yer | ✓ | ✓ |

### Çoklu Oturum Bellek Yönetimi (ConversationMemory)
- UUID tabanlı, `data/sessions/*.json` şeklinde ayrı dosyalarda saklanan çoklu sohbet oturumları
- Thread-safe, JSON tabanlı kalıcı depolama
- Kayan pencere (varsayılan: 20 tur = 40 mesaj)
- **Otomatik Özetleme**: Pencere %80 dolduğunda LLM ile özetleme tetiklenir
- En son güncellenen oturum başlangıçta otomatik yükleniyor
- `create_session()`, `load_session()`, `delete_session()`, `update_title()` API'si

### ReAct Döngüsü (SidarAgent)
- **AutoHandle**: Örüntü tabanlı hızlı komut eşleme (LLM gerektirmez)
- **ReAct**: `Düşün → Araç çağır → Gözlemle` döngüsü (max 10 adım)
- **Pydantic v2 Doğrulama**: JSON ayrıştırma hatası alındığında modele hata detayı + beklenen format geri beslenir
- **Araç Görselleştirme**: Her tool çağrısı SSE eventi olarak istemciye iletilir; web UI'da badge olarak gösterilir
- Streaming yanıt (daktilo efekti)

### GPU Hızlandırma (v2.6.0+)
- PyTorch CUDA 12.1 desteği (RTX / Ampere serisi)
- FP16 mixed precision embedding (`GPU_MIXED_PRECISION=true`)
- VRAM fraksiyonu kontrolü (`GPU_MEMORY_FRACTION`)
- Çoklu GPU desteği (`MULTI_GPU=true`)
- WSL2 NVIDIA sürücü desteği (pynvml + nvidia-smi fallback)

### GitHub Entegrasyonu (GitHubManager)
- Depo bilgisi ve istatistikleri
- Son commit listesi
- Uzak dosya okuma (`github_read`)
- Branch listeleme ve kod arama
- Çalışma zamanında aktif depo değiştirme (`/set-repo`)

### Web & Araştırma (WebSearchManager)
- **Tavily** (öncelikli), **Google Custom Search**, **DuckDuckGo** (sırasıyla denenir)
- URL içerik çekme — HTML temizleme dahil (`fetch_url`)
- Kütüphane dokümantasyon araması (`search_docs`)
- Stack Overflow araması (`search_stackoverflow`)

### Paket Bilgi Sistemi (PackageInfoManager)
- PyPI paket bilgisi ve sürüm karşılaştırma (`pypi`, `pypi_compare`)
- npm paket bilgisi (`npm`)
- GitHub Releases listesi ve en güncel sürüm (`gh_releases`, `gh_latest`)

### Hibrit RAG Belge Deposu (DocumentStore)
- ChromaDB vektör araması (semantik) + GPU embedding desteği
- BM25 anahtar kelime araması
- **Recursive Character Chunking** (`\nclass ` → `\ndef ` → `\n\n` → `\n` → ` ` öncelik sırası)
- URL'den async belge ekleme (`httpx.AsyncClient`)
- `RAG_CHUNK_SIZE`, `RAG_CHUNK_OVERLAP`, `RAG_TOP_K` env değişkenleri ile yapılandırılabilir

### Sistem Sağlığı (SystemHealthManager)
- CPU ve RAM kullanım izleme (psutil)
- GPU/CUDA bilgisi ve VRAM takibi (pynvml)
- GPU bellek optimizasyonu (VRAM boşaltma + Python GC)

### Web Arayüzü (v2.6.1)
- **Çoklu oturum sidebar**: oturum geçişi, oluşturma, silme, arama/filtreleme
- **Dışa Aktarma**: Sohbet geçmişini MD veya JSON olarak indirme
- **ReAct Araç Görselleştirmesi**: Her tool çağrısı animasyonlu Türkçe badge (23 araç)
- **Mobil Uyum**: 768px altında hamburger menüsü + sidebar overlay
- Koyu/Açık tema (localStorage tabanlı)
- Klavye kısayolları (`Ctrl+K`, `Ctrl+L`, `Alt+T`, `Esc`)
- Streaming durdur butonu (AbortController)
- Kod bloğu kopyala butonu (hover ile görünür)
- Dosya ekleme (200 KB limit, metin/kod dosyaları)
- Dinamik model ismi gösterimi (`/status` üzerinden)
- Dal seçimi — gerçek `git checkout` ile backend'e bağlı
- Rate limiting (20 istek/dakika/IP, yalnızca `/chat`)

---

## Araç Listesi (25 Araç)

| Araç | Açıklama | Argüman |
|------|----------|---------|
| `list_dir` | Dizin listele | yol |
| `read_file` | Dosya oku | dosya_yolu |
| `write_file` | Dosya yaz (tamamını) | `path\|\|\|content` |
| `patch_file` | Dosya yamala (fark) | `path\|\|\|eski\|\|\|yeni` |
| `execute_code` | Python REPL (Docker sandbox) | python_kodu |
| `audit` | Proje denetimi | `.` |
| `health` | Sistem sağlık raporu | — |
| `gpu_optimize` | GPU bellek temizle | — |
| `github_commits` | Son commit listesi | sayı |
| `github_info` | Depo bilgisi | — |
| `github_read` | Uzak depodaki dosyayı oku | dosya_yolu |
| `web_search` | Tavily/Google/DDG ile ara | sorgu |
| `fetch_url` | URL içeriğini çek | url |
| `search_docs` | Kütüphane dokümanı ara | `lib konu` |
| `search_stackoverflow` | Stack Overflow araması | sorgu |
| `pypi` | PyPI paket bilgisi | paket_adı |
| `pypi_compare` | Sürüm karşılaştır | `paket\|sürüm` |
| `npm` | npm paket bilgisi | paket_adı |
| `gh_releases` | GitHub release listesi | `owner/repo` |
| `gh_latest` | En güncel release | `owner/repo` |
| `docs_search` | Belge deposunda ara | sorgu |
| `docs_add` | URL'den belge ekle | `başlık\|url` |
| `docs_list` | Belgeleri listele | — |
| `docs_delete` | Belge sil | doc_id |
| `final_answer` | Kullanıcıya yanıt ver | yanıt_metni |

---

## Kurulum

### Conda ile (Önerilen)

```bash
cd sidar_project
conda env create -f environment.yml
conda activate sidar-ai
```

### pip ile

```bash
pip install python-dotenv httpx psutil pynvml \
            google-generativeai PyGithub duckduckgo-search \
            rank-bm25 chromadb sentence-transformers \
            fastapi uvicorn pydantic docker \
            pytest pytest-asyncio pytest-cov
```

> **Not:** GPU desteği için `torch` ve `torchvision`'ı [PyTorch resmi sitesinden](https://pytorch.org/get-started/locally/) CUDA sürümünüze uygun wheel ile kurun.

### Çevre Değişkenleri

```bash
cp .env.example .env
# .env dosyasını düzenleyin
```

### Ollama Kurulumu

```bash
# https://ollama.ai
ollama pull qwen2.5-coder:7b
ollama serve
```

### Docker ile

```bash
# CPU modu
docker compose up --build sidar-web-cpu

# GPU modu (NVIDIA)
docker compose up --build sidar-web-gpu
```

---

## Kullanım

### 🌐 Web Arayüzü (Önerilen)

```bash
python web_server.py
```

Tarayıcıda açılır: **http://localhost:7860**

```bash
# Özel host/port
python web_server.py --host 0.0.0.0 --port 8080

# Erişim seviyesi ile
python web_server.py --level full

# Gemini sağlayıcısı ile
python web_server.py --provider gemini --port 7860
```

Web arayüzü özellikleri:
- Streaming chat (daktilo efekti) + araç görselleştirmesi
- Çoklu oturum yönetimi (sidebar)
- Sohbet geçmişini MD/JSON olarak dışa aktarma
- Markdown ve kod bloğu renklendirme (highlight.js)
- Sistem durumu paneli (model, versiyon, GitHub, RAG, GPU)
- Dal seçimi (gerçek git checkout)
- Mobil uyumlu hamburger menüsü

### 💻 Terminal (CLI) Modu

```bash
python main.py
```

### Tek Komut Modu

```bash
python main.py -c "Proje dizinini listele"
python main.py --status
python main.py --level full -c "Sistemi denetle"
python main.py --provider gemini -c "FastAPI nedir?"
```

### CLI Seçenekleri

```
-c, --command   Tek komut çalıştır ve çık
--status        Sistem durumunu göster
--level         Erişim seviyesi (restricted/sandbox/full)
--provider      AI sağlayıcısı (ollama/gemini)
--model         Ollama model adı
--log           Log seviyesi (DEBUG/INFO/WARNING)
```

### Dahili Komutlar (CLI)

```
.status     Sistem durumunu göster
.clear      Konuşma belleğini temizle
.audit      Proje denetimini çalıştır
.health     Sistem sağlık raporu
.gpu        GPU belleğini optimize et
.github     GitHub bağlantı durumu
.level      Mevcut erişim seviyesini göster
.web        Web arama durumu
.docs       Belge deposunu listele
.help       Yardım
.exit / .q  Çıkış
```

---

## Örnek Komutlar

```
# Dizin & Dosya
"Ana klasördeki dosyaları listele"
"config.py dosyasını oku ve özetle"
"main.py içindeki X satırını Y ile değiştir"

# Kod Geliştirme
"Fibonacci dizisi hesaplayan bir fonksiyon yaz ve test et"
"Bu kodu çalıştır: print(sum(range(100)))"

# Sistem
"Sistem sağlık raporu ver"
"GPU belleğini temizle"
"Projeyi denetle ve teknik rapor ver"

# GitHub
"Son 10 commit'i listele"
"GitHub'dan README.md dosyasını oku"

# Web Araştırma
"FastAPI'nin son sürümünü kontrol et"
"web'de ara: Python async best practices 2025"
"pypi: httpx"
"stackoverflow: Python type hints generic"

# Belgeler (RAG)
"belge ekle https://docs.python.org/3/library/asyncio.html"
"docs ara: asyncio event loop"
```

---

## Proje Yapısı

```
sidar_project/
├── agent/
│   ├── __init__.py
│   ├── definitions.py      # Sidar karakter profili ve sistem talimatı (25 araç)
│   ├── sidar_agent.py      # Ana ajan (ReAct, Pydantic v2, dispatcher, araç sentinel)
│   └── auto_handle.py      # Örüntü tabanlı hızlı komut eşleyici (async)
├── core/
│   ├── __init__.py
│   ├── memory.py           # Çoklu oturum (session) yönetimi — thread-safe JSON
│   ├── llm_client.py       # Ollama stream + Gemini async istemcisi
│   └── rag.py              # Hibrit RAG (ChromaDB + BM25), Recursive Chunking, GPU
├── managers/
│   ├── __init__.py
│   ├── code_manager.py     # Dosya operasyonları, AST, Docker REPL sandbox
│   ├── system_health.py    # CPU/RAM/GPU izleme (pynvml + nvidia-smi fallback)
│   ├── github_manager.py   # GitHub API entegrasyonu (binary koruma, branch)
│   ├── security.py         # OpenClaw 3 seviyeli erişim kontrol sistemi
│   ├── web_search.py       # Tavily + Google + DuckDuckGo (async, çoklu motor)
│   └── package_info.py     # PyPI + npm + GitHub Releases (async)
├── tests/
│   ├── __init__.py
│   └── test_sidar.py       # 11 test sınıfı (GPU + Chunking + Pydantic testleri dahil)
├── web_ui/
│   └── index.html          # Tam özellikli web arayüzü (SSE, session, export, mobil)
├── data/                   # Oturum JSON'ları ve RAG veritabanı (gitignore'da)
├── temp/                   # Sandbox modunda yazma dizini (gitignore'da)
├── logs/                   # Log dosyaları — RotatingFileHandler (gitignore'da)
├── config.py               # Merkezi yapılandırma + GPU tespiti + WSL2 desteği
├── main.py                 # CLI giriş noktası (async döngü, asyncio.run doğru kullanımı)
├── web_server.py           # FastAPI + SSE + Rate limiting + Session API + /set-branch
├── github_upload.py        # GitHub'a otomatik yükleme yardımcı betiği
├── Dockerfile              # CPU/GPU dual-mode build (python:3.11-slim)
├── docker-compose.yml      # 4 servis: CPU/GPU × CLI/Web
├── environment.yml         # Conda — PyTorch CUDA 12.1 wheel, pytest-asyncio
├── .env.example            # Açıklamalı ortam değişkeni şablonu
└── install_sidar.sh        # Ubuntu/WSL sıfırdan kurulum scripti
```

---

## Testleri Çalıştır

```bash
cd sidar_project
pytest tests/ -v
pytest tests/ -v --cov=. --cov-report=term-missing
```

**Test sınıfları (11 adet):**
- `TestCodeManager` — Dosya yazma/okuma ve AST doğrulama
- `TestToolCallPydantic` — Pydantic v2 ToolCall şeması doğrulama
- `TestWebSearchManager` — Motor seçimi ve durum (async)
- `TestDocumentStore` — Chunking + retrieve + GPU parametreleri
- `TestSidarAgentInit` — SidarAgent başlatma (async)
- `TestHardwareInfo` — HardwareInfo dataclass alanları
- `TestConfigGPU` — Config GPU alanları
- `TestSystemHealthManager` — CPU-only rapor
- `TestSystemHealthGPU` — GPU bilgi yapısı
- `TestRAGGPU` — DocumentStore GPU parametreleri
- `TestSecurityManager` — OpenClaw izin sistemi

---

## Yapılandırma (.env)

```env
# AI Sağlayıcı
AI_PROVIDER=ollama              # ollama | gemini
CODING_MODEL=qwen2.5-coder:7b
OLLAMA_URL=http://localhost:11434/api
GEMINI_API_KEY=                 # Gemini kullanılacaksa

# Güvenlik
ACCESS_LEVEL=sandbox            # restricted | sandbox | full

# GitHub
GITHUB_TOKEN=
GITHUB_REPO=kullanici/depo

# Web Sunucu
WEB_HOST=127.0.0.1
WEB_PORT=7860

# Bellek & Oturum
MAX_MEMORY_TURNS=20
MEMORY_FILE=data/sessions/memory.json

# Web Arama
TAVILY_API_KEY=                 # Tavily kullanılacaksa (öncelikli)
GOOGLE_API_KEY=                 # Google Custom Search kullanılacaksa
GOOGLE_CSE_ID=
WEB_SEARCH_MAX_RESULTS=5
WEB_FETCH_TIMEOUT=15
WEB_FETCH_MAX_CHARS=4000

# RAG
RAG_TOP_K=3
RAG_CHUNK_SIZE=1000
RAG_CHUNK_OVERLAP=200

# Paket Bilgi
PACKAGE_INFO_TIMEOUT=12

# GPU (opsiyonel)
USE_GPU=false                   # true: GPU embedding aktif
GPU_DEVICE=0
GPU_MEMORY_FRACTION=0.8
GPU_MIXED_PRECISION=false
MULTI_GPU=false
```

---

## Geliştirme

```bash
black .
flake8 . --max-line-length=100
mypy . --ignore-missing-imports
```

---

## Sürüm Geçmişi

| Versiyon | Önemli Değişiklikler |
|----------|----------------------|
| **v2.6.1** | Web UI düzeltmeleri: dışa aktarma, araç görselleştirme, mobil menü, dinamik model adı, gerçek git checkout, CancelledError düzeltmesi |
| **v2.6.0** | GPU hızlandırma, Docker REPL sandbox, çoklu oturum, Recursive Chunking, Pydantic v2, rate limiting, WSL2 desteği |
| **v2.5.0** | Async mimari (httpx, asyncio.Lock), dispatcher tablosu, pytest-asyncio |
| **v2.3.2** | İlk kararlı sürüm |

---

## Lisans

Bu proje LotusAI ekosisteminin bir parçasıdır.

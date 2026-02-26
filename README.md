# SİDAR — Yazılım Mühendisi AI Asistanı

> **v2.3.2** — LotusAI ekosisteminden ilham alınmış bağımsız yazılım mühendisi AI projesi.

```
 ╔══════════════════════════════════════════════╗
 ║  ███████╗██╗██████╗  █████╗ ██████╗          ║
 ║  ██╔════╝██║██╔══██╗██╔══██╗██╔══██╗         ║
 ║  ███████╗██║██║  ██║███████║██████╔╝         ║
 ║  ╚════██║██║██║  ██║██╔══██║██╔══██╗         ║
 ║  ███████║██║██████╔╝██║  ██║██║  ██║         ║
 ║  ╚══════╝╚═╝╚═════╝ ╚═╝  ╚═╝╚═╝  ╚═╝         ║
 ║  Yazılım Mimarı & Baş Mühendis AI  v2.3.2   ║
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
- REPL: Alt süreçte güvenli kod çalıştırma (`execute_code`, 10 sn timeout)
- Metrik takibi (okunan/yazılan/doğrulanan)

### OpenClaw Güvenlik Sistemi (SecurityManager)

| Seviye | Okuma | Yazma | Kod Çalıştırma | Terminal (Shell) |
|--------|-------|-------|----------------|-----------------|
| `restricted` | ✓ | ✗ | ✗ | ✗ |
| `sandbox` | ✓ | Yalnızca `/temp` | ✓ | ✗ |
| `full` | ✓ | Her yer | ✓ | ✓ |

### Akıllı Bellek Yönetimi (ConversationMemory)
- Thread-safe, JSON tabanlı kalıcı depolama
- Kayan pencere (varsayılan: 20 tur = 40 mesaj)
- **Otomatik Özetleme**: Pencere %80 dolduğunda LLM ile özetleme tetiklenir; eski mesajlar sıkıştırılır, kritik bağlam korunur
- Son işlenen dosya takibi

### ReAct Döngüsü (SidarAgent)
- **AutoHandle**: Örüntü tabanlı hızlı komut eşleme (LLM gerektirmez)
- **ReAct**: `Düşün → Araç çağır → Gözlemle` döngüsü (max 10 adım)
- **JSON Hata Geri Besleme**: Parse hatası alındığında modele hata detayı + beklenen format geri beslenir
- Streaming yanıt (daktilo efekti)
- Lock tasarımı: Bellek/auto-handle kısa kilitli; generator akışı lock dışında

### GitHub Entegrasyonu (GitHubManager)
- Depo bilgisi ve istatistikleri
- Son commit listesi
- Uzak dosya okuma (`github_read`)
- Branch listeleme ve kod arama

### Web & Araştırma (WebSearchManager)
- DuckDuckGo web araması (`web_search`)
- URL içerik çekme — HTML temizleme dahil (`fetch_url`)
- Kütüphane dokümantasyon araması (`search_docs`)
- Stack Overflow araması (`search_stackoverflow`)
- `.env` üzerinden yapılandırılabilir: `WEB_SEARCH_MAX_RESULTS`, `WEB_FETCH_TIMEOUT`, `WEB_FETCH_MAX_CHARS`

### Paket Bilgi Sistemi (PackageInfoManager)
- PyPI paket bilgisi ve sürüm karşılaştırma (`pypi`, `pypi_compare`)
- npm paket bilgisi (`npm`)
- GitHub Releases listesi ve en güncel sürüm (`gh_releases`, `gh_latest`)
- `.env` üzerinden yapılandırılabilir: `PACKAGE_INFO_TIMEOUT`

### Hibrit RAG Belge Deposu (DocumentStore)
- ChromaDB vektör araması (semantik)
- BM25 anahtar kelime araması
- Yedek: basit kelime eşleme
- URL'den belge ekleme, listeleme, silme
- `RAG_TOP_K` env değişkeni ile sonuç sayısı yapılandırılabilir

### Sistem Sağlığı (SystemHealthManager)
- CPU ve RAM kullanım izleme
- GPU/CUDA bilgisi ve VRAM takibi
- GPU bellek optimizasyonu (VRAM boşaltma + Python GC)

---

## Araç Listesi (25 Araç)

| Araç | Açıklama | Argüman |
|------|----------|---------|
| `list_dir` | Dizin listele | yol |
| `read_file` | Dosya oku | dosya_yolu |
| `write_file` | Dosya yaz (tamamını) | `path\|\|\|content` |
| `patch_file` | Dosya yamala (fark) | `path\|\|\|eski\|\|\|yeni` |
| `execute_code` | Python REPL çalıştır | python_kodu |
| `audit` | Proje denetimi | `.` |
| `health` | Sistem sağlık raporu | — |
| `gpu_optimize` | GPU bellek temizle | — |
| `github_commits` | Son commit listesi | sayı |
| `github_info` | Depo bilgisi | — |
| `github_read` | Uzak depodaki dosyayı oku | dosya_yolu |
| `web_search` | DuckDuckGo ile ara | sorgu |
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
pip install python-dotenv requests psutil GPUtil pynvml ollama \
            google-generativeai PyGithub duckduckgo-search \
            rank-bm25 chromadb sentence-transformers pytest pytest-cov
```

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
docker compose up --build
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
- Streaming chat (daktilo efekti)
- Markdown ve kod bloğu renklendirme
- Hızlı eylem butonları (8 hazır komut)
- ⚡ Durum paneli (canlı sistem bilgisi)
- Bellek temizleme

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

### Dahili Komutlar

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
"web'de ara: Python async best practices 2024"
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
│   ├── sidar_agent.py      # Ana ajan (ReAct, özetleme, JSON feedback, lock fix)
│   └── auto_handle.py      # Örüntü tabanlı hızlı komut eşleyici
├── core/
│   ├── __init__.py
│   ├── memory.py           # Thread-safe bellek + otomatik özetleme desteği
│   ├── llm_client.py       # Ollama / Gemini API istemcisi
│   └── rag.py              # Hibrit RAG (ChromaDB + BM25), top_k yapılandırılabilir
├── managers/
│   ├── __init__.py
│   ├── code_manager.py     # Dosya operasyonları, REPL, sözdizimi
│   ├── system_health.py    # CPU/RAM/GPU izleme
│   ├── github_manager.py   # GitHub API entegrasyonu
│   ├── security.py         # OpenClaw erişim kontrol sistemi
│   ├── web_search.py       # DuckDuckGo + URL fetch (Config bağlı)
│   └── package_info.py     # PyPI / npm / GitHub Releases (Config bağlı)
├── tests/
│   ├── __init__.py
│   └── test_sidar.py       # 8 test sınıfı, 50+ test (mock dahil)
├── web_ui/
│   └── index.html          # Chat arayüzü (dark theme, Markdown, SSE streaming)
├── data/                   # Bellek ve RAG veritabanı (gitignore'da)
├── temp/                   # Sandbox modunda yazma dizini (gitignore'da)
├── logs/                   # Log dosyaları (gitignore'da)
├── config.py               # Merkezi yapılandırma (env → Config sınıfı)
├── main.py                 # Giriş noktası & CLI
├── web_server.py           # FastAPI + SSE web arayüzü sunucusu
├── github_upload.py        # GitHub'a otomatik yükleme yardımcı betiği (bağımsız)
├── Dockerfile              # Docker imajı (python:3.11-slim, v2.3.2)
├── docker-compose.yml      # Docker Compose servisi
├── environment.yml         # Conda ortamı
└── .env.example            # Ortam değişkenleri şablonu
```

---

## Testleri Çalıştır

```bash
cd sidar_project
pytest tests/ -v
pytest tests/ -v --cov=. --cov-report=term-missing
```

**Test sınıfları:**
- `TestSecurityManager` — OpenClaw izin sistemi
- `TestCodeManager` — Dosya işlemleri ve sözdizimi
- `TestSystemHealthManager` — Donanım izleme
- `TestConversationMemory` — Bellek + özetleme (needs_summarization, apply_summary)
- `TestDocumentStore` — RAG boş durum ve yapılandırma
- `TestWebSearchManager` — Mock tabanlı web arama ve fetch
- `TestPackageInfoManager` — Mock tabanlı PyPI ve npm sorguları
- `TestLLMClient` — Sağlayıcı doğrulama ve hata yönetimi

---

## Yapılandırma (.env)

```env
# AI Sağlayıcı
AI_PROVIDER=ollama          # ollama | gemini
CODING_MODEL=qwen2.5-coder:7b
OLLAMA_URL=http://localhost:11434/api
GEMINI_API_KEY=             # Gemini kullanılacaksa

# Güvenlik
ACCESS_LEVEL=sandbox        # restricted | sandbox | full

# GitHub
GITHUB_TOKEN=
GITHUB_REPO=kullanici/depo

# Bellek
MAX_MEMORY_TURNS=20

# Web Arama
WEB_SEARCH_MAX_RESULTS=5
WEB_FETCH_TIMEOUT=15
WEB_FETCH_MAX_CHARS=4000

# RAG
RAG_TOP_K=3

# Paket Bilgi
PACKAGE_INFO_TIMEOUT=12
```

---

## Geliştirme

```bash
black .
flake8 . --max-line-length=100
mypy . --ignore-missing-imports
```

---

## Lisans

Bu proje LotusAI ekosisteminin bir parçasıdır.
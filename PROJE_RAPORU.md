# SİDAR PROJESİ — GÜNCEL DURUM RAPORU

> **Rapor Tarihi:** 2026-03-01
> **Analiz Türü:** Tam Kaynak Kodu ve Yapılandırma Denetimi (Satır Satır)
> **Toplam İncelenen Dosya:** 30 (Python 16, Yapılandırma 5, Belge 3, Web 1, Script 1, Diğer 4)
> **Toplam Python Satırı:** 4.631

---

## 1. PROJE GENEL BAKIŞ

**SİDAR** (Yazılım Mimarı & Baş Mühendis AI), ReAct (Reason + Act) döngüsü tabanlı, yerel LLM ve bulut AI desteğine sahip, tam asenkron bir yazılım mühendisi yapay zeka asistanıdır.

| Alan | Değer |
|------|-------|
| **Güncel Sürüm** | v2.6.0 |
| **Python Gereksinimi** | 3.11+ |
| **AI Sağlayıcılar** | Ollama (yerel) / Google Gemini (bulut) |
| **Varsayılan Model** | qwen2.5-coder:7b (kod) / gemma2:9b (metin) |
| **Arayüzler** | CLI (terminal) + Web UI (FastAPI + SSE) |
| **Erişim Sistemi** | OpenClaw (3-seviye: restricted / sandbox / full) |
| **Araç Sayısı** | 24 araç (dispatch tablosu ile) |

---

## 2. DİZİN YAPISI (TAM)

```
/home/user/sidar_project/
│
├── .env.example              # Çevre değişkenleri şablonu (113 satır)
├── .gitignore                # Git yoksay kuralları (42 satır)
├── .note                     # WSL2/Conda uyumluluk notu (243 satır)
├── Dockerfile                # Docker build — CPU/GPU dual image (87 satır)
├── docker-compose.yml        # 4 servis tanımı (168 satır)
├── environment.yml           # Conda ortam tanımı (80 satır)
├── install_sidar.sh          # Otomatik sistem kurulum betiği (132 satır)
├── README.md                 # Kullanıcı kılavuzu
├── PROJE_RAPORU.md           # ← Bu dosya
│
├── main.py                   # CLI giriş noktası (228 satır)
├── config.py                 # Merkezi yapılandırma + donanım tespiti (415 satır)
├── web_server.py             # FastAPI + SSE web sunucusu (290 satır)
├── github_upload.py          # Otomatik GitHub push/pull betiği (174 satır)
│
├── agent/
│   ├── __init__.py
│   ├── sidar_agent.py        # ReAct döngüsü + 24 araç handler (474 satır)
│   ├── auto_handle.py        # Regex tabanlı hızlı komut eşleştirici (368 satır)
│   └── definitions.py        # Sistem prompt + araç tanımları (105 satır)
│
├── core/
│   ├── __init__.py
│   ├── llm_client.py         # Async LLM istemcisi (Ollama + Gemini) (255 satır)
│   ├── memory.py             # Kalıcı, oturum tabanlı bellek yöneticisi (240 satır)
│   └── rag.py                # ChromaDB + BM25 hibrit RAG sistemi (611 satır)
│
├── managers/
│   ├── __init__.py
│   ├── code_manager.py       # Dosya I/O + Docker REPL sandbox (353 satır)
│   ├── github_manager.py     # GitHub API entegrasyonu (207 satır)
│   ├── package_info.py       # PyPI + npm + GitHub Releases (268 satır)
│   ├── security.py           # OpenClaw erişim kontrol sistemi (99 satır)
│   ├── system_health.py      # CPU/RAM/GPU izleme ve optimizasyon (293 satır)
│   └── web_search.py         # Çoklu motor async web arama (251 satır)
│
├── tests/
│   ├── __init__.py
│   └── test_sidar.py         # Birim + entegrasyon test paketi (238 satır)
│
└── web_ui/
    └── index.html            # Karanlık/aydınlık tema SSE chat arayüzü
```

---

## 3. MODÜL DETAY ANALİZİ

### 3.1 `config.py` — Merkezi Yapılandırma (415 satır)

**Amaç:** Tüm sistem ayarlarını tek noktadan yönetir; modül yüklendiğinde donanım tespiti yapar ve loglama altyapısını kurar.

**`HardwareInfo` dataclass** (satır 103–111):
- `has_cuda: bool`, `gpu_name: str`, `gpu_count: int`, `cpu_count: int`, `cuda_version: str`, `driver_version: str`

**`_is_wsl2()` fonksiyonu** (satır 114–119):
- `/proc/sys/kernel/osrelease` dosyasını okuyarak WSL2 ortamını tespit eder.

**`check_hardware()` fonksiyonu** (satır 122–187):
- PyTorch kuruluysa CUDA tespiti yapar.
- WSL2 ortamında özel uyarılar üretir.
- `GPU_MEMORY_FRACTION` (.env) ile VRAM fraksiyonunu anında uygular.
- `pynvml` varsa sürücü sürümünü okur.
- Modül yükleme anında `HARDWARE = check_hardware()` ile bir kez çalışır.

**`Config` sınıfı** (satır 198–406) — 50+ sınıf özelliği:

| Grup | Önemli Özellikler |
|------|------------------|
| AI Sağlayıcı | `AI_PROVIDER`, `GEMINI_API_KEY`, `GEMINI_MODEL`, `OLLAMA_URL`, `OLLAMA_TIMEOUT`, `CODING_MODEL`, `TEXT_MODEL` |
| Erişim | `ACCESS_LEVEL` (restricted/sandbox/full) |
| GitHub | `GITHUB_TOKEN`, `GITHUB_REPO` |
| GPU | `USE_GPU`, `GPU_INFO`, `GPU_COUNT`, `GPU_DEVICE`, `CUDA_VERSION`, `DRIVER_VERSION`, `MULTI_GPU`, `GPU_MEMORY_FRACTION`, `GPU_MIXED_PRECISION` |
| Uygulama | `MAX_MEMORY_TURNS=20`, `LOG_LEVEL`, `MAX_REACT_STEPS=10`, `REACT_TIMEOUT=60` |
| Web Arama | `SEARCH_ENGINE`, `TAVILY_API_KEY`, `GOOGLE_SEARCH_API_KEY`, `GOOGLE_SEARCH_CX`, `WEB_SEARCH_MAX_RESULTS=5`, `WEB_FETCH_TIMEOUT=15` |
| RAG | `RAG_DIR`, `RAG_TOP_K=3`, `RAG_CHUNK_SIZE=1000`, `RAG_CHUNK_OVERLAP=200` |
| Web UI | `WEB_HOST=0.0.0.0`, `WEB_PORT=7860` |

**Classmethod'lar:**
- `initialize_directories()` — temp, logs, data dizinlerini oluşturur.
- `set_provider_mode(mode)` — Çalışma zamanında AI sağlayıcıyı değiştirir.
- `validate_critical_settings()` — Gemini/Ollama bağlantısını doğrular; Ollama için senkron `requests.get()` kullanır.
- `get_system_info()` → `Dict` — Sistem özeti döndürür.
- `print_config_summary()` — Konsola yapılandırma tablosu yazdırır.

---

### 3.2 `main.py` — CLI Giriş Noktası (228 satır)

**Amaç:** Komut satırı argümanlarını işler, ASCII banner'ı gösterir ve interaktif döngüyü yönetir.

**`BANNER`** (satır 42–52): ASCII art, v2.6.0 bilgisi.

**`HELP_TEXT`** (satır 54–76): Tüm CLI komutları — `.status`, `.clear`, `.audit`, `.health`, `.gpu`, `.github`, `.level`, `.web`, `.docs`, `.exit`, serbest metin örnekleri.

**`_setup_logging(level)`** (satır 29–35): Kök logger seviyesini günceller.

**`_interactive_loop_async(agent)` — async** (satır 83–167):
- Banner + durum bilgisi çıktısı.
- `asyncio.to_thread(input, ...)` ile senkron `input()` event loop'u bloke etmeden çalıştırılır.
- Dahili komutları ayrıştırır.
- `async for chunk in agent.respond(user_input)` ile streaming yanıt alır.

**`interactive_loop(agent)`** (satır 170–171): Tek `asyncio.run()` çağrısı — oturum boyunca tek event loop.

**`main()`** (satır 178–225): argparse — `-c/--command`, `--status`, `--level`, `--provider`, `--model`, `--log`.

---

### 3.3 `agent/sidar_agent.py` — Ana Ajan (474 satır)

**Amaç:** ReAct döngüsünü, tüm alt sistem yöneticilerini ve araç dispatch mekanizmasını barındırır.

**`ToolCall` Pydantic modeli** (satır 33–37):
```python
class ToolCall(BaseModel):
    thought: str       # LLM'in akıl yürütmesi
    tool: str          # Çağrılacak aracın adı
    argument: str = "" # Araç argümanı
```

**`SidarAgent` sınıfı** (satır 40–474):
- `VERSION = "2.6.0"`
- `__init__`: 9 alt sistem başlatılır (`SecurityManager`, `CodeManager`, `SystemHealthManager`, `GitHubManager`, `ConversationMemory`, `LLMClient`, `WebSearchManager`, `PackageInfoManager`, `DocumentStore`, `AutoHandle`).
- `_lock = None` — İlk `respond()` çağrısında olay döngüsü içinde oluşturulur.

**`respond(user_input)` → AsyncIterator[str]** (satır 95–127):
1. `asyncio.Lock` oluşturur (ilk çağrıda).
2. Mesajı belleğe ekler.
3. `AutoHandle.handle()` ile hızlı eşleşme dener.
4. Eşleşme yoksa bellek eşiğini kontrol eder; gerekiyorsa `_summarize_memory()` çağırır.
5. `_react_loop()` ile LLM döngüsüne girer.

**`_react_loop(user_input)` → AsyncIterator[str]** (satır 133–223):
1. LLM'i `stream=True` ile çağırır; tüm yanıtı biriktirir.
2. `re.search(r'\{.*\}', raw_text, re.DOTALL)` ile JSON bloğu çıkarır.
3. `ToolCall.model_validate_json()` ile Pydantic doğrulaması.
4. `final_answer` → kullanıcıya yield; diğer araçlar → `_execute_tool()`.
5. `ValidationError` ve `JSONDecodeError` için LLM'e geri bildirim.
6. `MAX_REACT_STEPS` (varsayılan: 10) aşılırsa döngüden çıkar.

**Araç Dispatch Tablosu** (satır 348–374) — 24 araç:

| Araç | Açıklama |
|------|----------|
| `list_dir` | Dizin listeleme (thread'e itilir) |
| `read_file` | Dosya okuma (thread'e itilir) |
| `write_file` | Dosya yazma `path\|\|\|content` (thread'e itilir) |
| `patch_file` | Satır düzeyi yama `path\|\|\|eski\|\|\|yeni` (thread'e itilir) |
| `execute_code` | Docker sandbox REPL (thread'e itilir) |
| `audit` | Tüm .py dosyaları AST denetimi (thread'e itilir) |
| `health` | CPU/RAM/GPU raporu |
| `gpu_optimize` | VRAM boşaltma + GC |
| `github_commits` | Son N commit listesi |
| `github_info` | Depo istatistikleri |
| `github_read` | Uzak dosya okuma |
| `web_search` | Async web araması |
| `fetch_url` | URL içeriği çekme |
| `search_docs` | Kütüphane dokümantasyonu araması |
| `search_stackoverflow` | Stack Overflow araması |
| `pypi` | PyPI paket bilgisi |
| `pypi_compare` | Kurulu/güncel sürüm karşılaştırma |
| `npm` | npm paket bilgisi |
| `gh_releases` | GitHub releases listesi |
| `gh_latest` | En son GitHub release |
| `docs_search` | RAG belge arama |
| `docs_add` | URL'den RAG belge ekleme |
| `docs_list` | Belge deposu listesi |
| `docs_delete` | Belge silme |

**`_summarize_memory()`** (satır 403–452):
1. Tüm konuşmayı `DocumentStore.add_document()` ile ChromaDB'ye arşivler ("Sonsuz Hafıza").
2. LLM ile kısa özet üretir (`json_mode=False`, `temperature=0.1`).
3. `memory.apply_summary()` ile belleği 2 mesaja sıkıştırır.

---

### 3.4 `agent/auto_handle.py` — Hızlı Komut İşleyici (368 satır)

**Amaç:** LLM çağrısına gerek kalmadan sık kullanılan komutları regex kalıplarıyla anında yanıtlar.

**`handle(text)` → Tuple[bool, str]** (satır 48–122):
- Senkron handler'lar → asenkron handler'lar sırasıyla denenir.
- `(True, yanıt)` → LLM çağrısı yapılmaz; `(False, "")` → ReAct döngüsüne geçer.

**Tetikleyici Regex Örnekleri:**

| Handler | Pattern |
|---------|---------|
| `_try_list_directory` | `listele\|dosyaları göster\|ls\b` |
| `_try_read_file` | `dosyayı? oku\|incele\|göster\|içeriğ\|cat\b` |
| `_try_audit` | `denetle\|sistemi tara\|audit\|teknik rapor` |
| `_try_health` | `sistem.*sağlık\|donanım\|hardware\|cpu\|ram` |
| `_try_gpu_optimize` | `gpu.*(optimize\|temizle\|boşalt)\|vram` |
| `_try_security_status` | `erişim\|güvenlik\|openclaw\|yetki` |
| `_try_web_search` | `web.?de ara\|internette ara\|google:` |
| `_try_pypi` | `pypi\|pip show\|paket bilgisi` |

---

### 3.5 `agent/definitions.py` — Ajan Tanımları (105 satır)

**`SIDAR_SYSTEM_PROMPT`** içeriği:
- **Kişilik:** Analitik, minimal, veriye dayalı, güvenliğe şüpheci.
- **Bilgi Sınırı:** 2024 başı — belirsiz konular için `web_search` veya `pypi` emredilir.
- **İlkeler:** PEP 8, `execute_code` ile önceden test, `patch_file` tercih et, hata sınıflandır.
- **Araç Stratejileri:** Hata kurtarma adımları (dosya bulunamadı → `list_dir`, patch hatası → `read_file`).
- **24 araç tanımı** + JSON format şeması + 3 örnek.

---

### 3.6 `core/llm_client.py` — LLM İstemcisi (255 satır)

**`LLMClient` sınıfı** — Ollama ve Gemini'yi tek arayüzde soyutlar.

**`chat(messages, model, system_prompt, temperature, stream, json_mode)`** (satır 30–55):
- `stream=True` → `AsyncIterator[str]`.
- `json_mode=True` → Ollama: `"format": "json"`; Gemini: `"response_mime_type": "application/json"`.

**Ollama akışı — `_stream_ollama_response()`** (satır 113–144):
- `aiter_bytes()` + buffer mekanizması ile TCP bölünmesi sorununu önler.
- `num_gpu=-1` ile tüm katmanlar GPU'ya taşınır.

**Gemini akışı** (satır 150–219):
- `google.generativeai` SDK — `send_message_async(stream=True)`.
- Geçmiş `history` formatına dönüştürülür.

**`list_ollama_models()`** ve **`is_ollama_available()`** — Yardımcı async metodlar.

---

### 3.7 `core/memory.py` — Konuşma Belleği (240 satır)

**`ConversationMemory` sınıfı** — Oturum tabanlı, kalıcı, thread-safe.

- `sessions_dir = data/sessions/` — Her oturum ayrı `{UUID}.json` dosyasında.
- `threading.RLock()` ile thread güvenliği.
- Her turn: `{role, content, timestamp}`.

**Oturum Yönetimi:** `create_session`, `load_session`, `delete_session`, `get_all_sessions` (`updated_at` azalan), `update_title`.

**Mesaj Yönetimi:** `add()` — `max_turns * 2` (40) limitli; `get_history(n_last)`; `get_messages_for_llm()`.

**Özetleme:** `needs_summarization()` — %80 eşiği; `apply_summary()` — 2 mesaja sıkıştırma.

**Dosya Takibi:** `set_last_file(path)` / `get_last_file()`.

---

### 3.8 `core/rag.py` — RAG Sistemi (611 satır)

**`DocumentStore` sınıfı** — ChromaDB + BM25 + anahtar kelime hibrit arama.

**GPU Embedding** (satır 25–74):
- `use_gpu=True` → `SentenceTransformerEmbeddingFunction("all-MiniLM-L6-v2")` CUDA.
- `mixed_precision=True` → `torch.autocast("cuda", dtype=float16)` ile FP16.

**Chunking — `_recursive_chunk_text(text)`** (satır 188–252):
- Ayırıcı önceliği: `"\nclass "` → `"\ndef "` → `"\n\n"` → `"\n"` → `" "` → karakter.
- Overlap: `current_chunk[-overlap_len:] + part`.

**Belge Yönetimi:**
- `add_document()` — MD5 hash ID, dosya sistemi + ChromaDB (parçalı) + JSON index.
- `add_document_from_url()` — `httpx.AsyncClient` + `_clean_html()`.
- `delete_document()` — Dosya + ChromaDB parçaları + index.

**Arama — 3 katman:**
1. **ChromaDB** — `n_results = top_k * 2`; tekrarlı parent_id filtrelenir.
2. **BM25** — `BM25Okapi(corpus)`.
3. **Anahtar Kelime** — title×5 + tags×3 + içerik×1 ağırlıklı skor.

---

### 3.9 `managers/code_manager.py` — Kod Yöneticisi (353 satır)

**Docker Başlatma** (satır 45–76): `docker.from_env()` → WSL2 socket fallback (`/var/run/docker.sock`, `/mnt/wsl/...`).

**`read_file(path)`** — `SecurityManager.can_read()` → UTF-8 okuma.

**`write_file(path, content, validate=True)`** — `can_write(path)` → `.py` AST kontrolü → yazma.

**`patch_file(path, target_block, replacement_block)`** — Hedef blok sayımı:
- 0 kez → "bulunamadı" hatası. 2+ kez → "belirsiz" hatası. 1 kez → yazma.

**`execute_code(code)` — Docker Sandbox** (satır 185–246):
- `python:3.11-alpine`, `network_disabled=True`, `mem_limit="128m"`, `cpu_quota=50000`, 10sn timeout.
- `container.kill()` → `container.remove(force=True)` — temiz kapatma.

**`audit_project(root)`** — `rglob("*.py")` + `validate_python_syntax()` denetimi.

**Metrikler:** `files_read`, `files_written`, `syntax_checks`, `audits_done` — `threading.RLock()` korumalı.

---

### 3.10 `managers/security.py` — OpenClaw Erişim Kontrol (99 satır)

| Seviye | Değer | Okuma | Yazma | Çalıştırma |
|--------|-------|-------|-------|-----------|
| `RESTRICTED` | 0 | ✓ | ✗ | ✗ |
| `SANDBOX` | 1 | ✓ | Yalnızca `/temp` | ✓ |
| `FULL` | 2 | ✓ | Her yer | ✓ |

- `can_read()` → Her seviyede `True`.
- `can_write(path)` → SANDBOX: `str(target).startswith(str(self.temp_dir.resolve()))`.
- `can_execute()` → `self.level >= SANDBOX`.

---

### 3.11 `managers/system_health.py` — Sistem Sağlığı (293 satır)

**`get_gpu_info()`** — Her GPU için: `id`, `name`, `compute_capability`, `total_vram_gb`, `allocated_gb`, `reserved_gb`, `free_gb`. pynvml varsa: `temperature_c`, `utilization_pct`, `mem_utilization_pct`.

**`optimize_gpu_memory()`** → `torch.cuda.empty_cache()` + `gc.collect()`, boşaltılan MB raporu.

**`_get_driver_version()`** → pynvml → `nvidia-smi` subprocess fallback.

**`full_report()`** → Platform, Python, CPU %, RAM, GPU ayrıntıları.

**`__del__()`** → `pynvml.nvmlShutdown()` temiz kapatma.

---

### 3.12 `managers/github_manager.py` — GitHub Entegrasyonu (207 satır)

**`SAFE_TEXT_EXTENSIONS`** (22 uzantı): `.py .txt .md .json .yaml .yml .ini .cfg .toml .csv .xml .html .css .js .ts .sh .bash .bat .sql .env .example .gitignore .dockerignore`.

**Metodlar:**
- `get_repo_info()` → yıldız, fork, açık PR/issue, varsayılan branch.
- `list_commits(n, branch)` → SHA[:7], tarih, yazar, mesaj[:72].
- `read_remote_file(path, ref)` → dizinse liste; dosyaysa uzantı güvenlik kontrolü → UTF-8 decode.
- `list_branches()`, `search_code(query)`.

---

### 3.13 `managers/web_search.py` — Web Arama (251 satır)

**Motor Fallback Zinciri (AUTO modu):** Tavily → Google → DuckDuckGo.

- `_search_tavily` → POST `https://api.tavily.com/search`.
- `_search_google` → GET `https://customsearch.googleapis.com/customsearch/v1`.
- `_search_duckduckgo` → `asyncio.to_thread(_sync_search)` (DDGS v8 uyumlu).

**`fetch_url(url)`** → `httpx.AsyncClient` + `_clean_html()` + 4000 karakter kırpma.

**`search_docs(library, topic)`** → `site:docs.python.org OR site:pypi.org OR ...` kısıtlı.

**`search_stackoverflow(query)`** → `site:stackoverflow.com <query>`.

---

### 3.14 `managers/package_info.py` — Paket Bilgi (268 satır)

Tamamen `httpx.AsyncClient` tabanlı.

- `pypi_info(package)` → Sürüm, yazar, lisans, Python gereksinimi, son 8 sürüm, bağımlılıklar.
- `pypi_compare(package, current_version)` → Güncelleme uyarısı.
- `npm_info(package)` → `https://registry.npmjs.org/{package}/latest`.
- `github_releases(repo, limit=5)` → GitHub API v3.
- `github_latest_release(repo)` → `/releases/latest`.

---

### 3.15 `web_server.py` — Web Sunucusu (290 satır)

**Rate Limiting:** `defaultdict(list)` ile IP başına 20 istek/60 saniye; middleware.

**CORS:** Yalnızca `localhost:7860` ve `127.0.0.1:7860`.

**Rotalar:**

| Metod | Yol | Açıklama |
|-------|-----|----------|
| GET | `/` | `web_ui/index.html` servis |
| GET | `/favicon.ico` | 204 No Content |
| POST | `/chat` | SSE stream — `async for chunk in agent.respond()` |
| GET | `/status` | JSON sistem durumu (GPU dahil) |
| GET | `/sessions` | Oturum listesi |
| GET | `/sessions/{id}` | Oturum yükleme + geçmiş |
| POST | `/sessions/new` | Yeni oturum |
| DELETE | `/sessions/{id}` | Oturum silme |
| POST | `/clear` | Aktif bellek temizleme |

**SSE Generator:** `data: {"chunk": ...}` → `data: {"done": true}`.

---

### 3.16 `github_upload.py` — GitHub Yükleme Betiği (174 satır)

- `run_command(command, show_output)` → `subprocess.run(shell=True)` wrapper.
- Akış: git kimlik → init → `git add .` → commit → çakışmada `git pull --rebase=false -X ours` → push.

---

### 3.17 `tests/test_sidar.py` — Test Paketi (238 satır)

**Çalıştırma:** `pytest tests/ -v --cov=.`

| Test | Kapsam |
|------|--------|
| `test_code_manager_read_write` | `write_file()` → `read_file()` döngüsü |
| `test_code_manager_validation` | Geçerli/geçersiz Python sözdizimi |
| `test_toolcall_pydantic_validation` | `ToolCall.model_validate_json()` kabul/ret |
| `test_web_search_fallback` | API anahtarsız WebSearchManager durumu |
| `test_rag_document_chunking` | 50 fonksiyonlu metin — chunking + tam geri okuma |
| `test_agent_initialization` | `agent.status()`, `VERSION`, `AI_PROVIDER`, `_build_context()` |
| `test_hardware_info_fields` | `HardwareInfo` dataclass alan tipleri |
| `test_config_gpu_fields` | Config GPU özellik varlık + tip kontrolü |
| `test_system_health_manager_cpu_only` | GPU kapalı rapor üretimi |
| `test_system_health_gpu_info_structure` | `get_gpu_info()` çıktı yapısı |
| `test_rag_gpu_params` | GPU parametreli DocumentStore başlatma |

---

## 4. YAPILANDIRMA DOSYALARI

### 4.1 `.env.example` (113 satır)

Tüm yapılandırılabilir parametreler örnek değerleriyle:

| Bölüm | Parametreler |
|-------|-------------|
| AI Sağlayıcı | `AI_PROVIDER`, `OLLAMA_URL`, `CODING_MODEL`, `TEXT_MODEL`, `OLLAMA_TIMEOUT`, `GEMINI_API_KEY`, `GEMINI_MODEL` |
| Erişim | `ACCESS_LEVEL` |
| GitHub | `GITHUB_TOKEN`, `GITHUB_REPO` |
| GPU | `USE_GPU`, `GPU_DEVICE`, `MULTI_GPU`, `GPU_MEMORY_FRACTION`, `GPU_MIXED_PRECISION` |
| HuggingFace | `HF_TOKEN`, `HF_HUB_OFFLINE` |
| Loglama | `LOG_LEVEL`, `LOG_FILE`, `LOG_MAX_BYTES`, `LOG_BACKUP_COUNT` |
| ReAct | `MAX_REACT_STEPS`, `REACT_TIMEOUT`, `MAX_MEMORY_TURNS` |
| Web Arama | `SEARCH_ENGINE`, `TAVILY_API_KEY`, `GOOGLE_SEARCH_API_KEY`, `GOOGLE_SEARCH_CX`, `WEB_SEARCH_MAX_RESULTS`, `WEB_FETCH_TIMEOUT`, `WEB_FETCH_MAX_CHARS` |
| RAG | `RAG_DIR`, `RAG_TOP_K`, `RAG_CHUNK_SIZE`, `RAG_CHUNK_OVERLAP` |
| Web UI | `WEB_HOST`, `WEB_PORT` |

### 4.2 `Dockerfile` (87 satır)

- `ARG BASE_IMAGE=python:3.11-slim` — GPU: `nvidia/cuda:12.4.1-runtime-ubuntu22.04`.
- `ARG GPU_ENABLED=false`.
- `environment.yml`'den pip bağımlılıkları PyYAML ile ayrıştırılır.
- Non-root `sidar` kullanıcısı, `HEALTHCHECK`, `EXPOSE 7860`.
- `ENTRYPOINT ["python", "main.py"]`.

### 4.3 `docker-compose.yml` (168 satır)

| Servis | Mod | Özellik |
|--------|-----|---------|
| `sidar-ai` | CLI CPU | `stdin_open: true`, `tty: true` |
| `sidar-gpu` | CLI GPU | `runtime: nvidia` |
| `sidar-web` | Web CPU | `command: python web_server.py`, port 7860 |
| `sidar-web-gpu` | Web GPU | `runtime: nvidia`, port 7860 |

### 4.4 `environment.yml` (80 satır)

Kanallar: `conda-forge`, `defaults`. Python 3.11.

pip bağımlılıkları: `python-dotenv`, `requests`, `httpx`, `psutil`, `GPUtil`, `pynvml`, `ollama`, `google-generativeai`, `PyGithub`, `duckduckgo-search`, `rank-bm25`, `chromadb`, `sentence-transformers`, `fastapi`, `uvicorn[standard]`, `docker`, `pydantic`, `pytest`, `pytest-asyncio`, `pytest-cov`, `black`, `flake8`, `mypy`.

### 4.5 `install_sidar.sh` (132 satır)

Otomatik kurulum: apt → Miniconda → Ollama → git clone → `conda env create` → model indirme (`qwen2.5-coder:7b`, `gemma2:9b`, `nomic-embed-text`).

---

## 5. WEB ARAYÜZÜ — `web_ui/index.html`

- **Kütüphaneler:** Highlight.js 11.9.0, Marked.js 9.1.6.
- **Tema:** CSS custom properties — karanlık/aydınlık (`data-theme="dark/light"`).
- **Bileşenler:** Üst bar, chat alanı, SSE akış, input, hızlı aksiyon butonları, oturum paneli, GPU/bellek durum paneli.
- **SSE İstemcisi:** `fetch()` + `ReadableStream` (EventSource yerine — daha güvenilir).

---

## 6. MİMARİ GENEL BAKIŞ

### 6.1 Modül Hiyerarşisi

```
main.py / web_server.py
    └── agent/sidar_agent.py (SidarAgent)
            ├── config.py (Config, HARDWARE)
            ├── core/llm_client.py  (LLMClient)
            ├── core/memory.py      (ConversationMemory)
            ├── core/rag.py         (DocumentStore)
            ├── managers/
            │   ├── code_manager.py   ← security.py
            │   ├── system_health.py
            │   ├── github_manager.py
            │   ├── web_search.py
            │   └── package_info.py
            └── agent/
                ├── auto_handle.py
                └── definitions.py
```

### 6.2 Asenkron Mimari Özeti

| Bileşen | Yöntem |
|---------|--------|
| CLI döngüsü | Tek `asyncio.run()` + `asyncio.to_thread(input)` |
| Web sunucusu | FastAPI + Uvicorn (ASGI) |
| LLM çağrıları | `httpx.AsyncClient` + `aiter_bytes()` buffer |
| Dosya I/O | `asyncio.to_thread(code.method)` |
| Docker REPL | `asyncio.to_thread(code.execute_code)` |
| DuckDuckGo SDK | `asyncio.to_thread(_sync_search)` — v8 uyumlu |
| Web/Paket API | `httpx.AsyncClient` doğrudan |

### 6.3 Thread Güvenliği

| Bileşen | Mekanizma |
|---------|-----------|
| `CodeManager` | `threading.RLock()` |
| `ConversationMemory` | `threading.RLock()` |
| `SecurityManager` | Değişmez config (lock yok) |
| `SidarAgent._lock` | `asyncio.Lock()` — ilk `respond()` çağrısında |
| Web singleton ajan | `asyncio.Lock()` — double-checked locking |

---

## 7. SÜRÜM DURUMU

| Dosya | Sürüm |
|-------|-------|
| `config.py` `Config.VERSION` | **v2.6.0** |
| `main.py` banner | **v2.6.0** |
| `agent/sidar_agent.py` `VERSION` | **v2.6.0** |
| `Dockerfile` LABEL | **v2.6.0** |
| `README.md` başlık | v2.3.2 ⚠️ güncellenmeli |

---

## 8. GÜVENLİK DEĞERLENDİRMESİ

| Alan | Durum | Detay |
|------|-------|-------|
| Dosya Erişim Kontrolü | ✓ | OpenClaw 3-seviye |
| Docker Sandbox | ✓ | Ağ yok, 128MB RAM, %50 CPU, 10sn timeout |
| Binary Dosya Koruması | ✓ | GitHub'dan yalnızca 22 güvenli uzantı |
| Rate Limiting | ✓ | 20 req/60sn per IP |
| CORS | ✓ | Yalnızca localhost:7860 |
| Sır Yönetimi | ✓ | `.env` gitignore'da |
| Sandbox Yazma Kısıtı | ✓ | SANDBOX modda yalnızca `temp/` |
| OLLAMA IPv4 | ⚠️ | `.env`'de `127.0.0.1` önerilir (WSL2 IPv6 riski) |

---

## 9. KOD İSTATİSTİKLERİ

| Dosya | Satır |
|-------|-------|
| `core/rag.py` | 611 |
| `agent/sidar_agent.py` | 474 |
| `config.py` | 415 |
| `agent/auto_handle.py` | 368 |
| `managers/code_manager.py` | 353 |
| `managers/system_health.py` | 293 |
| `web_server.py` | 290 |
| `managers/package_info.py` | 268 |
| `core/llm_client.py` | 255 |
| `managers/web_search.py` | 251 |
| `core/memory.py` | 240 |
| `tests/test_sidar.py` | 238 |
| `main.py` | 228 |
| `managers/github_manager.py` | 207 |
| `github_upload.py` | 174 |
| `agent/definitions.py` | 105 |
| `managers/security.py` | 99 |
| **TOPLAM** | **4.631** |

---

## 10. BAĞIMLILIKLAR

### Zorunlu (Çekirdek)
`python-dotenv`, `requests`, `httpx`, `pydantic`, `fastapi`, `uvicorn[standard]`, `docker`

### AI Sağlayıcıları
`ollama`, `google-generativeai`

### RAG
`chromadb`, `sentence-transformers`, `rank-bm25`

### Sistem İzleme
`psutil`, `pynvml` (nvidia-ml-py), `torch`

### Entegrasyon
`PyGithub`, `duckduckgo-search`

### Geliştirme / Test
`pytest`, `pytest-asyncio`, `pytest-cov`, `black`, `flake8`, `mypy`

---

## 11. DİKKAT EDİLMESİ GEREKEN NOKTALAR

### 11.1 README Sürüm Uyumsuzluğu
`README.md` başlığında v2.3.2 yazar; kod tabanının tamamı v2.6.0'dır. README güncellenmeli.

### 11.2 OLLAMA_URL IPv6 Riski (WSL2)
`config.py` satır 224'te varsayılan `http://localhost:11434/api` WSL2'de IPv6 üzerinden çözümlenebilir.
`.env` dosyasında `OLLAMA_URL=http://127.0.0.1:11434/api` olarak ayarlanması önerilir.

### 11.3 `config.validate_critical_settings()` Senkron HTTP
Ollama doğrulaması `requests.get()` ile yapılır. Yalnızca başlatma aşamasında çağrıldığı için event loop'u etkilemez; kabul edilebilir.

### 11.4 Docker REPL `time.sleep(0.5)` Döngüsü
`execute_code()` içindeki polling döngüsü `asyncio.to_thread()` içinde çalıştığından web sunucusunu bloklamaz; kabul edilebilir.

---

## 12. ÇALIŞTIRILMA YÖNTEMLERİ

### CLI
```bash
python main.py                          # interaktif mod
python main.py -c "main.py dosyasını oku"  # tek komut
python main.py --status                 # durum raporu
python main.py --level full --provider gemini
```

### Web Arayüzü
```bash
python web_server.py
# Tarayıcı: http://localhost:7860
```

### Docker
```bash
docker compose up sidar-web       # CPU
docker compose up sidar-web-gpu   # GPU
```

### Testler
```bash
pytest tests/ -v --cov=.
```

### Conda Kurulum
```bash
conda env create -f environment.yml
conda activate sidar-ai
```

---

*Bu rapor, projedeki tüm kaynak dosyalar satır satır okunarak hazırlanmıştır.*

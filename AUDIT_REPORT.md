# SİDAR Projesi — Eksiksiz Kod Analiz Raporu
**Tarih:** 2026-02-26
**İncelenen Branch:** claude/audit-project-files-eG07s
**Toplam Dosya:** 19 Python + 7 Config/Altyapı

---

## Proje Genel Bilgileri

| Özellik | Değer |
|---------|-------|
| Dil | Python 3.11 |
| Toplam Python Dosyası | 19 |
| Toplam Yaklaşık Satır | ~3.700 |
| Mimari | ReAct (Reason+Act) döngüsü |
| LLM Desteği | Ollama (yerel) + Google Gemini |
| Güvenlik Sistemi | OpenClaw (3 seviye: restricted/sandbox/full) |

---

## BÖLÜM 1 — DOSYALAR ARASI UYUMSUZLUKLAR (Kritik)

### 1. Sürüm Numarası Tutarsızlığı — 3 Farklı Değer

| Dosya | Satır | Sürüm |
|-------|-------|-------|
| `sidar_agent.py` | 33 | `VERSION = "2.3.2"` |
| `Dockerfile` | 6 | `LABEL version="2.2.0"` |
| `main.py` (Banner) | 53 | `v1.0.0` |

Üç farklı dosyada üç farklı sürüm numarası bulunuyor. Banner'daki değer en hatalı.

---

### 2. `ConversationMemory` — Test Dosyasında Yanlış Kullanım (TestFail)

`core/memory.py:21` → `__init__(self, file_path: Path, max_turns: int = 20)` — `file_path` **zorunlu** parametre.

`tests/test_sidar.py`'de 5 yerde `file_path` verilmeden çağrılıyor:

```python
# test_sidar.py:200
mem = ConversationMemory(max_turns=5)   # TypeError: file_path gerekli

# test_sidar.py:208
mem = ConversationMemory(max_turns=2)   # TypeError

# test_sidar.py:215, 222, 229
mem = ConversationMemory()              # TypeError
```

`TestConversationMemory` sınıfındaki tüm testler pytest çalıştırıldığında çöker.

---

### 3. `WebSearchManager` — Config Değerleri Yoksayılıyor

`config.py` bu ayarları tanımlıyor:
```python
WEB_SEARCH_MAX_RESULTS: int = int(os.getenv("WEB_SEARCH_MAX_RESULTS", "5"))
WEB_FETCH_TIMEOUT: int = int(os.getenv("WEB_FETCH_TIMEOUT", "15"))
WEB_FETCH_MAX_CHARS: int = int(os.getenv("WEB_FETCH_MAX_CHARS", "4000"))
```

Ama `web_search.py:22-24`'te bu değerler hard-coded sabit olarak tekrar tanımlanmış:
```python
MAX_RESULTS = 5
FETCH_TIMEOUT = 15
FETCH_MAX_CHARS = 4000
```

`sidar_agent.py:53`: `self.web = WebSearchManager()` — Config nesnesi hiç verilmiyor.
`.env` dosyasında bu ayarları değiştirmenin **hiçbir etkisi** yok.

---

### 4. `PackageInfoManager` — Aynı Config Sorunu

`config.py:89`:
```python
PACKAGE_INFO_TIMEOUT: int = int(os.getenv("PACKAGE_INFO_TIMEOUT", "12"))
```

`package_info.py:23`:
```python
TIMEOUT = 12  # hard-coded
```

`sidar_agent.py:54`: `self.pkg = PackageInfoManager()` — Config alınmıyor.
Env variable değişikliklerinin etkisi yok.

---

### 5. `execute_code` — Güvenlik Sistemi Bypass

`security.py:72-74`:
```python
def can_execute(self) -> bool:
    return self.level == FULL  # SANDBOX'ta False döner
```

`code_manager.py:157`:
```python
if self.security.level == 0:  # Sadece RESTRICTED engelleniyor!
    return False, "[OpenClaw] Kod çalıştırma yetkisi yok"
```

**SANDBOX modunda** `can_execute()` → `False` ama `execute_code()` çalışıyor.
`SecurityManager.can_execute()` metodu bypass ediliyor.

---

### 6. `github_read` Aracı — Auto-Handle'da Var, Agent'ta Yok

| Konum | Durum |
|-------|-------|
| `auto_handle.py:91-92` | ✅ Mevcut |
| `sidar_agent.py._execute_tool()` | ❌ Yok |
| `definitions.py` araç listesi | ❌ Yok |

LLM bu aracı JSON çağrısıyla kullanamıyor; sadece doğal dil tetikleyici çalışıyor.

---

### 7. Ollama URL Yapımındaki `rstrip()` Hatası

`llm_client.py:64`:
```python
url = f"{self.config.OLLAMA_URL.rstrip('/api')}/api/chat"
```

`rstrip('/api')` bir string değil, **karakter kümesi** alır: `/`, `a`, `p`, `i` karakterlerini sağdan teker siler.
Tesadüfen çalışıyor ama özel Ollama URL'lerinde yanlış sonuç üretebilir.
Aynı hata `llm_client.py:199` ve `210`'da da mevcut.

**Doğrusu:**
```python
url = f"{self.config.OLLAMA_URL.removesuffix('/api')}/api/chat"
```

---

### 8. `managers/__init__.py` — Eksik Export'lar

```python
# managers/__init__.py
__all__ = ["CodeManager", "SystemHealthManager", "GitHubManager", "SecurityManager"]
```

`WebSearchManager` ve `PackageInfoManager` **export edilmemiyor**.

---

### 9. `Config` Class'ında `DATA_DIR` Eksik

`config.py:15-22`: `DATA_DIR` modül seviyesinde tanımlı.
`Config` sınıfı `BASE_DIR`, `TEMP_DIR`, `LOGS_DIR`'ı expose ediyor ama `DATA_DIR`'ı **expose etmiyor**.
Dışarıdan `cfg.DATA_DIR` erişilemiyor, tutarsız tasarım.

---

## BÖLÜM 2 — KOD KALİTESİ SORUNLARI

### 10. `definitions.py` — 119 Satır Ölü Kod

`definitions.py:108-226`: Tüm eski sistem prompt'u ve sabitler yorum satırı olarak bırakılmış.
Dosyanın ~%54'ü kullanılmayan yorum kodu.

`SIDAR_KEYS` ve `SIDAR_WAKE_WORDS` sabitleri tanımlanmış ama projede **hiçbir yerde kullanılmıyor**.

---

### 11. `main.py:HELP_TEXT` — Satır Tekrarı

```python
# main.py:77-78
  docs ara: <sorgu>                → Belge deposunda ara
  belge ekle <url>                 → URL'den belge ekle
  docs ara: <sorgu>                → Depoda arama    ← TEKRAR!
```

---

### 12. `web_search.py` — `search_github()` Dead Code

`web_search.py:172-175`: `search_github()` metodu tanımlı ama:
- `definitions.py`'de araç olarak listede yok
- `sidar_agent.py._execute_tool()`'da handler yok
- `auto_handle.py`'de kullanılmıyor

Tamamen ulaşılamayan ölü kod.

---

### 13. `Dockerfile` — Conda Paketleri Kurulmuyor

Dockerfile sadece `pip` bölümünü ayrıştırıyor, conda-only paketler
(torch/pytorch-cuda) yoksayılıyor. GPU destekli paketler Docker imajına **kurulmuyor**.

---

### 14. `memory.py` — İç İçe Lock Çağrısı

`_save()` kendi içinde `with self._lock:` kullanıyor.
`add()` metodu zaten `with self._lock:` bloğu içinden `_save()` çağırıyor.
RLock olduğu için çalışıyor ama tasarım kafa karıştırıcı.

---

## BÖLÜM 3 — GELİŞTİRİLMESİ GEREKEN ALANLAR

| Öncelik | Konu | Açıklama |
|---------|------|----------|
| 🔴 Yüksek | **Bellek Özetleme** | 20 tur sonra bağlam kayboluyor; LLM tabanlı özetleme eklenmeli |
| 🔴 Yüksek | **Async I/O** | Web aramaları ve LLM çağrıları senkron; büyük isteklerde donma riski |
| 🔴 Yüksek | **JSON Hata Döngüsü** | JSON parse hatasında feedback loop yok; LLM hatalı yanıtı tekrarlayabilir |
| 🟡 Orta | **Test Coverage** | RAG, LLMClient, WebSearch, PackageInfo için test yok |
| 🟡 Orta | **Config Bütünlüğü** | Config ayarları Manager'lara iletilmiyor; env override işlevsiz |
| 🟡 Orta | **Güvenlik Uyarısı** | `--level full` ile erişim açıldığında kullanıcıya uyarı verilmiyor |
| 🟢 Düşük | **memory.json güvenliği** | `data/memory.json` .gitignore'da değil; konuşma geçmişi commit'lenebilir |
| 🟢 Düşük | **HTML temizleme tekrarı** | `web_search.py` ve `rag.py` aynı `_clean_html()` kodunu kopyalamış |

---

## BÖLÜM 4 — DOSYA BAZINDA ÖZET

| Dosya | Durum | Notlar |
|-------|-------|--------|
| `main.py` | ⚠️ Sorunlu | Banner sürümü yanlış (v1.0.0), HELP_TEXT tekrar |
| `config.py` | ⚠️ Eksik | `DATA_DIR` class attribute değil |
| `agent/sidar_agent.py` | ✅ İyi | Yapı sağlam; `github_read` tool eksik |
| `agent/definitions.py` | ⚠️ Kirli | %54 ölü kod, kullanılmayan sabitler |
| `agent/auto_handle.py` | ✅ İyi | Kapsamlı pattern matching |
| `core/llm_client.py` | ⚠️ Bug | `rstrip('/api')` yanlış, 3 yerde tekrar |
| `core/memory.py` | ✅ İyi | Thread-safe, persistent |
| `core/rag.py` | ✅ İyi | Hibrit arama iyi yapılandırılmış |
| `managers/security.py` | ⚠️ Tutarsız | `can_execute()` bypass ediliyor |
| `managers/code_manager.py` | ✅ İyi | Sağlam yapı |
| `managers/system_health.py` | ✅ İyi | Temiz |
| `managers/github_manager.py` | ✅ İyi | PyGithub entegrasyonu düzgün |
| `managers/web_search.py` | ⚠️ Sorunlu | Config almıyor, dead code |
| `managers/package_info.py` | ⚠️ Sorunlu | Config almıyor |
| `managers/__init__.py` | ⚠️ Eksik | 2 sınıf export edilmemiş |
| `tests/test_sidar.py` | 🔴 Hatalı | ConversationMemory testleri çöker (5 test) |
| `Dockerfile` | ⚠️ Sorunlu | Sürüm yanlış, conda paketleri kurulmuyor |
| `environment.yml` | ✅ İyi | Bağımlılıklar doğru |
| `.note` | ℹ️ Bilgi | Geliştirme notları |

---

## BÖLÜM 5 — ÖNCELİKLİ DÜZELTME LİSTESİ

1. **`tests/test_sidar.py`** — `ConversationMemory` çağrılarına `file_path=tmp_path / "mem.json"` ekle (5 yer)
2. **`main.py:53`** — Banner sürümünü `2.3.2` yap
3. **`Dockerfile:6`** — `LABEL version="2.3.2"` yap
4. **`llm_client.py:64,199,210`** — `rstrip('/api')` → `removesuffix('/api')`
5. **`managers/security.py + code_manager.py`** — `execute_code` izni `can_execute()` üzerinden kontrol edilmeli
6. **`definitions.py`** — Yorum satırlarını ve kullanılmayan sabitleri sil
7. **`managers/__init__.py`** — `WebSearchManager`, `PackageInfoManager` export listesine ekle
8. **`web_search.py` + `package_info.py`** — Config nesnesi parametresi ekle
9. **`config.py`** — `DATA_DIR` class attribute ekle
10. **`sidar_agent.py` + `definitions.py`** — `github_read` araç listesine ekle veya auto_handle'dan kaldır
11. **`main.py:78`** — Tekrarlanan `docs ara:` satırını sil
12. **`definitions.py:89-97`** — Kullanılmayan `SIDAR_KEYS`, `SIDAR_WAKE_WORDS` sabitlerini sil
13. **`.gitignore`** — `data/memory.json` satırını ekle

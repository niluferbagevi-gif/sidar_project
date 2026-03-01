# SİDAR — Web Arayüzü Öğretici Rehberi

**Adres:** `http://localhost:7860`
**Sürüm:** v2.6.1 · **Son güncelleme:** 2026-03-01

> Bu rehber, `python web_server.py` komutuyla açılan web arayüzünün **her öğesini görsel olarak açıklar**. Sayfayı ilk kez kullananlar için adım adım bir başlangıç kılavuzudur.

---

## Hızlı Başlangıç

```
1. conda activate sidar-ai
2. python web_server.py
3. Tarayıcıda aç: http://localhost:7860
```

---

## Arayüze Genel Bakış

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  SI  SİDAR     Görevler  Sohbet    🌙   📊  ⊙ Durum  ↓ MD  ↓ JSON  🗑       │  ← (A) ÜST ÇUBUK
├──────────────────────┬──────────────────────────────────────────────────────┤
│  ★ qwen2.5-coder:7b  │                                                      │
│  📁 sidar_projec  🌿 main│          Sidar'a bir görev ver                   │  ← (C) ANA İÇERİK
│                      │       Yazılım Mimarı & Baş Mühendis AI               │
│  + Yeni Sohbet       │                                                      │
│                      │  ┌──────────────────────────────────────────────┐    │
│  Sohbetlerde ara...  │  │  Bir görevi tanımla...                       │    │  ← (D) GÖREV KUTUSU
│                      │  │                                               │    │
│  📝 İlk Sohbet       │  │                                               │    │
│     5 saat önce      │  └──────────────────────────────────────────────┘    │
│                      │  [📁 niluferbagevi-gif/sidar_p...] [🌿 main] [Başlat]│
│                      │                                                      │
│                      │  Dizini listele · Sistem sağlığı · Proje denetimi   │  ← (E) HIZLI GÖREVLER
│                      │  Son commitler  · Web araması   · PyPI bilgisi       │
│                      │  Güvenlik durumu· RAG belgeleri                      │
└──────────────────────┴──────────────────────────────────────────────────────┘
        ↑ (B) SOL KENAR ÇUBUĞU
```

---

## (A) Üst Çubuk — Soldan Sağa

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  SI  SİDAR  │  Görevler  Sohbet  │  🌙   📊   ⊙ Durum  ↓ MD  ↓ JSON  🗑    │
│   1     2   │      3        4    │   5    6       7       8      9     10   │
└─────────────────────────────────────────────────────────────────────────────┘
```

| # | Öğe | Ne yapar? |
|---|-----|-----------|
| **1** | `SI` logo ikonu | Dekoratif marka simgesi |
| **2** | `SİDAR` yazısı | Uygulama adı |
| **3** | `Görevler` sekmesi | **Görev başlatma ekranı** — başlangıç sayfası; yeni iş tanımlamak için |
| **4** | `Sohbet` sekmesi | **Sohbet geçmişi ekranı** — devam eden konuşmayı görmek için |
| **5** | 🌙 **Tema butonu** | Koyu ↔ Açık tema değiştirir; seçim tarayıcıya kaydedilir |
| **6** | 📊 **Kısayollar butonu** | Tüm klavye kısayollarını gösterir |
| **7** | `⊙ Durum` butonu | Sistem durum penceresini açar (model, sağlayıcı, GPU, web arama bilgisi) |
| **8** | `↓ MD` butonu | Aktif sohbeti **Markdown** dosyası olarak indirir |
| **9** | `↓ JSON` butonu | Aktif sohbeti **JSON** formatında ham veri olarak indirir |
| **10** | 🗑 **Temizle** butonu | Aktif oturumun belleğini sıfırlar (sohbet geçmişini siler) |

---

## (B) Sol Kenar Çubuğu — Oturum Yönetimi

```
┌────────────────────┐
│  ★ qwen2.5-coder:7b│  ← Model chip (bilgi amaçlı, tıklanamaz)
│  📁 sidar_proje... │  ← Depo adı chip
│     🌿 main        │  ← Dal adı chip (tıkla → dal değiştir)
├────────────────────┤
│  + Yeni Sohbet     │  ← Yeni oturum başlat
├────────────────────┤
│  Sohbetlerde ara...│  ← Oturum arama kutusu
├────────────────────┤
│  📝 İlk Sohbet     │  ← Oturum listesi
│     5 saat önce 🗑  │    (üzerine gel → çöp kutusu görünür)
└────────────────────┘
```

### Model Chip — `★ qwen2.5-coder:7b`

- Şu an hangi Ollama modelinin kullanıldığını gösterir
- Bilgi amaçlıdır; buradan değiştirilmez
- Modeli değiştirmek için `.env` dosyasında `CODING_MODEL=` ayarını güncelleyin ve sunucuyu yeniden başlatın

### Depo Chip — `📁 niluferbagevi-gif/sidar_projec...`

- GitHub'daki bağlı depoyu gösterir
- `.env` dosyasında `GITHUB_REPO=kullanici/depo-adi` ile ayarlanır

### Dal Chip — `🌿 main`

- Tıklandığında açılır pencere çıkar → farklı bir dal seçebilirsiniz
- Seçim gerçek `git checkout` komutu çalıştırır (backend'de)
- Dal değiştirmek SİDAR'ın çalıştığı kod tabanını değiştirir

### `+ Yeni Sohbet` Butonu

- Her tıklamada temiz bir oturum açar
- Önceki oturum sidebar'da listelenir, kaybolmaz
- Klavye kısayolu: `Ctrl + K`

### Oturum Arama Kutusu — `Sohbetlerde ara...`

- Oturum başlıklarında anlık filtreleme yapar
- Çok sayıda sohbet biriktikçe işe yarar

### Oturum Listesi

- Her satır bir geçmiş sohbeti gösterir
- Sohbet başlığı ilk mesajınızın ilk ~30 karakterinden otomatik oluşturulur
- Üzerine gelince sağda 🗑 çöp kutusu belirir → tıklarsanız oturum kalıcı silinir
- Aktif oturum mor renkle vurgulanır

---

## (C) Görevler Sekmesi — İlk Açılış Ekranı

Bu, sayfayı açtığınızda karşınıza çıkan ana ekrandır.

```
          Sidar'a bir görev ver
     Yazılım Mimarı & Baş Mühendis AI
                                            ← Başlık alanı
┌─────────────────────────────────────────────────────────┐
│                                                         │
│  Bir görevi tanımla...                                  │  ← (D) Görev Kutusu
│                                                         │
│                                                         │
├──────────────────────────────────────────┬──────────────┤
│ [📁 niluferbagevi-gif/sidar_p...][🌿 main]│   Başlat ▶  │
└──────────────────────────────────────────┴──────────────┘

  Dizini listele  Sistem sağlığı  Proje denetimi  Son commitler    ← (E) Hızlı Görevler
  Web araması     PyPI bilgisi    Güvenlik durumu  RAG belgeleri
```

---

## (D) Görev Kutusu — Görev Girişi

```
┌──────────────────────────────────────────────────────────────┐
│                                                              │
│  Buraya görevinizi yazın...                                  │
│                                                              │
│  Örnek:                                                      │
│  "src/api/ klasöründeki tüm dosyaları oku ve                 │
│   olası güvenlik açıklarını listele"                         │
│                                                              │
├──────────────────────┬───────────────────────┬──────────────┤
│ [📁 depo-adı]        │ [🌿 main]              │  Başlat ▶   │
└──────────────────────┴───────────────────────┴──────────────┘
```

### Görev Kutusu Davranışı

| Özellik | Detay |
|---------|-------|
| **Çok satırlı giriş** | `Enter` yeni satır açar — `Ctrl+Enter` gönderir |
| **Uzun görevler** | Kutu dikey büyür (max 260px), sonra kaydırılır |
| **Depo chip** | Hangi GitHub deposunda çalışıldığını gösterir |
| **Dal chip** | Hangi branch'te olduğunu gösterir |
| **`Başlat` butonu** | Görevi SİDAR'a iletir ve Sohbet sekmesine geçer |

### Etkili Görev Yazma İpuçları

```
✅ İYİ: "requirements.txt dosyasını oku, eksik olan bağımlılıkları bul ve ekle"
✅ İYİ: "tests/ klasöründe pytest çalıştır, hata alan testleri düzelt"
✅ İYİ: "FastAPI'nin en yeni sürümünü kontrol et ve güncel mi söyle"

❌ ZAYIF: "kodu düzelt"
❌ ZAYIF: "her şeyi yap"
```

---

## (E) Hızlı Görev Düğmeleri

Yazmadan tek tıkla hazır görevleri başlatın:

| Düğme | Ne çalışır? | Örnek çıktı |
|-------|-------------|-------------|
| **Dizini listele** | Proje kök dizinini listeler | `sidar_project/` içindeki tüm dosyalar |
| **Sistem sağlığı** | CPU, RAM, GPU durumunu raporlar | `CPU: %12 · RAM: 3.2 GB · GPU: RTX 3070 Ti` |
| **Proje denetimi** | Kod kalite denetimi çalıştırır | Potansiyel sorunları listeler |
| **Son commitler** | Son 5 GitHub commit'ini getirir | Commit hash, mesaj, tarih |
| **Web araması** | Örnek bir arama yapar | DuckDuckGo/Tavily sonuçları |
| **PyPI bilgisi** | Örnek paket sorgular | Sürüm, bağımlılık, açıklama |
| **Güvenlik durumu** | Erişim seviyesini raporlar | OpenClaw durumu: Sandbox / Full |
| **RAG belgeleri** | Belge deposunu listeler | Eklenmiş dokümanlar |

---

## (F) Sohbet Sekmesi — Konuşma Ekranı

Görev başlatıldıktan sonra otomatik olarak bu sekmeye geçilir.

```
┌──────────────────────────────────────────────────────────────────┐
│  SI  SİDAR │ Görevler  Sohbet │ 🌙 📊 ⊙ Durum ↓MD ↓JSON 🗑 ■Durdur│
├────────────┬─────────────────────────────────────────────────────┤
│            │                                                     │
│  Oturum    │  👤 Siz                                             │
│  Listesi   │  "src/ klasörünü oku ve özetle"                     │
│            │                                                     │
│            │  ┌──────────────────────────────────────────────┐   │
│            │  │ ⚙ dizin_listele: src/                        │   │  ← Araç badge
│            │  │ ⚙ dosya_oku: src/main.py                     │   │
│            │  └──────────────────────────────────────────────┘   │
│            │                                                     │
│            │  🤖 SİDAR                                           │
│            │  src/ klasöründe 3 dosya buldum:                   │
│            │  • main.py — Ana giriş noktası...                  │
│            │                                                     │
│            │  [Kopyala] [Düzenle]         ← Mesaj aksiyonları   │
│            │                                                     │
│            ├─────────────────────────────────────────────────────┤
│            │  [📎]  Devam eden sorunuzu yazın...  [Ctrl+Enter ▶] │
└────────────┴─────────────────────────────────────────────────────┘
```

### Mesaj Aksiyonları (üzerine gelince görünür)

Her mesajın altında iki buton belirir:

| Buton | İşlev |
|-------|-------|
| **Kopyala** | Mesaj içeriğini panoya kopyalar |
| **Düzenle** | Mesajı düzenlenebilir hale getirir, değiştirip yeniden gönderebilirsiniz |

### Araç Badge'leri — SİDAR Ne Yapıyor?

SİDAR bir araç kullandığında sohbet akışında küçük bir badge gösterilir:

```
⚙ dosya_oku: src/config.py          → Dosya okunuyor
⚙ kod_çalıştır: test.py             → Docker sandbox'ta çalışıyor
⚙ web_ara: fastapi güncel sürüm     → İnternet araması yapılıyor
⚙ github_commitler                  → GitHub API'ye bağlanıyor
⚙ pypi: httpx                       → PyPI sorgulanıyor
⚙ rag_ara: ChromaDB embedding       → Belge deposunda arama
⚙ dosya_yaz: src/fix.py             → Dosya diske yazılıyor
```

### Durdur Butonu — `■ Durdur`

- SİDAR yanıt üretirken üst çubukta kırmızı `■ Durdur` butonu belirir
- Tıkladığınızda akış anında kesilir (`AbortController` ile)
- Klavye kısayolu: `Esc`

### Dosya Ekleme — `📎`

Mesaj kutusunun solundaki ataş simgesine tıklayarak dosya ekleyebilirsiniz:

```
Desteklenen türler: .py · .txt · .md · .json · .yaml · .csv
                    .html · .js · .ts · .sh · .env · ve diğerleri
Maksimum boyut: 200 KB
```

Dosya eklendikten sonra mesaj kutusunun üstünde dosya chip'i belirir:

```
┌─────────────────────────────────────────────┐
│ 📄 config.py  15 KB                    ✕    │  ← Ataşı kaldırmak için ✕
└─────────────────────────────────────────────┘
```

---

## (G) Durum Penceresi — `⊙ Durum`

Üst çubukta `⊙ Durum` butonuna basınca açılır:

```
┌────────────────────────────────────────────┐
│  Sistem Durumu                             │
├────────────────────────────────────────────┤
│  AI Sağlayıcı    ollama              ✓     │
│  Model           qwen2.5-coder:7b    ✓     │
│  GPU             RTX 3070 Ti         ✓     │
│  Bellek          SANDBOX             ✓     │
│  GitHub          bağlı               ✓     │
│  Web Arama       DuckDuckGo          ✓     │
│  Paket Durum     PyPI erişilebilir   ✓     │
├────────────────────────────────────────────┤
│              [Kapat]                       │
└────────────────────────────────────────────┘
```

| Satır | Ne anlam ifade eder? |
|-------|---------------------|
| **AI Sağlayıcı** | `ollama` (yerel) veya `gemini` (bulut) |
| **Model** | Aktif Ollama modeli |
| **GPU** | GPU algılandıysa model adını gösterir |
| **Bellek** | Erişim seviyesi: `restricted` / `sandbox` / `full` |
| **GitHub** | Token tanımlı ve bağlantı başarılı mı? |
| **Web Arama** | Aktif motor (Tavily/Google/DuckDuckGo) |
| **Paket Durum** | PyPI ve npm erişimi var mı? |

---

## (H) Klavye Kısayolları

| Kısayol | İşlev |
|---------|-------|
| `Ctrl + Enter` | Mesajı gönder / Görevi başlat |
| `Ctrl + K` | Yeni sohbet aç |
| `Ctrl + L` | Aktif oturumun belleğini temizle |
| `Ctrl + T` | Koyu / Açık tema değiştir |
| `Esc` | Yanıt akışını durdur |

Tüm kısayolları görmek için üst çubukta 📊 butonuna tıklayın.

---

## (I) Tema Değiştirme

Üst çubukta 🌙 / ☀ simgesine tıklayın:

```
🌙 → Koyu tema (varsayılan — koyu lacivert arkaplan)
☀  → Açık tema (beyaz arkaplan, iş ortamı)
```

Seçiminiz tarayıcıya kaydedilir, sayfayı yenileseniz de korunur.

---

## (J) Sohbet Dışa Aktarma

| Buton | Format | Ne için? |
|-------|--------|----------|
| `↓ MD` | Markdown (`.md`) | Belge haline getirme, paylaşma, GitHub'a yükleme |
| `↓ JSON` | JSON (`.json`) | Program ile işleme, arşivleme, veri analizi |

---

## İlk Kullanım — Adım Adım

### Adım 1 — Sayfayı Açın

```
http://localhost:7860
```

### Adım 2 — Sistemi Kontrol Edin

`⊙ Durum` butonuna tıklayın. Tüm satırlar ✓ göstermelidir.

> Eğer **AI Sağlayıcı ✗** görüyorsanız: Ollama çalışmıyordur.
> ```bash
> ollama serve
> ```

### Adım 3 — İlk Görevi Başlatın

1. `Görevler` sekmesinin açık olduğundan emin olun
2. Görev kutusuna yazın:
   ```
   src/ klasöründeki tüm Python dosyalarını listele ve kısaca özetle
   ```
3. `Başlat` butonuna tıklayın veya `Ctrl+Enter` kullanın

### Adım 4 — Yanıtı İzleyin

- Otomatik olarak `Sohbet` sekmesine geçilir
- SİDAR'ın hangi araçları kullandığını badge'lerden takip edin
- Yanıt üretilirken `■ Durdur` butonu belirir, tıklarsanız durur

### Adım 5 — Sohbete Devam Edin

Yanıt tamamlandıktan sonra alttaki mesaj kutusuna yazarak devam edebilirsiniz:

```
"Şimdi config.py dosyasını da oku"
"Bulduğun sorunları düzelt"
"Bunu Türkçe özetle"
```

---

## Sık Kullanım Senaryoları

### Senaryo 1 — Dosya Okuma ve Düzenleme

```
1. Görev kutusu: "main.py dosyasını oku ve asyncio kullanımını kontrol et"
2. Başlat
3. SİDAR yanıtlar → Sorun bulursa önerir
4. "Önerdiğin düzeltmeleri uygula" diyerek devam et
```

### Senaryo 2 — Web Araması

```
1. Hızlı Görev: "Web araması" → veya
2. Görev kutusu: "FastAPI'nin son sürümünü ara ve changelog'unu özetle"
3. SİDAR DuckDuckGo/Tavily ile arar, sonuçları özetler
```

### Senaryo 3 — Paket Bilgisi

```
1. Hızlı Görev: "PyPI bilgisi" → örnek sorgu
2. Veya görev kutusu: "httpx paketinin son sürümü nedir, chromadb ile uyumlu mu?"
3. SİDAR PyPI API'den gerçek veri getirir
```

### Senaryo 4 — Dosya Ekleme ile Analiz

```
1. 📎 simgesine tıkla → hatalı bir Python dosyası seç
2. Mesaj kutusuna: "Bu dosyadaki hataları bul ve düzelt"
3. Ctrl+Enter ile gönder
4. SİDAR dosyayı okur, hataları analiz eder, düzeltilmiş kodu yazar
```

### Senaryo 5 — Yeni Oturum Açma

```
1. Sol kenar çubuğu → "+ Yeni Sohbet" (veya Ctrl+K)
2. Önceki sohbet sidebar'da kayıtlı kalır
3. Farklı bir konu için temiz slate
```

### Senaryo 6 — Sohbeti Kaydetme

```
1. "↓ MD" → Sohbeti Markdown olarak indir
2. README.md veya döküman olarak kullan
   veya
1. "↓ JSON" → Ham veriyi indir
2. Başka araçlarla işle veya arşivle
```

---

## Olası Sorunlar ve Çözümleri

### Sayfa açılmıyor / bağlanamıyor

```
Kontrol: python web_server.py çalışıyor mu?
Kontrol: http://localhost:7860 doğru mu?
         (7860 .env'de WEB_PORT ile özelleştirilebilir)
```

### SİDAR yanıt vermiyor / "Sağlayıcı bağlantısı yok"

```
→ Durum penceresini açın (⊙ Durum)
→ AI Sağlayıcı ✗ ise:
   ollama serve          # Terminal'de çalıştırın
→ Model ✗ ise:
   ollama pull qwen2.5-coder:7b
```

### Yanıt çok yavaş geliyor

```
→ Durum penceresini açın
→ GPU ✗ ise: .env içinde USE_GPU=true yapın ve sunucuyu yeniden başlatın
→ GPU ✓ ise: .env içinde GPU_MIXED_PRECISION=true deneyin
→ Model olarak daha küçük bir model kullanın: CODING_MODEL=qwen2.5-coder:3b
```

### Bellek doldu uyarısı

```
→ Ctrl+L ile aktif oturum belleğini temizleyin
→ veya + Yeni Sohbet ile temiz oturum açın
→ SİDAR arka planda zaten özetleme yapıyor (40 mesaj eşiğinde)
```

### GitHub bağlantısı yok

```
→ .env dosyasında:
   GITHUB_TOKEN=ghp_...
   GITHUB_REPO=kullanici/depo-adi
→ Token izinleri: repo veya public_repo
→ Sunucuyu yeniden başlatın
```

---

## Hızlı Başvuru Kartı

```
┌───────────────────────────────────────────────────────────────┐
│                  SİDAR WEB ARAYÜZÜ — HIZLI KART               │
├───────────────────────────────────────────────────────────────┤
│  YENİ SOHBET          Ctrl+K   │  DURDUR           Esc        │
│  MESAJ GÖNDER         Ctrl+Enter│  TEMIZLE          Ctrl+L    │
│  TEMA DEĞİŞTİR        Ctrl+T   │  KISA YOLLAR      📊 butonu  │
├───────────────────────────────────────────────────────────────┤
│  DOSYA EKLE           📎       │  DIŞA AKTAR      ↓MD / ↓JSON │
│  SİSTEM DURUMU        ⊙ Durum  │  DAL DEĞİŞTİR    🌿 chip     │
├───────────────────────────────────────────────────────────────┤
│  HIZLI GÖREVLER: Dizin · Sağlık · Denetim · GitHub · Arama    │
│                  PyPI  · Güvenlik · RAG Belgeleri              │
└───────────────────────────────────────────────────────────────┘
```

---

*Bu rehber, `web_ui/index.html` arayüzü ve `web_server.py` backend'ine dayanılarak hazırlanmıştır.*
*SİDAR v2.6.1 · localhost:7860*
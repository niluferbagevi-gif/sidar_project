# Temel imaj olarak hafif Python 3.11 sürümünü kullanıyoruz
FROM python:3.11-slim

# Meta veriler
LABEL maintainer="Sidar AI Project"
LABEL version="2.2.0"
LABEL description="Yazılım Mühendisi AI Asistanı - Docker İzolasyonu"

# Çevresel değişkenler
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    ACCESS_LEVEL=sandbox

# Çalışma dizinini ayarla
WORKDIR /app

# Sistem bağımlılıklarını yükle (Git ve derleme araçları gerekebilir)
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Bağımlılıkları kopyala ve yükle
# Not: environment.yml yerine doğrudan pip paketlerini yüklüyoruz
# Docker için requirements.txt oluşturulması önerilir, ancak burada
# doğrudan kurulum komutu ile ilerliyoruz.
COPY environment.yml .
RUN pip install --upgrade pip && \
    pip install \
    requests \
    python-dotenv \
    psutil \
    GPUtil \
    pynvml \
    ollama \
    google-generativeai \
    PyGithub \
    duckduckgo-search \
    rank-bm25 \
    chromadb \
    sentence-transformers \
    colorama

# Uygulama kodlarını kopyala
COPY . .

# Kalıcı veri dizinlerini oluştur
RUN mkdir -p logs data temp

# Sidar kullanıcısı oluştur (Root olarak çalıştırmamak güvenlik için önemlidir)
RUN useradd -m sidar && \
    chown -R sidar:sidar /app
USER sidar

# Sağlık kontrolü (Opsiyonel)
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
  CMD ps aux | grep "[p]ython main.py" || exit 1

# Başlatma komutu
ENTRYPOINT ["python", "main.py"]
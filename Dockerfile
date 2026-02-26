# Temel imaj olarak hafif Python 3.11 sürümünü kullanıyoruz
FROM python:3.11-slim

# Meta veriler
LABEL maintainer="Sidar AI Project"
LABEL version="2.3.2"
LABEL description="Yazılım Mühendisi AI Asistanı - Docker İzolasyonu"

# Çevresel değişkenler
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    ACCESS_LEVEL=sandbox

# Çalışma dizinini ayarla
WORKDIR /app

# Sistem bağımlılıklarını yükle
# Not: git ve build araçları bazı python paketleri için gereklidir
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Bağımlılık Yönetimi (Environment.yml entegrasyonu)
# 1. environment.yml dosyasını kopyala
COPY environment.yml .

# 2. PyYAML kur (Yaml dosyasını okumak için) ve pip paketlerini ayrıştır
RUN pip install --upgrade pip setuptools wheel pyyaml && \
    python -c "import sys, yaml; \
    deps = yaml.safe_load(open('environment.yml')); \
    pip_deps = next((item['pip'] for item in deps['dependencies'] if isinstance(item, dict) and 'pip' in item), []); \
    print('\n'.join(pip_deps))" > requirements.txt && \
    \
# 3. Ayrıştırılan paketleri kur
    pip install -r requirements.txt

# Uygulama kodlarını kopyala
COPY . .

# Kalıcı veri dizinlerini oluştur
RUN mkdir -p logs data temp

# Sidar kullanıcısı oluştur (Güvenlik için root olmayan kullanıcı)
RUN useradd -m sidar && \
    chown -R sidar:sidar /app
USER sidar

# Web arayüzü için port aç (python web_server.py ile kullanılır)
EXPOSE 7860

# Sağlık kontrolü (CLI veya web sunucusu çalışıyorsa geçer)
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
  CMD ps aux | grep "[p]ython" || exit 1

# Varsayılan başlatma komutu (CLI modu)
# Web arayüzü için: docker run ... python web_server.py
ENTRYPOINT ["python", "main.py"]
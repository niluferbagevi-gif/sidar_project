#!/usr/bin/env bash

# Hata durumunda betiği durdur
set -euo pipefail

PROJECT_NAME="sidar_project"
ENV_NAME="sidar-ai"
# Gerekirse kendi SİDAR repo URL'nizle değiştirin
REPO_URL="https://github.com/niluferbagevi-gif/sidar_project"
PROJECT_DIR="$HOME/$PROJECT_NAME"
MINICONDA_DIR="$HOME/miniconda3"
MINICONDA_SH="$MINICONDA_DIR/miniconda.sh"
OLLAMA_PID=""

cleanup() {
  if [[ -n "${OLLAMA_PID}" ]] && kill -0 "${OLLAMA_PID}" >/dev/null 2>&1; then
    kill "${OLLAMA_PID}" || true
  fi
}
trap cleanup EXIT

print_header() {
  echo "============================================================"
  echo " 🚀 SİDAR - Sıfırdan Ubuntu (WSL) Otomatik Kurulum Aracı"
  echo "============================================================"
}

install_system_packages() {
  echo -e "\n📦 1. Sistem güncelleniyor ve temel Linux paketleri kuruluyor..."
  sudo apt update && sudo apt upgrade -y
  sudo apt install -y curl wget git build-essential software-properties-common zstd
  sudo apt install -y portaudio19-dev python3-pyaudio alsa-utils v4l-utils ffmpeg
}

install_google_chrome() {
  echo -e "\n🌐 1.5. Google Chrome ve bağımlılıkları kuruluyor..."
  wget https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb -O /tmp/chrome.deb
  sudo apt install -y /tmp/chrome.deb
  rm -f /tmp/chrome.deb
  echo "✅ Google Chrome başarıyla kuruldu."
}

install_miniconda() {
  echo -e "\n🐍 2. Miniconda kuruluyor..."
  if [[ ! -d "$MINICONDA_DIR" ]]; then
    mkdir -p "$MINICONDA_DIR"
    wget https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-x86_64.sh -O "$MINICONDA_SH"
    bash "$MINICONDA_SH" -b -u -p "$MINICONDA_DIR"
    rm -f "$MINICONDA_SH"
    "$MINICONDA_DIR/bin/conda" init bash
    echo "✅ Miniconda başarıyla kuruldu."
  else
    echo "✅ Miniconda zaten kurulu."
  fi

  # Conda'yı bu oturumda hemen kullanabilmek için etkinleştiriyoruz
  # shellcheck disable=SC1091
  source "$MINICONDA_DIR/etc/profile.d/conda.sh"
}

install_ollama() {
  echo -e "\n🦙 3. Ollama kuruluyor..."
  if ! ollama -v >/dev/null 2>&1; then
    echo "⚠️ Ollama bulunamadı veya kurulumu bozuk. Yeniden indiriliyor..."
    sudo rm -f /usr/local/bin/ollama
    curl -fsSL https://ollama.com/install.sh | sh
    echo "✅ Ollama başarıyla kuruldu."
  else
    echo "✅ Ollama zaten kurulu ve çalışıyor."
  fi
}

clone_or_update_repo() {
  echo -e "\n🐙 4. SİDAR projesi GitHub'dan çekiliyor..."
  if [[ ! -d "$PROJECT_DIR" ]]; then
    git clone "$REPO_URL" "$PROJECT_DIR"
  else
    echo "⚠️ SİDAR klasörü zaten var. Git pull ile güncelleniyor..."
    git -C "$PROJECT_DIR" pull
  fi
  cd "$PROJECT_DIR"
}

setup_conda_env() {
  echo -e "\n⚙️  5. Conda ortamı ($ENV_NAME) environment.yml dosyasından kuruluyor..."
  if conda info --envs | awk '{print $1}' | grep -qx "$ENV_NAME"; then
    echo "Ortam zaten var, güncelleniyor..."
    conda env update -f environment.yml --prune
  else
    conda env create -f environment.yml
  fi
}

pull_models() {
  echo -e "\n🧠 6. Gerekli yapay zeka modelleri indiriliyor (İnternet hızınıza göre sürebilir)..."
  ollama serve >/dev/null 2>&1 &
  OLLAMA_PID=$!

  echo -e "   Ollama servisi başlatılıyor..."
  local retries=30
  local i=0
  until curl -sf http://localhost:11434/api/tags >/dev/null 2>&1; do
    i=$((i + 1))
    if [[ $i -ge $retries ]]; then
      echo "❌ Ollama 30 saniye içinde yanıt vermedi. Kurulum durduruluyor."
      exit 1
    fi
    sleep 1
  done
  echo "   ✅ Ollama hazır (${i}s)."

  echo "-> nomic-embed-text (RAG embed) indiriliyor..."
  ollama pull nomic-embed-text
  echo "-> qwen2.5-coder:7b (SİDAR varsayılan model) indiriliyor..."
  ollama pull qwen2.5-coder:7b
  echo "-> gemma2:9b (Genel Metin Modeli) indiriliyor..."
  ollama pull gemma2:9b
}

print_footer() {
  echo "============================================================"
  echo "🎉 BÜTÜN KURULUM EKSİKSİZ TAMAMLANDI!"
  echo "============================================================"
  echo "Lütfen yeni ayarların yüklenmesi için terminali kapatıp YENİDEN AÇIN."
  echo ""
  echo "Sonrasında SİDAR'ı çalıştırmak için sırasıyla şunları yazın:"
  echo "  1. cd ~/$PROJECT_NAME"
  echo "  2. conda activate $ENV_NAME"
  echo "  3. cp .env.example .env  (Ayarlarınızı yapmak için)"
  echo "  4. python web_server.py  (Arayüzü başlatmak için)"
  echo "     veya terminal için: python main.py"
  echo "============================================================"
}

download_vendor_libs() {
  echo -e "\n📚 7. Web arayüzü bağımlılıkları yerel olarak indiriliyor (çevrimdışı destek)..."
  local vendor_dir="$PROJECT_DIR/web_ui/vendor"
  mkdir -p "$vendor_dir"

  curl -fsSL "https://cdnjs.cloudflare.com/ajax/libs/highlight.js/11.9.0/styles/github-dark.min.css" \
    -o "$vendor_dir/highlight.min.css"
  curl -fsSL "https://cdnjs.cloudflare.com/ajax/libs/highlight.js/11.9.0/highlight.min.js" \
    -o "$vendor_dir/highlight.min.js"
  curl -fsSL "https://cdn.jsdelivr.net/npm/marked@9.1.6/marked.min.js" \
    -o "$vendor_dir/marked.min.js"

  echo "✅ Vendor kütüphaneleri web_ui/vendor/ dizinine indirildi."
}

print_header
install_system_packages
install_google_chrome
install_miniconda
install_ollama
clone_or_update_repo
setup_conda_env
pull_models
download_vendor_libs
print_footer
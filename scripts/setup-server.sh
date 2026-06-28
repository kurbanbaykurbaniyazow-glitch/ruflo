#!/bin/bash
# Ruflo Video Pipeline — Server Setup
# Ubuntu 22.04 LTS | Run as root

set -e

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; NC='\033[0m'
ok()   { echo -e "${GREEN}✅ $1${NC}"; }
warn() { echo -e "${YELLOW}⚠️  $1${NC}"; }
err()  { echo -e "${RED}❌ $1${NC}"; exit 1; }

echo ""
echo "╔══════════════════════════════════════════╗"
echo "║   Ruflo Video Pipeline — Server Setup   ║"
echo "╚══════════════════════════════════════════╝"
echo ""

# ── 1. System Update ──────────────────────────────────────────
echo "[1/7] Обновление системы..."
apt-get update -y -q
apt-get upgrade -y -q
ok "Система обновлена"

# ── 2. System Dependencies ────────────────────────────────────
echo "[2/7] Установка системных пакетов..."
apt-get install -y -q \
    python3.11 python3.11-venv python3-pip \
    git curl wget unzip \
    ffmpeg \
    flite libflite-dev \
    fonts-ubuntu fonts-liberation2 fonts-dejavu-core \
    fonts-noto-color-emoji \
    supervisor \
    nodejs npm \
    build-essential
ok "Системные пакеты установлены"

# ── 3. App Directory ──────────────────────────────────────────
echo "[3/7] Создание директорий..."
mkdir -p /opt/ruflo
mkdir -p /tmp/content-automation
mkdir -p /tmp/pixabay-music
mkdir -p /var/log/ruflo
ok "Директории созданы"

# ── 4. Clone Repository ───────────────────────────────────────
echo "[4/7] Загрузка кода..."
cd /opt/ruflo

if [ -d ".git" ]; then
    warn "Репозиторий уже существует, обновляем..."
    git pull origin claude/ai-agents-content-automation-fbwwbg 2>/dev/null || true
else
    # Prompt for GitHub token if repo is private
    echo ""
    echo "Введи GitHub токен (Personal Access Token) для доступа к репозиторию:"
    echo "Получить: https://github.com/settings/tokens/new (выбери 'repo')"
    read -s -p "Token: " GITHUB_TOKEN
    echo ""

    if [ -n "$GITHUB_TOKEN" ]; then
        git clone --branch claude/ai-agents-content-automation-fbwwbg \
            "https://${GITHUB_TOKEN}@github.com/kurbanbaykurbaniyazow-glitch/ruflo.git" . \
            || err "Не удалось клонировать репозиторий. Проверь токен."
    else
        err "Токен не введён"
    fi
fi
ok "Код загружен"

# ── 5. Python Environment ─────────────────────────────────────
echo "[5/7] Настройка Python окружения..."
python3.11 -m venv /opt/ruflo/venv
source /opt/ruflo/venv/bin/activate

pip install --upgrade pip -q
pip install -q \
    numpy \
    pillow \
    imageio \
    imageio-ffmpeg \
    anthropic \
    langgraph \
    requests \
    python-dotenv \
    openai \
    fastapi \
    uvicorn \
    httpx

ok "Python пакеты установлены"

# ── 6. Environment File ───────────────────────────────────────
echo "[6/7] Настройка .env файла..."

if [ ! -f /opt/ruflo/.env ]; then
    cat > /opt/ruflo/.env << 'ENVEOF'
# ═══ API Ключи ════════════════════════════════════
ANTHROPIC_API_KEY=
PEXELS_API_KEY=G1Zva1QCdGKn62GJL9OApI96P2HQ6WbPh4MCy67ooPs2SzFqyxZThLv0
OPENAI_API_KEY=
ELEVENLABS_API_KEY=
MUBERT_API_KEY=

# ═══ Видео настройки ══════════════════════════════
VIDEO_OUTPUT_DIR=/var/data/ruflo-videos
BRAND_HANDLE=@AIInsiderDaily
MUSIC_LIBRARY_DIR=/tmp/pixabay-music

# ═══ YouTube ══════════════════════════════════════
YOUTUBE_CLIENT_ID=
YOUTUBE_CLIENT_SECRET=
YOUTUBE_REFRESH_TOKEN=
ENVEOF

    warn ".env создан. Заполни ключи: nano /opt/ruflo/.env"
else
    ok ".env уже существует"
fi

mkdir -p /var/data/ruflo-videos

# ── 7. Systemd Service ────────────────────────────────────────
echo "[7/7] Настройка автозапуска..."

cat > /etc/systemd/system/ruflo-pipeline.service << 'SVCEOF'
[Unit]
Description=Ruflo Video Generation Pipeline
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/opt/ruflo
Environment=PATH=/opt/ruflo/venv/bin:/usr/bin:/bin
ExecStart=/opt/ruflo/venv/bin/python scripts/test-viral-video.py
Restart=no
StandardOutput=append:/var/log/ruflo/pipeline.log
StandardError=append:/var/log/ruflo/pipeline.log

[Install]
WantedBy=multi-user.target
SVCEOF

systemctl daemon-reload
ok "Сервис настроен"

# ── Cron для автоматической генерации (3 видео в день) ────────
crontab -l 2>/dev/null | grep -v ruflo > /tmp/crontab_backup || true
echo "0 8  * * * cd /opt/ruflo && /opt/ruflo/venv/bin/python scripts/test-viral-video.py >> /var/log/ruflo/cron.log 2>&1" >> /tmp/crontab_backup
echo "0 14 * * * cd /opt/ruflo && /opt/ruflo/venv/bin/python scripts/test-viral-video.py >> /var/log/ruflo/cron.log 2>&1" >> /tmp/crontab_backup
echo "0 20 * * * cd /opt/ruflo && /opt/ruflo/venv/bin/python scripts/test-viral-video.py >> /var/log/ruflo/cron.log 2>&1" >> /tmp/crontab_backup
crontab /tmp/crontab_backup
ok "Cron настроен (3 видео/день: 8:00, 14:00, 20:00)"

# ── Final Test ────────────────────────────────────────────────
echo ""
echo "╔══════════════════════════════════════════╗"
echo "║         Установка завершена! ✅          ║"
echo "╚══════════════════════════════════════════╝"
echo ""
echo "📝 Следующие шаги:"
echo ""
echo "1. Заполни API ключи:"
echo "   nano /opt/ruflo/.env"
echo ""
echo "2. Запусти тест:"
echo "   cd /opt/ruflo && source venv/bin/activate"
echo "   python scripts/test-viral-video.py"
echo ""
echo "3. Видео будут сохраняться в:"
echo "   /var/data/ruflo-videos/"
echo ""
echo "4. Логи:"
echo "   tail -f /var/log/ruflo/pipeline.log"
echo ""

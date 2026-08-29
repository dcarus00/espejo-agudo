#!/usr/bin/env bash
# ============================================================
# Espejo Agudo - Script de instalación (Debian 12+ / Linux)
# Instala dependencias del sistema, Ollama + modelo, Qdrant,
# entorno virtual de Python y dependencias del bridge WhatsApp.
# ============================================================
set -e

echo "=========================================="
echo " Espejo Agudo - Instalación"
echo "=========================================="
echo ""
echo " ANTES DE EMPEZAR:"
echo " Vas a necesitar un TELEGRAM_TOKEN para configurar el bot."
echo " Si todavía no lo tenés, crealo ahora con @BotFather en"
echo " Telegram (comando /newbot) y guardalo: te lo va a pedir"
echo " al final de la instalación, al configurar el archivo .env."
echo ""
echo " La instalación puede continuar sin el token; solo lo"
echo " necesitás antes de arrancar."
echo ""

# --- 1. Dependencias del sistema ---
echo "[1/6] Actualizando paquetes e instalando dependencias del sistema..."
sudo apt update
sudo apt install -y curl git python3 python3-venv python3-pip ffmpeg docker.io docker-compose npm
echo "      Dependencias del sistema instaladas."

# --- 2. Ollama ---
echo "[2/6] Verificando Ollama..."
if command -v ollama >/dev/null 2>&1; then
  echo "      Ollama ya está instalado."
else
  echo "      Instalando Ollama..."
  curl -fsSL https://ollama.com/install.sh | sh
  echo "      Ollama instalado."
fi

# Asegurar que el servidor de Ollama esté corriendo para poder descargar el modelo.
if curl -fsS http://localhost:11434/api/tags >/dev/null 2>&1; then
  echo "      El servidor de Ollama ya está corriendo."
elif pgrep -x ollama >/dev/null 2>&1; then
  echo "      Hay un proceso de Ollama activo pero no responde todavía; esperando..."
else
  echo "      Iniciando servidor de Ollama en segundo plano..."
  ollama serve >/dev/null 2>&1 &
fi

# Esperar a que Ollama responda (hasta 60 segundos).
espera=0
until curl -fsS http://localhost:11434/api/tags >/dev/null 2>&1; do
  sleep 3
  espera=$((espera + 3))
  if [ "$espera" -ge 60 ]; then
    echo "      ERROR: Ollama no responde después de 60 segundos."
    echo "      Verificá manualmente con: ollama serve"
    exit 1
  fi
done
echo "      Ollama respondiendo correctamente."

echo "      Descargando modelo qwen2.5:14b (esto puede tardar bastante)..."
ollama pull qwen2.5:14b
echo "      Modelo descargado."

# --- 3. Qdrant (Docker) ---
echo "[3/6] Levantando Qdrant con Docker Compose..."

# Verificar permisos de Docker antes de intentar levantar el contenedor.
if docker ps >/dev/null 2>&1; then
  DOCKER="docker"
elif sudo docker ps >/dev/null 2>&1; then
  DOCKER="sudo docker"
  echo "      (usando sudo para Docker; ver nota al final para evitarlo)"
else
  echo "      ERROR: no se pudo acceder al daemon de Docker ni con sudo."
  echo "      Verificá que Docker esté instalado y corriendo:"
  echo "        sudo systemctl status docker"
  exit 1
fi

if $DOCKER compose version >/dev/null 2>&1; then
  $DOCKER compose up -d
else
  # Fallback a docker-compose (guion) en instalaciones viejas.
  if [ "$DOCKER" = "docker" ]; then
    docker-compose up -d
  else
    sudo docker-compose up -d
  fi
fi
echo "      Qdrant corriendo en el puerto 6333."

# --- 4. Entorno virtual de Python ---
echo "[4/6] Creando entorno virtual e instalando dependencias de Python..."
if [ ! -d venv ]; then
  python3 -m venv venv
fi
# shellcheck disable=SC1091
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
echo "      Dependencias de Python instaladas."

# --- 5. Bridge de WhatsApp ---
echo "[5/6] Instalando dependencias del bridge de WhatsApp (Node.js)..."
cd whatsapp-bridge
npm install
cd ..
echo "      Bridge de WhatsApp listo."

# --- 6. Instrucciones finales ---
echo "[6/6] Instalación completa."
echo ""
echo "=========================================="
echo " Próximos pasos:"
echo "=========================================="
echo " 1. Copiá los archivos de configuración y completalos:"
echo "      cp .env.example .env"
echo "      cp system_prompt.example.md system_prompt.md"
echo "      nano .env   # al menos TELEGRAM_TOKEN (de @BotFather)"
echo ""
echo " 2. Iniciá el núcleo (Telegram + API + scheduler):"
echo "      ./start.sh"
echo ""
echo " 3. En otra terminal, iniciá el bridge de WhatsApp:"
echo "      cd whatsapp-bridge && node index.js"
echo "    Escaneá el QR que aparece en consola con tu celular"
echo "    (WhatsApp > Dispositivos vinculados)."
echo ""
echo " Nota: si tu usuario no está en el grupo docker, ejecutá:"
echo "      sudo usermod -aG docker \$USER"
echo "    y volvé a iniciar sesión para no necesitar sudo."

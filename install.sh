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
if ! curl -fsS http://localhost:11434/api/tags >/dev/null 2>&1; then
  echo "      Iniciando servidor de Ollama en segundo plano..."
  ollama serve >/dev/null 2>&1 &
  sleep 5
fi

echo "      Descargando modelo qwen2.5:14b (esto puede tardar bastante)..."
ollama pull qwen2.5:14b
echo "      Modelo descargado."

# --- 3. Qdrant (Docker) ---
echo "[3/6] Levantando Qdrant con Docker Compose..."
docker compose up -d || docker-compose up -d
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
echo " 1. Copiá el archivo de configuración y completalo:"
echo "      cp .env.example .env"
echo "      nano .env   # al menos TELEGRAM_TOKEN"
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
echo "    y volvé a iniciar sesión."

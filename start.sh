#!/usr/bin/env bash
# ============================================================
# Espejo Agudo - Script de arranque del núcleo (Python).
#
# NOTA: el bridge de WhatsApp corre en un proceso aparte.
#       Abrí otra terminal y ejecutá:
#         cd whatsapp-bridge && node index.js
# ============================================================
set -e

cd "$(dirname "$0")"

# Verificar que existe el archivo de configuración.
if [ ! -f .env ]; then
  echo "ERROR: no existe el archivo .env"
  echo "Copiá el ejemplo y completalo:"
  echo "  cp .env.example .env"
  echo "  nano .env   # al menos TELEGRAM_TOKEN"
  exit 1
fi

# Cargar variables de entorno (ignorando comentarios).
export $(grep -v '^#' .env | xargs)

# Verificar que existe el entorno virtual.
if [ ! -d venv ]; then
  echo "ERROR: no existe el entorno virtual 'venv'."
  echo "Ejecutá primero ./install.sh"
  exit 1
fi

# Activar el entorno virtual.
# shellcheck disable=SC1091
source venv/bin/activate

echo "Iniciando Espejo Agudo (núcleo)..."
echo "Recordá: el bridge de WhatsApp corre aparte con: cd whatsapp-bridge && node index.js"
python espejo_agudo/main.py

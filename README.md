# Espejo Agudo

Un segundo cerebro digital 100% local y autohospedado. No busca agradarte: busca ser útil. No dice "buenos días", no desea suerte, no usa emojis, no finge empatía. Existe para reducir la fricción entre lo que decís que querés y lo que hacés.

Corre enteramente en tu máquina (Debian/Linux): el razonamiento, la memoria y la transcripción de voz son locales. Las únicas conexiones externas son Telegram y WhatsApp, usados exclusivamente como canal de mensajería.

## Requisitos del sistema

**Sistema operativo**
- Debian 12+ (o cualquier Linux con systemd: Ubuntu 22.04+, etc.)

**Hardware**
- CPU: 4 núcleos mínimo (no requiere GPU; todo corre en CPU, incluido Whisper en int8)
- RAM: 8 GB mínimo, 16 GB recomendados (el modelo Qwen 2.5 14B ocupa ~9 GB en RAM)
- Almacenamiento: ~15 GB libres (modelo LLM ~9 GB + Whisper ~1-2 GB + dependencias)

**Software** (lo instala `install.sh` automáticamente)
- Docker y Docker Compose
- Python 3.10+ y pip
- Node.js 18+ y npm (solo si usás WhatsApp)
- ffmpeg (para Whisper)

## Características distintivas

1. **No es un amigo, es un segundo cerebro.** Sin saludos, sin emojis, sin adulación. Responde con la verdad incómoda cuando hace falta.
2. **Memoria semántica persistente.** Todo lo que le contás queda guardado como embeddings vectoriales en Qdrant. Si hace semanas mencionaste un problema y hoy decís "estoy estresado", recupera el contexto sin que se lo recuerdes.
3. **Proactividad aleatoria inteligente.** No envía mensajes cada N horas. Elige momentos aleatorios dentro de una ventana diaria (9:00 a 21:00), revisa la memoria reciente y solo escribe si detecta una acción pendiente, una contradicción o un patrón de evasión. Si no hay nada útil que decir, responde internamente `SILENCIO` y no molesta.
4. **Recordatorios antes de compromisos.** Detecta automáticamente fechas y horas en tus mensajes (entrevistas, citas, plazos) usando el propio LLM como extractor, y programa recordatorios entre 30 y 90 minutos antes del evento. No para desearte suerte: para preguntarte si preparaste lo necesario.
5. **Voz local.** Recibe audios por Telegram y WhatsApp, los transcribe localmente con Whisper (sin conexión a internet), los guarda en memoria y responde como texto. Los audios se borran inmediatamente después de transcribir.
6. **Multiplataforma.** Telegram (API oficial, estable, texto y voz) y WhatsApp (vía whatsapp-web.js, no oficial, texto y voz).
7. **Tres registros de interacción automáticos:**
   - **Escucha fría:** cuando reportás una falla real sin excusas, responde con contención mínima: "Entendido. Contame cuando puedas."
   - **Pregunta de apertura:** cuando estás confundido pero no evadiendo: "¿Qué parte de esto te angustia más?"
   - **Pinchazo:** cuando tenés recursos pero evadís un patrón conocido: "Evadiste esto. ¿Por qué?" Señala una sola vez, sin insistir.

## Arquitectura

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│   Telegram      │     │   WhatsApp      │     │   Scheduler     │
│   (texto/voz)   │     │   (texto/voz)   │     │   (proactivo)   │
└────────┬────────┘     └────────┬────────┘     └────────┬────────┘
         │                       │                       │
         └───────────────────────┼───────────────────────┘
                                 │
                    ┌─────────────▼─────────────┐
                    │      FastAPI (Python)     │
                    │    Espejo Agudo Core      │
                    └─────────────┬─────────────┘
                                  │
        ┌─────────────────────────┼─────────────────────────┐
        │                         │                         │
┌───────▼────────┐    ┌──────────▼──────────┐    ┌────────▼───────┐
│    Qdrant      │    │      Ollama         │    │    Whisper     │
│  (memoria      │    │   (Qwen 2.5 14B)    │    │  (transcripción│
│   vectorial)   │    │   (razonamiento)    │    │     local)     │
└────────────────┘    └─────────────────────┘    └────────────────┘
```

## Stack tecnológico

- **Python 3.10+** — backend (FastAPI + Uvicorn, APScheduler, python-telegram-bot)
- **Node.js 18+** — bridge de WhatsApp (whatsapp-web.js + Express)
- **Ollama** con **Qwen 2.5 14B** — razonamiento local
- **Qdrant** (Docker) — memoria vectorial
- **sentence-transformers** (all-MiniLM-L6-v2) — embeddings (384 dimensiones)
- **faster-whisper** (small/medium, CPU, int8) — transcripción de voz local
- **python-dotenv** — configuración por variables de entorno

## Instalación

```bash
git clone https://github.com/dcarus00/espejo-agudo.git
cd espejo-agudo
chmod +x install.sh start.sh
./install.sh
```

`install.sh` se encarga de todo:

1. Actualiza el sistema e instala dependencias (curl, git, python3, venv, ffmpeg, docker, docker-compose, npm).
2. Instala Ollama si no existe y descarga el modelo `qwen2.5:14b`.
3. Levanta Qdrant con Docker Compose.
4. Crea el entorno virtual de Python e instala `requirements.txt`.
5. Instala las dependencias del bridge de WhatsApp (`npm install`).

## Configuración

```bash
cp .env.example .env
nano .env
```

Variables disponibles:

| Variable | Descripción | Default |
|---|---|---|
| `TELEGRAM_TOKEN` | Token del bot de Telegram (@BotFather) | — (requerida) |
| `OLLAMA_URL` | Endpoint de la API de Ollama | `http://localhost:11434/api/generate` |
| `OLLAMA_MODEL` | Modelo de Ollama | `qwen2.5:14b` |
| `QDRANT_HOST` | Host de Qdrant | `localhost` |
| `QDRANT_PORT` | Puerto de Qdrant | `6333` |
| `COLLECTION_NAME` | Colección de memoria vectorial | `espejo_agudo` |
| `WHISPER_MODEL` | Modelo de Whisper (`tiny`/`base`/`small`/`medium`) | `small` |
| `WHATSAPP_BRIDGE_URL` | Endpoint /send del bridge | `http://localhost:3000/send` |
| `HORA_INICIO` | Inicio de la ventana proactiva | `9` |
| `HORA_FIN` | Fin de la ventana proactiva | `21` |

## Arranque

Núcleo (Telegram + API + scheduler):

```bash
./start.sh
```

Bridge de WhatsApp, en otra terminal:

```bash
cd whatsapp-bridge && node index.js
```

La primera vez, escaneá el código QR que aparece en consola con tu celular (WhatsApp > Dispositivos vinculados). La sesión queda persistida en `whatsapp-bridge/session/` y el último QR se guarda en `whatsapp-bridge/last-qr.txt`.

## Privacidad

Todo corre local. El razonamiento (Ollama), la memoria (Qdrant) y la transcripción de voz (Whisper en CPU) nunca salen de tu máquina. Los audios se borran inmediatamente después de transcribirse. No hay telemetría, no hay analytics, no hay servidores de terceros procesando tus datos.

## Advertencia sobre WhatsApp

El bridge usa **whatsapp-web.js**, una librería **no oficial** que automatiza WhatsApp Web. Meta puede banear el número aunque el riesgo es bajo para uso personal. Se recomienda usar un número secundario. Telegram es 100% seguro (API oficial de bots).

## ¿Por qué Qwen 2.5 14B?

Porque es el punto justo para este proyecto: respeta system prompts estrictos (fundamental para que el espejo no se ablande), tiene español nativo de buena calidad y es directo. Gemma resulta demasiado "segura" y aduladora; Llama 3 tiende a la terapia barata. El espejo agudo no juzga, señala: la diferencia entre "otra vez no hiciste nada" (juzgar) y "dijiste A, hiciste B, ¿patrón o excepción?" (señalar) es vital.

## Licencia

MIT — Copyright (c) 2026 Diego Caruso. Ver [LICENSE](LICENSE).

## Autor

Diego Caruso — [github.com/dcarus00](https://github.com/dcarus00)

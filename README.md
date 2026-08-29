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
2. **Onboarding conversacional.** La primera vez que le escribís, el espejo se presenta (con su personalidad intacta: directo, sin emojis, sin adulación) y te entrevista para conocer tu vida: en qué trabajás o qué buscás, qué proyectos tenés, qué compromisos manejás y qué patrones querés que te señale. Con tus respuestas construye tu base de conocimiento; cuando tiene el panorama, cierra con un resumen y pasa a modo espejo. Sin formularios ni configuración manual del perfil.
3. **Memoria semántica persistente.** Todo lo que le contás queda guardado como embeddings vectoriales en Qdrant. Si hace semanas mencionaste un problema y hoy decís "estoy estresado", recupera el contexto sin que se lo recuerdes.
4. **Proactividad aleatoria inteligente.** No envía mensajes cada N horas. Elige momentos aleatorios dentro de una ventana diaria (9:00 a 21:00), revisa la memoria reciente y solo escribe si detecta una acción pendiente, una contradicción o un patrón de evasión. Si no hay nada útil que decir, responde internamente `SILENCIO` y no molesta.
5. **Recordatorios antes de compromisos.** Detecta automáticamente fechas y horas en tus mensajes (entrevistas, citas, plazos) usando el propio LLM como extractor, y programa recordatorios entre 30 y 90 minutos antes del evento. No para desearte suerte: para preguntarte si preparaste lo necesario.
6. **Voz local.** Recibe audios por Telegram y WhatsApp, los transcribe localmente con Whisper (sin conexión a internet), los guarda en memoria y responde como texto. Los audios se borran inmediatamente después de transcribir.
7. **Multiplataforma.** Telegram (API oficial, estable, texto y voz) y WhatsApp (vía whatsapp-web.js, no oficial, texto y voz).
8. **Tres registros de interacción automáticos:**
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
cp system_prompt.example.md system_prompt.md
nano .env
nano system_prompt.md
```

**Nota:** el system prompt no está en el código. Vive en `system_prompt.md` (ignorado por git) y define la personalidad del espejo — dejala como está. El contexto personal (proyectos, compromisos) **ya no hace falta cargarlo a mano**: el espejo lo construye solo en la entrevista inicial del primer mensaje. Si preferís precargar contexto, podés editar la sección `MIS PROYECTOS Y CONTEXTO` del archivo.

Variables disponibles:

| Variable | Descripción | Default |
|---|---|---|
| `TELEGRAM_TOKEN` | Token del bot de Telegram (@BotFather) | — (requerida) |
| `SYSTEM_PROMPT_FILE` | Archivo del system prompt | `system_prompt.md` |
| `OLLAMA_URL` | Endpoint de la API de Ollama | `http://localhost:11434/api/generate` |
| `OLLAMA_MODEL` | Modelo de Ollama | `qwen2.5:14b` |
| `QDRANT_HOST` | Host de Qdrant | `localhost` |
| `QDRANT_PORT` | Puerto de Qdrant | `6333` |
| `COLLECTION_NAME` | Colección de memoria vectorial | `espejo_agudo` |
| `WHISPER_MODEL` | Modelo de Whisper (`tiny`/`base`/`small`/`medium`) | `small` |
| `WHATSAPP_BRIDGE_URL` | Endpoint /send del bridge | `http://localhost:3000/send` |
| `HORA_INICIO` | Inicio de la ventana proactiva | `9` |
| `HORA_FIN` | Fin de la ventana proactiva | `21` |
| `ALLOWED_TELEGRAM_IDS` | IDs de Telegram autorizados (vacío = todos) | — (recomendado) |
| `ALLOWED_WHATSAPP_NUMBERS` | Números de WhatsApp autorizados (vacío = todos) | — (recomendado) |

## Cómo conectar tus cuentas

El espejo no tiene usuarios predefinidos: te registrás automáticamente la primera vez que le escribís. A partir de ese momento ya puede responderte y enviarte mensajes proactivos. Pero primero hay que crear las cuentas del lado de cada plataforma.

### Telegram (obligatorio para el núcleo)

1. **Crear el bot:** en Telegram, hablale a [@BotFather](https://t.me/BotFather), enviá `/newbot` y seguí los pasos (nombre y username). BotFather te da un **token**.
2. **Configurar el token:** pegalo en `.env` como `TELEGRAM_TOKEN=...`.
3. **Restringir el acceso (recomendado):** hablale a [@userinfobot](https://t.me/userinfobot) para conocer tu ID numérico y ponelo en `.env` como `ALLOWED_TELEGRAM_IDS=123456789`. Sin esto, cualquier persona que encuentre el bot por su username podría hablarle y ensuciar la memoria.
4. **Escribirle:** arrancá el núcleo (`./start.sh`), buscá tu bot en Telegram por su username y enviale cualquier mensaje. Quedás registrado y el espejo ya te puede escribir a vos.

Nota: el bot de Telegram **no puede iniciar conversaciones** con usuarios que nunca le escribieron (limitación de la plataforma). Por eso el primer mensaje siempre lo tenés que enviar vos.

### WhatsApp (opcional, vía bridge no oficial)

1. **El bridge usa un número propio:** al escanear el QR, el bridge inicia sesión con el número de ese celular. Recomendación fuerte: usá un **número secundario** dedicado al espejo (un chip prepago alcanza), no tu número personal. Meta puede banear números por uso no oficial; el riesgo es bajo en uso personal pero existe.
2. **Vincular:** `cd whatsapp-bridge && node index.js`, escaneá el QR con WhatsApp > Dispositivos vinculados.
3. **Cómo te escribe:** le hablás **al número del bridge** desde tu WhatsApp personal, como a cualquier contacto. El espejo te responde desde ese número.
4. **Restringir el acceso:** poné tu número personal en `.env` como `ALLOWED_WHATSAPP_NUMBERS=59899123456@c.us` (código de país + número, sin `+`). Así, si otra persona escribe al número del bridge, el espejo la ignora.

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

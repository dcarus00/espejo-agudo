/**
 * Bridge de WhatsApp para Espejo Agudo.
 *
 * Usa whatsapp-web.js (no oficial) con LocalAuth para persistir la sesión.
 * Recibe mensajes de texto y notas de voz y los reenvía al core FastAPI
 * (http://localhost:8000). Expone POST /send para enviar mensajes salientes.
 */

const { Client, LocalAuth, MessageTypes } = require('whatsapp-web.js');
const express = require('express');
const fs = require('fs');
const path = require('path');

// qrcode-terminal es opcional: si está instalado muestra el QR en consola.
let qrcodeTerminal = null;
try {
  qrcodeTerminal = require('qrcode-terminal');
} catch (e) {
  console.warn('[bridge] qrcode-terminal no instalado; el QR solo se guardará en last-qr.txt');
}

const CORE_URL = process.env.ESPEJO_CORE_URL || 'http://localhost:8000';
const BRIDGE_PORT = parseInt(process.env.WHATSAPP_BRIDGE_PORT || '3000', 10);
const QR_FILE = path.join(__dirname, 'last-qr.txt');

const client = new Client({
  authStrategy: new LocalAuth({ dataPath: path.join(__dirname, 'session') }),
  puppeteer: {
    headless: true,
    args: ['--no-sandbox', '--disable-setuid-sandbox'],
  },
});

client.on('qr', (qr) => {
  try {
    fs.writeFileSync(QR_FILE, qr + '\n', 'utf8');
    console.log(`[bridge] QR guardado en ${QR_FILE}`);
  } catch (err) {
    console.error('[bridge] Error guardando QR en archivo:', err.message);
  }
  if (qrcodeTerminal) {
    qrcodeTerminal.generate(qr, { small: true });
  }
  console.log('[bridge] Escaneá el QR con WhatsApp (Dispositivos vinculados).');
});

client.on('ready', () => {
  console.log('[bridge] Cliente de WhatsApp listo y autenticado.');
});

client.on('auth_failure', (msg) => {
  console.error('[bridge] Falla de autenticación:', msg);
});

client.on('disconnected', (reason) => {
  console.warn('[bridge] Cliente desconectado:', reason);
});

async function postToCore(endpoint, payload) {
  const url = `${CORE_URL}${endpoint}`;
  const res = await fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  if (!res.ok) {
    const text = await res.text().catch(() => '');
    throw new Error(`Core respondió ${res.status}: ${text}`);
  }
}

client.on('message_create', async (msg) => {
  try {
    if (msg.fromMe) return;

    if (msg.type === MessageTypes.TEXT || msg.type === 'chat') {
      console.log(`[bridge] Texto de ${msg.from}: ${msg.body}`);
      await postToCore('/whatsapp', {
        from: msg.from,
        body: msg.body,
        timestamp: msg.timestamp,
        type: 'text',
      });
      return;
    }

    if (msg.type === MessageTypes.VOICE || msg.type === 'ptt') {
      console.log(`[bridge] Nota de voz de ${msg.from}, descargando media...`);
      const media = await msg.downloadMedia();
      if (!media || !media.data) {
        console.warn('[bridge] No se pudo descargar el audio (media vacío).');
        return;
      }
      const mimetype = media.mimetype || 'audio/ogg';
      const ext = (mimetype.split('/')[1] || 'ogg').split(';')[0];
      const filename = media.filename || `voice_${msg.timestamp}.${ext}`;
      await postToCore('/whatsapp-voice', {
        from: msg.from,
        timestamp: msg.timestamp,
        type: 'voice',
        filename,
        mimetype,
        data: media.data, // base64
      });
      console.log(`[bridge] Audio de ${msg.from} enviado al core (${filename}).`);
      return;
    }

    // Otros tipos (imágenes, stickers, etc.) se ignoran.
  } catch (err) {
    console.error('[bridge] Error procesando mensaje entrante:', err.message);
  }
});

// --- API Express para mensajes salientes ---
const app = express();
app.use(express.json({ limit: '50mb' }));

app.post('/send', async (req, res) => {
  const { to, body } = req.body || {};
  if (!to || !body) {
    return res.status(400).json({ error: 'Se requieren los campos "to" y "body".' });
  }
  try {
    await client.sendMessage(to, body);
    console.log(`[bridge] Mensaje enviado a ${to}`);
    res.json({ ok: true });
  } catch (err) {
    console.error(`[bridge] Error enviando mensaje a ${to}:`, err.message);
    res.status(500).json({ error: err.message });
  }
});

app.listen(BRIDGE_PORT, () => {
  console.log(`[bridge] Endpoint /send escuchando en http://localhost:${BRIDGE_PORT}/send`);
});

console.log('[bridge] Inicializando cliente de WhatsApp...');
client.initialize();

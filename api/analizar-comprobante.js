/**
 * /api/analizar-comprobante — Analiza foto de comprobante de apuesta con Claude
 *
 * POST /api/analizar-comprobante
 * Body (JSON):
 *   {
 *     "image": "<base64>",          // imagen en base64 (sin prefijo data:...)
 *     "mediaType": "image/jpeg"     // "image/jpeg" | "image/png" | "image/webp" | "image/gif"
 *   }
 *
 * Respuesta:
 *   {
 *     "ok": true,
 *     "apuesta": {
 *       "casa": "Bet365",
 *       "fecha": "2025-06-13",
 *       "monto_apostado": 150.00,
 *       "cuota": 2.50,
 *       "ganancia_potencial": 375.00,
 *       "deporte": "Fútbol",
 *       "evento": "Real Madrid vs Barcelona",
 *       "seleccion": "Real Madrid gana",
 *       "estado": "Pendiente | Ganada | Perdida",
 *       "id_apuesta": "ABC123",
 *       "notas": "..."
 *     },
 *     "resumen": "Texto legible del análisis"
 *   }
 */

const ANTHROPIC_API = "https://api.anthropic.com/v1/messages";

const SYSTEM_PROMPT = `Eres un asistente especializado en analizar comprobantes y tickets de apuestas deportivas.
Tu tarea es extraer toda la información relevante de la imagen del comprobante y devolverla en formato JSON estricto.

SIEMPRE responde ÚNICAMENTE con un objeto JSON válido, sin texto adicional antes ni después.
Si no puedes leer algún campo, usa null para ese campo.
Los montos deben ser números (no strings).`;

const USER_PROMPT = `Analiza este comprobante de apuesta y extrae toda la información en el siguiente formato JSON exacto:

{
  "casa": "nombre de la casa de apuestas (ej: Bet365, Codere, Betano, 1xBet, etc.)",
  "fecha": "fecha de la apuesta en formato YYYY-MM-DD o null",
  "monto_apostado": número o null,
  "cuota": número o null,
  "ganancia_potencial": número o null,
  "deporte": "Fútbol, Básquetbol, Béisbol, etc. o null",
  "evento": "nombre del partido o evento apostado",
  "seleccion": "qué selección/pronóstico se hizo (ej: Local gana, +2.5 goles, etc.)",
  "estado": "Pendiente, Ganada, Perdida, Anulada o null si no se ve",
  "id_apuesta": "ID o número de ticket si aparece, o null",
  "moneda": "MXN, USD, EUR, etc. o null",
  "notas": "cualquier información adicional relevante del ticket"
}

Responde SOLO con el JSON, sin explicaciones.`;

async function callClaude(base64Image, mediaType) {
  const apiKey = process.env.ANTHROPIC_API_KEY;
  if (!apiKey) throw new Error("ANTHROPIC_API_KEY no configurada");

  const body = {
    model: "claude-opus-4-8",
    max_tokens: 1024,
    system: SYSTEM_PROMPT,
    messages: [
      {
        role: "user",
        content: [
          {
            type: "image",
            source: {
              type: "base64",
              media_type: mediaType,
              data: base64Image,
            },
          },
          {
            type: "text",
            text: USER_PROMPT,
          },
        ],
      },
    ],
  };

  const res = await fetch(ANTHROPIC_API, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "x-api-key": apiKey,
      "anthropic-version": "2023-06-01",
    },
    body: JSON.stringify(body),
  });

  if (!res.ok) {
    const err = await res.text();
    throw new Error(`Claude API ${res.status}: ${err}`);
  }

  const data = await res.json();
  const text = data?.content?.[0]?.text ?? "";
  return text;
}

function buildResumen(apuesta) {
  const lineas = [];

  if (apuesta.casa)            lineas.push(`🏠 Casa: ${apuesta.casa}`);
  if (apuesta.fecha)           lineas.push(`📅 Fecha: ${apuesta.fecha}`);
  if (apuesta.evento)          lineas.push(`⚽ Evento: ${apuesta.evento}`);
  if (apuesta.seleccion)       lineas.push(`🎯 Selección: ${apuesta.seleccion}`);
  if (apuesta.monto_apostado != null) {
    const moneda = apuesta.moneda ?? "";
    lineas.push(`💰 Monto apostado: ${moneda} ${apuesta.monto_apostado}`);
  }
  if (apuesta.cuota != null)   lineas.push(`📊 Cuota: ${apuesta.cuota}`);
  if (apuesta.ganancia_potencial != null) {
    const moneda = apuesta.moneda ?? "";
    lineas.push(`🤑 Ganancia potencial: ${moneda} ${apuesta.ganancia_potencial}`);
  }
  if (apuesta.estado)          lineas.push(`✅ Estado: ${apuesta.estado}`);
  if (apuesta.id_apuesta)      lineas.push(`🎫 Ticket ID: ${apuesta.id_apuesta}`);
  if (apuesta.notas)           lineas.push(`📝 Notas: ${apuesta.notas}`);

  return lineas.join("\n");
}

export default async function handler(req, res) {
  res.setHeader("Access-Control-Allow-Origin", "*");
  res.setHeader("Access-Control-Allow-Methods", "POST, OPTIONS");
  res.setHeader("Access-Control-Allow-Headers", "Content-Type");

  if (req.method === "OPTIONS") return res.status(204).end();
  if (req.method !== "POST") return res.status(405).json({ error: "Método no permitido. Usa POST." });

  let body;
  try {
    body = typeof req.body === "string" ? JSON.parse(req.body) : req.body;
  } catch {
    return res.status(400).json({ error: "Body inválido. Envía JSON." });
  }

  const { image, mediaType = "image/jpeg" } = body ?? {};

  if (!image) {
    return res.status(400).json({ error: "Campo 'image' requerido (base64 de la imagen)." });
  }

  const validTypes = ["image/jpeg", "image/png", "image/webp", "image/gif"];
  if (!validTypes.includes(mediaType)) {
    return res.status(400).json({ error: `mediaType inválido. Usa: ${validTypes.join(", ")}` });
  }

  // Strip data URL prefix if user sent it
  const base64Clean = image.replace(/^data:image\/[a-z]+;base64,/, "");

  try {
    const rawText = await callClaude(base64Clean, mediaType);

    // Extract JSON from Claude's response
    const jsonMatch = rawText.match(/\{[\s\S]*\}/);
    if (!jsonMatch) throw new Error("Claude no devolvió JSON válido");

    const apuesta = JSON.parse(jsonMatch[0]);
    const resumen = buildResumen(apuesta);

    res.setHeader("Cache-Control", "no-store");
    return res.status(200).json({ ok: true, apuesta, resumen });

  } catch (err) {
    return res.status(500).json({ ok: false, error: err.message });
  }
}

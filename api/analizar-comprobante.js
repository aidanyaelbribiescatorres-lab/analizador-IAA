/**
 * /api/analizar-comprobante — Analiza foto de comprobante de apuesta con Gemini (GRATIS)
 *
 * Usa Google Gemini 1.5 Flash — plan gratuito:
 *   • 1,500 requests/día
 *   • 15 requests/minuto
 *   • Sin tarjeta de crédito requerida
 *   → Obtén tu key GRATIS en: https://aistudio.google.com/apikey
 *
 * POST /api/analizar-comprobante
 * Body (JSON):
 *   {
 *     "image": "<base64>",          // imagen en base64 (con o sin prefijo data:...)
 *     "mediaType": "image/jpeg"     // "image/jpeg" | "image/png" | "image/webp"
 *   }
 *
 * Variable de entorno requerida: GEMINI_API_KEY
 */

const GEMINI_URL =
  "https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent";

const PROMPT = `Eres un asistente que analiza comprobantes y tickets de apuestas deportivas.
Extrae toda la información del comprobante en el siguiente formato JSON exacto.
Responde ÚNICAMENTE con el JSON, sin texto adicional, sin bloques de código.
Si no puedes leer un campo usa null. Los montos deben ser números (no strings).

{
  "casa": "nombre de la casa de apuestas (Bet365, Codere, Betano, 1xBet, Caliente, etc.)",
  "fecha": "YYYY-MM-DD o null",
  "monto_apostado": número o null,
  "cuota": número o null,
  "ganancia_potencial": número o null,
  "deporte": "Fútbol | Básquetbol | Béisbol | etc. o null",
  "evento": "nombre del partido o evento",
  "seleccion": "qué pronóstico se hizo (ej: Local gana, +2.5 goles, Ambos anotan)",
  "estado": "Pendiente | Ganada | Perdida | Anulada | null",
  "id_apuesta": "ID o número de ticket o null",
  "moneda": "MXN | USD | EUR | etc. o null",
  "notas": "cualquier otro dato relevante del ticket"
}`;

async function callGemini(base64Image, mediaType) {
  const apiKey = process.env.GEMINI_API_KEY;
  if (!apiKey) throw new Error("GEMINI_API_KEY no configurada. Obtén una gratis en https://aistudio.google.com/apikey");

  const body = {
    contents: [
      {
        parts: [
          {
            inline_data: {
              mime_type: mediaType,
              data: base64Image,
            },
          },
          { text: PROMPT },
        ],
      },
    ],
    generationConfig: {
      temperature: 0.1,
      maxOutputTokens: 1024,
    },
  };

  const res = await fetch(`${GEMINI_URL}?key=${apiKey}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });

  if (!res.ok) {
    const err = await res.text();
    throw new Error(`Gemini API ${res.status}: ${err}`);
  }

  const data = await res.json();
  const text = data?.candidates?.[0]?.content?.parts?.[0]?.text ?? "";
  if (!text) throw new Error("Gemini no devolvió respuesta");
  return text;
}

function buildResumen(apuesta) {
  const lineas = [];
  if (apuesta.casa)                    lineas.push(`Casa: ${apuesta.casa}`);
  if (apuesta.fecha)                   lineas.push(`Fecha: ${apuesta.fecha}`);
  if (apuesta.evento)                  lineas.push(`Evento: ${apuesta.evento}`);
  if (apuesta.seleccion)               lineas.push(`Seleccion: ${apuesta.seleccion}`);
  if (apuesta.monto_apostado != null)  lineas.push(`Monto apostado: ${apuesta.moneda ?? ""} ${apuesta.monto_apostado}`);
  if (apuesta.cuota != null)           lineas.push(`Cuota: ${apuesta.cuota}`);
  if (apuesta.ganancia_potencial != null) lineas.push(`Ganancia potencial: ${apuesta.moneda ?? ""} ${apuesta.ganancia_potencial}`);
  if (apuesta.estado)                  lineas.push(`Estado: ${apuesta.estado}`);
  if (apuesta.id_apuesta)              lineas.push(`Ticket ID: ${apuesta.id_apuesta}`);
  if (apuesta.notas)                   lineas.push(`Notas: ${apuesta.notas}`);
  return lineas.join("\n");
}

export default async function handler(req, res) {
  res.setHeader("Access-Control-Allow-Origin", "*");
  res.setHeader("Access-Control-Allow-Methods", "POST, OPTIONS");
  res.setHeader("Access-Control-Allow-Headers", "Content-Type");

  if (req.method === "OPTIONS") return res.status(204).end();
  if (req.method !== "POST")   return res.status(405).json({ error: "Usa POST." });

  let body;
  try {
    body = typeof req.body === "string" ? JSON.parse(req.body) : req.body;
  } catch {
    return res.status(400).json({ error: "Body inválido. Envía JSON." });
  }

  const { image, mediaType = "image/jpeg" } = body ?? {};

  if (!image) return res.status(400).json({ error: "Campo 'image' requerido (base64)." });

  const validTypes = ["image/jpeg", "image/png", "image/webp"];
  if (!validTypes.includes(mediaType)) {
    return res.status(400).json({ error: `mediaType inválido. Usa: ${validTypes.join(", ")}` });
  }

  // Quitar prefijo data URL si viene incluido
  const base64Clean = image.replace(/^data:image\/[a-z]+;base64,/, "");

  try {
    const rawText = await callGemini(base64Clean, mediaType);

    // Extraer JSON de la respuesta
    const jsonMatch = rawText.match(/\{[\s\S]*\}/);
    if (!jsonMatch) throw new Error("No se encontró JSON en la respuesta");

    const apuesta = JSON.parse(jsonMatch[0]);
    const resumen = buildResumen(apuesta);

    res.setHeader("Cache-Control", "no-store");
    return res.status(200).json({ ok: true, apuesta, resumen });

  } catch (err) {
    return res.status(500).json({ ok: false, error: err.message });
  }
}

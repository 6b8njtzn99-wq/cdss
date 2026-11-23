import json
import os

from dotenv import load_dotenv
from google import genai
from google.genai import types

load_dotenv()
client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
MODEL = os.getenv("GEMINI_MODEL", "gemini-3.5-flash")

FORMAT_JSON = """{
  "ringkasan": "3-4 kalimat penjelasan untuk dokter",
  "diagnosis_banding": [{"nama": "...", "alasan": "..."}],
  "pemeriksaan": [{"nama": "...", "alasan": "..."}],
  "terapi_prioritas": [{"nama": "...", "alasan": "..."}]
}"""


def susun_rekomendasi(data_kg, potongan_ppk, kondisi_pasien=None, obat_saat_ini=None):
    """Minta LLM merangkum data Knowledge Graph + potongan PNPK menjadi JSON."""
    teks_ppk = "\n\n".join(
        f"[{p['dokumen']} hal. {p['halaman']}]\n{p['teks']}" for p in potongan_ppk
    ) or "(tidak ada potongan dokumen)"

    prompt = f"""Kamu adalah asisten Clinical Decision Support System untuk dokter di Indonesia.
Tugasmu merangkum data di bawah, BUKAN menambah pengetahuan baru.

ATURAN WAJIB:
1. Semua nama diagnosis banding, pemeriksaan, dan terapi HANYA boleh disalin persis dari DATA KNOWLEDGE GRAPH.
2. Jangan menulis dosis baru. Dosis sudah tersedia di data.
3. "terapi_prioritas" berisi paling banyak 5 terapi yang paling relevan untuk kondisi pasien, beserta alasannya.
4. Kalau informasi tidak ada di data, tulis "tidak tersedia di sumber". Jangan mengarang.
5. Jawab HANYA dalam JSON dengan format:
{FORMAT_JSON}

KONDISI PASIEN: {", ".join(kondisi_pasien or []) or "tidak disebutkan"}
OBAT YANG SEDANG DIKONSUMSI: {", ".join(obat_saat_ini or []) or "tidak disebutkan"}

DATA KNOWLEDGE GRAPH:
{json.dumps(data_kg, ensure_ascii=False)}

POTONGAN DOKUMEN PNPK:
{teks_ppk}
"""
    response = client.models.generate_content(
        model=MODEL,
        contents=prompt,
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            temperature=0.2,
        ),
    )
    return json.loads(response.text)

"""
cdss_ai.py - Modul AI sederhana untuk Clinical Co-Pilot (versi tanpa Neo4j).

Alur kerja (berurutan):
  1. Baca semua CSV di folder data/
  2. Cari data klinis sesuai diagnosis (retrieval dari CSV)
  3. Cek keamanan obat: kontraindikasi + interaksi (aturan, BUKAN LLM)
  4. Kirim data hasil langkah 2 ke Gemini -> minta ringkasan dalam JSON
  5. Gabungkan jadi satu hasil JSON lengkap dengan sumber & halaman

Pakai:  python cdss_ai.py "hipertensi" "Captopril,Candesartan"
"""
import os
import sys
import json
import time
import glob
import re
import pandas as pd
from dotenv import load_dotenv

# ---------------------------------------------------------------
# LANGKAH 1: Baca semua CSV
# ---------------------------------------------------------------
FOLDER_DATA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")


def baca_gabung(awalan):
    """Gabungkan semua file data/<awalan>_*.csv jadi satu tabel."""
    file_list = glob.glob(os.path.join(FOLDER_DATA, awalan + "_*.csv"))
    tabel = [pd.read_csv(f, dtype=str).fillna("") for f in file_list]
    return pd.concat(tabel, ignore_index=True)


RELASI = baca_gabung("relasi")
KONTRA = baca_gabung("kontraindikasi")
INTERAKSI = baca_gabung("interaksi")  # PNPK + DDInter jadi satu


# ---------------------------------------------------------------
# LANGKAH 2: Cari data klinis berdasarkan diagnosis
# ---------------------------------------------------------------
def cari_diagnosis(kata_kunci):
    """Cari baris relasi. Kode ICD (mis. I63) dicocokkan persis;
    kalau bukan kode ICD, dicari di nama diagnosis."""
    k = kata_kunci.strip().lower()
    persis = RELASI[RELASI["icd"].str.lower() == k]
    if len(persis) > 0:
        return persis
    return RELASI[RELASI["diagnosis"].str.lower().str.contains(k, regex=False)]


# ---------------------------------------------------------------
# LANGKAH 3: Cek keamanan obat (rule-based)
# ---------------------------------------------------------------
def cek_keamanan(daftar_obat, kondisi_pasien=()):
    """
    daftar_obat    : list nama obat yang mau diberikan
    kondisi_pasien : list kondisi pasien, mis. ["hamil"]
    Return: list peringatan, tiap peringatan punya jenis, tingkat, isi, sumber.
    """
    obat = [o.strip().lower() for o in daftar_obat if o.strip()]
    kondisi = [c.strip().lower() for c in kondisi_pasien if c.strip()]
    peringatan = []

    # 3a. Interaksi: cek setiap pasangan obat (urutan A-B atau B-A)
    for _, r in INTERAKSI.iterrows():
        a, b = r["obat_a"].lower(), r["obat_b"].lower()
        if a in obat and b in obat:
            peringatan.append({
                "jenis": "INTERAKSI",
                "tingkat": r["tingkat"],
                "obat": [r["obat_a"], r["obat_b"]],
                "isi": r["keterangan"],
                "sumber": r["sumber"],
            })

    # 3b. Kontraindikasi: obat ada di daftar DAN kondisi pasien cocok
    for _, r in KONTRA.iterrows():
        if r["obat"].lower() in obat:
            kond_data = r["kondisi"].lower()
            if any(c in kond_data or kond_data in c for c in kondisi):
                peringatan.append({
                    "jenis": "KONTRAINDIKASI",
                    "tingkat": "TINGGI",
                    "obat": [r["obat"]],
                    "isi": f"{r['kondisi']}: {r['keterangan']}",
                    "sumber": r["sumber"],
                })
    return peringatan


# ---------------------------------------------------------------
# LANGKAH 4: Tanya Gemini (hanya merangkum data yang kita berikan)
# ---------------------------------------------------------------
def tanya_gemini(diagnosis, baris_data, peringatan, daftar_obat=(), kondisi_pasien=()):
    """Minta Gemini membuat ringkasan JSON HANYA dari data yang diberikan."""
    from google import genai
    from google.genai import types

    load_dotenv()
    # timeout 20 detik supaya tidak menggantung kalau server Gemini sibuk
    klien = genai.Client(
        api_key=os.getenv("GEMINI_API_KEY"),
        http_options=types.HttpOptions(timeout=20000),
    )

    # Sumber & halaman tidak perlu dikirim (lebih hemat token = lebih cepat).
    # Kita tempel sendiri nanti dari CSV, jadi tidak bisa dikarang Gemini.
    data_teks = baris_data[["relasi", "target_nama", "detail"]].to_csv(index=False)

    perintah = f"""Kamu asisten pendukung keputusan klinis untuk dokter.
ATURAN KETAT:
- Jawab HANYA dari DATA di bawah. Jangan menambah fakta klinis dari luar data.
- Jika data tidak cukup, tulis "tidak tersedia di data".
- Perhatikan KONDISI PASIEN. Jika ada baris KONDISI_KHUSUS yang cocok,
  utamakan pilihan terapi dari baris itu.
- JANGAN sarankan obat yang muncul di PERINGATAN KEAMANAN untuk pasien ini.
- "terapi": maksimal 5 obat paling sesuai untuk pasien ini, tiap item
  berformat "Nama obat - dosis/alasan singkat dari data".
- Jika baris KONDISI_KHUSUS hanya menyebut GOLONGAN obat (mis. "CCB"),
  tulis golongannya saja. JANGAN menyebut nama obat spesifik yang tidak
  disebut di baris itu.
- Keluarkan JSON dengan HANYA tiga kunci: "ringkasan" (maks 3 kalimat),
  "terapi" (list), "catatan_kondisi_pasien" (1-2 kalimat; isi "-" bila tidak ada).
- Bahasa Indonesia.

DIAGNOSIS: {diagnosis}
KONDISI PASIEN: {", ".join(kondisi_pasien) or "tidak disebutkan"}
OBAT YANG INGIN DIBERIKAN DOKTER: {", ".join(daftar_obat) or "belum ada"}

DATA PNPK:
{data_teks}

PERINGATAN KEAMANAN OBAT (dari aturan, bukan dari kamu):
{json.dumps(peringatan, ensure_ascii=False)}
"""
    # Coba model utama dulu; kalau server sibuk (503), pakai model cadangan
    try:
        config = types.GenerateContentConfig(
            response_mime_type="application/json",
            max_output_tokens=700,
            thinking_config=types.ThinkingConfig(thinking_level="low"),
        )
    except Exception:  # versi SDK lama: pakai konfigurasi biasa
        config = types.GenerateContentConfig(
            response_mime_type="application/json", max_output_tokens=700)

    kesalahan = None
    percobaan = []  # catatan: model apa dicoba, berapa detik, hasilnya
    for nama_model in ["gemini-3.1-flash-lite", "gemini-3.5-flash-lite"]:
        t0 = time.time()
        try:
            jawaban = klien.models.generate_content(
                model=nama_model, contents=perintah, config=config)
            hasil = json.loads(jawaban.text)  # gagal parse = JSON tidak valid
            percobaan.append(f"{nama_model}: OK {time.time() - t0:.1f}s")
            hasil["model_dipakai"] = nama_model
            hasil["percobaan_model"] = percobaan
            return hasil
        except Exception as e:
            percobaan.append(f"{nama_model}: GAGAL {time.time() - t0:.1f}s "
                             f"({str(e)[:60]})")
            kesalahan = e
    raise RuntimeError(" | ".join(percobaan))


# ---------------------------------------------------------------
# LANGKAH 4: Baca teks bebas dokter -> cari obat & kondisi -> cek keamanan
# (kata kunci saja; keputusan peringatan tetap dari aturan CSV, bukan AI)
# ---------------------------------------------------------------
_semua_obat = set(KONTRA["obat"]) | set(INTERAKSI["obat_a"]) | set(INTERAKSI["obat_b"])
OBAT_DIKENAL = sorted((o for o in _semua_obat if o), key=len, reverse=True)
KATA_KONDISI = {          # kondisi di CSV : kata yang mungkin diketik dokter
    "hamil": ["hamil", "kehamilan"],
    "gagal jantung": ["gagal jantung"],
    "asma": ["asma"],
    "bradikardi": ["bradikardi", "bradikardia"],
    "hiperkalemia": ["hiperkalemia"],
    "fibrilasi atrium": ["fibrilasi atrium"],
    "penyakit ginjal kronik": ["penyakit ginjal kronik", "pgk"],
    "gangguan hati": ["gangguan hati", "sirosis"],
    "perdarahan intraserebral": ["perdarahan intraserebral", "ich"],
}


def ada_kata(teks, kata):
    """True bila kata ada di teks dan TIDAK didahului tidak/bukan/tanpa (negasi sederhana)."""
    for m in re.finditer(r"\b" + re.escape(kata) + r"\b", teks):
        sebelum = teks[max(0, m.start() - 20):m.start()]
        if not re.search(r"\b(tidak|bukan|tanpa|disangkal)\b", sebelum):
            return True
    return False


def peringatan_dari_teks(teks):
    """Return (obat_terbaca, kondisi_terbaca, daftar_peringatan)."""
    teks = teks.lower()
    obat = sorted({o for o in OBAT_DIKENAL if ada_kata(teks, o.lower())})
    kondisi = [k for k, kata in KATA_KONDISI.items() if any(ada_kata(teks, w) for w in kata)]
    return obat, kondisi, (cek_keamanan(obat, kondisi) if obat else [])



# ---------------------------------------------------------------
# LANGKAH 4b: Bandingkan obat di Planning dokter dengan terapi di PNPK
# (aturan sederhana: nama obat -> golongan -> cari di baris TERAPI_* untuk ICD terpilih)
# ---------------------------------------------------------------
# kiri: nama obat yang mungkin diketik dokter | kanan: potongan nama target di CSV
PEMETAAN_OBAT = {
    # DM tipe 2 (PNPK DM2)
    "metformin": "metformin",
    "glimepirid": "sulfonilurea", "gliklazid": "sulfonilurea",
    "glibenklamid": "sulfonilurea", "glipizid": "sulfonilurea",
    "repaglinid": "glinid", "nateglinid": "glinid",
    "pioglitazon": "tiazolidinedion",
    "akarbose": "alfa glukosidase", "voglibosa": "alfa glukosidase",
    "vildagliptin": "dpp-4", "linagliptin": "dpp-4", "sitagliptin": "dpp-4",
    "saxagliptin": "dpp-4", "alogliptin": "dpp-4",
    "empagliflozin": "sglt-2", "dapagliflozin": "sglt-2",
    "canagliflozin": "sglt-2", "ipragliflozin": "sglt-2",
    "liraglutide": "glp-1", "semaglutide": "glp-1", "dulaglutide": "glp-1",
    "insulin": "insulin",
    "simvastatin": "statin", "atorvastatin": "statin", "rosuvastatin": "statin",
    "fenofibrat": "fibrat",
    "captopril": "ace inhibitor", "ramipril": "ace inhibitor", "lisinopril": "ace inhibitor",
    "candesartan": "ace inhibitor", "valsartan": "ace inhibitor", "telmisartan": "ace inhibitor",
    "amlodipin": "ace inhibitor", "bisoprolol": "ace inhibitor",
    # Variasi ejaan yang sering dipakai dokter (ejaan Inggris dll)
    "glimepiride": "sulfonilurea", "gliclazide": "sulfonilurea", "glibenclamide": "sulfonilurea",
    "glipizide": "sulfonilurea", "glyburide": "sulfonilurea",
    "repaglinide": "glinid", "nateglinide": "glinid",
    "pioglitazone": "tiazolidinedion", "acarbose": "alfa glukosidase", "voglibose": "alfa glukosidase",
    "liraglutid": "glp-1", "semaglutid": "glp-1", "dulaglutid": "glp-1",
    "fenofibrate": "fibrat", "amlodipine": "ace inhibitor",
    "nimodipine": "nimodipin", "edoxaban": "doac", "ticagrelor": "ticagrelor",
    "asam traneksamat": "antifibrinolitik", "traneksamat": "antifibrinolitik",
    "nicardipine": "antihipertensi iv", "nikardipin": "antihipertensi iv",
    "labetalol": "antihipertensi iv", "esmolol": "antihipertensi iv", "diltiazem": "antihipertensi iv",
    # Stroke (PNPK Stroke)
    "alteplase": "alteplase", "tenecteplase": "tenecteplase",
    "aspirin": "aspirin", "clopidogrel": "clopidogrel", "ticagrelor": "ticagrelor",
    "cilostazol": "cilostazol", "nimodipin": "nimodipin", "warfarin": "warfarin",
    "dabigatran": "doac", "rivaroxaban": "doac", "apixaban": "doac", "edoksaban": "doac",
}


def bandingkan_terapi(icd, teks_planning):
    """Bandingkan obat yang ditulis dokter di Planning dengan terapi PNPK untuk ICD tsb.
    Return list: {obat, status, baris}; status: SESUAI_PNPK, TIDAK_DIANJURKAN_PNPK
    (PNPK menyebut tidak dianjurkan) atau TIDAK_ADA_DI_DATA.
    Hanya perbandingan nama obat. Dosis & kecocokan klinis tetap dinilai dokter."""
    teks = teks_planning.lower()
    semua = {o.lower() for o in list(PEMETAAN_OBAT) + OBAT_DIKENAL}  # huruf kecil, tanpa duplikat
    obat_terbaca = sorted(o for o in semua if ada_kata(teks, o))
    # buang nama pendek yang hanya potongan nama lebih panjang (traneksamat di asam traneksamat)
    obat_terbaca = [o for o in obat_terbaca if not any(o != p and o in p for p in obat_terbaca)]
    data = cari_diagnosis(icd)
    terapi = data[data["relasi"].str.startswith("TERAPI")]
    hasil = []
    for obat in obat_terbaca:
        kunci = PEMETAAN_OBAT.get(obat.lower())
        cocok = pd.DataFrame()
        if kunci:
            nama = terapi["target_nama"].str.lower()
            cocok = terapi[nama == kunci]                    # nama persis dulu
            if cocok.empty:
                cocok = terapi[nama.str.contains(kunci, regex=False)]
        if cocok.empty:
            hasil.append({"obat": obat, "status": "TIDAK_ADA_DI_DATA", "baris": []})
        else:
            # baris yang di PNPK justru "tidak dianjurkan" (mis. antifibrinolitik pada PSA)
            tidak = cocok["detail"].str.lower().str.startswith("tidak dianjurkan").any()
            hasil.append({"obat": obat,
                          "status": "TIDAK_DIANJURKAN_PNPK" if tidak else "SESUAI_PNPK",
                          "baris": cocok[["relasi", "target_nama", "detail", "halaman", "sumber"]]
                                   .to_dict(orient="records")})
    return hasil


# ---------------------------------------------------------------
# LANGKAH 5: Gabungkan semuanya
# ---------------------------------------------------------------
def analisis(diagnosis, daftar_obat=(), kondisi_pasien=(), pakai_llm=True):
    mulai = time.time()
    data = cari_diagnosis(diagnosis)
    if data.empty:
        return {"error": f"Diagnosis '{diagnosis}' tidak ada di data."}

    peringatan = cek_keamanan(daftar_obat, kondisi_pasien)

    waktu_cari = round(time.time() - mulai, 3)

    t_llm = time.time()
    ringkasan = None
    if pakai_llm:
        try:
            ringkasan = tanya_gemini(data["diagnosis"].iloc[0], data, peringatan,
                                  daftar_obat, kondisi_pasien)
        except Exception as e:  # LLM gagal -> sistem tetap jalan
            ringkasan = {"error_llm": str(e)}

    waktu_llm = round(time.time() - t_llm, 2)

    # Daftar ini langsung dari CSV: pasti sesuai PNPK, tanpa risiko halusinasi
    def daftar(jenis):
        return data[data["relasi"] == jenis]["target_nama"].tolist()
    if isinstance(ringkasan, dict):
        ringkasan["diagnosis_banding"] = daftar("DIAGNOSIS_BANDING")
        ringkasan["pemeriksaan"] = daftar("PEMERIKSAAN")

    # Sumber ringkas (data lineage): satu baris per dokumen, halaman diurutkan
    sumber = []
    for dok, grup in data.groupby("sumber"):
        halaman = set()
        for teks in grup["halaman"]:
            for a, b in re.findall(r"(\d+)(?:-(\d+))?", teks):
                halaman.update(range(int(a), int(b or a) + 1))
        sumber.append(f"{dok} hal {', '.join(str(h) for h in sorted(halaman))}")

    return {
        "diagnosis": data["diagnosis"].iloc[0],
        "icd": data["icd"].iloc[0],
        "ringkasan_ai": ringkasan,
        "data_klinis": data[["relasi", "target_kode", "target_nama", "detail", "halaman"]]
            .to_dict(orient="records"),
        "peringatan": peringatan,
        "sumber": sumber,
        "waktu_cari_dan_cek_detik": waktu_cari,   # tanpa LLM
        "waktu_llm_detik": waktu_llm,             # hanya Gemini
        "waktu_respons_detik": round(time.time() - mulai, 2),
        "catatan": "Saran ini bersifat pendukung. Keputusan akhir ada pada dokter.",
    }


if __name__ == "__main__":
    dx = sys.argv[1] if len(sys.argv) > 1 else "hipertensi"
    obat = sys.argv[2].split(",") if len(sys.argv) > 2 else []
    kondisi = sys.argv[3].split(",") if len(sys.argv) > 3 else []
    hasil = analisis(dx, obat, kondisi)
    print(json.dumps(hasil, ensure_ascii=False, indent=2))

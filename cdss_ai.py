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
    # obat yang ditulis 'tidak diberikan' / 'dihindari' tidak dihitung sebagai obat yang dipakai
    obat = sorted({o for o in OBAT_DIKENAL if ada_kata(teks, o.lower()) and ada_positif(teks, o.lower())})
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
    # obat yang sudah diatur oleh aturan_klinis() tidak dibahas dua kali di sini
    if icd == "I63":
        diatur = set(ANTIHIPERTENSI) | {"nimodipin", "nimodipine"}
    elif icd in ("I60", "I61"):
        diatur = set(ANTIPLATELET) | set(ANTIKOAGULAN)
    else:
        diatur = set()
    obat_terbaca = [o for o in obat_terbaca if o not in diatur]
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
# LANGKAH 4c: Checklist dan aturan klinis dari teks S, O, P
# (kata kunci + aturan sederhana, BUKAN AI. Sumber aturan ada di tiap pesan.)
# ---------------------------------------------------------------
SUMBER_JOV = "Praktik klinis tervalidasi"

# Kelompok obat yang dipakai aturan. Tambah nama di sini kalau ada yang belum terbaca.
ANTIPLATELET = ["aspirin", "clopidogrel", "cilostazol", "ticagrelor", "abciximab",
                "eptifibatide", "tirofiban", "antiplatelet"]
ANTIKOAGULAN = ["rivaroksaban", "apixaban", "heparin", "warfarin", "dabigatran",
                "edoksaban", "enoxaparin", "antikoagulan"]
ANTIHIPERTENSI = ["captopril", "kaptopril", "lisinopril", "ramipril", "amlodipin", "amlodipine",
                  "candesartan", "valsartan", "telmisartan", "losartan", "bisoprolol",
                  "metoprolol", "hidroklorotiazid", "nifedipin", "diltiazem", "nicardipine",
                  "nikardipin", "labetalol", "esmolol", "antihipertensi"]
ANTI_DM = ["metformin", "glimepirid", "glimepiride", "gliklazid", "gliclazide", "glibenklamid",
           "glibenclamide", "glipizid", "glipizide", "repaglinid", "repaglinide", "nateglinid",
           "nateglinide", "pioglitazon", "pioglitazone", "akarbose", "acarbose", "voglibosa",
           "vildagliptin", "linagliptin", "sitagliptin", "saxagliptin", "alogliptin",
           "empagliflozin", "dapagliflozin", "canagliflozin", "ipragliflozin",
           "liraglutide", "semaglutide", "dulaglutide", "insulin"]
ANTI_LIPID = ["simvastatin", "atorvastatin", "rosuvastatin", "statin", "fenofibrat", "fenofibrate"]

# Pemeriksaan: kata yang mungkin dipakai dokter (regex) untuk tiap nama di CSV
SINONIM_PEMERIKSAAN = {
    "CT-scan kepala tanpa kontras": r"\bct[ -]?scan\b(?!\s*(perfusi|angiografi|venografi))|\bct kepala\b",
    "CT angiografi (CTA)": r"ct[ -]?angiografi|\bcta\b",
    "CT perfusi (CTP)": r"ct[ -]?perfusi|\bctp\b|ct perfusion",
    "CT venografi (CTV)": r"ct[ -]?venografi|\bctv\b",
    "MRI": r"\bmri\b(?!\s*(perfusi|angio))",
    "MR angiografi (MRA)": r"mr[ -]?angiografi|\bmra\b",
    "MR venografi (MRV)": r"mr[ -]?venografi|\bmrv\b",
    "MRI perfusi": r"mri[ -]?perfusi|mr[ -]?perfusi",
    "Skala NIHSS": r"nihss",
    "VAN score": r"\bvan score",
    "HbA1c": r"hba1c|\ba1c\b",
    "Glukosa plasma puasa": r"(glukosa|gula darah)( plasma)? puasa|\bgdp\b",
    "TTGO (beban glukosa 75 gram)": r"ttgo",
    "Glukosa darah sewaktu": r"(glukosa|gula) darah (sewaktu|acak)|\bgds\b|\bgda\b",
    "Profil lipid": r"profil lipid|\bldl\b|kolesterol total",
    "Tekanan darah": r"\btd\b|tekanan darah",
}


def ada_positif(teks, kata):
    """True bila kata ada di teks, TIDAK didahului negasi (tidak/bukan/tanpa/disangkal/belum)
    dan TIDAK diikuti tanda (-). Contoh: 'DM (-)' dianggap tidak ada."""
    for m in re.finditer(r"\b" + re.escape(kata) + r"\b", teks):
        sebelum = teks[max(0, m.start() - 20):m.start()]
        sesudah = teks[m.end():m.end() + 8]
        # sisa baris setelah kata (maks 45 huruf): 'aspirin dan clopidogrel tidak diberikan'
        sisa = re.split(r"[\n;]", teks[m.end():m.end() + 45])[0]
        if re.search(r"\b(tidak|bukan|tanpa|disangkal|belum|hindari|jangan|stop|hentikan)\b", sebelum):
            continue
        if re.search(r"\b(tidak|jangan)\s+(perlu|diberikan|boleh|dipakai|digunakan|dianjurkan)\b|dihindari|distop|dihentikan", sisa):
            continue
        if re.match(r"\s*:?\s*\(-\)", sesudah):
            continue
        return True
    return False


def obat_dari_daftar(teks, daftar):
    """Daftar nama (dari 'daftar') yang terbaca di teks."""
    teks = teks.lower()
    return sorted({k for k in daftar if ada_positif(teks, k)})


def baca_td(teks):
    """Ambil tekanan darah pertama yang ditulis, mis. 'TD 170/100' -> (170, 100). None bila tidak ada."""
    m = re.search(r"(?:\btd\b|tekanan darah)\s*[:=]?\s*(\d{2,3})\s*/\s*(\d{2,3})", teks.lower())
    return (int(m.group(1)), int(m.group(2))) if m else None


def _pola_baris(nama):
    """Pola pencarian untuk satu nama baris: sinonim dari tabel, atau nama itu sendiri
    + isi tanda kurung + nama obat dari PEMETAAN_OBAT yang cocok dengan nama baris."""
    if nama in SINONIM_PEMERIKSAAN:
        return SINONIM_PEMERIKSAAN[nama]
    kata = {nama.lower()}
    for dalam in re.findall(r"\(([^)]*)\)", nama):
        kata.update(x.strip().lower() for x in dalam.split(";") if x.strip())
    kata.add(re.sub(r"\(.*?\)", "", nama).strip().lower())
    for obat, kunci in PEMETAAN_OBAT.items():
        if kunci in nama.lower():
            kata.add(obat)
    kata = {k for k in kata if len(k) >= 4}
    return "|".join(r"\b" + re.escape(k) + r"\b" for k in sorted(kata, key=len, reverse=True)) or "(?!x)x"


def _terbaca(pola, teks):
    for m in re.finditer(pola, teks):
        sebelum = teks[max(0, m.start() - 20):m.start()]
        if not re.search(r"\b(tidak|bukan|tanpa|disangkal|belum)\b", sebelum):
            return True
    return False


def tandai_sudah(baris, teks_s, teks_o, teks_p):
    """Baris PNPK mana yang sudah tercatat dokter? baris = DataFrame data_klinis.
    Pemeriksaan dicari di S+O (sudah dilakukan); lainnya dicari di P (sudah direncanakan).
    Return: set (relasi, target_nama)."""
    so, p = f"{teks_s} {teks_o}".lower(), teks_p.lower()
    sudah = set()
    for r in baris.itertuples():
        # diagnosa banding tidak dicentang; baris rekomendasi dr. Jovian hanya dicentang bila berupa pemeriksaan
        if r.relasi == "DIAGNOSIS_BANDING":
            continue
        if r.relasi != "PEMERIKSAAN" and SUMBER_JOV in str(getattr(r, "sumber", "")):
            continue
        teks = so if r.relasi == "PEMERIKSAAN" else p
        # nama berbentuk "A + B": semua bagian harus terbaca
        bagian = [b.strip() for b in r.target_nama.split(" + ")]
        if all(_terbaca(_pola_baris(b), teks) for b in bagian):
            sudah.add((r.relasi, r.target_nama))
    return sudah


def filter_diagnosis_banding(icd, baris, teks_s, teks_o):
    """Masukan dr. Jovian (E11): E10 tidak perlu bila S/O menulis tidak pernah DM saat kecil;
    DM gestasional (O24.4) hanya bila pasien hamil. Return (baris_baru, catatan)."""
    if icd != "E11":
        return baris, []
    teks = f"{teks_s} {teks_o}".lower()
    catatan = []
    tanpa_dm_kecil = bool(
        re.search(r"(dm|diabetes)[^.]{0,40}(kecil|anak)[^.]{0,20}\(-\)", teks)
        or re.search(r"(tidak|tak) pernah[^.]{0,40}(dm|diabetes|kencing manis)[^.]{0,30}(kecil|anak)", teks)
        or re.search(r"(kecil|anak)[^.]{0,40}(tidak|tak) pernah[^.]{0,30}(dm|diabetes|kencing manis)", teks)
        or re.search(r"(dm|diabetes)[^.]{0,30}(kecil|anak)[^.]{0,20}(tidak|tak) pernah", teks))
    hamil = ada_positif(teks, "hamil") or ada_positif(teks, "kehamilan")
    kode = baris["target_kode"]
    buang = (kode == "E10") if tanpa_dm_kecil else (kode == "__tidak__")
    if tanpa_dm_kecil:
        catatan.append("E10 tidak ditampilkan: S/O menulis pasien tidak pernah DM saat kecil.")
    if not hamil:
        buang = buang | (kode == "O24.4")
        catatan.append("DM gestasional (O24.4) ditampilkan hanya bila pasien hamil.")
    return baris[~buang], catatan


def sembunyikan_antihipertensi(icd, data, teks_s, teks_o):
    """Masukan dr. Jovian (I63): bila TD terbaca 220/120 mmHg atau kurang, jangan menampilkan
    saran penurunan TD / antihipertensi. Target TD khusus trombolisis dan trombektomi tetap tampil."""
    if icd != "I63":
        return data
    td = baca_td(f"{teks_s} {teks_o}".lower())
    if not td or td[0] > 220 or td[1] > 120:
        return data
    return data[data["target_nama"] != "TD stroke iskemik akut"]


def aturan_klinis(icd, teks_s, teks_o, teks_p):
    """Aturan dari masukan dr. Jovian yang butuh membaca teks S/O/P.
    Return list: {kode, tingkat (MERAH/KUNING/BIRU), judul, isi, sumber}."""
    s_o = f"{teks_s} {teks_o}".lower()
    p = teks_p.lower()
    semua = f"{s_o} {p}"
    hasil = []

    def tambah(kode, tingkat, judul, isi):
        hasil.append({"kode": kode, "tingkat": tingkat, "judul": judul, "isi": isi,
                      "sumber": SUMBER_JOV})

    stroke = icd in ("I60", "I61", "I63")
    td = baca_td(s_o)
    td_teks = f"{td[0]}/{td[1]} mmHg" if td else "tidak terbaca"

    # --- Informasi klinis stroke belum lengkap
    if stroke and (teks_s.strip() or teks_o.strip()):
        kurang = []
        if not td:
            kurang.append("tekanan darah")
        if not re.search(r"\bct\b|\bmri\b|ct[ -]?scan", s_o):
            kurang.append("hasil CT scan atau MRI")
        if not re.search(r"riwayat (penggunaan )?obat|obat rutin|konsumsi obat", s_o):
            kurang.append("riwayat penggunaan obat")
        if kurang:
            tambah("DATA_KURANG", "BIRU", "Informasi klinis belum lengkap",
                   "Belum terbaca di S/O: " + ", ".join(kurang) + ". Mohon dilengkapi.")

    plat, koag = obat_dari_daftar(p, ANTIPLATELET), obat_dari_daftar(p, ANTIKOAGULAN)

    # --- I63: antihipertensi hanya bila TD di atas 220/120
    if icd == "I63":
        tinggi = bool(td) and (td[0] > 220 or td[1] > 120)
        antiht = obat_dari_daftar(p, ANTIHIPERTENSI + ["nimodipin", "nimodipine"])
        if tinggi:
            tambah("HIPERTENSI_EMERGENSI", "BIRU", "TD di atas 220/120 mmHg",
                   f"TD {td_teks}. Tambahkan koding hipertensi emergensi; antihipertensi IV "
                   "(nicardipine atau labetalol) dapat diberikan dengan target penurunan 15 persen dari MAP.")
        elif antiht:
            tambah("ANTIHIPERTENSI_I63", "MERAH", "Antihipertensi pada stroke iskemik",
                   f"Terbaca di Planning: {', '.join(antiht)}. Antihipertensi (semua golongan) dan nimodipin "
                   f"tidak diberikan kecuali TD di atas 220/120 mmHg. TD terbaca: {td_teks}.")
        if plat and koag:
            tambah("ANTITROMBOTIK_BERSAMAAN", "MERAH", "Antiplatelet dan antikoagulan bersamaan",
                   f"Terbaca: {', '.join(plat)} dan {', '.join(koag)}. Keduanya tidak boleh diberikan bersamaan.")
        koag_semua = obat_dari_daftar(semua, ANTIKOAGULAN)
        if re.search(r"alteplase|tenecteplase", p) and koag_semua:
            tambah("KONTRA_RELATIF_ANTIKOAG", "KUNING", "Antikoagulan oral dan trombolisis",
                   f"Terbaca: {', '.join(koag_semua)}. Konsumsi antikoagulan oral (warfarin atau DOAC) dalam "
                   "48 jam terakhir adalah kontraindikasi relatif pemberian alteplase. Keputusan klinis "
                   "mempertimbangkan manfaat dan risiko pasien.")

    # --- I60 dan I61: antiplatelet dan antikoagulan tidak boleh
    if icd in ("I60", "I61") and (plat or koag):
        tambah("ANTITROMBOTIK_PERDARAHAN", "MERAH", "Antiplatelet atau antikoagulan pada perdarahan",
               f"Terbaca di Planning: {', '.join(plat + koag)}. Pada perdarahan, antiplatelet dan antikoagulan tidak boleh diberikan.")

    # --- I69: faktor risiko harus punya obatnya
    if icd == "I69":
        dm = any(ada_positif(s_o, k) for k in ("dm", "diabetes melitus", "diabetes"))
        ht = any(ada_positif(s_o, k) for k in ("ht", "hipertensi"))
        lip = any(ada_positif(s_o, k) for k in ("dislipidemia", "kolesterol", "hiperkolesterolemia"))
        if dm and not obat_dari_daftar(p, ANTI_DM):
            tambah("I69_DM", "KUNING", "DM belum ada obat anti-DM", "S/O menyebut DM, tetapi obat anti-DM belum tertulis di Planning.")
        if ht and not obat_dari_daftar(p, ANTIHIPERTENSI):
            tambah("I69_HT", "KUNING", "HT belum ada obat anti-HT", "S/O menyebut HT, tetapi obat anti-HT belum tertulis di Planning.")
        if lip and not obat_dari_daftar(p, ANTI_LIPID):
            tambah("I69_LIPID", "KUNING", "Dislipidemia belum ada obat", "S/O menyebut dislipidemia, tetapi obat antidislipidemia belum tertulis di Planning.")
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
        # rekomendasi dr. Jovian tidak punya halaman PNPK -> cukup nama sumbernya
        sumber.append(f"{dok} hal {', '.join(str(h) for h in sorted(halaman))}" if halaman else dok)

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

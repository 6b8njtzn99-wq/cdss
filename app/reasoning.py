from app.graph import ambil_pengetahuan
from app.llm import susun_rekomendasi
from app.rag import cari_ppk
from app.safety import cek_keamanan

NAMA_KATEGORI = {
    "TERAPI_LINI_1": "Terapi lini pertama",
    "TERAPI_LINI_2": "Terapi lini kedua",
    "TERAPI_LANJUTAN": "Terapi lanjutan",
    "TERAPI_AKUT": "Terapi fase akut",
    "TERAPI_PENCEGAHAN": "Terapi pencegahan",
    "TERAPI_KOMORBID": "Terapi komorbid",
    "TERAPI_KHUSUS": "Terapi kondisi khusus",
    "TERAPI_PSA": "Terapi perdarahan subaraknoid",
    "TERAPI_PERDARAHAN_INTRASEREBRAL": "Tata laksana perdarahan intraserebral",
}


def label_kategori(kode):
    return NAMA_KATEGORI.get(kode, (kode or "").replace("_", " ").capitalize())


def _saring(item_llm, item_kg, kunci_kg):
    """Anti-halusinasi: item dari LLM hanya dipakai kalau namanya ada di Knowledge Graph.

    Data (dosis, sumber, halaman) selalu dari Knowledge Graph; LLM hanya menambah
    penjelasan. Mengembalikan (daftar item, jumlah item LLM yang dibuang).
    """
    hasil = [dict(x) for x in item_kg]
    terpakai, dibuang = set(), 0
    for x in item_llm or []:
        nama = str(x.get("nama") or x.get("obat") or "").strip().lower()
        idx = next((i for i, k in enumerate(hasil)
                    if str(k.get(kunci_kg) or "").strip().lower() == nama and i not in terpakai), None)
        if idx is None:
            dibuang += 1
            continue
        terpakai.add(idx)
        if x.get("alasan"):
            hasil[idx]["penjelasan_ai"] = x["alasan"]
        hasil[idx]["prioritas"] = True
    return hasil, dibuang


def buat_rekomendasi(icd, kondisi_pasien=None, obat_saat_ini=None):
    icd = icd.strip().upper()

    # 1. Knowledge Graph: relasi pasti dari PNPK
    kg = ambil_pengetahuan(icd)
    if kg is None:
        return {"status": "tidak_ditemukan",
                "pesan": f"Kode {icd} belum ada di Knowledge Graph"}

    # 2. RAG: potongan dokumen PNPK yang relevan
    try:
        konteks = " ".join([kg["nama"], "tata laksana terapi"] + list(kondisi_pasien or []))
        potongan = cari_ppk(konteks)
    except Exception as e:
        print("RAG gagal:", e)
        potongan = []

    # 3. LLM: rangkuman dan prioritas (kalau gagal, data KG tetap ditampilkan)
    try:
        llm = susun_rekomendasi(kg, potongan, kondisi_pasien, obat_saat_ini)
        mode = "Knowledge Graph + RAG + LLM"
    except Exception as e:
        print("LLM gagal, memakai data Knowledge Graph saja:", e)
        llm = {"ringkasan": "LLM tidak tersedia. Data ditampilkan langsung dari Knowledge Graph."}
        mode = "Knowledge Graph saja"

    banding, d1 = _saring(llm.get("diagnosis_banding"), kg["diagnosis_banding"], "nama")
    pemeriksaan, d2 = _saring(llm.get("pemeriksaan"), kg["pemeriksaan"], "nama")
    terapi, d3 = _saring(llm.get("terapi_prioritas"), kg["terapi"], "obat")
    for t in terapi:
        t["kategori_label"] = label_kategori(t.get("kategori"))
    panduan = [dict(p, kategori_label=label_kategori(p.get("kategori"))) for p in kg["panduan"]]

    # 4. Safety check berbasis aturan
    peringatan = cek_keamanan([t["obat"] for t in terapi], kondisi_pasien, obat_saat_ini)
    ditandai = {p["obat"].lower() for p in peringatan}
    for t in terapi:
        t["ada_peringatan"] = t["obat"].lower() in ditandai

    return {
        "status": "ok",
        "mode": mode,
        "diagnosis_utama": {"icd": kg["icd"], "nama": kg["nama"]},
        "ringkasan": llm.get("ringkasan", ""),
        "diagnosis_banding": banding,
        "pemeriksaan": pemeriksaan,
        "terapi": terapi,
        "panduan": panduan,
        "peringatan": peringatan,
        "item_llm_dibuang": d1 + d2 + d3,
        "referensi_ppk": [{"dokumen": p["dokumen"], "halaman": p["halaman"]} for p in potongan],
    }

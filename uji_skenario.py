"""
uji_skenario.py - Menjalankan semua skenario di skenario_uji.csv ke cdss_ai.py.
Tanpa Gemini (cepat dan tidak tergantung layanan luar).

Tiap skenario dicek 4 hal:
  1. Isi Co-Pilot untuk kode ICD: semua nama di kolom harus_ada HARUS muncul,
     semua nama di kolom harus_tidak_ada TIDAK BOLEH muncul.
  2. Peringatan keamanan dari teks S + O + P sama dengan yang diharapkan.
  3. Semua baris data kode itu punya sumber dan halaman (data lineage).
  4. Perbandingan obat di Planning dengan PNPK (kolom terapi_diharapkan;
     kosong = tidak dicek, KOSONG = tidak boleh ada obat terbaca).

Jalankan:  python uji_skenario.py
Hasil lengkap disimpan di hasil_uji.csv
"""
import csv
import cdss_ai

# ---- LANGKAH 1: baca skenario
with open("skenario_uji.csv", encoding="utf-8") as f:
    skenario = list(csv.DictReader(f))

hasil = []
for s in skenario:
    masalah = []   # daftar alasan gagal

    # ---- LANGKAH 2: cek isi Co-Pilot untuk kode ICD
    r = cdss_ai.analisis(s["kode_icd"], pakai_llm=False)
    if "error" in r:
        masalah.append("kode ICD tidak ada di data")
        nama_ada, baris = set(), []
    else:
        baris = r["data_klinis"]
        nama_ada = {b["target_nama"] for b in baris}

    for nama in filter(None, s["harus_ada"].split(";")):
        if nama not in nama_ada:
            masalah.append(f"harus ada tapi tidak muncul: {nama}")
    for nama in filter(None, s["harus_tidak_ada"].split(";")):
        if nama in nama_ada:
            masalah.append(f"tidak boleh muncul tapi muncul: {nama}")

    # ---- LANGKAH 3: cek peringatan dari teks dokter
    teks = f'{s["subjektif"]} {s["objektif"]} {s["planning"]}'
    obat, kondisi, peringatan = cdss_ai.peringatan_dari_teks(teks)
    muncul = {f'{p["jenis"]}:{"+".join(sorted(p["obat"]))}' for p in peringatan}
    muncul_kecil = {m.lower() for m in muncul}
    diharapkan = s["peringatan_diharapkan"]
    if diharapkan == "TIDAK_ADA":
        if muncul:
            masalah.append(f"seharusnya tanpa peringatan, tapi muncul: {sorted(muncul)}")
    else:
        # urutkan nama obat supaya "Alteplase+Warfarin" = "Warfarin+Alteplase"
        jenis, obat_txt = diharapkan.split(":")
        kunci = f'{jenis}:{"+".join(sorted(obat_txt.split("+")))}'.lower()
        if kunci not in muncul_kecil:
            masalah.append(f"peringatan {diharapkan} tidak muncul (yang muncul: {sorted(muncul)})")

    # ---- LANGKAH 4: cek data lineage
    kosong = [b["target_nama"] for b in baris if not str(b["halaman"]).strip()]
    if kosong:
        masalah.append(f"tanpa halaman: {kosong[:3]}")

    # ---- LANGKAH 5: cek perbandingan terapi Planning vs PNPK
    if s["terapi_diharapkan"]:
        banding = cdss_ai.bandingkan_terapi(s["kode_icd"], s["planning"])
        muncul_t = {f'{b["obat"]}={b["status"]}' for b in banding}
        harapan_t = set() if s["terapi_diharapkan"] == "KOSONG" else set(s["terapi_diharapkan"].split(";"))
        if muncul_t != harapan_t:
            masalah.append(f"terapi diharapkan {sorted(harapan_t)}, muncul {sorted(muncul_t)}")

    hasil.append({"id": s["id"], "kode_icd": s["kode_icd"],
                  "status": "LULUS" if not masalah else "GAGAL",
                  "alasan": " | ".join(masalah)})

# ---- LANGKAH 6: tampilkan ringkasan dan simpan
for h in hasil:
    print(h["id"], h["kode_icd"], h["status"], h["alasan"])
lulus = sum(h["status"] == "LULUS" for h in hasil)
print(f"\nRINGKASAN: {lulus} dari {len(hasil)} skenario LULUS")

with open("hasil_uji.csv", "w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=["id", "kode_icd", "status", "alasan"])
    w.writeheader(); w.writerows(hasil)

"""Evaluasi teknis memakai data/skenario_uji.csv.

Kolom skenario:
    no, icd, kondisi_pasien, obat_saat_ini, banding_diharapkan, terapi_diharapkan, peringatan_diharapkan
Isi beberapa nilai dalam satu kolom dipisah titik koma (;).
banding_diharapkan boleh berupa kode ICD atau nama diagnosis.
"""
import csv
import time

from app.reasoning import buat_rekomendasi
from app.safety import cocok_obat


def pisah(teks):
    return [x.strip() for x in (teks or "").split(";") if x.strip()]


def recall(harap, ditemukan):
    if not harap:
        return ""
    return round(sum(1 for h in harap if ditemukan(h)) / len(harap), 2)


baris_hasil = []
with open("data/skenario_uji.csv", encoding="utf-8-sig") as f:
    for s in csv.DictReader(f):
        mulai = time.time()
        hasil = buat_rekomendasi(s["icd"], pisah(s["kondisi_pasien"]), pisah(s["obat_saat_ini"]))
        waktu = round(time.time() - mulai, 2)

        if hasil["status"] != "ok":
            baris_hasil.append({"no": s["no"], "icd": s["icd"], "status": hasil["status"]})
            print(f"Skenario {s['no']}: {hasil['status']}")
            continue

        banding = hasil["diagnosis_banding"]
        terapi = [t["obat"] for t in hasil["terapi"]]
        harap_peringatan = int(s.get("peringatan_diharapkan") or 0)
        muncul = len(hasil["peringatan"])

        baris_hasil.append({
            "no": s["no"],
            "icd": s["icd"],
            "status": "ok",
            "mode": hasil["mode"],
            "recall_banding": recall(pisah(s["banding_diharapkan"]), lambda h: any(
                h.upper() == (d.get("icd") or "").upper() or h.lower() == d["nama"].lower() for d in banding)),
            "recall_terapi": recall(pisah(s["terapi_diharapkan"]), lambda h: any(cocok_obat(t, h) for t in terapi)),
            "peringatan_diharapkan": harap_peringatan,
            "peringatan_muncul": muncul,
            "peringatan_sesuai": str((muncul > 0) == (harap_peringatan > 0)),
            "item_llm_dibuang": hasil.get("item_llm_dibuang", 0),
            "waktu_detik": waktu,
            "di_bawah_2_detik": str(waktu < 2),
        })
        print(f"Skenario {s['no']} selesai ({waktu} detik, {muncul} peringatan)")

kolom = ["no", "icd", "status", "mode", "recall_banding", "recall_terapi", "peringatan_diharapkan",
         "peringatan_muncul", "peringatan_sesuai", "item_llm_dibuang", "waktu_detik", "di_bawah_2_detik"]
with open("hasil_evaluasi.csv", "w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=kolom)
    w.writeheader()
    w.writerows(baris_hasil)

ok = [b for b in baris_hasil if b["status"] == "ok"]
if ok:
    def rata(k):
        nilai = [float(b[k]) for b in ok if b[k] != ""]
        return round(sum(nilai) / len(nilai), 2) if nilai else "-"
    print("\nRINGKASAN")
    print("Jumlah skenario:", len(ok))
    print("Rata-rata recall diagnosis banding:", rata("recall_banding"))
    print("Rata-rata recall terapi:", rata("recall_terapi"))
    print("Peringatan keamanan sesuai harapan:", sum(b["peringatan_sesuai"] == "True" for b in ok), "dari", len(ok))
    print("Total item LLM di luar Knowledge Graph yang dibuang:", sum(int(b["item_llm_dibuang"]) for b in ok))
    print("Rata-rata waktu (detik):", rata("waktu_detik"))
    print("Memakai LLM:", sum(b["mode"] == "Knowledge Graph + RAG + LLM" for b in ok), "dari", len(ok))
print("Detail tersimpan di hasil_evaluasi.csv")

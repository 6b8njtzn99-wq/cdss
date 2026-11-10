"""Membuat data/interaksi_obat.csv dari file unduhan DDInter.

Cara pakai (dari folder cdss):
    1. Simpan semua file ddinter_downloads_code_*.csv di folder data/ddinter/
    2. Simpan daftar_obat_pionas.csv di folder data/
    3. Jalankan: python scripts/buat_interaksi.py
"""
import csv
import glob

FOLDER_DDINTER = "data/ddinter"
FILE_PIONAS = "data/daftar_obat_pionas.csv"
FILE_HASIL = "data/interaksi_obat.csv"

# Nama di DDInter (versi Amerika) yang berbeda dengan nama internasional di PIONAS
SINONIM = {
    "acetaminophen": "paracetamol",
    "albuterol": "salbutamol",
    "glyburide": "glibenclamide",
    "rifampin": "rifampicin",
    "meperidine": "pethidine",
    "cyclosporine": "ciclosporin",
    "epinephrine": "adrenaline",
    "norepinephrine": "noradrenaline",
    "lidocaine": "lignocaine",
    "isoproterenol": "isoprenaline",
    "nitroglycerin": "glyceryl trinitrate",
    "dicyclomine": "dicycloverine",
}

TINGKAT = {"Major": "TINGGI", "Moderate": "SEDANG", "Minor": "RENDAH"}

# Peta nama internasional -> nama Indonesia dari PIONAS
peta = {}
with open(FILE_PIONAS, encoding="utf-8") as f:
    for r in csv.DictReader(f):
        en = r["nama_internasional"].strip().lower()
        if en and en not in peta:
            peta[en] = r["nama_obat"].strip()


def ke_indonesia(nama_ddinter):
    kunci = nama_ddinter.strip().lower()
    for calon in (kunci, SINONIM.get(kunci, "")):
        if calon in peta:
            nama = peta[calon]
            return nama[:1].upper() + nama[1:]
    return None


hasil = {}
for path in sorted(glob.glob(f"{FOLDER_DDINTER}/*.csv")):
    with open(path, encoding="utf-8") as f:
        for r in csv.DictReader(f):
            if r["Level"] not in TINGKAT:
                continue  # tingkat "Unknown" dilewati
            a, b = ke_indonesia(r["Drug_A"]), ke_indonesia(r["Drug_B"])
            if not a or not b or a.lower() == b.lower():
                continue
            kunci = tuple(sorted([a.lower(), b.lower()]))
            hasil[kunci] = {
                "obat_a": a,
                "obat_b": b,
                "tingkat": TINGKAT[r["Level"]],
                "keterangan": f"Interaksi {r['Level']} ({r['Drug_A']} - {r['Drug_B']}); cek detail di ddinter.scbdd.com",
                "sumber": f"DDInter ({r['DDInterID_A']} - {r['DDInterID_B']})",
            }

urutan = {"TINGGI": 0, "SEDANG": 1, "RENDAH": 2}
baris = sorted(hasil.values(), key=lambda x: (x["obat_a"].lower(), urutan[x["tingkat"]], x["obat_b"].lower()))
with open(FILE_HASIL, "w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=["obat_a", "obat_b", "tingkat", "keterangan", "sumber"])
    w.writeheader()
    w.writerows(baris)

print(f"Selesai: {len(baris)} pasangan interaksi disimpan di {FILE_HASIL}")
for t in ("TINGGI", "SEDANG", "RENDAH"):
    print(f"  {t}: {sum(1 for x in baris if x['tingkat'] == t)}")

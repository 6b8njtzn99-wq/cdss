"""Mengambil teks kontraindikasi dari file bulk openFDA drug label.

Cara pakai:
    python ekstrak_openfda.py <folder_zip_openfda> <daftar_obat_pionas.csv> <file_hasil.csv>

Script membaca file drug-label-*.json.zip satu per satu secara streaming
(tidak perlu diekstrak dan tidak memakan banyak RAM), lalu mengambil label
yang nama generiknya ada di daftar obat PIONAS.
"""
import csv
import glob
import io
import json
import os
import sys
import zipfile

folder_zip, file_pionas, file_hasil = sys.argv[1], sys.argv[2], sys.argv[3]

# Nama di PIONAS -> nama yang dipakai di label FDA (Amerika)
SINONIM = {
    "paracetamol": "acetaminophen",
    "salbutamol": "albuterol",
    "glibenclamide": "glyburide",
    "rifampicin": "rifampin",
    "pethidine": "meperidine",
    "ciclosporin": "cyclosporine",
    "adrenaline": "epinephrine",
    "noradrenaline": "norepinephrine",
    "lignocaine": "lidocaine",
    "isoprenaline": "isoproterenol",
    "glyceryl trinitrate": "nitroglycerin",
    "dicycloverine": "dicyclomine",
}

# nama generik FDA (huruf kecil) -> (nama Indonesia, nama internasional PIONAS)
target = {}
with open(file_pionas, encoding="utf-8") as f:
    for r in csv.DictReader(f):
        en = r["nama_internasional"].strip().lower()
        if not en:
            continue
        indo = r["nama_obat"].strip()
        indo = indo[:1].upper() + indo[1:]
        for kunci in (en, SINONIM.get(en)):
            if kunci and kunci not in target:
                target[kunci] = (indo, en)


def rapikan(teks_list, batas):
    teks = " ".join(" ".join(t.split()) for t in (teks_list or []))
    return teks[:batas]


def baca_label(path_zip):
    """Generator: keluarkan satu label (dict) per iterasi tanpa memuat seluruh file."""
    with zipfile.ZipFile(path_zip) as z:
        nama = [n for n in z.namelist() if n.endswith(".json")][0]
        with z.open(nama) as raw:
            stream = io.TextIOWrapper(raw, encoding="utf-8")
            decoder = json.JSONDecoder()
            buf = ""
            # cari awal array "results"
            while True:
                potong = stream.read(1 << 20)
                if not potong:
                    return
                buf += potong
                i = buf.find('"results"')
                if i != -1:
                    j = buf.find("[", i)
                    if j != -1:
                        buf = buf[j + 1:]
                        break
            pos = 0
            while True:
                # lewati spasi dan koma pemisah antarlabel
                while pos < len(buf) and buf[pos] in " \n\r\t,":
                    pos += 1
                if pos >= len(buf):
                    potong = stream.read(8 << 20)
                    if not potong:
                        return
                    buf, pos = buf[pos:] + potong, 0
                    continue
                if buf[pos] == "]":
                    return
                try:
                    obj, akhir = decoder.raw_decode(buf, pos)
                except json.JSONDecodeError:
                    potong = stream.read(8 << 20)
                    if not potong:
                        return
                    buf, pos = buf[pos:] + potong, 0
                    continue
                yield obj
                pos = akhir


terbaik = {}  # nama generik -> data label terpilih
jumlah_label = 0
for path in sorted(glob.glob(os.path.join(folder_zip, "drug-label-*.json.zip"))):
    print("Membaca", os.path.basename(path), flush=True)
    for label in baca_label(path):
        jumlah_label += 1
        openfda = label.get("openfda", {})
        nama_generik = [g.strip().lower() for g in openfda.get("generic_name", [])]
        kontra = label.get("contraindications")
        if not kontra:
            continue
        for g in nama_generik:
            if g not in target:
                continue
            tanggal = label.get("effective_time", "")
            resep = "PRESCRIPTION" in " ".join(openfda.get("product_type", []))
            skor = (resep, tanggal)
            lama = terbaik.get(g)
            if lama is None or skor > lama["skor"]:
                terbaik[g] = {
                    "skor": skor,
                    "kontraindikasi": rapikan(kontra, 4000),
                    "kehamilan": rapikan(label.get("pregnancy") or label.get("pregnancy_or_breast_feeding"), 1500),
                    "set_id": label.get("set_id", ""),
                    "tanggal": tanggal,
                    "merek": ", ".join(openfda.get("brand_name", [])[:3]),
                }

baris = []
for g, d in terbaik.items():
    indo, en = target[g]
    baris.append({
        "obat": indo,
        "nama_internasional": en,
        "nama_di_label_fda": g,
        "kontraindikasi_en": d["kontraindikasi"],
        "kehamilan_en": d["kehamilan"],
        "contoh_merek_fda": d["merek"],
        "tanggal_label": d["tanggal"],
        "sumber": f"openFDA drug label set_id {d['set_id']}",
    })
baris.sort(key=lambda x: x["obat"].lower())

with open(file_hasil, "w", newline="", encoding="utf-8-sig") as f:
    w = csv.DictWriter(f, fieldnames=list(baris[0].keys()) if baris else ["obat"])
    w.writeheader()
    w.writerows(baris)

print(f"Selesai: {jumlah_label} label dibaca, {len(baris)} obat PIONAS punya teks kontraindikasi")
print("Hasil:", file_hasil)

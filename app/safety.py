"""Safety check berbasis aturan (bukan AI): interaksi obat dan kontraindikasi.

Membaca semua file:
    data/interaksi*.csv      kolom: obat_a, obat_b, tingkat, keterangan, sumber
    data/kontraindikasi*.csv kolom: obat, kondisi, keterangan, sumber

Pencocokan nama dibuat toleran terhadap perbedaan ejaan (Amlodipine/Amlodipin,
Captopril/Kaptopril), nama gabungan ("Aspirin + clopidogrel"), nama dalam kurung
("Tiazolidinedion (pioglitazon)"), dan golongan obat ("Antikoagulan" mencakup warfarin).
"""
import csv
import glob
import re

# Golongan obat -> anggota. Dipakai supaya aturan berbasis golongan di PNPK
# (misalnya "Antikoagulan") ikut mengenali nama obatnya. Cek ulang oleh tim/dokter.
GOLONGAN = {
    "antikoagulan": ["warfarin", "doac", "rivaroksaban", "apiksaban", "dabigatran", "edoksaban",
                     "heparin", "lmwh", "enoksaparin"],
    "antiplatelet": ["aspirin", "klopidogrel", "tikagrelor", "silostazol"],
    "statin": ["atorvastatin", "simvastatin", "rosuvastatin", "pravastatin"],
    "sulfonilurea": ["glibenklamid", "glimepirid", "glipizid", "gliklazid"],
    "glinid": ["repaglinid", "nateglinid"],
    "tiazolidinedion": ["pioglitazon"],
    "inhibitor dpp-4": ["sitagliptin", "vildagliptin", "linagliptin", "saksagliptin", "alogliptin"],
    "inhibitor sglt-2": ["empagliflozin", "dapagliflozin", "kanagliflozin", "ipragliflozin"],
    "inhibitor alfa glukosidase": ["akarbose", "voglibosa"],
    "ccb non-dihidropiridin": ["verapamil", "diltiazem"],
    "penyekat beta": ["atenolol", "bisoprolol", "metoprolol", "nebivolol", "propranolol", "karvedilol"],
    "fibrat": ["fenofibrat", "gemfibrozil"],
    "ace inhibitor": ["kaptopril", "enalapril", "lisinopril", "perindopril", "ramipril", "imidapril"],
    "arb": ["kandesartan", "irbesartan", "losartan", "olmesartan", "telmisartan", "valsartan"],
    "oral antidiabetik": ["metformin", "glibenklamid", "glimepirid", "glipizid", "gliklazid",
                          "pioglitazon", "akarbose", "sitagliptin", "vildagliptin", "linagliptin"],
}

# Salah ketik yang sering muncul di data
EJAAN = {"propanolol": "propranolol"}


def _norm(teks):
    """Samakan ejaan: huruf kecil, c->k, th->t, ph->f, x->ks, buang huruf dobel dan 'e' di akhir kata."""
    t = (teks or "").lower().strip()
    t = t.replace("ph", "f").replace("th", "t").replace("x", "ks").replace("qu", "kw").replace("c", "k")
    t = re.sub(r"(.)\1+", r"\1", t)
    t = " ".join(w[:-1] if w.endswith("e") and len(w) > 4 else w for w in t.split())
    return EJAAN.get(t, t)


GOLONGAN_NORM = {_norm(k): [_norm(x) for x in v] for k, v in GOLONGAN.items()}

# Kata keterangan sediaan/pemakaian yang dibuang: "Diltiazem SR" -> "diltiazem"
KETERANGAN = {"sr", "ir", "la", "kd", "iv", "ksr", "er", "rutin", "tartat", "tartrat",
              "profilaksis", "intensif", "oral"}


def _istilah(nama, arah):
    """Pecah satu nama menjadi kumpulan istilah yang sudah dinormalisasi.

    arah="obat"   : nama obat yang dipakai/direkomendasikan; ditambah nama golongannya
                    (Warfarin -> warfarin + antikoagulan)
    arah="aturan" : nama di tabel aturan; golongan diperluas ke anggotanya
                    (Antikoagulan -> antikoagulan + warfarin + doac + ...)
    Dengan dua arah ini, sesama anggota golongan (Metformin dan Akarbose) TIDAK dianggap sama.
    """
    bagian = re.split(r"\s*(?:\+|;|/|,|\(|\)|\bdan\b|\batau\b)\s*", nama or "")
    hasil = set()
    for b in bagian:
        kata = _norm(b).split()
        while len(kata) > 1 and kata[-1] in KETERANGAN:
            kata.pop()
        n = " ".join(kata)
        if not n:
            continue
        hasil.add(n)
        for gol, anggota in GOLONGAN_NORM.items():
            if arah == "aturan" and (n == gol or n.startswith(gol + " ")):
                hasil.update(anggota)
            if arah == "obat" and n in anggota:
                hasil.add(gol)
    return {h for h in hasil if len(h) >= 3}


def cocok_obat(obat, aturan):
    """True bila obat (rekomendasi atau obat pasien) terkena aturan untuk nama/golongan `aturan`."""
    return bool(_istilah(obat, "obat") & _istilah(aturan, "aturan"))


def cocok_kondisi(kondisi_pasien, kondisi_aturan):
    """Cocok bila sama, atau salah satu memuat yang lain (mis. 'hamil' dan 'kehamilan')."""
    p = _norm(kondisi_pasien)
    if len(p) < 4:
        return False
    for bagian in [kondisi_aturan] + kondisi_aturan.split(";"):
        a = _norm(bagian)
        if len(a) >= 4 and (p == a or p in a or a in p):
            return True
    return False


def _baca(pola):
    baris = []
    for path in sorted(glob.glob(pola)):
        with open(path, encoding="utf-8-sig") as f:
            baris.extend(csv.DictReader(f))
    return baris


INTERAKSI = _baca("data/interaksi*.csv")
KONTRAINDIKASI = _baca("data/kontraindikasi*.csv")


def daftar_kondisi():
    return sorted({r["kondisi"].strip() for r in KONTRAINDIKASI if r.get("kondisi")}, key=str.lower)


def daftar_obat():
    nama = set()
    for r in INTERAKSI:
        nama.update([r["obat_a"].strip(), r["obat_b"].strip()])
    return sorted(nama, key=str.lower)


def cek_keamanan(obat_rekomendasi, kondisi_pasien=None, obat_saat_ini=None):
    """Kembalikan daftar peringatan.

    - Interaksi: satu sisi cocok dengan obat yang direkomendasikan, sisi lain cocok
      dengan obat yang sedang dikonsumsi pasien.
    - Kontraindikasi: obat yang direkomendasikan cocok dengan kondisi pasien.
    """
    obat_saat_ini = [o for o in (obat_saat_ini or []) if o.strip()]
    kondisi_pasien = [k for k in (kondisi_pasien or []) if k.strip()]
    peringatan, sudah = [], set()

    def tambah(jenis, tingkat, rekom, pesan, sumber):
        kunci = (jenis, rekom.lower(), pesan)
        if kunci not in sudah:
            sudah.add(kunci)
            peringatan.append({"jenis": jenis, "tingkat": tingkat, "obat": rekom,
                               "pesan": pesan, "sumber": sumber})

    for rekom in obat_rekomendasi:
        for row in INTERAKSI:
            a, b = row["obat_a"], row["obat_b"]
            for sisi_rekom, sisi_lain in ((a, b), (b, a)):
                if not cocok_obat(rekom, sisi_rekom):
                    continue
                for o in obat_saat_ini:
                    if cocok_obat(o, sisi_lain):
                        tambah("INTERAKSI OBAT", row["tingkat"], rekom,
                               f"{rekom} dengan obat pasien {o} ({a} + {b}): {row['keterangan']}",
                               row["sumber"])

        for row in KONTRAINDIKASI:
            if not cocok_obat(rekom, row["obat"]):
                continue
            for k in kondisi_pasien:
                if cocok_kondisi(k, row["kondisi"]):
                    tambah("KONTRAINDIKASI", "TINGGI", rekom,
                           f"{rekom} pada pasien dengan {row['kondisi']}: {row['keterangan']}",
                           row["sumber"])

    return peringatan

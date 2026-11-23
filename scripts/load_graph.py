"""Memuat semua CSV relasi ke Knowledge Graph Neo4j.

File yang dibaca (semuanya opsional, minimal satu harus ada):
    data/relasi_*.csv    (contoh: relasi_dm2.csv, relasi_hipertensi.csv, relasi_stroke.csv)
    data/relasi/*.csv
    data/relasi.csv

Jenis relasi:
    DIAGNOSIS_BANDING  -> node Diagnosis (pembanding)
    PEMERIKSAAN        -> node Pemeriksaan
    TERAPI_*           -> node Terapi (semua jenis terapi: LINI_1, LINI_2, LANJUTAN, AKUT, dst.)
    jenis lainnya      -> node Panduan (SASARAN, ALGORITMA, KLASIFIKASI, KRISIS_HIPERTENSI, dst.)

Jalankan dari folder utama project:
    python scripts/load_graph.py
"""
import csv
import glob
import os

from dotenv import load_dotenv
from neo4j import GraphDatabase

load_dotenv()
driver = GraphDatabase.driver(
    os.getenv("NEO4J_URI"),
    auth=(os.getenv("NEO4J_USER"), os.getenv("NEO4J_PASSWORD")),
)

Q_UTAMA = """
MERGE (d:Diagnosis {kunci: $icd})
SET d.icd = $icd, d.nama = $diagnosis, d.utama = true
"""

Q_BANDING = """
MATCH (d:Diagnosis {kunci: $icd})
MERGE (b:Diagnosis {kunci: $kunci})
SET b.icd = $kode, b.nama = $nama
MERGE (d)-[r:DIAGNOSIS_BANDING]->(b)
SET r.alasan = $detail, r.sumber = $sumber, r.halaman = $halaman, r.urutan = $urutan
"""

Q_PEMERIKSAAN = """
MATCH (d:Diagnosis {kunci: $icd})
MERGE (p:Pemeriksaan {nama: $nama})
SET p.jenis = $kode
MERGE (d)-[r:PERLU_PEMERIKSAAN]->(p)
SET r.tujuan = $detail, r.sumber = $sumber, r.halaman = $halaman, r.urutan = $urutan
"""

Q_TERAPI = """
MATCH (d:Diagnosis {kunci: $icd})
MERGE (o:Terapi {nama: $nama})
MERGE (d)-[r:TERAPI {kategori: $relasi}]->(o)
SET r.detail = $detail, r.kode = $kode, r.sumber = $sumber, r.halaman = $halaman, r.urutan = $urutan
"""

Q_PANDUAN = """
MATCH (d:Diagnosis {kunci: $icd})
MERGE (g:Panduan {kategori: $relasi, nama: $nama, icd: $icd})
MERGE (d)-[r:PANDUAN]->(g)
SET r.detail = $detail, r.kode = $kode, r.sumber = $sumber, r.halaman = $halaman, r.urutan = $urutan
"""


def jalankan(query, **param):
    driver.execute_query(query, parameters_=param, database_="neo4j")


daftar_file = sorted(set(glob.glob("data/relasi_*.csv")) | set(glob.glob("data/relasi/*.csv")))
if os.path.exists("data/relasi.csv"):
    daftar_file.insert(0, "data/relasi.csv")
if not daftar_file:
    raise SystemExit("Tidak ada file relasi. Simpan CSV di data/relasi_*.csv, data/relasi/ atau data/relasi.csv")

# Hapus isi graf lama supaya script aman dijalankan berulang kali
jalankan("MATCH (n) DETACH DELETE n")

jumlah = {"DIAGNOSIS_BANDING": 0, "PEMERIKSAAN": 0, "TERAPI": 0, "PANDUAN": 0}
urutan = 0
for path in daftar_file:
    with open(path, encoding="utf-8-sig") as f:
        baris_file = list(csv.DictReader(f))
    print(f"Membaca {path}: {len(baris_file)} baris")

    for baris in baris_file:
        icd = (baris.get("icd") or "").strip().upper()
        nama = (baris.get("target_nama") or "").strip()
        if not icd or not nama:
            continue  # lewati baris kosong
        urutan += 1
        relasi = (baris.get("relasi") or "").strip().upper()
        kode = (baris.get("target_kode") or "").strip().upper()
        param = {
            "icd": icd,
            "diagnosis": (baris.get("diagnosis") or "").strip(),
            "relasi": relasi,
            "kode": kode,
            "nama": nama,
            "detail": (baris.get("detail") or "").strip(),
            "sumber": (baris.get("sumber") or "").strip(),
            "halaman": (baris.get("halaman") or "").strip(),
            "urutan": urutan,
        }
        jalankan(Q_UTAMA, **param)

        if relasi == "DIAGNOSIS_BANDING":
            # Diagnosis banding tanpa kode ICD tetap dimuat, dikenali lewat namanya
            jalankan(Q_BANDING, kunci=kode or f"NAMA:{nama.lower()}", **param)
            jumlah["DIAGNOSIS_BANDING"] += 1
        elif relasi == "PEMERIKSAAN":
            jalankan(Q_PEMERIKSAAN, **param)
            jumlah["PEMERIKSAAN"] += 1
        elif relasi.startswith("TERAPI"):
            jalankan(Q_TERAPI, **param)
            jumlah["TERAPI"] += 1
        else:
            jalankan(Q_PANDUAN, **param)
            jumlah["PANDUAN"] += 1

print("\nSelesai memuat Knowledge Graph:")
for jenis, n in jumlah.items():
    print(f"  {jenis}: {n}")
print(f"  TOTAL: {sum(jumlah.values())} relasi")
driver.close()

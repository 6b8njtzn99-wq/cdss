import os

from dotenv import load_dotenv
from neo4j import GraphDatabase

load_dotenv()
driver = GraphDatabase.driver(
    os.getenv("NEO4J_URI"),
    auth=(os.getenv("NEO4J_USER"), os.getenv("NEO4J_PASSWORD")),
)


def _query(query, **param):
    records, _, _ = driver.execute_query(query, parameters_=param, database_="neo4j")
    return [r.data() for r in records]


def daftar_diagnosis():
    """Semua diagnosis utama yang ada di Knowledge Graph (untuk pilihan di dashboard)."""
    return _query("""
        MATCH (d:Diagnosis {utama: true})
        RETURN d.icd AS icd, d.nama AS nama ORDER BY d.icd
    """)


def _cari_kunci(icd):
    """Cari diagnosis utama. Kalau E11.9 tidak ada, coba kode induknya (E11)."""
    calon = [icd]
    if "." in icd:
        calon.append(icd.split(".")[0])
    for kode in calon:
        hasil = _query("MATCH (d:Diagnosis {kunci: $k, utama: true}) RETURN d.nama AS nama", k=kode)
        if hasil:
            return kode, hasil[0]["nama"]
    return None, None


def ambil_pengetahuan(icd):
    """Ambil semua relasi pasti dari Knowledge Graph untuk satu kode ICD."""
    kunci, nama = _cari_kunci(icd)
    if kunci is None:
        return None

    banding = _query("""
        MATCH (:Diagnosis {kunci: $k})-[r:DIAGNOSIS_BANDING]->(b:Diagnosis)
        RETURN b.icd AS icd, b.nama AS nama, r.alasan AS alasan,
               r.sumber AS sumber, r.halaman AS halaman
        ORDER BY r.urutan
    """, k=kunci)

    pemeriksaan = _query("""
        MATCH (:Diagnosis {kunci: $k})-[r:PERLU_PEMERIKSAAN]->(p:Pemeriksaan)
        RETURN p.nama AS nama, p.jenis AS jenis, r.tujuan AS tujuan,
               r.sumber AS sumber, r.halaman AS halaman
        ORDER BY r.urutan
    """, k=kunci)

    terapi = _query("""
        MATCH (:Diagnosis {kunci: $k})-[r:TERAPI]->(o:Terapi)
        RETURN o.nama AS obat, r.kategori AS kategori, r.detail AS dosis,
               r.sumber AS sumber, r.halaman AS halaman
        ORDER BY r.urutan
    """, k=kunci)

    panduan = _query("""
        MATCH (:Diagnosis {kunci: $k})-[r:PANDUAN]->(g:Panduan)
        RETURN g.kategori AS kategori, g.nama AS nama, r.detail AS detail,
               r.kode AS kode, r.sumber AS sumber, r.halaman AS halaman
        ORDER BY r.urutan
    """, k=kunci)

    return {
        "icd": kunci,
        "nama": nama,
        "diagnosis_banding": banding,
        "pemeriksaan": pemeriksaan,
        "terapi": terapi,
        "panduan": panduan,
    }

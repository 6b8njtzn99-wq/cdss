import json
import os

import psycopg2
from dotenv import load_dotenv

load_dotenv()


def koneksi():
    return psycopg2.connect(
        host=os.getenv("POSTGRES_HOST", "localhost"),
        user=os.getenv("POSTGRES_USER"),
        password=os.getenv("POSTGRES_PASSWORD"),
        dbname=os.getenv("POSTGRES_DB"),
    )


def _jalankan(sql, param=None, ambil=False):
    conn = koneksi()
    try:
        with conn, conn.cursor() as cur:
            cur.execute(sql, param)
            return cur.fetchone()[0] if ambil else None
    finally:
        conn.close()


def buat_tabel():
    _jalankan("""
        CREATE TABLE IF NOT EXISTS log_rekomendasi (
            id SERIAL PRIMARY KEY,
            waktu TIMESTAMP DEFAULT NOW(),
            icd_input VARCHAR(10),
            hasil JSONB,
            waktu_proses_detik REAL,
            keputusan_dokter VARCHAR(20),
            catatan_dokter TEXT,
            waktu_keputusan TIMESTAMP
        )
    """)


def simpan_log(icd, hasil, waktu_proses):
    return _jalankan(
        "INSERT INTO log_rekomendasi (icd_input, hasil, waktu_proses_detik) "
        "VALUES (%s, %s, %s) RETURNING id",
        (icd, json.dumps(hasil, ensure_ascii=False), waktu_proses),
        ambil=True,
    )


def simpan_keputusan(log_id, keputusan, catatan):
    _jalankan(
        "UPDATE log_rekomendasi SET keputusan_dokter = %s, catatan_dokter = %s, "
        "waktu_keputusan = NOW() WHERE id = %s",
        (keputusan, catatan, log_id),
    )

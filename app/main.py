import time
from typing import List

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from app import db
from app.graph import ambil_pengetahuan, daftar_diagnosis
from app.reasoning import buat_rekomendasi, label_kategori
from app.safety import daftar_kondisi, daftar_obat

app = FastAPI(title="CDSS Clinical Co-Pilot")

# Izinkan tampilan web lain (misalnya frontend SOAP di localhost port lain) memanggil API ini
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

db.buat_tabel()


class Permintaan(BaseModel):
    icd: str
    kondisi_pasien: List[str] = []
    obat_saat_ini: List[str] = []


class Keputusan(BaseModel):
    log_id: int
    keputusan: str  # DITERIMA / DIUBAH / DITOLAK
    catatan: str = ""


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/opsi")
def opsi():
    """Pilihan untuk dashboard: diagnosis, kondisi pasien, dan obat yang dikenal sistem."""
    return {"diagnosis": daftar_diagnosis(), "kondisi": daftar_kondisi(), "obat": daftar_obat()}


@app.get("/diagnosis/{icd}")
def diagnosis(icd: str):
    """Data Knowledge Graph untuk satu kode ICD, tanpa LLM dan tanpa safety check (cepat).

    Contoh: GET /diagnosis/I64 atau /diagnosis/E11.9 (otomatis dicari ke kode induk E11).
    """
    kg = ambil_pengetahuan(icd.strip().upper())
    if kg is None:
        raise HTTPException(status_code=404, detail=f"Kode {icd} belum ada di Knowledge Graph")
    for t in kg["terapi"]:
        t["kategori_label"] = label_kategori(t.get("kategori"))
    for g in kg["panduan"]:
        g["kategori_label"] = label_kategori(g.get("kategori"))
    return kg


@app.post("/recommend")
def recommend(p: Permintaan):
    mulai = time.time()
    hasil = buat_rekomendasi(p.icd, p.kondisi_pasien, p.obat_saat_ini)
    if hasil["status"] == "tidak_ditemukan":
        raise HTTPException(status_code=404, detail=hasil["pesan"])
    hasil["waktu_proses_detik"] = round(time.time() - mulai, 2)
    hasil["log_id"] = db.simpan_log(p.icd, hasil, hasil["waktu_proses_detik"])
    return hasil


@app.post("/keputusan")
def keputusan(k: Keputusan):
    if k.keputusan not in ("DITERIMA", "DIUBAH", "DITOLAK"):
        raise HTTPException(status_code=400, detail="Keputusan harus DITERIMA, DIUBAH, atau DITOLAK")
    db.simpan_keputusan(k.log_id, k.keputusan, k.catatan)
    return {"status": "tersimpan"}

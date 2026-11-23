# CDSS Clinical Co-Pilot

Clinical Decision Support System berbasis **Knowledge Graph** dan **Retrieval-Augmented Generation (RAG)** untuk membantu dokter menyusun diagnosis banding, pemeriksaan penunjang, dan terapi sesuai Pedoman Nasional Pelayanan Kedokteran (PNPK) Kemenkes.

Kelompok 7 · Manajemen Data · Departemen Teknologi Kedokteran ITS

## Cakupan

| ICD-10 | Penyakit | Sumber |
| --- | --- | --- |
| E11 | Diabetes melitus tipe 2 | PNPK Tata Laksana DM Tipe 2 Dewasa (KMK HK.01.07/MENKES/302/2026) |
| I10 | Hipertensi esensial | PNPK Tata Laksana Hipertensi Dewasa (KMK HK.01.07/MENKES/303/2026) |
| I64 | Stroke | PNPK Tata Laksana Stroke (KMK HK.01.07/MENKES/304/2026) |

## Arsitektur

- **Neo4j**: Knowledge Graph diagnosis, diagnosis banding, pemeriksaan, terapi, dan panduan klinis
- **ChromaDB**: vector database potongan dokumen PNPK (RAG)
- **Gemini**: merangkum rekomendasi; item di luar Knowledge Graph otomatis dibuang
- **Safety check berbasis aturan**: interaksi obat (PNPK + DDInter) dan kontraindikasi (PNPK)
- **PostgreSQL**: log rekomendasi dan keputusan dokter
- **FastAPI** (backend) dan **Streamlit** (dashboard dokter)

## Struktur folder

```
app/        reasoning engine, API, koneksi database
scripts/    pemuatan data (Knowledge Graph, RAG) dan pengolahan data mentah
ui/         dashboard Streamlit
data/       relasi_*.csv, interaksi*.csv, kontraindikasi*.csv, skenario_uji.csv, ppk/ (PDF PNPK)
```

## Versi yang dipakai

- Python 3.12
- Neo4j 5 dan PostgreSQL 16 (lewat Docker, lihat `docker-compose.yml`)
- ChromaDB (lokal, folder `chroma_db/`)
- Gemini (`gemini-3.5-flash`, bisa diganti lewat `GEMINI_MODEL`)

## Menjalankan

1. Salin `.env.example` menjadi `.env`, lalu isi nilainya (password Neo4j/PostgreSQL dan `GEMINI_API_KEY`). File `.env` tidak di-upload ke GitHub.
2. Simpan PDF PNPK di `data/ppk/` (PDF tidak ikut di repo karena ukurannya besar).
3. Jalankan:

```
py -3.12 -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
docker compose up -d
python scripts/load_graph.py
python scripts/ingest_ppk.py
uvicorn app.main:app --reload
```

Dokumentasi API: http://127.0.0.1:8000/docs. Neo4j Browser: http://localhost:7474.

Dashboard dokter (opsional): `streamlit run ui/dashboard.py`.

Evaluasi teknis: `python evaluasi.py` (hasil di `hasil_evaluasi.csv`).

## Endpoint API

| Method | Endpoint | Fungsi |
| --- | --- | --- |
| GET | `/health` | Cek API hidup |
| GET | `/opsi` | Daftar diagnosis, kondisi pasien, dan obat yang dikenal sistem |
| GET | `/diagnosis/{icd}` | Data Knowledge Graph untuk satu kode ICD (tanpa LLM, cepat) |
| POST | `/recommend` | Rekomendasi lengkap: Knowledge Graph + RAG + LLM + safety check |
| POST | `/keputusan` | Simpan keputusan dokter (DITERIMA / DIUBAH / DITOLAK) |

### Contoh: `GET /diagnosis/I10`

Hasil (dipotong):

```json
{
  "icd": "I10",
  "nama": "Hipertensi esensial",
  "diagnosis_banding": [
    {"icd": "G47.3", "nama": "Obstructive sleep apnea",
     "alasan": "Mengorok; obesitas; sakit kepala pagi hari; mengantuk siang hari",
     "sumber": "PNPK Tata Laksana Hipertensi Dewasa (KMK HK.01.07/MENKES/303/2026)", "halaman": "11"}
  ],
  "pemeriksaan": [
    {"nama": "EKG 12-lead", "jenis": "LAIN",
     "tujuan": "Penapisan LVH dan kelainan kardiak; mendokumentasikan denyut dan irama jantung",
     "sumber": "PNPK Tata Laksana Hipertensi Dewasa (KMK HK.01.07/MENKES/303/2026)", "halaman": "22"}
  ],
  "terapi": [
    {"obat": "Hidroklorothiazid", "kategori": "TERAPI_LINI_1", "kategori_label": "Terapi lini pertama",
     "dosis": "Dosis 25-50 mg/hari; frekuensi 1x per hari; waktu pagi hari",
     "sumber": "PNPK Tata Laksana Hipertensi Dewasa (KMK HK.01.07/MENKES/303/2026)", "halaman": "35"}
  ],
  "panduan": ["..."]
}
```

### Contoh: `POST /recommend`

```json
{"icd": "I10", "kondisi_pasien": ["hamil"], "obat_saat_ini": []}
```

Hasilnya berisi `ringkasan`, `diagnosis_banding`, `pemeriksaan`, `terapi`, `panduan`, `peringatan` (misalnya kontraindikasi Captopril pada kehamilan), `mode`, dan `waktu_proses_detik`.

## Catatan

Sistem ini adalah alat bantu. Keputusan klinis tetap di tangan dokter. Pengujian memakai kasus sintetis, bukan data pasien asli.

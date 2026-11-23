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

## Menjalankan

```
py -3.12 -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
docker compose up -d
python scripts/load_graph.py
python scripts/ingest_ppk.py
uvicorn app.main:app --reload
streamlit run ui/dashboard.py
```

Buat file `.env` berisi `GEMINI_API_KEY`, konfigurasi Neo4j, dan PostgreSQL sebelum menjalankan. File ini tidak di-upload ke GitHub.

Evaluasi teknis: `python evaluasi.py` (hasil di `hasil_evaluasi.csv`).

## Catatan

Sistem ini adalah alat bantu. Keputusan klinis tetap di tangan dokter. Pengujian memakai kasus sintetis, bukan data pasien asli.

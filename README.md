# Clinical Co-Pilot (aplikasi SOAP)

Pendukung keputusan klinis (CDSS) berbasis PNPK untuk Stroke dan Diabetes Melitus Tipe 2.
Dokter mengisi Subjektif (S) dan Objektif (O), memilih diagnosis (A), lalu sistem
menyarankan terapi (P) lengkap dengan sumber PNPK dan nomor halaman, peringatan
keamanan obat, dan ringkasan dari Gemini.

Mode demo: bukan pasien sungguhan. Saran bersifat pendukung dan bukan pengganti
penilaian dokter. Data klinis dan aturan telah divalidasi oleh dr. Jovian.

Proyek kelompok 7, mata kuliah Manajemen Data (ITS Teknologi Kedokteran).
Layanan Knowledge Graph, RAG, dan API ada di branch `rag-neo4j`.

## Isi folder

- `app.py` : tampilan Streamlit (S, O, A, P)
- `cdss_ai.py` : pencarian data, aturan keamanan, dan pemanggilan Gemini
- `data/relasi_stroke.csv`, `data/relasi_dm2.csv` : data PNPK per penyakit (kolom sumber dan halaman)
- `skenario_uji.csv` dan `uji_skenario.py` : 45 skenario uji

## Cara menjalankan

1. Pasang Python 3.10 atau lebih baru.
2. Pasang pustaka:
   ```
   pip install streamlit pandas python-dotenv google-genai
   ```
3. Buat file `.env` di folder yang sama dengan `app.py`, isi:
   ```
   GEMINI_API_KEY=isi_kunci_gemini_kamu
   ```
   (Jangan commit file `.env`.)
4. Jalankan:
   ```
   streamlit run app.py
   ```
5. Buka alamat yang muncul (biasanya http://localhost:8501).

## Menjalankan uji skenario

```
python uji_skenario.py
```
Hasil akhir: `RINGKASAN: N dari M skenario LULUS`.

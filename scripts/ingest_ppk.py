import os

import chromadb
from pypdf import PdfReader

FOLDER_PPK = "data/ppk"
PANJANG_POTONGAN = 1000

client = chromadb.PersistentClient(path="chroma_db")
# Hapus koleksi lama supaya script aman dijalankan berulang kali
try:
    client.delete_collection("ppk")
except Exception:
    pass
koleksi = client.get_or_create_collection("ppk")

ids, dokumen, metadata = [], [], []
for nama_file in os.listdir(FOLDER_PPK):
    if not nama_file.lower().endswith(".pdf"):
        continue
    print("Membaca", nama_file)
    reader = PdfReader(os.path.join(FOLDER_PPK, nama_file))
    for nomor, halaman in enumerate(reader.pages, start=1):
        teks = (halaman.extract_text() or "").strip()
        if len(teks) < 50:
            continue
        for awal in range(0, len(teks), PANJANG_POTONGAN):
            ids.append(f"{nama_file}-hal{nomor}-{awal}")
            dokumen.append(teks[awal:awal + PANJANG_POTONGAN + 200])
            metadata.append({"dokumen": nama_file, "halaman": nomor})

print(f"Menyimpan {len(ids)} potongan teks ke ChromaDB...")
for i in range(0, len(ids), 100):
    koleksi.add(ids=ids[i:i + 100], documents=dokumen[i:i + 100], metadatas=metadata[i:i + 100])
    print(f"  {min(i + 100, len(ids))}/{len(ids)}")

print("Selesai")

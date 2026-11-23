import chromadb

client = chromadb.PersistentClient(path="chroma_db")
koleksi = client.get_or_create_collection("ppk")


def cari_ppk(pertanyaan, jumlah=4):
    """Cari potongan teks PPK yang paling mirip maknanya dengan pertanyaan."""
    if koleksi.count() == 0:
        return []
    hasil = koleksi.query(query_texts=[pertanyaan], n_results=min(jumlah, koleksi.count()))
    return [
        {"teks": teks, "dokumen": meta["dokumen"], "halaman": meta["halaman"]}
        for teks, meta in zip(hasil["documents"][0], hasil["metadatas"][0])
    ]

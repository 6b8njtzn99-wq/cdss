import requests
import streamlit as st

API = "http://localhost:8000"

st.set_page_config(page_title="CDSS Co-Pilot", layout="wide")
st.title("CDSS Clinical Co-Pilot")
st.caption("Rekomendasi bersifat pendukung berdasarkan PNPK Kemenkes. Keputusan klinis akhir tetap di tangan dokter.")


@st.cache_data(ttl=300)
def ambil_opsi():
    try:
        return requests.get(f"{API}/opsi", timeout=30).json()
    except requests.RequestException:
        return None


def sumber(item):
    hal = item.get("halaman")
    return f"_Sumber: {item.get('sumber')}{' hal. ' + str(hal) if hal else ''}_"


opsi = ambil_opsi()
if opsi is None:
    st.error("API belum berjalan. Jalankan dulu: uvicorn app.main:app --reload")
    st.stop()

# ---------------- Input ----------------
with st.form("input"):
    pilihan_dx = {f"{d['icd']} - {d['nama']}": d["icd"] for d in opsi["diagnosis"]}
    if pilihan_dx:
        dx = st.selectbox("Diagnosis utama (ICD-10)", list(pilihan_dx.keys()))
        icd = pilihan_dx[dx]
    else:
        icd = st.text_input("Kode ICD-10 diagnosis utama", placeholder="contoh: I10")
    kol_a, kol_b = st.columns(2)
    with kol_a:
        kondisi = st.multiselect("Kondisi pasien", opsi["kondisi"])
        kondisi_lain = st.text_input("Kondisi lain (opsional, pisahkan dengan koma)")
    with kol_b:
        obat_now = st.multiselect("Obat yang sedang dikonsumsi", opsi["obat"])
        obat_lain = st.text_input("Obat lain (opsional, pisahkan dengan koma)")
    kirim = st.form_submit_button("Minta rekomendasi", type="primary")

if kirim and icd:
    kondisi_semua = kondisi + [x.strip() for x in kondisi_lain.split(",") if x.strip()]
    obat_semua = obat_now + [x.strip() for x in obat_lain.split(",") if x.strip()]
    with st.spinner("Memproses rekomendasi..."):
        r = requests.post(f"{API}/recommend", timeout=180, json={
            "icd": icd, "kondisi_pasien": kondisi_semua, "obat_saat_ini": obat_semua})
    if r.status_code == 200:
        st.session_state["hasil"] = r.json()
        st.session_state.pop("tersimpan", None)
    else:
        st.session_state.pop("hasil", None)
        st.error(r.json().get("detail", r.text))

# ---------------- Hasil ----------------
hasil = st.session_state.get("hasil")
if hasil:
    du = hasil["diagnosis_utama"]
    st.header(f"{du['nama']} ({du['icd']})")

    peringatan = hasil.get("peringatan", [])
    if peringatan:
        st.subheader(f"Peringatan keamanan ({len(peringatan)})")
        for p in peringatan:
            st.error(f"**{p['jenis']} · {p['tingkat']}**  \n{p['pesan']}  \nSumber: {p['sumber']}")
    else:
        st.success("Tidak ada peringatan interaksi obat atau kontraindikasi untuk data pasien ini.")

    if hasil.get("ringkasan"):
        st.info(hasil["ringkasan"])

    tab1, tab2, tab3, tab4 = st.tabs(["Terapi", "Pemeriksaan penunjang", "Diagnosis banding", "Panduan klinis"])

    with tab1:
        kategori = []
        for t in hasil["terapi"]:
            if t["kategori_label"] not in kategori:
                kategori.append(t["kategori_label"])
        for kat in kategori:
            st.markdown(f"#### {kat}")
            for t in [x for x in hasil["terapi"] if x["kategori_label"] == kat]:
                tanda = "⚠️ " if t.get("ada_peringatan") else ""
                bintang = " ⭐ prioritas" if t.get("prioritas") else ""
                st.markdown(f"**{tanda}{t['obat']}**{bintang}  \n{t.get('dosis') or ''}  \n{sumber(t)}")
                if t.get("penjelasan_ai"):
                    st.caption(f"Penjelasan AI: {t['penjelasan_ai']}")

    with tab2:
        for p in hasil["pemeriksaan"]:
            st.markdown(f"**{p['nama']}** ({p.get('jenis') or '-'})  \n{p.get('tujuan') or ''}  \n{sumber(p)}")
            if p.get("penjelasan_ai"):
                st.caption(f"Penjelasan AI: {p['penjelasan_ai']}")

    with tab3:
        if not hasil["diagnosis_banding"]:
            st.write("Tidak ada diagnosis banding di sumber untuk diagnosis ini.")
        for d in hasil["diagnosis_banding"]:
            kode = f"{d['icd']} " if d.get("icd") else ""
            st.markdown(f"**{kode}{d['nama']}**  \n{d.get('alasan') or ''}  \n{sumber(d)}")
            if d.get("penjelasan_ai"):
                st.caption(f"Penjelasan AI: {d['penjelasan_ai']}")

    with tab4:
        kategori = []
        for g in hasil["panduan"]:
            if g["kategori_label"] not in kategori:
                kategori.append(g["kategori_label"])
        for kat in kategori:
            with st.expander(kat):
                for g in [x for x in hasil["panduan"] if x["kategori_label"] == kat]:
                    st.markdown(f"**{g['nama']}**  \n{g.get('detail') or ''}  \n{sumber(g)}")

    st.caption(f"Mode: {hasil.get('mode')} · Waktu proses: {hasil.get('waktu_proses_detik')} detik · "
               f"Item LLM di luar Knowledge Graph yang dibuang: {hasil.get('item_llm_dibuang', 0)} · "
               f"Log ID: {hasil.get('log_id')}")

    # ---------------- Keputusan dokter ----------------
    st.divider()
    st.subheader("Keputusan dokter")
    keputusan = st.radio("Keputusan", ["DITERIMA", "DIUBAH", "DITOLAK"], horizontal=True)
    catatan = st.text_area("Catatan atau perubahan dari dokter")
    if st.button("Simpan keputusan"):
        requests.post(f"{API}/keputusan", timeout=30, json={
            "log_id": hasil["log_id"], "keputusan": keputusan, "catatan": catatan})
        st.session_state["tersimpan"] = keputusan
    if st.session_state.get("tersimpan"):
        st.success(f"Keputusan {st.session_state['tersimpan']} tersimpan ke log PostgreSQL")

"""
app.py - Clinical Co-Pilot, tata letak SOAP (sesuai masukan dr. Jovian).

Alur layar:
  S (Subjektif)  : teks bebas, TIDAK dianalisis
  O (Objektif)   : teks bebas, TIDAK dianalisis
  A (Asesmen)    : pilih kode ICD-10 diagnosis utama  -> ini satu-satunya yang dianalisis
      -> Co-Pilot menampilkan: Diagnosa banding (+ kode ICD-10),
         Saran pemeriksaan penunjang, Saran tatalaksana (semua dari PNPK)
  P (Planning)   : teks bebas, TIDAK dianalisis

Jalankan:  python -m streamlit run app.py
"""
import time
import streamlit as st
import cdss_ai  # modul AI dan data CSV

st.set_page_config(page_title="Clinical Co-Pilot", page_icon="🩺", layout="wide")

# Tampilan: warna teal seperti mockup, lencana huruf S/O/A/P, kode ICD berlabel
st.markdown("""
<style>
.block-container {max-width: 1200px; padding-top: 1.5rem;}
.lencana {display:inline-flex; width:28px; height:28px; border-radius:8px;
          background:#E3F1F3; color:#0F6F7C; font-weight:700;
          align-items:center; justify-content:center; margin-right:10px;}
.lencana.utama {background:#0F6F7C; color:#FFFFFF;}
.judul-bagian {font-size:1.15rem; font-weight:600; margin:0.4rem 0;}
.kode {background:#E3F1F3; color:#0A4F59; padding:1px 7px; border-radius:6px;
       font-size:0.85rem; font-weight:600; margin-right:6px;}
div[data-testid="stVerticalBlockBorderWrapper"] {border-radius:12px;}
</style>
""", unsafe_allow_html=True)


def bagian(huruf, nama, utama=False):
    """Judul bagian SOAP dengan lencana huruf."""
    kelas = "lencana utama" if utama else "lencana"
    st.markdown(f'<div class="judul-bagian"><span class="{kelas}">{huruf}</span>{nama}</div>',
                unsafe_allow_html=True)


# ---------------------------------------------------------------
# Daftar ICD-10 untuk dropdown: diambil otomatis dari data CSV,
# jadi kalau ada penyakit/kode baru di CSV, dropdown ikut bertambah.
# ---------------------------------------------------------------
ref = cdss_ai.RELASI[["icd", "diagnosis"]].drop_duplicates()
ADA_DATA = set(ref["icd"])
PILIHAN = {f"{r.icd} - {r.diagnosis}": r.icd for r in ref.itertuples()}

# Kode utama menurut dr. Jovian: I60, I61, I63, I69 (stroke), E11. Kode tambahan di bawah
# atas permintaan kelompok dan BELUM divalidasi dokter, jadi diberi tanda.
TAMBAHAN = {"I64", "I65", "I66", "I67", "I10"}
PILIHAN = {(k + " [tambahan, belum divalidasi]" if v in TAMBAHAN and v != "I10" else k): v
           for k, v in PILIHAN.items()}
PILIHAN = dict(sorted(PILIHAN.items()))


# Judul kelompok tatalaksana yang enak dibaca
JUDUL = {
    "TATA_LAKSANA_UMUM": "Tata laksana umum", "TERAPI_AKUT": "Terapi fase akut",
    "KRITERIA_TROMBOLISIS": "Kriteria trombolisis", "TROMBEKTOMI": "Trombektomi",
    "TERAPI_KHUSUS": "Kondisi khusus", "TERAPI_PSA": "Terapi perdarahan subaraknoid",
    "TERAPI_PERDARAHAN_INTRASEREBRAL": "Terapi perdarahan intraserebral",
    "TERAPI_PENCEGAHAN": "Terapi pencegahan", "TERAPI_BEDAH": "Tindakan bedah dan revaskularisasi",
    "REHABILITASI_FPKTP": "Rehabilitasi di FPKTP", "REHABILITASI_FASE_AKUT": "Rehabilitasi fase akut",
    "REHABILITASI_SUBAKUT": "Rehabilitasi subakut", "PERSIAPAN_PULANG": "Persiapan pulang dan kembali bekerja", "PENCEGAHAN_SEKUNDER": "Pencegahan sekunder",
}
TIDAK_TERMASUK = {"DIAGNOSIS_BANDING", "PEMERIKSAAN", "KLASIFIKASI"}

if "hasil" not in st.session_state:
    st.session_state.hasil = None
if "jejak" not in st.session_state:
    st.session_state.jejak = []


def judul(kode):
    return JUDUL.get(kode, kode.replace("_", " ").capitalize())


# ---------------------------------------------------------------
st.title("🩺 Clinical Co-Pilot")
st.caption("Pendukung keputusan klinis berbasis PNPK  |  "
           "🟠 MODE DEMO: bukan pasien sungguhan")

# ---------------------------------------------------------------
# S - Subjektif, O - Objektif (teks bebas, tidak dianalisis)
# ---------------------------------------------------------------
kiri, kanan = st.columns(2)
with kiri:
    bagian("S", "Subjektif")
    teks_s = st.text_area("Keluhan pasien", height=130, label_visibility="collapsed",
                 placeholder="Keluhan utama, riwayat penyakit... (teks bebas)")
with kanan:
    bagian("O", "Objektif")
    teks_o = st.text_area("Pemeriksaan", height=130, label_visibility="collapsed",
                 placeholder="Tanda vital, pemeriksaan fisik, hasil lab... (teks bebas)")
st.caption("Saran Co-Pilot hanya dari kode ICD-10. Teks S, O, dan P hanya dibaca untuk peringatan keamanan obat.")

# ---------------------------------------------------------------
# A - Asesmen: pilih kode ICD-10
# ---------------------------------------------------------------
bagian("A", "Asesmen", utama=True)
pilih = st.selectbox("Diagnosis utama (ICD-10)", list(PILIHAN))
tekan = st.button("Minta saran Co-Pilot", type="primary")

if tekan and PILIHAN[pilih] not in ADA_DATA:
    st.session_state.hasil = None
    st.session_state.kosong = PILIHAN[pilih]
elif tekan:
    st.session_state.kosong = None
    icd = PILIHAN[pilih]
    mulai = time.time()
    cepat = cdss_ai.analisis(icd, pakai_llm=False)
    st.session_state.hasil = {
        "icd": icd, "data": cdss_ai.cari_diagnosis(icd),
        "diagnosis": cepat["diagnosis"], "sumber": cepat["sumber"],
        "waktu_cari": cepat["waktu_cari_dan_cek_detik"],
        "mulai": mulai, "ai": None, "waktu_total": None,
    }

hasil = st.session_state.hasil
if st.session_state.get("kosong"):
    st.info(f"Data PNPK untuk {st.session_state.kosong} belum dimasukkan ke sistem, "
            "jadi Co-Pilot belum bisa memberi saran. Dokter tetap bisa mengisi S, O, dan P.")

# ---------------------------------------------------------------
# Kartu Co-Pilot
# ---------------------------------------------------------------
if hasil:
    data, icd = hasil["data"], hasil["icd"]
    st.subheader(f"Co-Pilot: {icd} - {hasil['diagnosis']}")

    if icd.startswith("I6"):
        st.warning("Terapi stroke berbeda untuk tiap jenis (I60 perdarahan subaraknoid, "
                   "I61 perdarahan intraserebral, I63 infark). Pastikan jenis stroke "
                   "sudah dikonfirmasi dengan CT-scan kepala.")
    if icd == "I64":
        st.info("Jenis stroke belum ditentukan, jadi terapi spesifik belum ditampilkan. "
                "Tentukan jenisnya dulu, lalu pilih I60, I61, atau I63.")

    kotak_ai = st.container()
    k1, k2, k3 = st.columns(3)

    with k1.container(border=True):
        st.markdown("### Diagnosa banding")
        baris = data[data["relasi"] == "DIAGNOSIS_BANDING"]
        if baris.empty:
            st.info("Belum ada data diagnosis banding di PNPK yang sudah dimasukkan.")
        for r in baris.itertuples():
            kode = f'<span class="kode">{r.target_kode}</span>' if r.target_kode else ""
            st.markdown(f"{kode}**{r.target_nama}**", unsafe_allow_html=True)
            st.caption(f"{r.detail}  (hal {r.halaman})")

    with k2.container(border=True):
        st.markdown("### Saran pemeriksaan penunjang")
        baris = data[data["relasi"] == "PEMERIKSAAN"]
        if baris.empty:
            st.info("Belum ada data pemeriksaan.")
        for r in baris.itertuples():
            st.markdown(f"**{r.target_nama}**")
            st.caption(f"{r.detail}  (hal {r.halaman})")

    with k3.container(border=True):
        st.markdown("### Saran tatalaksana")
        terapi = data[~data["relasi"].isin(TIDAK_TERMASUK)]
        if terapi.empty:
            st.info("Belum ada data tatalaksana.")
        for jenis, grup in terapi.groupby("relasi", sort=False):
            st.markdown(f"_{judul(jenis)}_")
            for r in grup.itertuples():
                st.markdown(f"**{r.target_nama}**")
                st.caption(f"{r.detail}  (hal {r.halaman})")

    # Ringkasan AI: dihitung sekali, setelah kartu tampil
    with kotak_ai:
        if hasil["ai"] is None:
            with st.spinner("AI sedang merangkum dari data PNPK..."):
                try:
                    ai = cdss_ai.tanya_gemini(hasil["diagnosis"], data, [])
                except Exception as e:  # AI gagal: kartu tetap valid
                    ai = {"error_llm": str(e)}
            hasil["ai"] = ai
            hasil["waktu_total"] = round(time.time() - hasil["mulai"], 2)
        ai = hasil["ai"]
        if "error_llm" in ai:
            st.warning("Ringkasan AI sedang tidak tersedia (layanan Gemini sibuk). "
                       "Saran dari data PNPK di bawah tetap valid.")
        else:
            st.markdown("**Ringkasan AI (hanya dari data PNPK)**")
            st.info(ai.get("ringkasan", ""))

    st.markdown("**Sumber data**")
    for s in hasil["sumber"]:
        st.code(s, language=None)

# ---------------------------------------------------------------
# P - Planning (teks bebas + cek interaksi obat otomatis)
# ---------------------------------------------------------------
bagian("P", "Planning")
rencana = st.text_area("Rencana", height=110, label_visibility="collapsed",
                       placeholder="Rencana terapi, edukasi, tindak lanjut... (teks bebas)")


# Peringatan keamanan dari teks S + O + P (aturan CSV, tanpa LLM)
obat_ada, kondisi_ada, peringatan = cdss_ai.peringatan_dari_teks(f"{teks_s} {teks_o} {rencana}")
if obat_ada:
    st.markdown("**⚠️ Peringatan keamanan obat (dari teks yang dokter tulis)**")
    st.caption(f"Obat terbaca: {', '.join(obat_ada)}"
               + (f"  |  Kondisi terbaca: {', '.join(kondisi_ada)}" if kondisi_ada else ""))
    if not peringatan:
        st.success("Tidak ada interaksi atau kontraindikasi di basis data untuk obat tersebut.")
    for p in peringatan:
        isi = (f"**{p['jenis']} ({p['tingkat']})**: {' + '.join(p['obat'])}  \n"
               f"{p['isi']}  \n_Sumber: {p['sumber']}_")
        (st.error if p["tingkat"] in ("TINGGI", "TIDAK_DIREKOMENDASIKAN") else st.warning)(isi)

# Bandingkan obat di Planning dengan terapi PNPK untuk ICD yang dipilih
if hasil:
    banding = cdss_ai.bandingkan_terapi(hasil["icd"], rencana)
    if banding:
        st.markdown("**💊 Perbandingan terapi di Planning dengan PNPK**")
        for b in banding:
            if b["status"] == "SESUAI_PNPK":
                rujukan = "; ".join(f"{x['target_nama']} ({x['relasi'].replace('_', ' ').lower()}, hal {x['halaman']})"
                                    for x in b["baris"])
                st.success(f"**{b['obat'].capitalize()}**: tercantum di PNPK, {rujukan}")
            elif b["status"] == "TIDAK_DIANJURKAN_PNPK":
                rujukan = "; ".join(f"{x['target_nama']}, hal {x['halaman']}: {x['detail']}" for x in b["baris"])
                st.warning(f"**{b['obat'].capitalize()}**: PNPK tidak menganjurkan. {rujukan}")
            else:
                st.info(f"**{b['obat'].capitalize()}**: tidak tercantum di data PNPK kami untuk diagnosis ini. "
                        "Belum tentu salah, mohon dicek dokter.")
        st.caption("Hanya mencocokkan nama obat. Dosis dan kecocokan dengan kondisi pasien tetap penilaian dokter.")

# Keputusan dokter (Human-in-the-Loop)
if hasil:
    st.divider()
    alasan = st.text_input("Catatan / alasan (wajib bila Ubah atau Tolak)")
    b1, b2, b3 = st.columns(3)
    keputusan = None
    if b1.button("✅ Terima saran", use_container_width=True):
        keputusan = "TERIMA"
    if b2.button("✏️ Ubah", use_container_width=True):
        keputusan = "UBAH"
    if b3.button("❌ Tolak", use_container_width=True):
        keputusan = "TOLAK"
    if keputusan:
        if keputusan != "TERIMA" and not alasan.strip():
            st.error("Isi catatan/alasan dulu untuk Ubah atau Tolak.")
        else:
            st.session_state.jejak.append({
                "waktu": time.strftime("%H:%M:%S"), "icd": hasil["icd"],
                "keputusan": keputusan, "catatan": alasan or "-"})
            st.success(f"Keputusan '{keputusan}' tercatat.")

    m1, m2, m3 = st.columns(3)
    m1.metric("Pencarian data", f"{hasil['waktu_cari']} dtk")
    m2.metric("Total respons (termasuk AI)", f"{hasil['waktu_total']} dtk")
    m3.metric("Model AI", (hasil["ai"] or {}).get("model_dipakai", "-"))

if st.session_state.jejak:
    with st.expander("Jejak keputusan dokter (audit log)"):
        st.table(st.session_state.jejak)

st.divider()
st.caption("Saran sistem ini bersifat pendukung dan bukan pengganti penilaian dokter. "
           "Keputusan klinis akhir sepenuhnya ada pada dokter.")

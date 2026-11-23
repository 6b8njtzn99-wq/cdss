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

st.set_page_config(page_title="Clinical Co-Pilot", page_icon="✚", layout="wide")

# Tampilan: warna teal seperti mockup, lencana huruf S/O/A/P, kode ICD berlabel
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&display=swap');
html, body, [class*="css"], .stApp {font-family:'Plus Jakarta Sans', sans-serif;}
.stApp {background: linear-gradient(180deg,#EAF6F7 0%,#F8FBFB 320px,#FFFFFF 100%);}
header[data-testid="stHeader"] {background:transparent;}
.block-container {max-width: 1240px; padding-top: 1.2rem; padding-bottom: 3rem;}

/* ---- Hero ---- */
.hero {display:flex; align-items:center; gap:18px; background: linear-gradient(120deg,#0B5560 0%,#0F6F7C 55%,#1CA3A3 100%);
       border-radius:22px; padding:26px 32px; color:#fff; margin-bottom:18px;
       box-shadow:0 14px 34px rgba(15,111,124,.28); position:relative; overflow:hidden;}
.hero:after {content:""; position:absolute; right:-60px; top:-60px; width:230px; height:230px;
             border-radius:50%; background:rgba(255,255,255,.10);}
.hero h1 {margin:0; font-size:2rem; font-weight:800; letter-spacing:-.5px; color:#fff; padding:0;}
.logo {width:56px; height:56px; border-radius:16px; background:rgba(255,255,255,.18); border:1px solid rgba(255,255,255,.35); display:flex; align-items:center; justify-content:center; font-size:1.7rem; font-weight:800; flex-shrink:0;}
.hero p {margin:4px 0 0; font-size:1rem; opacity:.92;}
.pil {display:inline-block; padding:4px 12px; border-radius:999px; font-size:.78rem;
      font-weight:600; margin-right:8px; background:rgba(255,255,255,.18); color:#fff;
      border:1px solid rgba(255,255,255,.28);}
.pil.demo {background:#FFB547; color:#5A3300; border-color:#FFB547;}

/* ---- Lencana SOAP + judul bagian ---- */
.lencana {display:inline-flex; width:34px; height:34px; border-radius:11px;
          background:#D7EEF0; color:#0F6F7C; font-weight:800;
          align-items:center; justify-content:center; margin-right:12px;}
.lencana.utama {background:linear-gradient(135deg,#0F6F7C,#1CA3A3); color:#FFFFFF;
                box-shadow:0 4px 10px rgba(15,111,124,.35);}
.judul-bagian {font-size:1.2rem; font-weight:700; margin:1.1rem 0 .5rem; color:#0B3D44;}
.kode {background:#D7EEF0; color:#0A4F59; padding:2px 9px; border-radius:7px;
       font-size:.82rem; font-weight:700; margin-right:7px;}

/* ---- Kartu ---- */
div[data-testid="stVerticalBlockBorderWrapper"] {border-radius:16px; border:1px solid #D5E7E9;
    background:#FFFFFF; box-shadow:0 4px 16px rgba(15,111,124,.07); transition:all .2s ease;}
div[data-testid="stVerticalBlockBorderWrapper"]:hover {box-shadow:0 10px 26px rgba(15,111,124,.15);
    border-color:#9FD0D4;}
div[data-testid="stColumn"] h3 {color:#0F6F7C; font-weight:800; font-size:1.15rem !important;
    padding-bottom:8px; margin-bottom:10px; border-bottom:3px solid #BFE3E6;}

/* ---- Input ---- */
div[data-baseweb="select"] > div {border-radius:12px; border-color:#C5DEE1;}

/* ---- Tombol ---- */
button[kind="primary"] {background:linear-gradient(120deg,#0F6F7C,#1CA3A3); border:none;
    border-radius:12px; font-weight:700; padding:.6rem 1.6rem;
    box-shadow:0 6px 16px rgba(15,111,124,.32); transition:transform .15s ease;}
button[kind="primary"]:hover {transform:translateY(-2px); box-shadow:0 10px 22px rgba(15,111,124,.4);}
button[kind="secondary"] {border-radius:12px; border-color:#9FD0D4;}

/* ---- Notifikasi ---- */
div[data-testid="stAlert"] {border-radius:14px; border:none; box-shadow:0 2px 8px rgba(0,0,0,.05);}
hr {border-color:#D5E7E9;}
/* ---- Kunci warna: tampil sama di tema terang maupun gelap ---- */
:root, .stApp {color-scheme: light !important;}
.stApp, .stApp p, .stApp li, .stApp span, .stApp label, .stApp h2, .stApp h3, .stApp h4,
.stApp div[data-testid="stMarkdownContainer"] {color:#12313A;}
.stApp [data-testid="stCaptionContainer"], .stApp [data-testid="stCaptionContainer"] * {color:#3A5A62 !important;}
.stApp label p, .stApp label {color:#0B3D44 !important; font-weight:600;}
.stApp .hero, .stApp .hero h1, .stApp .hero p, .stApp .hero .logo, .stApp .hero * {color:#FFFFFF !important;}
.stApp .lencana.utama {color:#FFFFFF !important;}
.stApp .lencana {color:#0F6F7C;}
.stApp .lencana.utama {color:#FFFFFF;}
/* kotak teks */
.stApp [data-testid="stTextAreaRootElement"], .stApp [data-testid="stTextAreaRootElement"] * {background:#FFFFFF !important;}
.stApp [data-testid="stTextAreaRootElement"] {border:1.5px solid #C5DEE1 !important; border-radius:14px !important;}
.stApp [data-testid="stTextAreaRootElement"]:focus-within {border-color:#1CA3A3 !important; box-shadow:0 0 0 3px rgba(28,163,163,.18);}
.stApp textarea {color:#12313A !important; -webkit-text-fill-color:#12313A !important; caret-color:#0F6F7C; border:none !important;}
.stApp textarea::placeholder {color:#7C9AA1 !important; -webkit-text-fill-color:#7C9AA1 !important; opacity:1;}
/* dropdown */
.stApp div[data-baseweb="select"] > div, .stApp div[data-baseweb="select"] span, .stApp div[data-baseweb="select"] input {
    background:#FFFFFF !important; color:#12313A !important; -webkit-text-fill-color:#12313A !important;}
.stApp div[data-baseweb="select"] > div {border:1.5px solid #C5DEE1 !important; border-radius:12px !important;}
.stApp div[data-baseweb="select"] svg {fill:#0F6F7C !important;}
div[data-baseweb="popover"], div[data-baseweb="popover"] * {background:#FFFFFF !important; color:#12313A !important;}
div[data-baseweb="popover"] li:hover, div[data-baseweb="popover"] li[aria-selected="true"] {background:#E3F1F3 !important;}
.stApp input[type="text"] {background:#FFFFFF !important; color:#12313A !important; -webkit-text-fill-color:#12313A !important;}
/* tombol */
.stApp button[kind="primary"], .stApp button[kind="primary"] * {color:#FFFFFF !important;}
.stApp button[kind="secondary"], .stApp button[kind="secondary"] * {background:#FFFFFF !important; color:#0F6F7C !important;}
/* notifikasi: warna per jenis */
.stApp [data-testid="stAlertContainer"] {border-radius:14px; border:1px solid transparent;}
.stApp [data-testid="stAlertContainer"] * {color:#12313A !important; background:transparent !important;}
.stApp [data-testid="stAlertContainer"]:has([data-testid="stAlertContentSuccess"]) {background:#E3F6EA !important; border-color:#A9DDBB;}
.stApp [data-testid="stAlertContainer"]:has([data-testid="stAlertContentError"]) {background:#FDE8E8 !important; border-color:#F2B3B3;}
.stApp [data-testid="stAlertContainer"]:has([data-testid="stAlertContentWarning"]) {background:#FFF3D6 !important; border-color:#F2D58A;}
.stApp [data-testid="stAlertContainer"]:has([data-testid="stAlertContentInfo"]) {background:#E3F1F7 !important; border-color:#A9D3E6;}
.stApp div[data-testid="stColumn"] h3 {color:#0F6F7C !important;}
.stApp hr {border-color:#D5E7E9;}
.stApp div[data-baseweb="select"] * {background:#FFFFFF !important;}
.stApp [data-testid="stCaptionContainer"] {opacity:1 !important;}
.stApp [data-testid="stCaptionContainer"] p {color:#34545C !important; opacity:1 !important;}
.stApp [data-testid="stColumn"] [data-testid="stVerticalBlock"]:not(:has([data-testid="stVerticalBlock"])) {border:1px solid #CFE4E7 !important; border-radius:16px !important;
    background:#FFFFFF !important; box-shadow:0 4px 16px rgba(15,111,124,.08); transition:box-shadow .2s ease, border-color .2s ease;}
.stApp [data-testid="stColumn"] [data-testid="stVerticalBlock"]:not(:has([data-testid="stVerticalBlock"])):hover {box-shadow:0 10px 26px rgba(15,111,124,.16); border-color:#9FD0D4 !important;}

/* ---- Gaya mengikuti desain Figma (tampilan saja) ---- */
.stApp {background: radial-gradient(circle at 6% 28%, rgba(140,195,208,.60) 0, transparent 34%),
        radial-gradient(circle at 94% 22%, rgba(110,200,200,.50) 0, transparent 36%),
        radial-gradient(circle at 12% 88%, rgba(140,195,215,.50) 0, transparent 34%),
        linear-gradient(180deg,#CDE3E9 0%,#DBEDEF 100%) !important;}
.block-container {max-width: 1100px !important;}
.stApp .hero h1 {text-transform:uppercase; letter-spacing:.5px; font-weight:800 !important; font-size:2.1rem !important;}
.stApp .lencana, .stApp .lencana.utama {background:linear-gradient(135deg,#0F6F7C,#1CA3A3) !important; color:#FFFFFF !important;
    box-shadow:0 4px 10px rgba(15,111,124,.30); border-radius:10px;}
.stApp .judul-bagian {margin:.2rem 0 .7rem !important;}
/* kartu S, O, A, P */
.stApp .st-key-kartu_s, .stApp .st-key-kartu_o, .stApp .st-key-kartu_a, .stApp .st-key-kartu_p {
    background:#FFFFFF !important; border:1px solid #E1EEF1 !important; border-radius:18px !important;
    padding:1.1rem 1.3rem 1.2rem !important; box-shadow:0 10px 28px rgba(15,70,90,.10) !important;}
.stApp .st-key-kartu_s:hover, .stApp .st-key-kartu_o:hover, .stApp .st-key-kartu_a:hover, .stApp .st-key-kartu_p:hover {
    box-shadow:0 14px 32px rgba(15,70,90,.16) !important; border-color:#E1EEF1 !important;}
/* kotak teks dan dropdown */
.stApp [data-testid="stTextAreaRootElement"], .stApp [data-testid="stTextAreaRootElement"] * {background:#E8F1F5 !important;}
.stApp [data-testid="stTextAreaRootElement"] {border:1.5px solid #B7D0D9 !important; border-radius:10px !important;}
.stApp div[data-baseweb="select"] *  {background:#D9E9EE !important;}
.stApp div[data-baseweb="select"] > div {border:1.5px solid #6FAAB8 !important; border-radius:8px !important;}
/* tombol utama oranye-merah, kecil, rata kiri */
.stApp button[kind="primary"] {background:linear-gradient(180deg,#DD5520,#BC3A0A) !important; border:none !important;
    border-radius:8px !important; font-size:.85rem !important; padding:.35rem 1.3rem !important;
    box-shadow:0 6px 14px rgba(188,58,10,.35) !important;}
.stApp button[kind="primary"]:hover {transform:translateY(-1px); box-shadow:0 9px 18px rgba(188,58,10,.45) !important;}
/* notifikasi */
.stApp [data-testid="stAlertContainer"]:has([data-testid="stAlertContentSuccess"]) {background:#C9ECD8 !important; border-color:#A8DDBE !important;}
.stApp [data-testid="stAlertContainer"]:has([data-testid="stAlertContentWarning"]) {background:#FDE8A6 !important; border-color:#F3D27A !important;}
.stApp [data-testid="stAlertContainer"]:has([data-testid="stAlertContentInfo"]) {background:#C9DDF7 !important; border-color:#9DBFEA !important;}
.stApp [data-testid="stAlertContainer"]:has([data-testid="stAlertContentError"]) {background:#FBD3D3 !important; border-color:#F0AAAA !important;}
/* kartu hasil: judul besar tanpa garis bawah */
.stApp div[data-testid="stColumn"] h3 {border-bottom:none !important; color:#0B3D44 !important; font-size:1.45rem !important; font-weight:600 !important;}
.stApp [data-testid="stColumn"] [data-testid="stVerticalBlock"]:not(:has([data-testid="stVerticalBlock"])) {border-color:#E1EEF1 !important;
    box-shadow:0 8px 22px rgba(15,70,90,.10) !important;}
/* dropdown: kotak akar + isi */
.stApp [data-testid="stSelectbox"] [data-baseweb="select"], .stApp [data-testid="stSelectbox"] [data-baseweb="select"] * {background:#D9E9EE !important; border-color:#6FAAB8 !important;}
.stApp [data-testid="stSelectbox"] [data-baseweb="select"] {border:1.5px solid #6FAAB8 !important; border-radius:8px !important; overflow:hidden;}
.stApp [data-testid="stSelectbox"] [data-baseweb="select"] > div {border:none !important;}
.stApp [data-testid="stSelectbox"] svg {fill:#0F6F7C !important; color:#0F6F7C !important;}
.stApp [data-testid="stSelectbox"] div[role="group"] {background:#D9E9EE !important; border:1.5px solid #6FAAB8 !important; border-radius:8px !important;}
.stApp [data-testid="stSelectbox"] div[role="group"] * {background:transparent !important;}
.stApp [data-testid="stSelectbox"] input {color:#12313A !important; -webkit-text-fill-color:#12313A !important;}
.stApp [data-testid="stSelectbox"] button, .stApp [data-testid="stSelectbox"] [data-testid="stSelectboxVirtualDropdown"] {color:#0F6F7C !important;}
.stApp [data-testid="stTextInput"] [data-baseweb="input"], .stApp [data-testid="stTextInput"] div[role="group"] {background:#E8F1F5 !important; border:1.5px solid #B7D0D9 !important; border-radius:8px !important;}
.stApp [data-testid="stTextInput"] [data-baseweb="input"] *, .stApp [data-testid="stTextInput"] div[role="group"] * {background:transparent !important;}
/* kotak sumber data */
.stApp [data-testid="stCode"], .stApp [data-testid="stCode"] pre, .stApp [data-testid="stCode"] code {background:#D7E8EC !important;
    color:#1B3A44 !important; border-radius:10px;}
.stApp [data-testid="stCode"] {border:1px solid #BCD6DC;}
</style>
""", unsafe_allow_html=True)


def kartu(kunci):
    """Kotak putih berbingkai (tampilan saja). Pakai key bila versi Streamlit mendukung."""
    try:
        return st.container(border=True, key=kunci)
    except TypeError:
        return st.container(border=True)


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
st.markdown("""
<div class="hero">
  <div class="logo">✚</div>
  <div>
    <h1>Clinical Co-Pilot</h1>
    <p>Pendukung keputusan klinis berbasis PNPK</p>
  </div>
</div>
""", unsafe_allow_html=True)

# ---------------------------------------------------------------
# S - Subjektif, O - Objektif (teks bebas, tidak dianalisis)
# ---------------------------------------------------------------
kiri, kanan = st.columns(2)
with kiri, kartu("kartu_s"):
    bagian("S", "Subjektif")
    teks_s = st.text_area("Keluhan pasien", height=130, label_visibility="collapsed", key="teks_s",
                 placeholder="Keluhan utama, riwayat penyakit... (teks bebas)")
with kanan, kartu("kartu_o"):
    bagian("O", "Objektif")
    teks_o = st.text_area("Pemeriksaan", height=130, label_visibility="collapsed", key="teks_o",
                 placeholder="Tanda vital, pemeriksaan fisik, hasil lab... (teks bebas)")
st.caption("Saran Co-Pilot ditentukan oleh kode ICD-10. Teks S, O, dan P dibaca untuk tanda centang (sudah dilakukan), peringatan keamanan obat, dan aturan klinis.")

# ---------------------------------------------------------------
# A - Asesmen: pilih kode ICD-10
# ---------------------------------------------------------------
with kartu("kartu_a"):
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
    # masukan dr. Jovian: TD 220/120 atau kurang pada I63 -> saran antihipertensi tidak ditampilkan
    data = cdss_ai.sembunyikan_antihipertensi(
        icd, data, st.session_state.get("teks_s", ""), st.session_state.get("teks_o", ""))
    st.subheader(f"Co-Pilot: {icd} - {hasil['diagnosis']}")

    # Teks P dibaca dari session_state karena kotak Planning digambar di bawah kartu
    teks_p_kini = st.session_state.get("teks_p", "")
    sudah = cdss_ai.tandai_sudah(data, teks_s, teks_o, teks_p_kini)   # untuk centang
    aturan = cdss_ai.aturan_klinis(icd, teks_s, teks_o, teks_p_kini)  # aturan dr. Jovian

    def centang(relasi, nama, kata):
        """Tanda centang bila sudah tercatat dokter di S/O/P."""
        return f"✅ **{nama}**  _({kata})_" if (relasi, nama) in sudah else f"**{nama}**"

    def asal(r):
        """Teks sumber: halaman PNPK, atau 'praktik klinis tervalidasi' bila bukan dari PNPK."""
        return "praktik klinis tervalidasi" if str(r.halaman).strip() in ("-", "") else f"hal {r.halaman}"

    for a_ in aturan:
        pesan = f"**{a_['judul']}**: {a_['isi']}"
        {"MERAH": st.error, "KUNING": st.warning, "BIRU": st.info}[a_["tingkat"]](pesan)

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
        baris, catatan_ddx = cdss_ai.filter_diagnosis_banding(
            icd, data[data["relasi"] == "DIAGNOSIS_BANDING"], teks_s, teks_o)
        if baris.empty:
            st.info("Belum ada data diagnosis banding di PNPK yang sudah dimasukkan.")
        for r in baris.itertuples():
            kode = f'<span class="kode">{r.target_kode}</span>' if r.target_kode else ""
            st.markdown(f"{kode}**{r.target_nama}**", unsafe_allow_html=True)
            st.caption(f"{r.detail}  ({asal(r)})")
        for c_ in catatan_ddx:
            st.caption(f"ℹ️ {c_}")

    with k2.container(border=True):
        st.markdown("### Saran pemeriksaan penunjang")
        baris = data[data["relasi"] == "PEMERIKSAAN"]
        if baris.empty:
            st.info("Belum ada data pemeriksaan.")
        for r in baris.itertuples():
            st.markdown(centang(r.relasi, r.target_nama, "sudah ada di S/O"))
            st.caption(f"{r.detail}  ({asal(r)})")

    with k3.container(border=True):
        st.markdown("### Saran tatalaksana")
        terapi = data[~data["relasi"].isin(TIDAK_TERMASUK)]
        if terapi.empty:
            st.info("Belum ada data tatalaksana.")
        for jenis, grup in terapi.groupby("relasi", sort=False):
            st.markdown(f"_{judul(jenis)}_")
            for r in grup.itertuples():
                st.markdown(centang(r.relasi, r.target_nama, "sudah tercatat di Planning"))
                st.caption(f"{r.detail}  ({asal(r)})")

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
with kartu("kartu_p"):
    bagian("P", "Planning")
    rencana = st.text_area("Rencana", height=110, label_visibility="collapsed", key="teks_p",
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
           "Keputusan klinis akhir sepenuhnya ada pada dokter.  \n"
           "Data klinis dan aturan dalam aplikasi ini telah divalidasi oleh dr. Jovian.  \n"
           "Mode demo: bukan pasien sungguhan.")

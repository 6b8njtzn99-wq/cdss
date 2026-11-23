import json

from app.reasoning import buat_rekomendasi

# Contoh: pasien hipertensi yang sedang hamil dan sedang minum spironolakton
hasil = buat_rekomendasi("I10", kondisi_pasien=["hamil"], obat_saat_ini=["Spironolakton"])

print(json.dumps(hasil, indent=2, ensure_ascii=False))
print("\nMode:", hasil.get("mode"))
print("Jumlah terapi:", len(hasil.get("terapi", [])))
print("Jumlah peringatan:", len(hasil.get("peringatan", [])))

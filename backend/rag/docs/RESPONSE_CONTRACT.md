# Kontrak Respons Chat

Dokumen ini menjelaskan bentuk jawaban `/api/chat` agar frontend,
evaluasi, dan prompt selalu sepakat.

## Bentuk baku

Setiap jawaban berdasar data memakai tiga bagian:

1. **Baris pembuka** — menyebut dashboard dan chart sumbernya.
2. **Angka** — tabel Markdown ringkas (atau bullets untuk 1-3 baris).
   Satuan mengikuti data. Tidak ada angka karangan.
3. **Blok `Sumber:`** — satu baris per chart yang dipakai:

```
Sumber:
- Dashboard Simpeg (Kepegawaian) — Jumlah Pegawai Berdasarkan Pendidikan (baris 1-14, data 2026-09-24)
```

Jawaban tanpa data (salam, "tidak ada data relevan") tidak memakai
blok sumber.

## Catatan otomatis

Formatter (`rag/chat/response.py`) menambahkan catatan bila perlu:

- Seluruh passages bertanda basi → `_Catatan: seluruh sumber data ini
  ditandai mungkin basi._`
- Cakupan parsial (`rows_covered` tidak penuh) → `_Catatan: data yang
  ditampilkan bersifat parsial dari tabel sumber._`

## Contoh

Pertanyaan: "Berapa jumlah pegawai berdasarkan pendidikan?"

```markdown
Berdasarkan **Dashboard Simpeg (Kepegawaian)**,
chart **Jumlah Pegawai Berdasarkan Pendidikan** (data 2026-09-24):

| Tingkat pendidikan | Jumlah pegawai |
|---|---:|
| Sekolah Dasar | 21 |
| SLTP | 46 |
| SLTA | 441 |

Sumber:
- Dashboard Simpeg (Kepegawaian) — Jumlah Pegawai Berdasarkan Pendidikan (baris 1-14, data 2026-09-24)
```

## Aturan penguji

- `reply_format` selalu `"markdown"` — frontend merender Markdown,
  bukan teks polos.
- Blok `Sumber:` dibangun dari passages aktual, bukan dari teks model.
  Test `tests/test_response.py` memastikan sumber karangan model
  dibuang dan diganti yang asli.
- Bila model mengembalikan teks kosong, API mengembalikan pesan
  fallback, bukan string kosong.

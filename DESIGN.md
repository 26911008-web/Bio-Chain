# Bio-Chain Design System — "Field Noir" (DESIGN.md)

> Versi 1.1 · 2026-10-10 · SATU-SATUNYA sumber pedoman visual (menggantikan DESIGN_SYSTEM.md)
> Referensi visual: SourceOne (Webflow showcase), platform supply chain dengan fokus keberlanjutan.
> Target implementasi: `app/static/index.html` (SPA vanilla HTML/CSS/JS yang disajikan FastAPI).
> Prinsip: **hanya presentation layer**. Fungsi JS, `fetch()` ke API, alur peran, dan `sw.js` tidak diubah.


## 0. Filosofi (Rural-Tech & Circular Agritech)

Bio-Chain menghubungkan ekosistem pedesaan akar rumput (petani padi, operator penggilingan, supir truk logistik) dengan industri manufaktur pirolisis modern dan registri karbon internasional. Desain antarmuka Bio-Chain menganut prinsip:

1. **Dual-Environment Contrast ("Field Noir")**:
   - **Mode `field` (Light / High-Visibility)**: Didesain khusus untuk pemakaian di bawah terik matahari langsung (*direct sunlight 50.000+ lux*) bagi Petani, Pengepul, dan Supir. Tidak ada latar transparan kabur atau teks tipis; kontras teks selalu ≥ 4.5:1 (WCAG 2.1 AA).
   - **Mode `noir` (Dark / Precision Control)**: Didesain untuk ruang kontrol, pabrik pirolisis, auditor karbon, dan admin sistem yang bekerja dengan layar multi-panel dalam durasi lama.
2. **Thumb-First & One-Handed Rural Ergonomics**:
   - Target sentuh aksi utama berukuran besar (≥ 52 px untuk Petani/Pengepul, ≥ 56 px untuk Supir) dengan area aman jempol di bagian bawah layar.
   - Stepper kuantitas numerik dengan tombol preset cepat (+50 kg, +100 kg, +500 kg, +1 ton) untuk mengurangi kesalahan input ketik manual di lapangan.
3. **Resilient Data Integrity & Anti-AI Slop**:
   - Antarmuka mengutamakan kejelasan data faktual, nomor registrasi lot, koordinat GPS, dan status fisik barang nyata.
   - Setiap status tidak hanya dibedakan oleh warna (ramah buta warna), melainkan selalu dipasangkan dengan teks penjelas dan ikon standar.

---

## 1. Ringkasan rekomendasi

| Keputusan | Pilihan | Alasan |
|---|---|---|
| Stack styling | **CSS custom properties murni** di `app/static/tokens.css` + `components.css` | Repo tidak memiliki build step atau Node. Tailwind/Next.js akan menambah toolchain dan berisiko memutus logika SPA |
| Identitas | Monokrom hitam/putih + aksen **lime `#d6ff4d`** (dari referensi) | Sejalan dengan tema "green logistics / circular", tegas, dan tidak generik |
| Tema | **Dua tema dari token yang sama**: `field` (terang) & `noir` (gelap) | Referensi bertema gelap penuh, padahal petani/driver bekerja di bawah sinar matahari. Tema gelap penuh sulit dibaca di luar ruangan |
| Default tema per peran | `field` → petani, pengepul, driver · `noir` → login, pabrik, auditor, admin | Peran lapangan butuh keterbacaan; peran kantor/kontrol mendapat estetika referensi |
| Toggle | Tombol tema di header, disimpan di `localStorage` (try/catch) | Misalnya driver malam hari bisa beralih ke `noir` |
| Font display | **Syne** 800, **hanya momen merek** (logo header & judul login) | Revisi Okt 2026 (audit Refactoring UI): Syne terlalu lebar untuk judul dan angka, membuat nama terpotong di HP dan angka sulit dibaca sekilas. Judul, kartu dan KPI memakai `--font-heading` = Plus Jakarta Sans |
| Font UI/body | **Plus Jakarta Sans** (sudah dipakai) | Syne terlalu lebar untuk tabel dan form di HP 375px. Jakarta Sans lebih mudah dibaca, angkanya tabular |
| Dihapus | Font Outfit, `--bg-mesh` gradient | Diganti Syne; latar dibuat flat sesuai referensi |
| Tidak dipakai | Eurostile (dipakai referensi) | Font komersial berlisensi |

---

## 2. Token warna

### 2.1 Primitif (palet referensi)

| Token | Hex | Sumber |
|---|---|---|
| `--c-black` | `#111111` | `--black` SourceOne |
| `--c-black-2` | `#181818` | `--black-2` (kartu) |
| `--c-black-3` | `#1f1f1f` | turunan, untuk hover |
| `--c-white` | `#ffffff` | |
| `--c-smoke` | `#f8f8f8` | `--white-smoke` |
| `--c-smoke-3` | `#eaeae9` | `--white-smoke-3` (tombol netral) |
| `--c-gainsboro` | `#e8e8e8` | tagline netral |
| `--c-lime` | `#d6ff4d` | `--green` (aksen utama) |
| `--c-olive` | `#4a6300` | turunan lime agar aman dipakai sebagai teks di latar terang |
| `--c-red-pastel` | `#d17171` | `--indian-red` |
| `--c-amber-pastel` | `#eaa065` | `--sandy-brown` |
| `--c-khaki` | `#e4e58b` | `--khaki` |
| `--c-blue-pastel` | `#6e9ac5` | `--cornflower-blue` |
| `--c-green-pastel` | `#82c782` | `--dark-sea-green` |

### 2.2 Semantik (yang dipakai komponen)

| Token | `field` (terang) | `noir` (gelap) | Kontras teks |
|---|---|---|---|
| `--surface-0` (latar halaman) | `#f8f8f8` | `#111111` | — |
| `--surface-1` (kartu) | `#ffffff` | `#181818` | — |
| `--surface-2` (hover, header tabel) | `#f3f3f1` | `#1f1f1f` | — |
| `--border` | `#e2e2de` | `rgba(255,255,255,.14)` | dekoratif |
| `--border-strong` (input, fokus netral) | `#8a8a85` | `rgba(255,255,255,.40)` | ≥3:1 (non-teks) ✅ |
| `--ink` | `#111111` | `#ffffff` | 17.8 / 18.9 ✅ |
| `--ink-muted` | `#525252` | `#b5b5b5` | 7.8 / 8.7 ✅ |
| `--ink-subtle` (placeholder, meta) | `#6b6b6b` | `#a3a3a3` | 5.3 / 7.5 ✅ |
| `--accent` (fill tombol utama) | `#111111` | `#d6ff4d` | — |
| `--on-accent` | `#ffffff` | `#111111` | 18.9 / 16.4 ✅ |
| `--accent-ink` (teks/ikon aksen) | `#4a6300` | `#d6ff4d` | 6.8 / 15.5 ✅ |
| `--accent-soft` (badge/selected) | `#eef8cc` | `rgba(214,255,77,.12)` | teks `#3f5500` 7.5 ✅ |
| `--focus-ring` | `#4a6300` | `#d6ff4d` | ≥3:1 ✅ |

**Aturan lime:** `#d6ff4d` di atas putih hanya mencapai kontras **1.15:1**. Lime **tidak boleh** dipakai sebagai teks atau garis di tema `field`. Di sana lime hanya boleh berupa **fill** dengan teks `#111`, misalnya highlight KPI, progress bar, atau badge "Terverifikasi".

### 2.3 Status

| Status | `field`: teks / soft-bg | `noir`: fill pastel + teks `#111` | Pemakaian |
|---|---|---|---|
| success | `#1f6b2a` / `#e7f4e8` | `#82c782` (9.4:1) | Lulus QC, terkirim, lunas |
| warning | `#9a4a00` / `#fdf0e3` | `#eaa065` (8.7:1) | Menunggu, kadar air batas |
| danger | `#b42318` / `#fdecea` | `#d17171` (5.7:1) | Ditolak, gagal, sengketa |
| info | `#1d4f86` / `#e8f0f9` | `#6e9ac5` (6.4:1) | Dalam perjalanan, catatan |
| pending | `#5b5b00` / `#f7f7d9` | `#e4e58b` (14.3:1) | Draf, antrean offline |

Status **selalu** disertai ikon atau teks, tidak hanya warna, demi aksesibilitas buta warna.

### 2.3a Personalisasi per peran (`<html data-role>`)

Setelah login, `ui-enhance.js` menulis `data-role` dan `data-theme`. Aksen, kepadatan, dan banner sapaan mengikuti peran.

| Peran | Tema default | Aksen field (teks putih) | Aksen noir (teks #111) | Kepadatan | Makna |
|---|---|---|---|---|---|
| Petani | field | `#4a6300` zaitun (6.8:1) | `#d6ff4d` lime | tap 52px, KPI besar | panen / sekam |
| Pengepul | field | `#8a4b00` cokelat sekam (6.8:1) | `#eaa065` | tap 52px | gudang / grading |
| Driver | field | `#1d4f86` biru jalan (8.4:1) | `#9fc3e6` | tap 56px, font 17px | jalan / rute |
| Pabrik | noir | `#4a6300` | `#d6ff4d` lime | padat (tap 40px) | pirolisis / biochar |
| Auditor | noir | `#1d4f86` | `#9fc3e6` | padat + label READ-ONLY | audit, baca saja |
| Admin | noir | `#5b5b00` (7.1:1) | `#e4e58b` khaki | padat | kendali sistem |

**Banner peran** ada di atas Portal Persona, berisi:
- tagline `role_label`
- "Halo, {nama}". Bagian dalam kurung pada nama dipindah menjadi chip.
- deskripsi peran dari data akun demo
- chip mode (Lapangan/Jalan/Kontrol), lokasi kecamatan, dan untuk driver chip "tetap jalan saat offline"
- emblem kubus CSS 3D berisi ikon peran

Di HP deskripsi disembunyikan agar data kerja langsung terlihat. Pengguna tetap bisa mengganti tema lewat tombol ☀️/🌙. Pilihan disimpan, dan akan kembali mengikuti peran bila pengguna memilih tema yang sama dengan default perannya.

### 2.4 Pemetaan token lama (alias, agar JS/inline style tidak rusak)

```css
--primary        → var(--accent-ink)
--primary-dark   → var(--ink)
--primary-light  → var(--c-lime)
--primary-soft   → var(--accent-soft)
--primary-border → var(--border-strong)
--card           → var(--surface-1)
--card-glass     → var(--surface-1)
--bg-mesh        → var(--surface-0)
--ink / --ink-muted / --ink-subtle / --border  → nama sama, nilai baru
--amber*, --red*, --blue*, --purple*           → status warning/danger/info/pending
```
81 hex hardcoded di `index.html` akan diaudit di Fase 2 dan diganti token bila berupa warna UI.

---

## 3. Tipografi

Skala modular **1.25 (major third)**, basis 16px. Line-height rapat untuk display (1.15–1.2, mengikuti referensi) dan lega untuk body (1.5).

| Token | Font | Desktop ≥1280 | Tablet 768 | Mobile 375 | Weight | Pemakaian |
|---|---|---|---|---|---|---|
| `--fs-hero` | Syne | 4rem | 3.25rem | 2.5rem | 700 | Hanya hero halaman login |
| `--fs-h1` | Jakarta Sans | 2.5rem | 2.25rem | 1.75rem | 700 | Judul halaman/peran |
| `--fs-h2` | Jakarta Sans | 2rem | 1.75rem | 1.5rem | 700 | Judul section |
| `--fs-h3` | Jakarta Sans | 1.5rem | 1.375rem | 1.25rem | 600 | Judul kartu |
| `--fs-kpi` | Jakarta Sans | 2.25rem | 2rem | 1.75rem | 700 | Angka KPI (`tabular-nums`) |
| `--fs-lg` | Jakarta | 1.125rem | 1.125rem | 1rem | 500 | Lead text (`text-size-medium`) |
| `--fs-md` | Jakarta | 1rem | 1rem | 1rem | 400 | Body, input (min 16px agar iOS tidak zoom) |
| `--fs-sm` | Jakarta | .875rem | .875rem | .875rem | 500 | Tabel, label |
| `--fs-xs` | Jakarta | .75rem | .75rem | .75rem | 600 | Meta, timestamp |
| `--fs-tag` | Jakarta Sans | .75rem | .75rem | .75rem | 700, UPPERCASE, `letter-spacing:.06em` | Tagline/eyebrow (`.tagline` referensi) |

- Judul memakai `letter-spacing: -0.02em`. Tombol dan nav memakai UPPERCASE dengan `letter-spacing: .02em`, mengikuti gaya `navbar2_link`.
- Ukuran fluid memakai `clamp()`, contoh: `--fs-h1: clamp(1.75rem, 1.2rem + 2.2vw, 2.5rem)`.
- Font Syne dimuat dengan `font-display: swap`, weight 800 saja (hanya logo & judul login).
- Semua angka tampil diformat `id-ID` lewat `num()`/`rp()` (desimal koma), tidak pakai `toFixed()` di UI.
- Ukuran huruf hanya dari token `--fs-*`; jarak hanya dari skala 4/8/12/16/20/24/32 px.

---

## 4. Spacing, layout & breakpoint

**Skala 4px:** `--sp-1:4px · 2:8 · 3:12 · 4:16 · 5:20 · 6:24 · 8:32 · 10:40 · 12:48 · 16:64 · 20:80 · 28:112`

| Breakpoint | Lebar | Gutter (`padding-global`) | Kolom | Kontainer |
|---|---|---|---|---|
| Mobile | <768px (uji 375) | 16px | 4 | 100% |
| Tablet | 768–1279px | 32px | 8 | 100% |
| Desktop | ≥1280px | 48px | 12 | max 90rem (`container-large`) |

- Konsolidasi breakpoint lama (560/640/768/900/1024) menjadi **3 breakpoint** di atas.
- Section padding hanya untuk halaman login/landing: 7rem / 5rem / 4rem. Dashboard memakai jarak antar-kartu `--sp-6` (desktop) dan `--sp-4` (mobile).
- Navigasi peran: desktop berupa tab horizontal di header. Mobile berupa **bottom bar** untuk peran lapangan (petani/pengepul/driver) agar terjangkau ibu jari.
- Tidak boleh ada scroll horizontal pada halaman. Tabel lebar dibungkus `overflow-x:auto` atau berubah menjadi kartu di mobile.

---

## 5. Radius & elevasi

| Token | Nilai | Pemakaian |
|---|---|---|
| `--r-xs` | 6px | chip kecil, nav link (`.375rem` referensi) |
| `--r-sm` | 12px | input, select, dropdown |
| `--r-md` | 16px | kartu, modal, KPI tile (`1rem` referensi, paling sering dipakai) |
| `--r-lg` | 24px | media/peta/foto produk (`1.5rem` referensi) |
| `--r-pill` | 999px | tombol, badge, user pill (`67px` referensi) |

**Elevasi:** referensi memakai **garis rambut (hairline)**, bukan bayangan.
- `--elev-0`: tanpa border (latar)
- `--elev-1`: `1px solid var(--border)`. Ini standar kartu. Referensi memakai 0.5px, tetapi 0.5px tidak konsisten di HP Android low-DPI, jadi dipakai 1px.
- `--elev-2`: border + `0 8px 24px rgba(0,0,0,.08)` (field) / `0 8px 24px rgba(0,0,0,.5)` (noir), untuk dropdown dan toast
- `--elev-3`: modal, `0 24px 64px rgba(0,0,0,.25)` + backdrop `rgba(17,17,17,.6)` dengan `backdrop-filter: blur(4px)` (jika didukung)

---

## 6. Pustaka komponen mikro (spesifikasi Fase 3)

| Komponen | Spesifikasi |
|---|---|
| **Button primary** | Pill, fill `--accent`, teks `--on-accent`, UPPERCASE 700, padding `14px 24px`, tinggi min **48px**. Hover memakai efek **text roll**: label bergeser ke atas dan duplikatnya masuk dari bawah (pola `button-inner-text-hover` referensi) |
| **Button secondary** | Pill, fill `--c-smoke-3` (field) / transparan + border `--border-strong` (noir) |
| **Button ghost / danger** | Ghost: tanpa fill, underline saat hover. Danger: teks/border danger |
| **Badge** | Pill, `--fs-xs` UPPERCASE, ikon titik 6px + label, warna mengikuti tabel status |
| **Tagline/eyebrow** | `--fs-tag`, warna `--accent-ink`, diletakkan di atas judul section |
| **Card** | `--surface-1`, `--elev-1`, radius `--r-md`, padding 40px / 32px / 20px (desktop/tablet/mobile). Hover (bila dapat diklik): border `--border-strong`, `translateY(-2px)` |
| **KPI tile** | Card + angka `--fs-kpi` Jakarta Sans 700 `tabular-nums` + label `--fs-xs` muted. Strip 4px di kiri **hanya untuk status**: `kpi-warn` (kuning), `kpi-danger` (merah), `eval-tile-*`. `kpi-amber/blue/purple` kini netral (dulu dekoratif) |
| **Data table** | Header `--surface-2` sticky, `--fs-sm`, baris 52px, angka rata kanan `tabular-nums`. Di mobile berubah menjadi kartu bertumpuk |
| **Input** | Tinggi 48px, radius `--r-sm`, border `--border-strong`, label selalu terlihat (bukan hanya placeholder), pesan error di bawah dengan `aria-describedby` |
| **Modal** | `<dialog>` atau `role="dialog" aria-modal="true"`, radius `--r-md`, fokus terjebak di dalam, Esc menutup. Di mobile berupa bottom-sheet |
| **Skeleton** | Blok `--surface-2` dengan shimmer 1.2s. Mati bila `prefers-reduced-motion` |
| **Empty state** | Ikon garis 48px, judul `--fs-h3`, satu kalimat, satu tombol aksi |
| **Error banner** | Strip danger-soft + ikon + teks + tombol "Coba lagi", `role="alert"` |
| **Offline banner** (driver) | Strip `pending` sticky di atas: "Offline — N data menunggu sinkron", `aria-live="polite"` |

---

## 7. Motion & micro-interactions

| Token | Nilai |
|---|---|
| `--ease-out` | `cubic-bezier(.22, 1, .36, 1)` |
| `--ease-in-out` | `cubic-bezier(.65, 0, .35, 1)` |
| `--dur-fast` | 120ms (press, toggle) |
| `--dur-base` | 320ms (hover; `.32s` referensi) |
| `--dur-slow` | 560ms (masuk section, modal) |

- **Press:** `scale(.97)` selama `--dur-fast`.
- **Hover tombol:** text roll vertikal 1.5rem selama `--dur-base`.
- **Masuk kartu:** fade + `translateY(12px→0)` berurutan (stagger 40ms, maksimal 6 elemen).
- **Logo mitra di login:** marquee horizontal berjalan lambat (40s), berhenti saat hover/fokus.
- **Disabled:** opacity .45, `cursor:not-allowed`, tanpa animasi.
- **`prefers-reduced-motion: reduce`:** semua transform/marquee/shimmer dimatikan, hanya opacity 0→1 yang tersisa.
- Animasi hanya pada `transform` dan `opacity` (tanpa animasi layout) agar CLS tetap ≈0.

---

## 7a. Ornamen 3D (permintaan tambahan)

Prinsip: **3D sebagai ornamen, bukan penghalang kerja.** Ornamen tidak boleh menutupi data, menunda interaksi, atau menguras baterai HP lapangan. Ornamen dibangun dalam tiga tingkat; tingkat lebih tinggi hanya aktif bila perangkat mampu.

| Tingkat | Teknologi | Di mana | Isi ornamen |
|---|---|---|---|
| **T1 — CSS 3D** (selalu ada) | `perspective` + `transform-style: preserve-3d` + `translateZ`. Tanpa library | Semua peran | **Tilt card** pada KPI & kartu produk (rotasi ≤ `--tilt-max` 8° mengikuti pointer, dengan glare radial). **Badge bertumpuk** (lapisan `--depth-1..3`). **Isometrik karung/pelet sekam** sebagai ilustrasi empty state (SVG + CSS, tanpa WebGL) |
| **T2 — Scroll/hover depth** | CSS `@scroll-timeline` bila didukung, fallback `IntersectionObserver` | Login & dashboard noir (pabrik/auditor/admin) | Kartu "featured" sticky yang terangkat (`translateZ` + skala 0.96→1) saat masuk viewport, mirip `featured_products-wrapper` referensi |
| **T3 — WebGL (three.js)** | three.js dari CDN dengan versi terkunci, dimuat **lazy** hanya di hero login | Hanya halaman login (tema noir) | Ornamen hero: **partikel sekam padi/biochar** melayang membentuk siklus (lingkaran → pelet), material matte gelap + rim-light lime. Kanvas `aria-hidden="true"`, di belakang konten |

**Isi T3 (v2, disusun dengan skill `threejs-*`):**
- **Lighting:** IBL `RoomEnvironment` (PMREM), hemisphere hangat, key light, rim light lime, dan point light di inti.
- **Materials dan shaders:** sekam memakai `instanceColor` emas yang bervariasi. Pelet memakai `MeshPhysicalMaterial` clearcoat dengan tepi fresnel lime (`onBeforeCompile`). Ada 900 partikel debu `ShaderMaterial` yang berkelip (additive).
- **Postprocessing:** `EffectComposer`, lalu `RenderPass`, lalu `UnrealBloomPass` setengah resolusi (0.7 / 0.5 / 0.86), lalu `OutputPass` (ACES).
- **Interaction:** pointer diproyeksikan ke bidang z=0 (ray-plane), dan butiran dalam radius 0,9 menyingkir. Klik di area hero memicu siklus 2,4 detik: sekam tersedot ke inti dan glow naik.
- **Animation:** intro 2,6 detik waktu nyata. Butiran berkumpul dari jauh dan kamera bergerak mendekat.
- **Penurun kualitas otomatis:** bila rata-rata frame lebih dari 29 ms, bloom dimatikan lebih dulu, lalu DPR diturunkan ke 1.
- **Pemuatan dan tampilan:** modul dimuat lewat `<script type="importmap">` (`three`, `three/addons/`) dari jsDelivr dengan versi terkunci 0.160.0. Kanvasnya buram (latar #111), jadi tepinya disamarkan dengan `mask-image: radial-gradient(closest-side …)`.

**Syarat aktif T3 (semuanya wajib):** `!prefers-reduced-motion`, `navigator.connection.saveData !== true`, `deviceMemory ≥ 4` (bila tersedia), WebGL2 tersedia, layar ≥ 768px. Jika salah satu gagal, tampilkan fallback **T1 statis** (SVG isometrik + gradien lime). Render dijeda saat tab tidak terlihat (`visibilitychange`) dan saat kanvas di luar viewport. Batas: ≤ 60fps, `devicePixelRatio` dibatasi 1.5, anggaran JS three.js ≤ 160KB gzip dan tidak ikut di-precache `sw.js` (agar instal offline driver tetap ringan).

**Aturan tilt (T1):**
- JS hanya menulis variabel `--rx`, `--ry`, `--glare-x`, `--glare-y` pada elemen `[data-tilt]`. Tidak ada perubahan pada handler/state bisnis.
- Mati di perangkat sentuh (`@media (hover: none)`) dan bila reduced-motion (`--tilt-max: 0deg`).
- Kartu yang berisi form/tabel **tidak** diberi tilt. Tilt hanya untuk tile ringkasan dan kartu navigasi.
- Kembali ke 0° dengan `--ease-out` `--dur-slow` saat pointer keluar.

Token 3D sudah ada di `tokens.css`: `--persp`, `--persp-deep`, `--tilt-max`, `--depth-1..3`, `--rx/--ry`, `--glare-x/y`, `--ornament-glow`.

Skill pendukung yang direkomendasikan (dari ekosistem skills.sh, repo `cloudai-x/threejs-skills`, ±3.5K stars, 10–17K install): `threejs-fundamentals`, `threejs-geometry`, `threejs-materials`, `threejs-lighting`, `threejs-animation`, `threejs-interaction`.

---

## 8. Aksesibilitas & kondisi lapangan (wajib)

1. Kontras teks ≥ **4.5:1** (body) dan ≥ 3:1 (teks ≥24px & elemen UI). Semua pasangan di §2 sudah dihitung.
2. Fokus keyboard: `outline: 2px solid var(--focus-ring); outline-offset: 2px` pada `:focus-visible` untuk **semua** elemen interaktif. `outline:none` tanpa pengganti dilarang.
3. Target sentuh minimal **48×48px** untuk peran lapangan dan 40px untuk peran kantor.
4. Hierarki heading: satu `<h1>` per tampilan peran, tanpa lompat level.
5. Ikon tanpa label wajib diberi `aria-label`. Elemen dekoratif diberi `aria-hidden="true"`.
6. Font input minimal 16px. Field numerik (berat, kadar air) memakai `inputmode="decimal"`.
7. Tema `field` diuji di kecerahan layar maksimum (simulasi sinar matahari). Info penting tidak boleh hanya dibedakan dengan warna.
8. Performa: tanpa framework baru. CSS tambahan ditargetkan <25KB, font Syne hanya 3 weight. `sw.js` perlu diperbarui agar `tokens.css`/`components.css` ikut di-cache offline.

---

## 9. Struktur file (terimplementasi)

```
app/static/
├── index.html        ← markup + logika bisnis SPA; import map three.js; kartu Evaluasi & Optimasi
├── tokens.css        ← primitif + semantik + [data-theme] + [data-role] + alias token lama
├── components.css    ← komponen, login hero, banner peran, kartu evaluasi, ergonomi lapangan
├── ui-enhance.js     ← tema/peran, a11y runtime, tilt & hero three.js, stepper/foto/sortir/konfirmasi/banner sinyal
└── sw.js             ← shell + 3 file di atas di-precache (three.js hanya runtime cache)
app/services/insights.py  ← KPI & prioritas Evaluasi & Optimasi (deterministik)
```
Tema & peran: atribut `data-theme="field|noir"` dan `data-role` di `<html>`, ditulis `ui-enhance.js` dari peran aktif + preferensi tersimpan.

---

## 10. Ergonomi lapangan (Rural-Tech UX) — terimplementasi di `ui-enhance.js` §4

| Pola | Perilaku | Di mana |
|---|---|---|
| **Stepper kuantitas** | Tombol `−50 · +50 · +100 · +500 · +1 ton` di bawah input kg; tinggi = `--tap-min` (52 px petani/pengepul, 56 px driver). Menulis nilai lalu memicu `input`/`change` sehingga pratinjau harga yang ada ikut menghitung. Menghormati `min`/`max`. | `#f-qty`, `#ls-qty`, `#v-weight`, `#dr-qty` |
| **Konfirmasi transaksi sensitif** | `<dialog>` native (fokus terkunci, Esc = batal) dengan ringkasan angka (kg × Rp = total). Tombol 48 px. Dialog menutup pada klik pertama → klik ganda tidak menggandakan transaksi; `withBusy` tetap mengunci tombol asal. | tawar lelang, terima tawaran, batalkan listing, tandai lunas, simpan QC, selesaikan rute, stop gagal, setujui/tolak DR |
| **Banner "Mode Hemat Sinyal"** | Satu indikator sticky di atas (menggantikan pill status jaringan): offline → "data aman di HP, terkirim otomatis"; sesi berakhir → minta login ulang; online + antrean → tombol "Kirim sekarang". `role=status`, `aria-live=polite`. | semua peran |
| **Foto bukti dari kamera** | `capture=environment` → kompres di HP (maks 1600 px, JPEG 0,75, EXIF terbuang) → `POST /api/v1/uploads` → URL terisi otomatis + thumbnail. Offline → pesan jelas, transaksi tetap bisa disimpan tanpa foto. | `#v-photo`, `rcv-photo-*` |
| **Tabel tersortir** | Judul kolom data menjadi tombol (keyboard Enter/Spasi), `aria-sort`, angka format Indonesia dikenali. Kolom aksi (berisi tombol/input) tidak dijadikan tombol sortir. | semua `table.data-table` |
| **Resi serah-terima** | Setelah timbang pengepul, resi bulanan `TRX-PTN0006-PGP0003-2610-00018` tampil sebagai QR + teks untuk ditunjukkan/difoto bersama petani. | verifikasi pengepul |
| **Gerbang masuk** | Kartu peran besar; daftar akun uji coba **dilipat** (`<details>`), hilang otomatis di produksi (`DEMO_MODE=False`). | login |

## 11. Dashboard Evaluasi & Optimasi per persona

- **Sumber angka:** `app/services/insights.py` — dari ledger yang sama dengan Laporan Bulanan (cakupan per peran ditentukan server). KPI tanpa data berstatus **Data kurang** + petunjuk apa yang perlu diisi; tidak ada angka default karangan.
- **Target:** menu Parameter → grup *Target Evaluasi & Optimasi* (`evaluasi.*`) + parameter domain yang sudah ada (toleransi susut, margin target, toleransi penutupan, kWh/ton rencana, harga dasar, kadar air ideal).
- **Status:** baik / perhatian (di dalam pita `evaluasi.warn_band_pct`) / kritis — selalu ikon + teks, bukan warna saja. Skor = rata-rata berbobot KPI ber-target (100/60/20).
- **Prioritas:** kritis dulu, lalu dampak Rupiah terbesar (dihitung dari data: selisih margin × kg, kg susut di atas toleransi × harga, piutang tertahan, kWh berlebih × tarif).
- **AI (opsional):** tombol "Susun rencana optimasi AI" → `POST /api/v1/assistant/evaluate/stream`. Model hanya menafsirkan blok DATA (berpengaman *prompt injection*); bila AI tidak tersedia, ringkasan otomatis dengan header `X-AI-Fallback`.
- **Visual:** skor = angka besar (bukan gauge); komposisi output pabrik = bar 100% dengan celah 2 px, label langsung + legenda bernilai. Warna kategori memakai slot tervalidasi (`dataviz/validate_palette.js`): terang `#2a78d6 #eb6834 #1baf7a`, gelap `#3987e5 #d95926 #199e70`; sisa massa = arsir netral.

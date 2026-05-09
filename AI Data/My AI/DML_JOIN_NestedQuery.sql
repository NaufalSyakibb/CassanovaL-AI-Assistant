-- ================================================================
--  TUTORIAL SQL LENGKAP
--  Video  : Tutorial Data Manipulation Language (DML) |
--           JOIN & Nested Query
--  Channel: Faqih Hamami
--  Topik  : DML (INSERT/SELECT/UPDATE/DELETE) + JOIN + Subquery
--  DB     : MySQL / MariaDB
-- ================================================================


-- ================================================================
-- BAGIAN 0 : SETUP SCHEMA
-- ================================================================

CREATE DATABASE IF NOT EXISTS db_tutorial;
USE db_tutorial;

-- ── Tabel Mahasiswa ──────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS tb_mahasiswa (
    nim           VARCHAR(13)  PRIMARY KEY,
    nama          VARCHAR(50)  NOT NULL,
    alamat        VARCHAR(100),
    jenis_kelamin CHAR(1),          -- 'L' atau 'P'
    tgl_lahir     DATE,
    email         VARCHAR(60),
    ipk           DECIMAL(3,2) DEFAULT 0.00
);

-- ── Tabel Program Studi ──────────────────────────────────────────
CREATE TABLE IF NOT EXISTS tb_prodi (
    kode_prodi  VARCHAR(5)  PRIMARY KEY,
    nama_prodi  VARCHAR(50) NOT NULL,
    jenjang     VARCHAR(5)           -- D3, S1, S2
);

-- ── Tabel Dosen ──────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS tb_dosen (
    nip         VARCHAR(10)  PRIMARY KEY,
    nama_dosen  VARCHAR(50)  NOT NULL,
    bidang_ahli VARCHAR(40),
    kode_prodi  VARCHAR(5),
    FOREIGN KEY (kode_prodi) REFERENCES tb_prodi(kode_prodi)
);

-- ── Tabel Mata Kuliah ────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS tb_matakuliah (
    kode_mk   VARCHAR(7)  PRIMARY KEY,
    nama_mk   VARCHAR(60) NOT NULL,
    sks       TINYINT,
    semester  TINYINT,
    nip       VARCHAR(10),
    FOREIGN KEY (nip) REFERENCES tb_dosen(nip)
);

-- ── Tabel KRS (Kartu Rencana Studi) ─────────────────────────────
CREATE TABLE IF NOT EXISTS tb_krs (
    id_krs    INT AUTO_INCREMENT PRIMARY KEY,
    nim       VARCHAR(13),
    kode_mk   VARCHAR(7),
    tahun_ak  CHAR(9),              -- contoh: '2023/2024'
    semester  CHAR(6),              -- 'Ganjil' / 'Genap'
    UNIQUE KEY uk_krs (nim, kode_mk, tahun_ak, semester),
    FOREIGN KEY (nim)     REFERENCES tb_mahasiswa(nim),
    FOREIGN KEY (kode_mk) REFERENCES tb_matakuliah(kode_mk)
);

-- ── Tabel Nilai ──────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS tb_nilai (
    nim       VARCHAR(13),
    kode_mk   VARCHAR(7),
    absen     DECIMAL(5,2) DEFAULT 0,
    tugas     DECIMAL(5,2) DEFAULT 0,
    uts       DECIMAL(5,2) DEFAULT 0,
    uas       DECIMAL(5,2) DEFAULT 0,
    PRIMARY KEY (nim, kode_mk),
    FOREIGN KEY (nim)     REFERENCES tb_mahasiswa(nim),
    FOREIGN KEY (kode_mk) REFERENCES tb_matakuliah(kode_mk)
);


-- ================================================================
-- BAGIAN 1 : INSERT — Mengisi Data Awal
-- ================================================================

-- ── Prodi ────────────────────────────────────────────────────────
INSERT INTO tb_prodi VALUES
('SI',  'Sistem Informasi',      'S1'),
('TI',  'Teknik Informatika',    'S1'),
('MI',  'Manajemen Informatika', 'D3'),
('DS',  'Data Science',          'S1');

-- ── Dosen ────────────────────────────────────────────────────────
INSERT INTO tb_dosen VALUES
('D001', 'Dr. Ahmad Fauzi',     'Basis Data',        'SI'),
('D002', 'Ir. Budi Hartono',    'Pemrograman',       'TI'),
('D003', 'Dra. Citra Dewi',     'Algoritma',         'SI'),
('D004', 'M.Kom. Dedi Supriadi','Machine Learning',  'DS'),
('D005', 'Dr. Eka Putri',       'Jaringan',          'TI');

-- ── Mata Kuliah ──────────────────────────────────────────────────
INSERT INTO tb_matakuliah VALUES
('SBD001', 'Sistem Basis Data',           3, 3, 'D001'),
('ALG001', 'Algoritma & Pemrograman',     3, 1, 'D003'),
('WEB001', 'Pemrograman Web',             3, 3, 'D002'),
('JAR001', 'Jaringan Komputer',           3, 4, 'D005'),
('DSC001', 'Pengantar Data Science',      3, 5, 'D004'),
('MAT001', 'Matematika Diskrit',          2, 2, 'D003'),
('OBJ001', 'Pemrograman Berorientasi Obj',3, 2, 'D002');

-- ── Mahasiswa ────────────────────────────────────────────────────
INSERT INTO tb_mahasiswa VALUES
('2301001', 'Ahmad Rizky',     'Jl. Merdeka No.1',    'L', '2003-05-10', 'rizky@email.com',    3.75),
('2301002', 'Bella Safitri',   'Jl. Margacinta No.5', 'P', '2003-07-22', 'bella@email.com',    3.50),
('2301003', 'Cahya Nugraha',   'Jl. Sudirman No.3',   'L', '2002-11-10', 'cahya@email.com',    3.80),
('2301004', 'Dewi Anggraini',  'Jl. Margacinta No.8', 'P', '2003-01-05', 'dewi@email.com',     3.20),
('2301005', 'Eko Prasetyo',    'Jl. Dago No.12',      'L', '2003-09-18', 'eko@email.com',      2.90),
('2301006', 'Fitri Handayani', 'Jl. Merdeka No.7',    'P', '2003-05-30', 'fitri@email.com',    3.90),
('2301007', 'Galih Setiawan',  'Jl. Sukajadi No.4',   'L', '2002-02-14', 'galih@email.com',    3.60),
('2301008', 'Hana Pertiwi',    'Jl. Setiabudi No.9',  'P', '2003-08-25', 'hana@email.com',     3.10),
('2301009', 'Ivan Kusuma',     'Jl. Buah Batu No.2',  'L', '2002-12-01', 'ivan@email.com',     2.75),
('2301010', 'Julia Wati',      'Jl. Cihampelas No.6', 'P', '2003-03-17', 'julia@email.com',    3.45);

-- ── KRS ──────────────────────────────────────────────────────────
INSERT INTO tb_krs (nim, kode_mk, tahun_ak, semester) VALUES
('2301001', 'SBD001', '2023/2024', 'Ganjil'),
('2301001', 'ALG001', '2023/2024', 'Ganjil'),
('2301001', 'WEB001', '2023/2024', 'Ganjil'),
('2301002', 'SBD001', '2023/2024', 'Ganjil'),
('2301002', 'ALG001', '2023/2024', 'Ganjil'),
('2301003', 'SBD001', '2023/2024', 'Ganjil'),
('2301003', 'JAR001', '2023/2024', 'Ganjil'),
('2301004', 'SBD001', '2023/2024', 'Ganjil'),
('2301004', 'MAT001', '2023/2024', 'Ganjil'),
('2301005', 'ALG001', '2023/2024', 'Ganjil'),
('2301006', 'SBD001', '2023/2024', 'Ganjil'),
('2301006', 'DSC001', '2023/2024', 'Ganjil'),
('2301007', 'WEB001', '2023/2024', 'Ganjil'),
('2301008', 'MAT001', '2023/2024', 'Ganjil'),
('2301009', 'ALG001', '2023/2024', 'Ganjil'),
('2301010', 'SBD001', '2023/2024', 'Ganjil'),
('2301010', 'OBJ001', '2023/2024', 'Ganjil');

-- ── Nilai ────────────────────────────────────────────────────────
INSERT INTO tb_nilai VALUES
('2301001','SBD001', 88, 82, 78, 85),
('2301001','ALG001', 75, 70, 72, 68),
('2301001','WEB001', 90, 85, 80, 88),
('2301002','SBD001', 92, 88, 90, 91),
('2301002','ALG001', 85, 87, 89, 86),
('2301003','SBD001', 80, 78, 82, 79),
('2301003','JAR001', 70, 75, 68, 72),
('2301004','SBD001', 65, 60, 62, 68),
('2301004','MAT001', 72, 70, 68, 71),
('2301005','ALG001', 55, 58, 60, 56),
('2301006','SBD001', 95, 92, 94, 96),
('2301006','DSC001', 88, 90, 87, 92),
('2301007','WEB001', 78, 80, 76, 82),
('2301008','MAT001', 68, 65, 70, 66),
('2301009','ALG001', 50, 55, 52, 58),
('2301010','SBD001', 82, 80, 78, 84),
('2301010','OBJ001', 76, 78, 74, 80);


-- ================================================================
-- BAGIAN 2 : SELECT — Menampilkan Data
-- ================================================================

-- Semua mahasiswa
SELECT * FROM tb_mahasiswa;

-- Kolom tertentu + alias
SELECT  nim                 AS 'NIM',
        nama                AS 'Nama Mahasiswa',
        jenis_kelamin       AS 'JK',
        ipk                 AS 'IPK'
FROM    tb_mahasiswa;

-- Filter dengan WHERE
SELECT nama, ipk
FROM   tb_mahasiswa
WHERE  ipk >= 3.5;

-- Kombinasi kondisi
SELECT nama, jenis_kelamin, ipk
FROM   tb_mahasiswa
WHERE  jenis_kelamin = 'P' AND ipk >= 3.5;

-- DISTINCT — hilangkan duplikat
SELECT DISTINCT jenis_kelamin FROM tb_mahasiswa;

-- Ekspresi di SELECT
SELECT  nim, nama,
        YEAR(CURDATE()) - YEAR(tgl_lahir) AS umur
FROM    tb_mahasiswa;


-- ================================================================
-- BAGIAN 3 : UPDATE — Mengubah Data
-- ================================================================

-- Update 1 baris berdasarkan PK
UPDATE tb_mahasiswa
SET    alamat = 'Jl. Pasteur No.20',
       email  = 'rizky.new@email.com'
WHERE  nim = '2301001';

-- Update berdasarkan kondisi
UPDATE tb_mahasiswa
SET    ipk = ipk + 0.05
WHERE  jenis_kelamin = 'P' AND ipk < 3.5;

-- Update nilai UAS
UPDATE tb_nilai
SET    uas = 75
WHERE  nim = '2301005' AND kode_mk = 'ALG001';

-- Update dengan subquery — naikkan IPK mahasiswa yang UAS rata-rata >= 80
UPDATE tb_mahasiswa
SET    ipk = ipk + 0.10
WHERE  nim IN (
    SELECT nim
    FROM   tb_nilai
    GROUP BY nim
    HAVING AVG(uas) >= 80
);


-- ================================================================
-- BAGIAN 4 : DELETE — Menghapus Data
-- ================================================================

-- Hapus baris spesifik
DELETE FROM tb_nilai
WHERE  nim = '2301009' AND kode_mk = 'ALG001';

-- Hapus berdasarkan kondisi
DELETE FROM tb_krs
WHERE  tahun_ak = '2022/2023';

-- Verifikasi sebelum hapus (selalu lakukan ini dulu!)
SELECT * FROM tb_mahasiswa WHERE ipk < 2.80;
-- DELETE FROM tb_mahasiswa WHERE ipk < 2.80;  -- uncomment setelah verifikasi


-- ================================================================
-- BAGIAN 5 : JOIN — Menggabungkan Tabel
-- ================================================================

-- ── 5.1 INNER JOIN ───────────────────────────────────────────────
-- Hanya baris yang cocok di kedua tabel

-- Daftar mata kuliah beserta nama dosen pengampunya
SELECT  mk.kode_mk,
        mk.nama_mk,
        mk.sks,
        d.nama_dosen,
        d.bidang_ahli
FROM    tb_matakuliah mk
INNER JOIN tb_dosen d ON mk.nip = d.nip;

-- Mahasiswa beserta nilai pada mata kuliah tertentu
SELECT  m.nim,
        m.nama,
        mk.nama_mk,
        n.uts,
        n.uas
FROM    tb_nilai n
INNER JOIN tb_mahasiswa  m  ON n.nim     = m.nim
INNER JOIN tb_matakuliah mk ON n.kode_mk = mk.kode_mk
WHERE   mk.kode_mk = 'SBD001'
ORDER BY n.uas DESC;

-- Alternatif menggunakan USING
SELECT  m.nim, m.nama, mk.nama_mk, n.uas
FROM    tb_nilai n
JOIN    tb_mahasiswa  m  USING (nim)
JOIN    tb_matakuliah mk USING (kode_mk);

-- ── 5.2 LEFT JOIN ────────────────────────────────────────────────
-- Semua baris tabel kiri + baris cocok dari kanan (NULL jika tidak ada)

-- Semua mahasiswa, tampilkan nilai SBD001 jika ada
SELECT  m.nim,
        m.nama,
        n.uts,
        n.uas
FROM    tb_mahasiswa m
LEFT JOIN tb_nilai n ON m.nim = n.nim AND n.kode_mk = 'SBD001'
ORDER BY m.nim;

-- Mahasiswa yang BELUM memiliki nilai apapun
SELECT  m.nim, m.nama
FROM    tb_mahasiswa m
LEFT JOIN tb_nilai n ON m.nim = n.nim
WHERE   n.nim IS NULL;

-- Semua mata kuliah meski tidak ada mahasiswanya
SELECT  mk.kode_mk, mk.nama_mk, COUNT(n.nim) AS peserta
FROM    tb_matakuliah mk
LEFT JOIN tb_nilai n ON mk.kode_mk = n.kode_mk
GROUP BY mk.kode_mk, mk.nama_mk
ORDER BY peserta DESC;

-- ── 5.3 RIGHT JOIN ───────────────────────────────────────────────
-- Semua baris tabel kanan + baris cocok dari kiri

-- Semua mata kuliah + dosen, meski dosen belum mengajar mk apapun
SELECT  d.nama_dosen,
        mk.kode_mk,
        mk.nama_mk
FROM    tb_matakuliah mk
RIGHT JOIN tb_dosen d ON mk.nip = d.nip
ORDER BY d.nama_dosen;

-- ── 5.4 NATURAL JOIN ─────────────────────────────────────────────
-- Join otomatis berdasarkan kolom bernama sama, kolom duplikat hanya muncul sekali

SELECT * FROM tb_nilai
NATURAL JOIN tb_matakuliah;

-- ── 5.5 JOIN 3 Tabel ─────────────────────────────────────────────
-- Laporan lengkap: mahasiswa + mata kuliah + dosen + nilai

SELECT  m.nim,
        m.nama              AS mahasiswa,
        mk.nama_mk,
        mk.sks,
        d.nama_dosen        AS dosen,
        n.absen,
        n.tugas,
        n.uts,
        n.uas,
        ROUND(
            (n.absen*0.10 + n.tugas*0.20 + n.uts*0.30 + n.uas*0.40)
        , 2)                AS nilai_akhir
FROM    tb_nilai n
JOIN    tb_mahasiswa  m  USING (nim)
JOIN    tb_matakuliah mk USING (kode_mk)
JOIN    tb_dosen      d  ON mk.nip = d.nip
ORDER BY mk.nama_mk, nilai_akhir DESC;

-- ── 5.6 FULL JOIN (simulasi MySQL) ───────────────────────────────
-- MySQL tidak punya FULL OUTER JOIN, gunakan UNION
SELECT  m.nim, m.nama, n.kode_mk, n.uas
FROM    tb_mahasiswa m
LEFT JOIN tb_nilai n ON m.nim = n.nim
UNION
SELECT  m.nim, m.nama, n.kode_mk, n.uas
FROM    tb_mahasiswa m
RIGHT JOIN tb_nilai n ON m.nim = n.nim;


-- ================================================================
-- BAGIAN 6 : NESTED QUERY (SubQuery)
-- ================================================================

-- ── 6.1 SubQuery di klausa WHERE ─────────────────────────────────

-- Mahasiswa yang mengambil mata kuliah 'Sistem Basis Data'
SELECT  nim, nama
FROM    tb_mahasiswa
WHERE   nim IN (
    SELECT nim
    FROM   tb_krs
    WHERE  kode_mk = (
        SELECT kode_mk
        FROM   tb_matakuliah
        WHERE  nama_mk = 'Sistem Basis Data'
    )
);

-- Mahasiswa dengan IPK di atas IPK rata-rata
SELECT  nim, nama, ipk
FROM    tb_mahasiswa
WHERE   ipk > (SELECT AVG(ipk) FROM tb_mahasiswa)
ORDER BY ipk DESC;

-- Mahasiswa yang nilai UAS SBD001-nya di atas rata-rata UAS SBD001
SELECT  m.nim, m.nama, n.uas
FROM    tb_nilai n
JOIN    tb_mahasiswa m USING (nim)
WHERE   n.kode_mk = 'SBD001'
  AND   n.uas > (
      SELECT AVG(uas)
      FROM   tb_nilai
      WHERE  kode_mk = 'SBD001'
  )
ORDER BY n.uas DESC;

-- ── 6.2 SubQuery dengan ANY / ALL ────────────────────────────────

-- Mahasiswa dengan IPK > IPK mahasiswa mana saja di Jl. Margacinta
SELECT  nim, nama, ipk
FROM    tb_mahasiswa
WHERE   ipk > ANY (
    SELECT ipk
    FROM   tb_mahasiswa
    WHERE  alamat LIKE '%Margacinta%'
);

-- Mahasiswa dengan IPK > IPK SEMUA mahasiswa laki-laki
SELECT  nim, nama, ipk
FROM    tb_mahasiswa
WHERE   ipk > ALL (
    SELECT ipk
    FROM   tb_mahasiswa
    WHERE  jenis_kelamin = 'L'
);

-- ── 6.3 SubQuery dengan EXISTS / NOT EXISTS ───────────────────────

-- Mahasiswa yang sudah memiliki nilai (pernah ujian)
SELECT  nim, nama
FROM    tb_mahasiswa m
WHERE   EXISTS (
    SELECT 1
    FROM   tb_nilai n
    WHERE  n.nim = m.nim
);

-- Mahasiswa yang belum memiliki nilai sama sekali
SELECT  nim, nama
FROM    tb_mahasiswa m
WHERE   NOT EXISTS (
    SELECT 1
    FROM   tb_nilai n
    WHERE  n.nim = m.nim
);

-- Mata kuliah yang belum ada pesertanya
SELECT  kode_mk, nama_mk
FROM    tb_matakuliah mk
WHERE   NOT EXISTS (
    SELECT 1
    FROM   tb_krs k
    WHERE  k.kode_mk = mk.kode_mk
);

-- ── 6.4 SubQuery di klausa FROM (Inline View / Derived Table) ────

-- Rata-rata nilai akhir per mahasiswa, filter yang >= 75
SELECT  sub.nim,
        sub.nama,
        sub.avg_nilai_akhir
FROM (
    SELECT  m.nim,
            m.nama,
            ROUND(AVG(n.absen*0.10 + n.tugas*0.20 + n.uts*0.30 + n.uas*0.40), 2)
                AS avg_nilai_akhir
    FROM    tb_nilai n
    JOIN    tb_mahasiswa m USING (nim)
    GROUP BY m.nim, m.nama
) AS sub
WHERE   sub.avg_nilai_akhir >= 75
ORDER BY sub.avg_nilai_akhir DESC;

-- ── 6.5 SubQuery di klausa SELECT (Scalar SubQuery) ───────────────

-- Untuk setiap mahasiswa, tampilkan jumlah MK yang diambil
SELECT  nim,
        nama,
        ipk,
        (SELECT COUNT(*)
         FROM   tb_krs k
         WHERE  k.nim = m.nim) AS total_mk_diambil
FROM    tb_mahasiswa m
ORDER BY total_mk_diambil DESC;

-- Untuk setiap mata kuliah, tampilkan nilai UAS tertinggi
SELECT  kode_mk,
        nama_mk,
        sks,
        (SELECT MAX(uas)
         FROM   tb_nilai n
         WHERE  n.kode_mk = mk.kode_mk) AS uas_tertinggi
FROM    tb_matakuliah mk;

-- ── 6.6 Correlated SubQuery ──────────────────────────────────────
-- SubQuery yang merujuk ke kolom dari query luar

-- Mahasiswa yang nilai UAS-nya lebih tinggi dari rata-rata UAS
-- pada setiap mata kuliah yang sama
SELECT  m.nama,
        n.kode_mk,
        n.uas
FROM    tb_nilai n
JOIN    tb_mahasiswa m USING (nim)
WHERE   n.uas > (
    SELECT AVG(n2.uas)
    FROM   tb_nilai n2
    WHERE  n2.kode_mk = n.kode_mk   -- korelasi dengan query luar
)
ORDER BY n.kode_mk, n.uas DESC;


-- ================================================================
-- BAGIAN 7 : QUERY GABUNGAN (DML + JOIN + SubQuery)
-- ================================================================

-- ── 7.1 INSERT berdasarkan hasil SELECT dari tabel lain ───────────
-- (Copy data: hanya mahasiswa dengan IPK >= 3.5 yang masuk tabel honor)

CREATE TABLE IF NOT EXISTS tb_mahasiswa_honor (
    nim       VARCHAR(13) PRIMARY KEY,
    nama      VARCHAR(50),
    ipk       DECIMAL(3,2),
    keterangan VARCHAR(30)
);

INSERT INTO tb_mahasiswa_honor (nim, nama, ipk, keterangan)
SELECT  nim, nama, ipk, 'Cumlaude Candidate'
FROM    tb_mahasiswa
WHERE   ipk >= 3.7;

-- Verifikasi
SELECT * FROM tb_mahasiswa_honor;

-- ── 7.2 UPDATE menggunakan hasil JOIN ────────────────────────────
-- Hitung ulang IPK dari tabel nilai dan update ke tb_mahasiswa

UPDATE tb_mahasiswa m
JOIN (
    SELECT  nim,
            ROUND(AVG(absen*0.10 + tugas*0.20 + uts*0.30 + uas*0.40) / 25, 2)
                AS ipk_baru   -- normalisasi 0-100 → 0-4
    FROM    tb_nilai
    GROUP BY nim
) AS sub ON m.nim = sub.nim
SET  m.ipk = sub.ipk_baru;

-- ── 7.3 DELETE dengan SubQuery ───────────────────────────────────
-- Hapus KRS mahasiswa yang sudah di-drop (tidak ada di tb_mahasiswa)
DELETE FROM tb_krs
WHERE  nim NOT IN (SELECT nim FROM tb_mahasiswa);

-- ── 7.4 Laporan Akhir Komprehensif ────────────────────────────────
SELECT  m.nim,
        m.nama                                          AS mahasiswa,
        m.jenis_kelamin                                 AS jk,
        mk.nama_mk                                      AS mata_kuliah,
        d.nama_dosen                                    AS dosen,
        n.absen, n.tugas, n.uts, n.uas,
        ROUND(n.absen*0.10 + n.tugas*0.20
            + n.uts*0.30 + n.uas*0.40, 2)              AS nilai_akhir,
        CASE
            WHEN (n.absen*0.10+n.tugas*0.20+n.uts*0.30+n.uas*0.40) >= 85 THEN 'A'
            WHEN (n.absen*0.10+n.tugas*0.20+n.uts*0.30+n.uas*0.40) >= 75 THEN 'B'
            WHEN (n.absen*0.10+n.tugas*0.20+n.uts*0.30+n.uas*0.40) >= 65 THEN 'C'
            WHEN (n.absen*0.10+n.tugas*0.20+n.uts*0.30+n.uas*0.40) >= 55 THEN 'D'
            ELSE 'E'
        END                                             AS grade
FROM    tb_nilai n
JOIN    tb_mahasiswa  m  USING (nim)
JOIN    tb_matakuliah mk USING (kode_mk)
JOIN    tb_dosen      d  ON mk.nip = d.nip
ORDER BY mk.nama_mk ASC, nilai_akhir DESC;

-- ── 7.5 Ringkasan statistik per mata kuliah ───────────────────────
SELECT  mk.kode_mk,
        mk.nama_mk,
        mk.sks,
        d.nama_dosen,
        COUNT(n.nim)                                        AS peserta,
        ROUND(AVG(n.uas), 2)                                AS avg_uas,
        MAX(n.uas)                                          AS max_uas,
        MIN(n.uas)                                          AS min_uas,
        SUM(CASE WHEN n.uas >= 75 THEN 1 ELSE 0 END)        AS lulus,
        SUM(CASE WHEN n.uas <  75 THEN 1 ELSE 0 END)        AS tidak_lulus
FROM    tb_matakuliah mk
LEFT JOIN tb_nilai n    USING (kode_mk)
LEFT JOIN tb_dosen d    ON mk.nip = d.nip
GROUP BY mk.kode_mk, mk.nama_mk, mk.sks, d.nama_dosen
ORDER BY avg_uas DESC;


-- ================================================================
-- QUICK REFERENCE — Cheat Sheet
-- ================================================================

/*
┌─────────────────────────────────────────────────────────────┐
│  DML (Data Manipulation Language)                           │
├──────────────┬──────────────────────────────────────────────┤
│ INSERT       │ INSERT INTO tabel (kol) VALUES (val)         │
│ SELECT       │ SELECT kol FROM tabel WHERE kondisi          │
│ UPDATE       │ UPDATE tabel SET kol=val WHERE kondisi       │
│ DELETE       │ DELETE FROM tabel WHERE kondisi              │
├─────────────────────────────────────────────────────────────┤
│  JOIN Types                                                 │
├──────────────┬──────────────────────────────────────────────┤
│ INNER JOIN   │ Hanya baris yang cocok di kedua tabel        │
│ LEFT JOIN    │ Semua kiri + cocok dari kanan (NULL jika tdk)│
│ RIGHT JOIN   │ Semua kanan + cocok dari kiri (NULL jika tdk)│
│ NATURAL JOIN │ Auto-join kolom bernama sama                  │
│ FULL JOIN    │ Semua baris (simulasi: LEFT UNION RIGHT)      │
├─────────────────────────────────────────────────────────────┤
│  SubQuery                                                   │
├──────────────┬──────────────────────────────────────────────┤
│ WHERE        │ WHERE kol = (SELECT ...)                     │
│ FROM         │ FROM (SELECT ...) AS alias                   │
│ SELECT       │ SELECT (SELECT COUNT(*) ...) AS total        │
│ ANY          │ WHERE kol > ANY (SELECT ...)                 │
│ ALL          │ WHERE kol > ALL (SELECT ...)                 │
│ EXISTS       │ WHERE EXISTS (SELECT 1 ...)                  │
│ NOT EXISTS   │ WHERE NOT EXISTS (SELECT 1 ...)              │
└──────────────┴──────────────────────────────────────────────┘

Urutan eksekusi SQL:
  FROM → JOIN → WHERE → GROUP BY → HAVING → SELECT → ORDER BY → LIMIT
*/

-- ================================================================
-- END OF FILE
-- Jalankan di MySQL Workbench atau:
--   mysql -u root -p db_tutorial < dml_join_nested.sql
-- ================================================================

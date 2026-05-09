SELECT
    kode_mk,
    nama_mk,
    MAX(uas) AS nilai_uas_tertinggi
FROM tb_nilai n
JOIN tb_mk mk USING (kode_mk)
GROUP BY kode_mk, nama_mk;

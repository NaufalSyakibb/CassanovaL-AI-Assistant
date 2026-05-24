// PixelSprites — LTTP chibi character library (16×24 px, vanilla JS)
// Usage: PixelSprites.render(canvasEl, 'alfred', 4)
(function () {
  const PW = 16, PH = 24;

  function paint(ctx, rows, pal, s) {
    ctx.clearRect(0, 0, PW * s, PH * s);
    for (let y = 0; y < PH; y++) {
      const row = rows[y] ?? "";
      for (let x = 0; x < PW; x++) {
        const c = row[x];
        if (!c || c === "." || !pal[c]) continue;
        ctx.fillStyle = pal[c];
        ctx.fillRect(x * s, y * s, s, s);
      }
    }
  }

  function setRow(chars, id, idx, str) {
    const ch = chars.find(c => c.id === id);
    if (ch) ch.rows[idx] = str.padEnd(PW, ".").slice(0, PW);
  }

  const CHARS = [

    // ── SET I ────────────────────────────────────────────────────────────────

    {
      id: "alfred", name: "Alfred", role: "Asisten & Pelayan",
      pal: {
        H: "#111122", G: "#909090", L: "#C8C8C8", S: "#FFCD94",
        E: "#222244", W: "#F2F2F2", K: "#0D0D1A", V: "#060610",
        B: "#303030", Z: "#050508", P: "#1A1A2A",
      },
      rows: [
        "......HHHH......",
        ".....HHHHHH.....",
        ".....HHHHHH.....",
        "....HHHHHHHHHH..",
        "...GGHHLLLHHGG..",
        "..GGSSSSSSSSGG..",
        "..GSSSSSSSSSSSG.",
        "..GSSEESSSEESSG.",
        "..GSSSSSSSSSSSG.",
        "..GSSSSSSSSSSSG.",
        "...GSSSSSSSSSG..",
        "....SSSSSSSS....",
        "...KWWVVVVWWKK..",
        "..KKKWWWWWWKKKK.",
        "..KKKWWWWWWKKKK.",
        "...KBBBBBBBBKK..",
        "..KKKWWWWWWKKKK.",
        "....PP....PP....",
        "....PP....PP....",
        "....PP....PP....",
        "....PP....PP....",
        "....ZZ....ZZ....",
        "....ZZ....ZZ....",
        "...ZZZZ..ZZZZ...",
      ],
    },

    {
      id: "cicero", name: "Cicero", role: "Orator & Negosiator",
      pal: {
        R: "#3A8A10", r: "#5AB820", G: "#C8C8A0", S: "#FFCD94",
        E: "#222244", W: "#F5F5F5", w: "#DDDDDD", P: "#7B2FBE", B: "#8B6914",
      },
      rows: [
        "....RRrrrRRR....",
        "...RRrSSSSrRR...",
        "..GGRrSSSSSSrRGG",
        "..GGSSSSSSSSSSGG",
        "..GGSSSSSSSSSSGG",
        "..GGSSEESSSEESGG",
        "..GGSSSSSSSSSSGG",
        "..GGSSSSSSSSSSGG",
        "...GGSSSSSSSSGGG",
        "....SSSSSSSS....",
        "...WWWWSWWWWWWW.",
        "..PWWWWWWWWWWWPP",
        "..PWWWWWWWWWWWPP",
        "..PWWWWWWWWWWWPP",
        "..PWWWWWWWWWWWPP",
        "..PPWWWWWWWWWPPP",
        "...WWWWWWWWWWWW.",
        "...BBBBBB.......",
        "....BBBB........",
        "....BBBB........",
        "....BBBB........",
        ".......BBBBBB...",
        "........BBBB....",
        "...BBBB.BBBBBB..",
      ],
    },

    {
      id: "najwa", name: "Najwa", role: "Moderator & Jurnalis",
      pal: {
        H: "#1A1A2E", h: "#2E2E50", S: "#FFCD94", E: "#222244",
        m: "#CC4455", N: "#1B3A6B", n: "#284A80", W: "#F2F2F2",
        B: "#080812", Z: "#040408", M: "#888888", t: "#BBBBBB",
      },
      rows: [
        "....HHHHHHHHHH..",
        "...HHHHHHHHHhH..",
        "..HHHhhhhhhhHHH.",
        "..HHSSSSSSSSHHH.",
        "..HHSSSSSSSSHHH.",
        "..HHSSSSSSSSHHH.",
        "..HHSSEESSSEEHH.",
        "..HHSSSSSSSSHHH.",
        "..HHHSSSSSSSHHH.",
        "....SSSSSSSS....",
        "...NNWWSWWWWNNN.",
        "..NNNnWWWWWnNNNN",
        "..NNNnWWWWWnNNNN",
        "..NNNnWWWWWnNNNN",
        "..NNNNNNNNNNNNmm",
        "..NNNNNNNNNNNNmm",
        "..NNNNNNNNNNNNtt",
        "....BB....BB....",
        "....BB....BB....",
        "....BB....BB....",
        "....BB....BB....",
        "....ZZ....ZZ....",
        "....ZZ....ZZ....",
        "...ZZZZ..ZZZZ...",
      ],
    },

    // ── SET II ───────────────────────────────────────────────────────────────

    {
      id: "linus", name: "Linus Torvalds", role: "Developer & Arsitek Sistem",
      pal: {
        H: "#5A3520", h: "#7A5030", L: "#A07040", S: "#FFCD94",
        E: "#334455", C: "#445566", F: "#5C3B2E", f: "#8B5A52",
        G: "#9E9E9E", J: "#3A5A8C", B: "#0A0A14", K: "#0A0A0A",
        W: "#EEEEEE", O: "#FF6600",
      },
      rows: [
        "....HhLLLLhH....",
        "...HhhLLLLLLhH..",
        "..HHhLLLLLLLhHH.",
        "..HHhSSSSSSShHH.",
        "..HHhSSSSSSShHH.",
        "..HHhSSSSSSShHH.",
        "..HHhSCECSCEChHH",
        "..HHhSCCCCCCShHH",
        "..HHhSSSSSSShHH.",
        "....SSSSSSSS....",
        "...FfGGSGGGfFF..",
        "..FFFfGGGGGGfFFF",
        "..FfFfGGGGGGfFfF",
        "..FFFfGGGGGGfFFF",
        "..FfFfGGGGGGfFfF",
        "....GGGGGGGG....",
        "....JJJJJJJJ....",
        "KKWWJJ....JJ....",
        "KKWWJJ....JJ....",
        "KKWWJJ....JJ....",
        "KKWWJJ....JJ....",
        "OOJJBB....BB....",
        "OOJJBB....BB....",
        "..JJJBBBBBB.....",
      ],
    },

    {
      id: "miyamoto", name: "S. Miyamoto", role: "Game Designer & Ide Kreatif",
      pal: {
        H: "#1A1020", h: "#2A2030", S: "#FFCD94", E: "#222244",
        m: "#CC6633", R: "#CC2200", r: "#AA1A00", K: "#111122",
        D: "#2A2A3E", B: "#050510", Z: "#C0C0C0", X: "#FFD700",
      },
      rows: [
        "....HHhhhhHH....",
        "...HHHhhhhhHHH..",
        "..HHHhSSSSShHHH.",
        "..HHhSSSSSSShHH.",
        "..HHhSSSSSSShHH.",
        "..HHhSESSSSEShHH",
        "..HHhSSSSSSShHH.",
        "..HHhSSmmmSSShH.",
        "..HHhSSSSSSShHH.",
        "....SSSSSSSS....",
        "...KKRRrRRRKKK..",
        "..KKKRRRrRRRKKKK",
        "..KKKRRRrRRRKKKK",
        "..KKKRRRrRRRKKKZ",
        "..KKKRRRrRRXXZZZ",
        "..KKKRRRrRRRKZZZ",
        "....DDDDDDDDDZZZ",
        "....DD....DDDZZZ",
        "....DD....DDDZZZ",
        "....DD....DDDZZZ",
        "....DD....DDDZZZ",
        "....BB....BBBZZZ",
        "....BB....BBBZZZ",
        "...BBBB..BBBBZZZ",
      ],
    },

    // ── SET III ──────────────────────────────────────────────────────────────

    {
      id: "musa", name: "Mansa Musa", role: "Ekonomi & Manajemen Aset",
      pal: {
        Y: "#FFD700", y: "#C89400", D: "#5C3317", d: "#7A4828",
        E: "#1A0A04", W: "#C8860A", w: "#A06000", O: "#E0A020",
        r: "#CC0000", b: "#0044CC", g: "#00AA44", K: "#120800", B: "#0A0500",
      },
      rows: [
        "....Y.YYY.YY....",
        "...YYYYyyyYYYY..",
        "..YYyrDDDDDDryYY",
        "..YydDDDDDDDdyYY",
        "...dDDDDDDDDDd..",
        "...dDdEDDDEdDd..",
        "...dDDDDDDDDDd..",
        "...dDDDDDDDDDd..",
        "....dDDDDDDDdd..",
        "....DDDDDDDD....",
        "..YYWWWDDDWWWwYY",
        "..YYWOOOOOOOWYYYY",
        "..YWWOOOOOOOWWYY.",
        "..YWWOOOOOOOWYY..",
        "..YWWOOOOOOOWYYY.",
        "...YWWOOOOOWWYY..",
        "...YYWWWWWWWYY...",
        "....WW....WW....",
        "....WW....WW....",
        "....KK....KK....",
        "....KK....KK....",
        "....BB....BB....",
        "....BB....BB....",
        "...BBBB..BBBB...",
      ],
    },

    {
      id: "lavoisier", name: "A. Lavoisier", role: "Analisis & Data-driven",
      pal: {
        W: "#EEEEEE", w: "#CCCCCC", v: "#AAAAAA", S: "#FFCD94",
        E: "#222244", P: "#5B2D8E", p: "#7B3FBE", L: "#F5F5F5",
        l: "#DDDDDD", G: "#2ECC40", K: "#0D0D1A", B: "#050505",
      },
      rows: [
        "..WWWWWWWWWWWW..",
        ".WWWWWWWWWWWWWW.",
        ".WwWWWWWWWWWWwW.",
        ".WWWSSSSSSSSSWW.",
        ".WWWSSSSSSSSSWW.",
        ".WWWSSEESSEESSWW",
        ".WWWSSSSSSSSSWW.",
        ".WWwSSSSSSSSSwW.",
        ".WWWSSSSSSSSSwW.",
        "..WWWSSSSSSWWW..",
        "....SSSSSSSS....",
        "..WWLLLSSLLLWWWW",
        "..WLLLPPPPPPLLLW",
        "..WLLLPPPPPPLLLW",
        "..WLLLPPPPPPLLLG",
        "..WLLLPPPPPPLLLG",
        "..WLLLLLLLLLLLLW",
        "....LLLLLLLLL...",
        "....KK....KK....",
        "....KK....KK....",
        "....KK....KK....",
        "....KK....KK....",
        "....BB....BB....",
        "....BB....BB....",
      ],
    },

    {
      id: "davinci", name: "Leonardo da Vinci", role: "Polimat & Inovasi",
      pal: {
        G: "#888888", g: "#AAAAAA", L: "#CCCCCC", S: "#FFCD94",
        E: "#222244", T: "#8B4513", t: "#A05A28", K: "#1A1A2E",
        B: "#1A0A04", W: "#F0F0F0", Q: "#D4A017",
      },
      rows: [
        ".GGGGGGGGGGGGGGG",
        ".GgLLLLLLLLLgGG.",
        ".GGgLLLLLLLgGGG.",
        ".GGGgSSSSSSgGGG.",
        ".GGGGSSSSSSGGGg.",
        ".GGGGSESSSSEGGg.",
        ".GGGGSSSSSSGGGg.",
        ".GGGGSSSssSGGGg.",
        "GGGGGGGGGGGGGGgg",
        "GGGgSSSSSSSSgGGG",
        "....SSSSSSSS....",
        "..GGgTTSTTTgGGGG",
        "..GGTTtTTTTtTTGG",
        "..GGTTtTTTTtTTGG",
        "..GGTTTTTTTTTTww",
        "..GGTTTTTTTTTTww",
        "....TTTTTTTTTTQQ",
        "....TTTTTTTT....",
        "....KKKKKKKK....",
        "GG..KK....KKGGGG",
        "GG..KK....KKGGGG",
        "GG..KK....KKGGGG",
        "GG..KK....KKGGGG",
        "....BB....BBGGGG",
      ],
    },

    {
      id: "euler", name: "L. Euler", role: "Logika & Matematika",
      pal: {
        H: "#1C2A4A", h: "#2A3E6A", f: "#C89020", S: "#FFCD94",
        E: "#222244", N: "#1A2E5A", n: "#243E78", W: "#F2F2F2",
        C: "#B8860B", c: "#D4A820", K: "#0A1020", B: "#050510",
      },
      rows: [
        "H...HHHHHHHH...H",
        ".HHHHhhhhhhhHHH.",
        "..HHHhhhhhhhHHH.",
        "...fffffffffffffff",
        "..fHHhhhhhhhHHf.",
        "...HSSSSSSSSSH..",
        "...HSSSSSSSSSH..",
        "...HSESSSSESSSh.",
        "...HSSESSSSESH..",
        "...HSSSSSSSSSH..",
        "...HSSSSSSSSSH..",
        "....SSSSSSSS....",
        "..NNNWWnWWnWNNNN",
        "..NNNnWWWWWnNNNN",
        "..NNNnWWWWWnNNNN",
        "..NNNnWWWWWnNNCc",
        "..NNNNNNNNNNNNCc",
        "..NNNNNNNNNNNNCc",
        "....NNNNNNNN....",
        "....KK....KK....",
        "....KK....KK....",
        "....KK....KK....",
        "....KK....KK....",
        "....BB....BB....",
      ],
    },

    {
      id: "orwell", name: "George Orwell", role: "Wawasan & Kritik Etika",
      pal: {
        O: "#FF7700", I: "#CC2200", H: "#2C2020", h: "#3E3030",
        S: "#FFCD94", E: "#222244", T: "#7B5544", t: "#9A7060",
        G: "#8E8E9E", K: "#1A1A2E", B: "#050505", c: "#F0F0E0", f: "#FF6600",
      },
      rows: [
        "....OOOIIIOOOO..",
        "...OOIIIIIIIOOO.",
        "....HHHHHHHHHHH.",
        "...HHHhhhhhHHHH.",
        "..HHHhSSSSShHHH.",
        "..HHhSSSSSSShHH.",
        "..HHhSESSSSEShHH",
        "..HHhSSSSSSShHH.",
        "..HHhSSSSSSShHH.",
        "....SSSSSSSS....",
        "..TTtGGSGGGtTTTc",
        "..TTtGGSGGGtTTcc",
        "..TTtGGSSGGtTTTf",
        "...TTtGGGGGGtTTT",
        "...TTtGGGGGGtTTT",
        "...TTTGGGGGGtTTT",
        "...TTTtGGGGtTTTT",
        "...TTTTTTTTTTTTT",
        "...TTTTTTTTTTTTT",
        "....KK....KK....",
        "....KK....KK....",
        "....KK....KK....",
        "....KK....KK....",
        "....BB....BB....",
      ],
    },

  ];

  // Normalize all rows to exactly PW×PH
  CHARS.forEach(ch => {
    ch.rows = ch.rows.map(row => {
      if (!row) return "................";
      if (row.length > PW) return row.slice(0, PW);
      return row.padEnd(PW, ".");
    });
    if (ch.rows.length > PH) ch.rows = ch.rows.slice(0, PH);
    while (ch.rows.length < PH) ch.rows.push("................");
  });

  // Post-fix corrections
  setRow(CHARS, "alfred",    7,  "..GSSEEESSEESG..");
  setRow(CHARS, "cicero",    5,  "..GGSSEESSEEEGG.");
  setRow(CHARS, "lavoisier", 7,  ".WWWSSSSSSSSSwW.");
  setRow(CHARS, "linus",     23, "..JJBBBBBB......");
  setRow(CHARS, "miyamoto",  14, "..KKKRRRrRRXXZZZ");
  setRow(CHARS, "musa",      5,  "...dDWEDDDEWDd..");
  setRow(CHARS, "musa",      11, "..YWWOOOOOOOWWYY");
  setRow(CHARS, "davinci",   1,  ".GGgLLLLLLLgGGG.");
  setRow(CHARS, "davinci",   15, "....TTTTTTTT....");
  setRow(CHARS, "euler",     3,  "..fHHhhhhhhhHHf.");
  setRow(CHARS, "euler",     6,  "...HSSESSSSESH..");
  setRow(CHARS, "orwell",    10, "..TTTGGGSGGGTTTf");

  // Public API
  window.PixelSprites = {
    /**
     * Render a character sprite onto a canvas element.
     * @param {HTMLCanvasElement} canvas
     * @param {string} id  — character id (e.g. 'alfred', 'lavoisier')
     * @param {number} [scale=4]  — pixels per sprite pixel
     */
    render: function (canvas, id, scale) {
      const ch = CHARS.find(c => c.id === id);
      if (!ch || !canvas) return;
      const s = scale || 4;
      canvas.width  = PW * s;
      canvas.height = PH * s;
      const ctx = canvas.getContext("2d");
      ctx.imageSmoothingEnabled = false;
      paint(ctx, ch.rows, ch.pal, s);
    },

    list: function () {
      return CHARS.map(c => ({ id: c.id, name: c.name, role: c.role }));
    },
  };
})();

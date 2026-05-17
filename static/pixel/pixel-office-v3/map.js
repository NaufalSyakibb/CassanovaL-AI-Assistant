// Pixel office map v3: 30x18 grid at 24px tile -> 720x432 native canvas.
// Reference-matched layout: 4 desk pods (8 agents), pantry w/ vending+water+microwave,
// lounge w/ red sofas + coffee table + wall art.

window.OfficeMap = (function () {
  const COLS = 30, ROWS = 18, TILE = 24;

  const FLOOR_WOOD = 1;
  const FLOOR_TILE = 2;
  const FLOOR_CARPET = 3;
  const WALL = 4;

  function buildTiles() {
    const t = [];
    for (let r = 0; r < ROWS; r++) {
      const row = [];
      for (let c = 0; c < COLS; c++) {
        let v;
        if (r === 0 || r === ROWS - 1 || c === 0 || c === COLS - 1) v = WALL;
        else if (c < 18) v = FLOOR_WOOD;
        else if (r < 9) v = FLOOR_TILE;
        else v = FLOOR_CARPET;
        row.push(v);
      }
      t.push(row);
    }
    // Inner vertical wall col 18
    for (let r = 1; r < ROWS - 1; r++) t[r][18] = WALL;
    // Doorway to pantry (top): rows 4-5
    t[4][18] = FLOOR_TILE; t[5][18] = FLOOR_TILE;
    // Doorway to lounge (bottom): rows 12-13
    t[12][18] = FLOOR_CARPET; t[13][18] = FLOOR_CARPET;
    // Horizontal wall between pantry and lounge: row 9 cols 19-28
    for (let c = 19; c < COLS - 1; c++) t[9][c] = WALL;
    return t;
  }

  function buildFurniture() {
    const f = [];

    // ===== WORKSPACE north wall (row 1 decorations on wall above) =====
    f.push({ type: 'wallShelf', x: 2, y: 1, w: 5, h: 0 });
    f.push({ type: 'boxesStack', x: 7, y: 1, w: 3, h: 2 });
    f.push({ type: 'wallShelf', x: 11, y: 1, w: 6, h: 0 });
    f.push({ type: 'plant', x: 1, y: 1, w: 1, h: 1 });
    f.push({ type: 'plant', x: 17, y: 1, w: 1, h: 1 });
    f.push({ type: 'plant', x: 1, y: 16, w: 1, h: 1 });
    f.push({ type: 'plant', x: 17, y: 16, w: 1, h: 1 });

    // ===== 4 DESK PODS (each pod = 2 back-to-back desks + 2 stools between) =====
    // Pod structure:
    //   row Y0   : desk (faces SOUTH, monitor on south end)
    //   row Y0+1 : agent seat (facing UP toward desk)
    //   row Y0+2 : stool
    //   row Y0+3 : stool
    //   row Y0+4 : agent seat (facing DOWN toward bottom desk)
    //   row Y0+5 : desk (faces NORTH, monitor on north end)
    const pods = [
      { col: 3,  y0: 3 },
      { col: 11, y0: 3 },
      { col: 3,  y0: 10 },
      { col: 11, y0: 10 },
    ];
    let deskId = 0;
    for (const p of pods) {
      // Top desk: agent at south side, monitor at south side of desk
      f.push({ type: 'desk', x: p.col, y: p.y0, w: 3, h: 1,
        deskId, facing: 'south',
        seat: { x: p.col + 1, y: p.y0 + 1, facing: 'up' } });
      deskId++;
      // Stools between
      f.push({ type: 'stool', x: p.col, y: p.y0 + 2, w: 1, h: 1, stoolId: deskId * 2 });
      f.push({ type: 'stool', x: p.col + 2, y: p.y0 + 2, w: 1, h: 1, stoolId: deskId * 2 + 1 });
      // Bottom desk: agent at north side, monitor at north side of desk
      f.push({ type: 'desk', x: p.col, y: p.y0 + 5, w: 3, h: 1,
        deskId, facing: 'north',
        seat: { x: p.col + 1, y: p.y0 + 4, facing: 'down' } });
      deskId++;
    }

    // ===== PANTRY (cols 19-28, rows 1-8) =====
    // North wall counter
    f.push({ type: 'counter', x: 24, y: 1, w: 4, h: 1 });
    f.push({ type: 'microwave', x: 25, y: 1, w: 2, h: 1 });
    f.push({ type: 'wallClock', x: 22, y: 1, w: 1, h: 0 });
    f.push({ type: 'trashbin', x: 27, y: 2, w: 1, h: 1 });

    // Vending machine + water dispenser
    f.push({ type: 'vending', x: 19, y: 1, w: 2, h: 2 });
    f.push({ type: 'waterDispenser', x: 21, y: 1, w: 1, h: 2 });
    f.push({ type: 'plantTall', x: 28, y: 2, w: 1, h: 1 });

    // ===== LOUNGE (cols 19-28, rows 10-16) =====
    // North wall: built-in horizontal bookshelves + framed painting between
    f.push({ type: 'wallShelf', x: 19, y: 10, w: 3, h: 0 });
    f.push({ type: 'wallPainting', x: 22, y: 10, w: 3, h: 0 });
    f.push({ type: 'wallShelf', x: 25, y: 10, w: 3, h: 0 });
    f.push({ type: 'plantPineapple', x: 21, y: 11, w: 1, h: 1 });
    f.push({ type: 'plantPineapple', x: 25, y: 11, w: 1, h: 1 });

    // Hand sanitizer on left wall
    f.push({ type: 'sanitizer', x: 18, y: 12, w: 0, h: 1 });

    // Two red sofas facing each other with coffee table between
    f.push({ type: 'sofa', x: 20, y: 13, w: 2, h: 2, facing: 'right' });
    f.push({ type: 'sofa', x: 25, y: 13, w: 2, h: 2, facing: 'left' });
    f.push({ type: 'coffeeTable', x: 23, y: 13, w: 2, h: 2 });

    // Plants in corners
    f.push({ type: 'plant', x: 19, y: 16, w: 1, h: 1 });
    f.push({ type: 'plant', x: 27, y: 16, w: 1, h: 1 });

    return f;
  }

  function buildStations(furniture) {
    const s = {
      desks: [],
      stools: [],
      vending: { x: 19, y: 3 },        // stand south of vending machine
      water:   { x: 21, y: 3 },        // stand south of dispenser
      microwave: { x: 26, y: 2 },      // stand south of counter
      trash: { x: 27, y: 3 },
      sofas: [
        { x: 22, y: 13, facing: 'right' },
        { x: 22, y: 14, facing: 'right' },
        { x: 24, y: 13, facing: 'left' },
        { x: 24, y: 14, facing: 'left' },
      ],
      chatSpots: [
        { x: 6,  y: 6 }, { x: 14, y: 6 },
        { x: 6,  y: 13 }, { x: 14, y: 13 },
        { x: 22, y: 5 },
      ],
      toilet: { x: 27, y: 16 },
    };
    for (const ff of furniture) {
      if (ff.type === 'desk') s.desks.push({ x: ff.seat.x, y: ff.seat.y, facing: ff.seat.facing, deskId: ff.deskId });
      if (ff.type === 'stool') s.stools.push({ x: ff.x, y: ff.y });
    }
    return s;
  }

  function buildWalkable(tiles, furniture) {
    const w = [];
    for (let r = 0; r < ROWS; r++) {
      const row = [];
      for (let c = 0; c < COLS; c++) {
        row.push(tiles[r][c] !== WALL);
      }
      w.push(row);
    }
    const wallMounted = new Set(['wallShelf', 'wallPainting', 'wallClock', 'sanitizer']);
    for (const f of furniture) {
      if (wallMounted.has(f.type)) continue;
      for (let r = f.y; r < f.y + f.h; r++) {
        for (let c = f.x; c < f.x + f.w; c++) {
          if (r >= 0 && r < ROWS && c >= 0 && c < COLS) w[r][c] = false;
        }
      }
    }
    return w;
  }

  const tiles = buildTiles();
  const furniture = buildFurniture();
  const stations = buildStations(furniture);
  const walkable = buildWalkable(tiles, furniture);

  return {
    COLS, ROWS, TILE,
    FLOOR_WOOD, FLOOR_TILE, FLOOR_CARPET, WALL,
    tiles, furniture, stations, walkable,
  };
})();

// Pixel-art renderers v3 @ 24px tile.
// Hand-tuned to match reference photo: cute chunky pixel style, warm wood, dark walls.

window.OfficeRender = (function () {
  const M = window.OfficeMap;
  const TILE = M.TILE; // 24

  // ----- Color palette -----
  const C = {
    // floors
    wood1: '#8a5a2c', wood2: '#7a4a25', wood3: '#9a6634', wood4: '#653a18',
    woodGrout: '#3a1f0e', woodGrain: '#5a3018',
    tile1: '#ead6c6', tile2: '#dcc4b0', tile3: '#f0dfd0', tileGrout: '#b8a08c',
    carpet1: '#1a3a6e', carpet2: '#15305c', carpet3: '#20437a',

    // walls
    wallDark: '#1a0f0c', wallMid: '#2a1810', wallEdge: '#3a2418',
    wallSkirt: '#3a2418', wallShadow: '#0a0604',
    // pantry walls (lighter pink-grey)
    wallPantry: '#d8c8b8', wallPantryShadow: '#a89888',

    // bookshelf
    shelfWood: '#5a3318', shelfWoodDark: '#3a1f0e', shelfWoodHi: '#7a4a25',
    book1: '#c84a3a', book2: '#3a8a3a', book3: '#e8a838', book4: '#3a6abc',
    book5: '#a14fc8', book6: '#dfdadc', book7: '#1a1a1f', book8: '#d87890',

    // desk
    deskTop: '#8a5630', deskTop2: '#7a4a25', deskTop3: '#9a6634',
    deskTrim: '#3a1f0e', deskShadow: '#1a0f0a',
    deskDrawer: '#6b3f1f', deskKnob: '#d4a050',

    // monitor / electronics
    monBezel: '#1a1a1f', monBack: '#2a2730',
    monScreen: '#1c2a48', monLight: '#3a78c8', monHeader: '#dfdadc',
    monCode1: '#c84a3a', monCode2: '#4ac86a', monCode3: '#e6c050',
    kbBody: '#1a1a1f', kbKey: '#3a3640',
    mouseBody: '#dfdadc',
    mug1: '#dfdadc', mug2: '#c84a3a', coffeeDark: '#3a1f0e',
    paper: '#ededed', paperLine: '#9a93a8',

    // stool
    stoolTop: '#e6d2b0', stoolTopHi: '#f0e0c2', stoolTopDark: '#bfa580',
    stoolLeg: '#5a3318', stoolLegHi: '#7a4a25',

    // chair (for desks)
    chairBack: '#2a2024', chairSeat: '#3b3236', chairBackHi: '#4a4046',
    chairWheel: '#1a1418', chairStem: '#1a1418',

    // boxes
    box1: '#b08050', box2: '#80583a', box3: '#c89868',
    tape: '#e6c074', tapeShadow: '#a68040',

    // plant
    pot: '#c47245', potDark: '#9a4f2c', potBand: '#7a3a1c',
    soil: '#3a1f0e',
    leaf1: '#3a9d3a', leaf2: '#2a7a2a', leaf3: '#4abc4a', leafHi: '#7adc7a',
    leafStripe: '#1a5a1a',

    // pineapple plant
    ppLeaf: '#5aaf5a', ppLeafDark: '#2a7a2a', ppLeafHi: '#7adc7a',
    ppStripe: '#1a4a1a',

    // vending machine
    vendBody: '#c8302a', vendBodyDark: '#9a201a', vendBodyHi: '#e8504a',
    vendGlass: '#2a3a4e', vendGlassHi: '#5a708a',
    vendShelf: '#1a1a1f',
    drink1: '#c8302a', drink2: '#3a78c8', drink3: '#4ac86a', drink4: '#e6c050',
    vendButton: '#1a1a1f', vendLed: '#4ac86a',

    // water dispenser
    wdBody: '#dfdadc', wdShadow: '#a89888', wdDark: '#6a6068',
    wdWater: '#5ab0e0', wdWaterHi: '#9ad8f0',
    wdBlue: '#3a78c8', wdRed: '#c84a3a',
    wdCap: '#3a78c8',

    // microwave
    mwBody: '#1a1a1f', mwBodyHi: '#3b3640', mwWindow: '#0a0608',
    mwGlow: '#e6c050', mwDisp: '#4ac86a', mwHandle: '#56505c',

    // counter
    counterTop: '#f0e8e0', counterTop2: '#dcc9b8', counterEdge: '#a89888',
    cabFront: '#dfd2c2', cabFront2: '#a89888', cabHandle: '#3b3742',

    // trash bin
    trashBody: '#3b3742', trashLid: '#56505c', trashRim: '#1a1a1f',

    // wall clock
    clockFrame: '#2a1810', clockFrameHi: '#5a3818',
    clockFace: '#f0e8e0', clockHand: '#1a1a1f', clockNum: '#3a2418',

    // sofa (red)
    sofa: '#a8302a', sofaDark: '#7a201a', sofaHi: '#c8504a',
    sofaShadow: '#5a1614',
    sofaPillow: '#e8c83a', sofaPillowDark: '#b08a20',

    // coffee table
    ctTop: '#7a4a25', ctTop2: '#5a3318', ctTopHi: '#9a6634',
    ctTrim: '#3a1f0e',

    // laptop (on table)
    lapBody: '#3b3640', lapBack: '#2a2024',
    lapScreen: '#1c2a48', lapKey: '#1a1a1f',

    // painting
    paintFrame: '#a0784a', paintFrameDark: '#704830',
    paintSky: '#9fc4e8', paintSun: '#f5d048',
    paintMtn: '#6a5e5a', paintGrass: '#5aa56a',

    // sanitizer dispenser
    sanBody: '#ededed', sanBodyDark: '#bdb0a8',
    sanBottle: '#dfdadc', sanLiquid: '#bdedbd',
    sanNozzle: '#3b3742',

    // toilet (unused but kept)
    toilet: '#ededed', toiletDark: '#a8b0b8',
  };

  // ----- low-level draw helpers -----
  function rect(ctx, color, x, y, w, h) { ctx.fillStyle = color; ctx.fillRect(x, y, w, h); }
  function px(ctx, color, x, y) { ctx.fillStyle = color; ctx.fillRect(x, y, 1, 1); }
  function shade(hex, amt) {
    const n = parseInt(hex.replace('#',''), 16);
    let r = (n>>16)&0xff, g = (n>>8)&0xff, b = n&0xff;
    r = Math.max(0, Math.min(255, r + Math.round(255*amt)));
    g = Math.max(0, Math.min(255, g + Math.round(255*amt)));
    b = Math.max(0, Math.min(255, b + Math.round(255*amt)));
    return '#' + ((r<<16)|(g<<8)|b).toString(16).padStart(6,'0');
  }

  // Check if the tile above a given tile is a wall (for adjusting wall rendering)
  function isWallAbove(x, y) {
    if (y <= 0) return true;
    return M.tiles[y-1][x] === M.WALL;
  }

  // ----- floor / wall tiles -----
  function drawTile(ctx, x, y, type) {
    const ox = x * TILE, oy = y * TILE;
    if (type === M.WALL) {
      // Determine if this wall is in pantry/lounge or workspace
      // Pantry walls (next to tile floor) get lighter color; lounge walls dark
      let isPantryArea = false;
      // Look at adjacent floor tile
      for (const [dx, dy] of [[0,1],[0,-1],[1,0],[-1,0]]) {
        const nx = x + dx, ny = y + dy;
        if (nx >= 0 && nx < M.COLS && ny >= 0 && ny < M.ROWS) {
          if (M.tiles[ny][nx] === M.FLOOR_TILE) { isPantryArea = true; break; }
        }
      }
      if (isPantryArea) {
        rect(ctx, C.wallPantry, ox, oy, TILE, TILE);
        rect(ctx, C.wallPantryShadow, ox, oy, TILE, 2);
        rect(ctx, C.wallPantryShadow, ox, oy + TILE - 3, TILE, 1);
        rect(ctx, C.wallPantry, ox, oy + TILE - 2, TILE, 2);
        // subtle tile-wall pattern (small horizontal lines)
        rect(ctx, C.wallPantryShadow, ox, oy + 8, TILE, 1);
        rect(ctx, C.wallPantryShadow, ox, oy + 16, TILE, 1);
      } else {
        // Dark wood-look wall (like reference)
        rect(ctx, C.wallDark, ox, oy, TILE, TILE);
        rect(ctx, C.wallEdge, ox, oy, TILE, 2);
        rect(ctx, C.wallShadow, ox, oy + TILE - 4, TILE, 1);
        rect(ctx, C.wallSkirt, ox, oy + TILE - 3, TILE, 3);
        rect(ctx, C.wallShadow, ox, oy + TILE - 1, TILE, 1);
        // subtle wood-panel vertical seams every tile
        rect(ctx, C.wallShadow, ox + TILE - 1, oy, 1, TILE);
      }
    } else if (type === M.FLOOR_WOOD) {
      const plankIdx = Math.floor(x / 4);
      const tone = (plankIdx + Math.floor(y / 6)) % 3;
      const base = tone === 0 ? C.wood1 : tone === 1 ? C.wood3 : C.wood2;
      rect(ctx, base, ox, oy, TILE, TILE);
      // plank highlight at top
      rect(ctx, shade(base, 0.04), ox, oy + 1, TILE, 1);
      // grain marks
      rect(ctx, C.woodGrain, ox + 3, oy + 7, 8, 1);
      rect(ctx, C.woodGrain, ox + 12, oy + 15, 7, 1);
      px(ctx, C.woodGrain, ox + 17, oy + 5);
      px(ctx, C.woodGrain, ox + 5, oy + 19);
      // vertical plank seam (every 4 cols)
      if (x % 4 === 3) rect(ctx, C.woodGrout, ox + TILE - 1, oy, 1, TILE);
      // horizontal plank break - sparser (every 6 rows for given plank)
      if (y % 6 === plankIdx % 6) rect(ctx, C.woodGrout, ox, oy, TILE, 1);
    } else if (type === M.FLOOR_TILE) {
      // square tiles - one per cell, with diagonal subtle shading
      rect(ctx, C.tile1, ox, oy, TILE, TILE);
      rect(ctx, C.tile3, ox + 1, oy + 1, TILE - 2, 2);
      rect(ctx, C.tile2, ox + 1, oy + 3, TILE - 2, TILE - 4);
      // grout cross
      rect(ctx, C.tileGrout, ox, oy, TILE, 1);
      rect(ctx, C.tileGrout, ox, oy, 1, TILE);
      // sparkle pixel
      px(ctx, C.tile3, ox + TILE - 5, oy + 4);
      px(ctx, C.tileGrout, ox + 14, oy + 17);
    } else if (type === M.FLOOR_CARPET) {
      rect(ctx, C.carpet1, ox, oy, TILE, TILE);
      // weave stripes
      rect(ctx, C.carpet3, ox, oy + 1, TILE, 1);
      rect(ctx, C.carpet2, ox, oy + TILE - 1, TILE, 1);
      // crosshatch dot pattern
      for (let i = 3; i < TILE - 2; i += 5) {
        for (let j = 3; j < TILE - 2; j += 5) {
          px(ctx, C.carpet3, ox + i, oy + j);
          px(ctx, C.carpet2, ox + i + 2, oy + j + 2);
        }
      }
    }
  }

  // ----- furniture -----
  const F = {};

  // Wall-mounted bookshelf (drawn UPWARD into the wall row above).
  // Wide horizontal shelf with vertical book spines.
  F.wallShelf = function (ctx, f) {
    const ox = f.x * TILE, oy = f.y * TILE;
    const W = f.w * TILE;
    const sh = 18;
    const fy = oy - sh;
    // shelf frame
    rect(ctx, C.shelfWoodDark, ox, fy, W, sh);
    rect(ctx, C.shelfWoodHi, ox + 1, fy + 1, W - 2, 1);
    // top shelf board
    rect(ctx, C.shelfWood, ox + 1, fy + 1, W - 2, sh - 3);
    // 2 rows of books
    const rows = 2;
    const rowH = Math.floor((sh - 4) / rows);
    const bookColors = [C.book1, C.book2, C.book3, C.book4, C.book5, C.book6, C.book7, C.book8, C.book1, C.book2];
    for (let r = 0; r < rows; r++) {
      const ry = fy + 2 + r * rowH;
      // shelf board line
      rect(ctx, C.shelfWoodDark, ox + 1, ry + rowH - 1, W - 2, 1);
      // books
      let bx = ox + 2;
      let bi = r * 7 + f.x;
      while (bx < ox + W - 2) {
        const bw = 2 + (bi % 2);
        const bh = rowH - 2 - (bi % 3);
        const by = ry + (rowH - 1) - bh - 1;
        rect(ctx, bookColors[bi % bookColors.length], bx, by, bw, bh);
        // book spine highlight
        rect(ctx, shade(bookColors[bi % bookColors.length], 0.15), bx, by, 1, bh);
        // gap
        bx += bw;
        if ((bi % 4) === 0) bx += 1;
        bi++;
      }
    }
    // bottom edge of shelf
    rect(ctx, C.shelfWoodDark, ox, fy + sh - 2, W, 2);
  };

  // Stacked cardboard boxes (decoration, sits in workspace corner)
  F.boxesStack = function (ctx, f) {
    const ox = f.x * TILE, oy = f.y * TILE;
    const W = f.w * TILE, H = f.h * TILE;
    // Drawn UP into the wall row above for stacked look. Bottom box at oy, top above.
    const fy = oy - H + TILE;
    // Bottom box (larger)
    rect(ctx, C.box2, ox + 4, oy - 8, W - 8, 30);
    rect(ctx, C.box1, ox + 5, oy - 7, W - 10, 28);
    rect(ctx, C.box3, ox + 5, oy - 7, W - 10, 2);
    // tape
    rect(ctx, C.tape, ox + W / 2 - 3, oy - 8, 6, 30);
    rect(ctx, C.tapeShadow, ox + W / 2 - 3, oy - 8, 1, 30);
    rect(ctx, C.tape, ox + 4, oy + 5, W - 8, 3);
    // label
    rect(ctx, C.book6, ox + 8, oy - 4, 10, 5);
    px(ctx, C.box2, ox + 10, oy - 3);
    px(ctx, C.box2, ox + 13, oy - 3);
    rect(ctx, C.box2, ox + 9, oy - 1, 8, 1);
    // Top box (smaller, offset)
    rect(ctx, C.box2, ox + 9, oy - 28, W - 18, 18);
    rect(ctx, C.box1, ox + 10, oy - 27, W - 20, 16);
    rect(ctx, C.box3, ox + 10, oy - 27, W - 20, 2);
    rect(ctx, C.tape, ox + 9, oy - 19, W - 18, 3);
  };

  // Desk: 3 wide Ã 1 tall. facing='south' (monitor at south end of desk top), 'north' (monitor at north end)
  F.desk = function (ctx, f) {
    const ox = f.x * TILE, oy = f.y * TILE;
    const W = f.w * TILE, H = f.h * TILE;

    // Desk top
    rect(ctx, C.deskTrim, ox, oy, W, H);
    rect(ctx, C.deskTop2, ox + 1, oy + 1, W - 2, H - 2);
    rect(ctx, C.deskTop, ox + 1, oy + 2, W - 2, H - 4);
    rect(ctx, C.deskTop3, ox + 1, oy + 1, W - 2, 1);
    // wood grain
    rect(ctx, C.deskTrim, ox + 6, oy + 7, 16, 1);
    rect(ctx, C.deskTrim, ox + 28, oy + 13, 22, 1);
    rect(ctx, C.deskTrim, ox + 54, oy + 7, 14, 1);
    // drawer fronts on lower edge
    const dh = 9;
    const dy = oy + H - dh - 1;
    for (let i = 0; i < 3; i++) {
      const dx = ox + 2 + i * Math.floor((W - 4) / 3);
      const dw = Math.floor((W - 4) / 3) - 1;
      rect(ctx, C.deskDrawer, dx, dy, dw, dh);
      rect(ctx, C.deskTrim, dx, dy, dw, 1);
      rect(ctx, C.deskTrim, dx, dy + dh - 1, dw, 1);
      rect(ctx, C.deskKnob, dx + dw / 2 - 1, dy + dh / 2 - 1, 2, 2);
    }
    // floor shadow under desk
    rect(ctx, C.deskShadow, ox + 2, oy + H, W - 4, 1);

    // Items on desk: arrangement depends on facing
    // The "front" of the desk is where the agent sits. South-facing desk â agent sits south, monitor on south edge.
    // For our top view, draw monitor extending into adjacent row (away from agent direction).

    const south = f.facing === 'south';
    // Monitor: drawn into the row OPPOSITE to where the agent sits.
    // If south-facing (agent south), monitor renders UP into row above (north of desk).
    // If north-facing (agent north), monitor renders DOWN into row below (south of desk).
    const dir = south ? -1 : 1; // direction monitor extends
    const my = south ? oy - 18 : oy + H + 1;

    // Monitor centered on desk
    const cx = ox + W / 2;
    // Stand visible at desk edge
    if (south) {
      // monitor sits at north edge of desk, base on desk
      rect(ctx, C.monBezel, cx - 4, oy + 2, 8, 3);
      rect(ctx, C.kbBody, cx - 2, oy - 1, 4, 4);
    } else {
      rect(ctx, C.monBezel, cx - 4, oy + H - 5, 8, 3);
      rect(ctx, C.kbBody, cx - 2, oy + H - 3, 4, 4);
    }
    // monitor body (drawn into adjacent row)
    rect(ctx, C.monBack, cx - 12, my, 24, 18);
    rect(ctx, C.monBezel, cx - 12, my, 24, 18);
    rect(ctx, C.monScreen, cx - 11, my + 1, 22, 14);
    // screen UI - varied by desk id
    const seed = (f.deskId || 0) * 13;
    rect(ctx, C.monHeader, cx - 10, my + 2, 20, 2);
    px(ctx, C.monCode1, cx - 9, my + 2);
    px(ctx, C.monCode2, cx - 7, my + 2);
    px(ctx, C.monCode3, cx - 5, my + 2);
    const lines = [
      [C.monCode2, -10, 5, 8],
      [C.monLight, -10, 7, 6], [C.monCode3, -2, 7, 10],
      [C.monCode1, -10, 9, 5], [C.monCode2, -4, 9, 7],
      [C.monLight, -10, 11, 14],
      [C.monCode3, -10, 13, 9],
    ];
    for (let i = 0; i < lines.length; i++) {
      const [color, lx, ly, len] = lines[i];
      if (((seed + i) % 4) === 0) continue;
      const w = Math.max(2, len - ((seed + i) % 3));
      rect(ctx, color, cx + lx, my + ly, w, 1);
    }

    // Keyboard, mouse, mug â placed on the OTHER half of the desk, closer to the agent
    // For south-facing desk (agent south), keyboard is on south half of desk.
    // For north-facing, keyboard on north half.
    const kbY = south ? oy + H - 9 - 2 : oy + 3;
    // We already drew drawer fronts on south edge; offset accordingly.
    // Simpler: keyboard centered horizontally, just above drawer line for south, or just below desk-top edge for north.
    const kbX = cx - 13;
    const kbDrawY = south ? dy - 6 : oy + 3;
    rect(ctx, C.kbBody, kbX, kbDrawY, 26, 5);
    for (let r2 = 0; r2 < 1; r2++)
      for (let c2 = 0; c2 < 11; c2++)
        px(ctx, C.kbKey, kbX + 2 + c2 * 2, kbDrawY + 2);

    // Mouse + mousepad
    const padX = south ? ox + W - 18 : ox + 6;
    const padY = south ? dy - 6 : oy + 3;
    rect(ctx, C.kbKey, padX, padY, 14, 5);
    rect(ctx, C.mouseBody, padX + 4, padY + 1, 5, 3);

    // Mug
    const mugX = south ? ox + 6 : ox + W - 12;
    const mugY = south ? dy - 8 : oy + 2;
    rect(ctx, C.deskTrim, mugX, mugY, 6, 7);
    rect(ctx, C.mug1, mugX, mugY + 1, 6, 6);
    rect(ctx, C.mug2, mugX, mugY + 1, 6, 2);
    rect(ctx, C.coffeeDark, mugX + 1, mugY + 1, 4, 1);
    // handle
    rect(ctx, C.mug1, mugX + 6, mugY + 2, 1, 3);
  };

  // Wooden stool: 1 tile. round cushioned top + 4 legs visible
  F.stool = function (ctx, f) {
    const ox = f.x * TILE, oy = f.y * TILE;
    // shadow
    rect(ctx, 'rgba(0,0,0,0.25)', ox + 3, oy + TILE - 2, TILE - 6, 2);
    // legs (4, visible from top-down at corners)
    rect(ctx, C.stoolLeg, ox + 4, oy + 10, 2, 12);
    rect(ctx, C.stoolLeg, ox + TILE - 6, oy + 10, 2, 12);
    rect(ctx, C.stoolLeg, ox + 7, oy + 14, 2, 8);
    rect(ctx, C.stoolLeg, ox + TILE - 9, oy + 14, 2, 8);
    // cushion top (round-ish)
    rect(ctx, C.stoolLeg, ox + 3, oy + 4, TILE - 6, 10);
    rect(ctx, C.stoolTopDark, ox + 3, oy + 4, TILE - 6, 8);
    rect(ctx, C.stoolTop, ox + 4, oy + 5, TILE - 8, 6);
    rect(ctx, C.stoolTopHi, ox + 5, oy + 5, TILE - 10, 1);
    // edge pixels for rounded look
    px(ctx, C.stoolTopDark, ox + 3, oy + 4);
    px(ctx, C.stoolTopDark, ox + TILE - 4, oy + 4);
    px(ctx, C.stoolTopDark, ox + 3, oy + 11);
    px(ctx, C.stoolTopDark, ox + TILE - 4, oy + 11);
    // seat indent
    rect(ctx, C.stoolTopDark, ox + 8, oy + 9, 8, 1);
  };

  // Plant in striped terra-cotta pot
  F.plant = function (ctx, f) {
    const ox = f.x * TILE, oy = f.y * TILE;
    // pot
    rect(ctx, C.potDark, ox + 6, oy + 16, 12, 7);
    rect(ctx, C.pot, ox + 7, oy + 17, 10, 5);
    rect(ctx, C.potBand, ox + 6, oy + 15, 12, 2);
    rect(ctx, C.potBand, ox + 7, oy + 21, 10, 1);
    // soil
    rect(ctx, C.soil, ox + 8, oy + 15, 8, 1);
    // foliage - bushy
    rect(ctx, C.leaf2, ox + 4, oy + 7, 16, 9);
    rect(ctx, C.leaf1, ox + 5, oy + 5, 14, 9);
    rect(ctx, C.leaf3, ox + 7, oy + 4, 10, 4);
    // pointed leaves
    rect(ctx, C.leaf2, ox + 3, oy + 9, 2, 5);
    rect(ctx, C.leaf2, ox + 19, oy + 9, 2, 5);
    rect(ctx, C.leaf1, ox + 2, oy + 10, 1, 3);
    rect(ctx, C.leaf1, ox + 21, oy + 10, 1, 3);
    rect(ctx, C.leaf2, ox + 10, oy + 2, 4, 4);
    rect(ctx, C.leaf3, ox + 11, oy + 1, 2, 3);
    // highlights
    px(ctx, C.leafHi, ox + 8, oy + 7);
    px(ctx, C.leafHi, ox + 13, oy + 6);
    px(ctx, C.leafHi, ox + 16, oy + 9);
    px(ctx, C.leafHi, ox + 7, oy + 11);
    px(ctx, C.leafHi, ox + 12, oy + 12);
  };

  // Pineapple-style plant (long striped leaves)
  F.plantPineapple = function (ctx, f) {
    const ox = f.x * TILE, oy = f.y * TILE;
    // pot (lighter, taller, banded)
    rect(ctx, C.potDark, ox + 5, oy + 15, 14, 8);
    rect(ctx, '#dfd2c2', ox + 6, oy + 16, 12, 6);
    rect(ctx, C.potBand, ox + 6, oy + 18, 12, 1);
    rect(ctx, C.potDark, ox + 5, oy + 14, 14, 2);
    // leaves - long, pointed, striped
    const leafConfigs = [
      [10, -5, 12, 0],  // center tall
      [6, -2, 10, -1],  // left lean
      [14, -2, 10, 1],  // right lean
      [4, 2, 8, -2],
      [16, 2, 8, 2],
      [2, 5, 6, -3],
      [18, 5, 6, 3],
    ];
    for (const [cx, cy, len, skew] of leafConfigs) {
      // leaf body
      for (let i = 0; i < len; i++) {
        const lx = ox + cx + Math.round(i * skew / len);
        const ly = oy + 14 - i;
        if (ly < oy - 2 || lx < ox || lx >= ox + TILE) continue;
        const w = i < 2 ? 2 : 1;
        rect(ctx, C.ppLeaf, lx, ly, w, 1);
        if (i < len - 2) px(ctx, C.ppLeafDark, lx, ly);
        if (i > 1 && i % 2 === 0) px(ctx, C.ppStripe, lx + (w - 1), ly);
      }
    }
    // top tuft
    rect(ctx, C.ppLeafHi, ox + 9, oy + 1, 4, 2);
  };

  // Vending machine 2 wide Ã 2 tall, drawn upward into wall as a tall unit
  F.vending = function (ctx, f) {
    const ox = f.x * TILE, oy = f.y * TILE;
    const W = f.w * TILE, H = f.h * TILE;
    const fh = H + 14; // extend up into wall a bit
    const fy = oy - 14;
    // body
    rect(ctx, C.vendBodyDark, ox + 2, fy, W - 4, fh);
    rect(ctx, C.vendBody, ox + 3, fy + 1, W - 6, fh - 2);
    rect(ctx, C.vendBodyHi, ox + 3, fy + 1, W - 6, 2);
    // top header section (sign)
    rect(ctx, C.vendBodyDark, ox + 4, fy + 4, W - 8, 6);
    rect(ctx, C.book6, ox + 5, fy + 5, W - 10, 4);
    rect(ctx, C.vendBody, ox + 6, fy + 6, W - 12, 2);
    // glass front
    const gx = ox + 6, gy = fy + 12, gw = W - 12, gh = fh - 26;
    rect(ctx, C.vendBody, gx - 1, gy - 1, gw + 2, gh + 2);
    rect(ctx, C.vendGlass, gx, gy, gw, gh);
    rect(ctx, C.vendGlassHi, gx + 1, gy + 1, 2, gh - 2);
    // 3 shelves of drinks
    const drinks = [C.drink1, C.drink2, C.drink3, C.drink4, C.drink1, C.drink2, C.drink3, C.drink2, C.drink4];
    for (let row = 0; row < 3; row++) {
      const ry = gy + 3 + row * Math.floor((gh - 4) / 3);
      // shelf bar
      rect(ctx, C.vendShelf, gx, ry + Math.floor((gh - 4) / 3) - 2, gw, 1);
      for (let col = 0; col < 3; col++) {
        const cx2 = gx + 2 + col * Math.floor((gw - 4) / 3);
        const d = drinks[(row * 3 + col) % drinks.length];
        rect(ctx, d, cx2, ry, 4, Math.floor((gh - 4) / 3) - 3);
        rect(ctx, shade(d, 0.15), cx2, ry, 1, Math.floor((gh - 4) / 3) - 3);
        // cap
        rect(ctx, C.book7, cx2, ry, 4, 1);
      }
    }
    // keypad right side
    rect(ctx, C.vendBodyDark, ox + W - 8, fy + 14, 5, 14);
    // keypad buttons
    for (let r2 = 0; r2 < 4; r2++) {
      px(ctx, C.vendButton, ox + W - 6, fy + 16 + r2 * 3);
      px(ctx, C.vendButton, ox + W - 4, fy + 16 + r2 * 3);
    }
    // coin slot + return
    rect(ctx, C.vendBodyDark, ox + 4, fy + fh - 12, 5, 1);
    rect(ctx, C.vendBodyDark, ox + 4, fy + fh - 8, 8, 4);
    rect(ctx, C.book7, ox + 5, fy + fh - 7, 6, 2);
    // LED
    px(ctx, C.vendLed, ox + W - 5, fy + 12);
  };

  // Water dispenser 1 wide Ã 2 tall
  F.waterDispenser = function (ctx, f) {
    const ox = f.x * TILE, oy = f.y * TILE;
    const H = f.h * TILE;
    const fh = H + 12;
    const fy = oy - 12;
    // body
    rect(ctx, C.wdShadow, ox + 2, fy, TILE - 4, fh);
    rect(ctx, C.wdBody, ox + 3, fy + 1, TILE - 6, fh - 2);
    rect(ctx, C.wdShadow, ox + 3, fy + 1, TILE - 6, 1);
    // top water bottle (inverted)
    rect(ctx, C.wdCap, ox + 9, fy + 2, 6, 3);
    rect(ctx, C.wdShadow, ox + 7, fy + 5, 10, 2);
    rect(ctx, C.wdWater, ox + 7, fy + 6, 10, 8);
    rect(ctx, C.wdWaterHi, ox + 8, fy + 7, 1, 6);
    // bubbles
    px(ctx, C.book6, ox + 10, fy + 9);
    px(ctx, C.book6, ox + 14, fy + 11);
    px(ctx, C.book6, ox + 12, fy + 13);
    // display
    rect(ctx, C.wdDark, ox + 6, fy + 16, 12, 3);
    rect(ctx, C.vendLed, ox + 7, fy + 17, 2, 1);
    // taps
    rect(ctx, C.wdBlue, ox + 7, fy + 22, 4, 3);
    rect(ctx, C.wdRed, ox + 13, fy + 22, 4, 3);
    // spout
    rect(ctx, C.wdDark, ox + 9, fy + 25, 6, 2);
    rect(ctx, C.wdDark, ox + 11, fy + 27, 2, 3);
    // drip tray
    rect(ctx, C.wdDark, ox + 6, fy + fh - 6, 12, 4);
    rect(ctx, C.wdShadow, ox + 7, fy + fh - 5, 10, 2);
  };

  // Microwave 2 wide Ã 1 tall (sits on counter)
  F.microwave = function (ctx, f) {
    const ox = f.x * TILE, oy = f.y * TILE;
    const W = f.w * TILE;
    const mh = 18;
    const my = oy - mh + 4;
    rect(ctx, C.mwBody, ox + 2, my, W - 4, mh);
    rect(ctx, C.mwBodyHi, ox + 2, my, W - 4, 1);
    // window
    rect(ctx, C.mwBodyHi, ox + 3, my + 2, Math.floor((W - 6) * 0.6), mh - 4);
    rect(ctx, C.mwWindow, ox + 4, my + 3, Math.floor((W - 6) * 0.6) - 2, mh - 6);
    // food inside (glow)
    rect(ctx, C.mwGlow, ox + 6, my + 6, 8, 3);
    px(ctx, C.mug2, ox + 7, my + 7);
    // controls panel
    const px2 = ox + 2 + Math.floor((W - 6) * 0.6) + 2;
    rect(ctx, C.mwBodyHi, px2, my + 2, W - 4 - (px2 - ox - 2), mh - 4);
    rect(ctx, C.mwDisp, px2 + 1, my + 3, 6, 2);
    // buttons
    for (let i = 0; i < 3; i++) {
      px(ctx, C.book6, px2 + 1 + i * 2, my + 7);
      px(ctx, C.book6, px2 + 1 + i * 2, my + 9);
      px(ctx, C.book6, px2 + 1 + i * 2, my + 11);
    }
    // handle on door (right side of window)
    rect(ctx, C.mwHandle, ox + 2 + Math.floor((W - 6) * 0.6) - 1, my + 4, 1, mh - 8);
  };

  // Counter under microwave / appliances
  F.counter = function (ctx, f) {
    const ox = f.x * TILE, oy = f.y * TILE;
    const W = f.w * TILE, H = f.h * TILE;
    rect(ctx, C.counterEdge, ox, oy, W, H);
    rect(ctx, C.counterTop, ox, oy + 1, W, 6);
    rect(ctx, C.counterTop2, ox, oy + 7, W, H - 9);
    // marble specks
    for (let i = 2; i < W; i += 7) {
      px(ctx, C.counterEdge, ox + i, oy + 3);
      px(ctx, C.counterEdge, ox + i + 3, oy + 5);
    }
    // cabinet doors at bottom
    rect(ctx, C.cabFront, ox, oy + H - 2, W, 2);
    rect(ctx, C.cabFront2, ox, oy + H - 1, W, 1);
    // handles spacing
    for (let dx = 4; dx < W; dx += 12) {
      rect(ctx, C.cabHandle, ox + dx, oy + H - 2, 3, 1);
    }
  };

  // Trash bin
  F.trashbin = function (ctx, f) {
    const ox = f.x * TILE, oy = f.y * TILE;
    rect(ctx, C.trashRim, ox + 5, oy + 6, 14, 16);
    rect(ctx, C.trashBody, ox + 6, oy + 7, 12, 14);
    rect(ctx, C.trashLid, ox + 4, oy + 5, 16, 4);
    rect(ctx, C.trashRim, ox + 4, oy + 5, 16, 1);
    rect(ctx, C.trashRim, ox + 9, oy + 6, 6, 1);
    // vertical lines
    rect(ctx, C.trashRim, ox + 9, oy + 9, 1, 12);
    rect(ctx, C.trashRim, ox + 14, oy + 9, 1, 12);
  };

  // Wall clock (mounted on wall above, drawn UP)
  F.wallClock = function (ctx, f) {
    const ox = f.x * TILE, oy = f.y * TILE;
    const cy = oy - 10;
    const cx = ox + TILE / 2;
    // frame
    rect(ctx, C.clockFrame, cx - 6, cy, 12, 12);
    rect(ctx, C.clockFrameHi, cx - 5, cy, 10, 1);
    rect(ctx, C.clockFace, cx - 5, cy + 1, 10, 10);
    // 12-3-6-9 ticks
    px(ctx, C.clockNum, cx, cy + 2);
    px(ctx, C.clockNum, cx, cy + 9);
    px(ctx, C.clockNum, cx - 4, cy + 6);
    px(ctx, C.clockNum, cx + 3, cy + 6);
    // hands
    rect(ctx, C.clockHand, cx, cy + 3, 1, 3);
    rect(ctx, C.clockHand, cx, cy + 6, 4, 1);
    // center
    px(ctx, C.clockFrame, cx, cy + 6);
  };

  // Wall painting (drawn upward into wall row)
  F.wallPainting = function (ctx, f) {
    const ox = f.x * TILE, oy = f.y * TILE;
    const W = f.w * TILE;
    const ph = 16, fy = oy - ph - 1;
    rect(ctx, C.paintFrameDark, ox + 6, fy, W - 12, ph);
    rect(ctx, C.paintFrame, ox + 7, fy + 1, W - 14, 2);
    rect(ctx, C.paintSky, ox + 8, fy + 3, W - 16, ph - 5);
    // sun
    rect(ctx, C.paintSun, ox + 13, fy + 5, 3, 3);
    px(ctx, C.book6, ox + 14, fy + 6);
    // mountains
    rect(ctx, C.paintMtn, ox + 8, fy + ph - 8, W - 16, 3);
    rect(ctx, C.book6, ox + 11, fy + ph - 9, 2, 1);
    rect(ctx, C.book6, ox + W - 16, fy + ph - 9, 2, 1);
    // grass
    rect(ctx, C.paintGrass, ox + 8, fy + ph - 4, W - 16, 2);
    // frame bottom
    rect(ctx, C.paintFrameDark, ox + 6, fy + ph - 1, W - 12, 1);
  };

  // Hand sanitizer dispenser (mounted on left wall - vertical)
  F.sanitizer = function (ctx, f) {
    const ox = f.x * TILE, oy = f.y * TILE;
    // tile is at x=18 (the wall col). Draw on right side of wall (inside lounge)
    const fx = ox + TILE - 8;
    rect(ctx, C.sanBodyDark, fx, oy + 4, 6, 12);
    rect(ctx, C.sanBody, fx + 1, oy + 5, 4, 10);
    // bottle window
    rect(ctx, C.sanBottle, fx + 1, oy + 6, 4, 6);
    rect(ctx, C.sanLiquid, fx + 2, oy + 9, 2, 3);
    // nozzle
    rect(ctx, C.sanNozzle, fx + 2, oy + 14, 2, 2);
    rect(ctx, C.sanNozzle, fx + 2, oy + 16, 1, 1);
  };

  // Red sofa: 2 wide Ã 2 tall. facing 'right' = back is left, facing 'left' = back is right
  F.sofa = function (ctx, f) {
    const ox = f.x * TILE, oy = f.y * TILE;
    const W = f.w * TILE, H = f.h * TILE;
    const right = f.facing === 'right';
    // shadow
    rect(ctx, 'rgba(0,0,0,0.25)', ox + 2, oy + H - 2, W - 4, 2);
    // backrest (against opposite side from facing direction)
    if (right) {
      // back on left
      rect(ctx, C.sofaDark, ox, oy, 8, H);
      rect(ctx, C.sofa, ox + 2, oy + 2, 5, H - 4);
      rect(ctx, C.sofaHi, ox + 2, oy + 2, 5, 1);
    } else {
      rect(ctx, C.sofaDark, ox + W - 8, oy, 8, H);
      rect(ctx, C.sofa, ox + W - 7, oy + 2, 5, H - 4);
      rect(ctx, C.sofaHi, ox + W - 7, oy + 2, 5, 1);
    }
    // seat cushions
    const sx = right ? ox + 8 : ox;
    const sw = W - 8;
    rect(ctx, C.sofaShadow, sx, oy + 3, sw, H - 6);
    rect(ctx, C.sofa, sx + 1, oy + 4, sw - 1, H - 8);
    rect(ctx, C.sofaHi, sx + 1, oy + 4, sw - 1, 1);
    // cushion split (horizontal between 2 cushions)
    rect(ctx, C.sofaShadow, sx + 1, oy + H / 2 - 1, sw - 1, 1);
    // armrest at front (opposite end of backrest)
    if (right) {
      rect(ctx, C.sofaDark, ox + W - 5, oy + 2, 5, H - 4);
      rect(ctx, C.sofa, ox + W - 4, oy + 3, 3, H - 6);
      rect(ctx, C.sofaHi, ox + W - 4, oy + 3, 3, 1);
    } else {
      rect(ctx, C.sofaDark, ox, oy + 2, 5, H - 4);
      rect(ctx, C.sofa, ox + 1, oy + 3, 3, H - 6);
      rect(ctx, C.sofaHi, ox + 1, oy + 3, 3, 1);
    }
    // back top stripe
    if (right) rect(ctx, C.sofaShadow, ox + 7, oy, 1, H);
    else rect(ctx, C.sofaShadow, ox + W - 8, oy, 1, H);
    // legs
    rect(ctx, C.shelfWoodDark, ox + 2, oy + H - 2, 2, 2);
    rect(ctx, C.shelfWoodDark, ox + W - 4, oy + H - 2, 2, 2);
  };

  // Coffee table (round-ish wood) with laptop on top
  F.coffeeTable = function (ctx, f) {
    const ox = f.x * TILE, oy = f.y * TILE;
    const W = f.w * TILE, H = f.h * TILE;
    // shadow
    rect(ctx, 'rgba(0,0,0,0.3)', ox + 3, oy + H - 3, W - 6, 3);
    // table top oval-ish
    rect(ctx, C.ctTrim, ox + 4, oy + 4, W - 8, H - 10);
    rect(ctx, C.ctTop2, ox + 5, oy + 5, W - 10, H - 12);
    rect(ctx, C.ctTop, ox + 5, oy + 5, W - 10, 1);
    rect(ctx, C.ctTopHi, ox + 6, oy + 6, W - 12, 1);
    // rounded corners
    px(ctx, C.ctTrim, ox + 4, oy + 4);
    px(ctx, C.ctTrim, ox + W - 5, oy + 4);
    // legs visible
    rect(ctx, C.ctTrim, ox + 6, oy + H - 8, 2, 6);
    rect(ctx, C.ctTrim, ox + W - 8, oy + H - 8, 2, 6);

    // Laptop centered on table (open, screen facing one side)
    const lx = ox + W / 2 - 9, ly = oy + 9;
    // base
    rect(ctx, C.lapBack, lx, ly + 5, 18, 5);
    rect(ctx, C.lapBody, lx + 1, ly + 6, 16, 3);
    // hinge
    rect(ctx, C.lapBack, lx + 1, ly + 4, 16, 2);
    // screen back
    rect(ctx, C.lapBack, lx + 1, ly, 16, 5);
    // screen front
    rect(ctx, C.lapScreen, lx + 2, ly + 1, 14, 3);
    rect(ctx, C.monCode2, lx + 3, ly + 2, 4, 1);
    rect(ctx, C.monLight, lx + 8, ly + 2, 4, 1);
    rect(ctx, C.monHeader, lx + 13, ly + 2, 2, 1);
    // mug at corner
    rect(ctx, C.mug1, ox + 7, oy + 7, 4, 4);
    rect(ctx, C.mug2, ox + 7, oy + 7, 4, 1);
    rect(ctx, C.coffeeDark, ox + 8, oy + 7, 2, 1);
  };

  // Office chair for desks (with wheels)
  function drawDeskChair(ctx, x, y, facing) {
    const ox = x * TILE, oy = y * TILE;
    rect(ctx, 'rgba(0,0,0,0.3)', ox + 4, oy + TILE - 3, TILE - 8, 3);
    // wheel base
    rect(ctx, C.chairWheel, ox + 4, oy + 16, TILE - 8, 3);
    rect(ctx, C.chairBackHi, ox + 4, oy + 16, TILE - 8, 1);
    // wheels
    px(ctx, C.chairBack, ox + 4, oy + 18);
    px(ctx, C.chairBack, ox + TILE - 5, oy + 18);
    px(ctx, C.chairBack, ox + TILE / 2 - 1, oy + 19);
    // stem
    rect(ctx, C.chairStem, ox + TILE / 2 - 1, oy + 12, 2, 6);
    // seat
    rect(ctx, C.chairBack, ox + 4, oy + 9, TILE - 8, 5);
    rect(ctx, C.chairSeat, ox + 5, oy + 10, TILE - 10, 3);
    rect(ctx, C.chairBackHi, ox + 5, oy + 10, TILE - 10, 1);
    // backrest
    if (facing === 'down') {
      rect(ctx, C.chairBack, ox + 5, oy + 2, TILE - 10, 8);
      rect(ctx, C.chairSeat, ox + 6, oy + 3, TILE - 12, 6);
      rect(ctx, C.chairBackHi, ox + 6, oy + 3, TILE - 12, 1);
      // armrests
      rect(ctx, C.chairBack, ox + 2, oy + 8, 3, 4);
      rect(ctx, C.chairBack, ox + TILE - 5, oy + 8, 3, 4);
    } else if (facing === 'up') {
      rect(ctx, C.chairBack, ox + 5, oy + 14, TILE - 10, 8);
      rect(ctx, C.chairSeat, ox + 6, oy + 15, TILE - 12, 6);
      rect(ctx, C.chairBackHi, ox + 6, oy + 15, TILE - 12, 1);
      rect(ctx, C.chairBack, ox + 2, oy + 12, 3, 4);
      rect(ctx, C.chairBack, ox + TILE - 5, oy + 12, 3, 4);
    }
  }

  // Public chair drawer (only used for desks - facing is either up or down)
  function drawChair(ctx, x, y, facing) {
    drawDeskChair(ctx, x, y, facing);
  }

  // ----- Agent sprite (18Ã22 within 24Ã24 tile) -----
  function drawAgent(ctx, a, frame) {
    const ox = a.tileX * TILE + Math.round(a.dx * TILE);
    const oy = a.tileY * TILE + Math.round(a.dy * TILE);

    const skin = a.skin || '#f0c8a0';
    const skinDark = shade(skin, -0.14);
    const hair = a.hair || '#3a2820';
    const hairDark = shade(hair, -0.18);
    const hairHi = shade(hair, 0.12);
    const shirt = a.shirt || '#3a78c8';
    const shirtDark = shade(shirt, -0.2);
    const shirtHi = shade(shirt, 0.1);
    const pants = a.pants || '#2a2730';
    const pantsHi = shade(pants, 0.12);
    const hairStyle = a.hairStyle || 'short';

    const facing = a.facing || 'down';
    const sitting = a.sitting;
    const sleeping = a.sleeping;

    // shadow
    if (!sitting) {
      ctx.fillStyle = 'rgba(0,0,0,0.32)';
      ctx.fillRect(ox + 4, oy + TILE - 2, 14, 2);
    }

    // === LEGS === (only when standing)
    if (!sitting) {
      const lo = frame ? 0 : 1;
      const ro = frame ? 1 : 0;
      // left leg
      rect(ctx, pants, ox + 6, oy + 16 + lo, 3, 5 - lo);
      rect(ctx, pantsHi, ox + 6, oy + 16 + lo, 1, 3);
      // right leg
      rect(ctx, pants, ox + 12, oy + 16 + ro, 3, 5 - ro);
      rect(ctx, pantsHi, ox + 12, oy + 16 + ro, 1, 3);
      // shoes
      rect(ctx, '#1a1a1f', ox + 5, oy + 20 + lo, 4, 2);
      rect(ctx, '#1a1a1f', ox + 12, oy + 20 + ro, 4, 2);
    }

    // === TORSO ===
    // shirt base
    rect(ctx, shirtDark, ox + 4, oy + 10, 14, 7);
    rect(ctx, shirt, ox + 5, oy + 10, 12, 6);
    rect(ctx, shirtHi, ox + 5, oy + 10, 12, 1);

    // collar / neckline by facing
    if (facing === 'down') {
      // V-neck dip
      rect(ctx, skinDark, ox + 9, oy + 10, 4, 2);
      px(ctx, shirtDark, ox + 8, oy + 10);
      px(ctx, shirtDark, ox + 13, oy + 10);
      // (optional tie: if a.tie)
      if (a.tie) {
        rect(ctx, a.tie, ox + 10, oy + 11, 2, 5);
        rect(ctx, shade(a.tie, -0.2), ox + 10, oy + 11, 1, 5);
      }
    } else if (facing === 'left') {
      rect(ctx, shirtDark, ox + 5, oy + 10, 6, 1);
    } else if (facing === 'right') {
      rect(ctx, shirtDark, ox + 11, oy + 10, 6, 1);
    }

    // belt
    rect(ctx, '#1a1a1f', ox + 5, oy + 15, 12, 1);

    // === ARMS ===
    if (!sitting) {
      const swing = frame ? 1 : 0;
      // sleeves
      rect(ctx, shirtDark, ox + 3, oy + 10, 2, 5);
      rect(ctx, shirtDark, ox + 17, oy + 10, 2, 5);
      rect(ctx, shirt, ox + 3, oy + 10, 1, 4);
      rect(ctx, shirt, ox + 18, oy + 10, 1, 4);
      // hands
      rect(ctx, skin, ox + 3, oy + 13 + swing, 2, 2);
      rect(ctx, skin, ox + 17, oy + 13 + (1 - swing), 2, 2);
    } else {
      // arms forward on desk
      rect(ctx, shirtDark, ox + 3, oy + 11, 2, 3);
      rect(ctx, shirtDark, ox + 17, oy + 11, 2, 3);
      rect(ctx, skin, ox + 3, oy + 13, 3, 2);
      rect(ctx, skin, ox + 16, oy + 13, 3, 2);
    }

    // === HEAD ===
    // skin
    rect(ctx, skin, ox + 6, oy + 3, 10, 7);
    rect(ctx, skinDark, ox + 6, oy + 9, 10, 1);

    // hair by style + facing
    drawHair(ctx, ox, oy, hair, hairDark, hairHi, hairStyle, facing);

    // ear hint
    if (facing === 'left') px(ctx, skinDark, ox + 6, oy + 6);
    else if (facing === 'right') px(ctx, skinDark, ox + 15, oy + 6);

    // === FACE ===
    if (facing !== 'up') {
      if (sleeping) {
        rect(ctx, '#1a1a1f', ox + 7, oy + 6, 3, 1);
        rect(ctx, '#1a1a1f', ox + 12, oy + 6, 3, 1);
      } else if (facing === 'down') {
        // eyes
        rect(ctx, '#1a1a1f', ox + 8, oy + 6, 1, 2);
        rect(ctx, '#1a1a1f', ox + 13, oy + 6, 1, 2);
        // highlight
        px(ctx, '#ffffff', ox + 8, oy + 6);
        px(ctx, '#ffffff', ox + 13, oy + 6);
        // mouth
        px(ctx, skinDark, ox + 10, oy + 8);
        px(ctx, skinDark, ox + 11, oy + 8);
        // blush
        px(ctx, '#e69090', ox + 7, oy + 8);
        px(ctx, '#e69090', ox + 14, oy + 8);
      } else if (facing === 'left') {
        rect(ctx, '#1a1a1f', ox + 7, oy + 6, 1, 2);
        px(ctx, '#ffffff', ox + 7, oy + 6);
        px(ctx, skinDark, ox + 8, oy + 8);
      } else {
        rect(ctx, '#1a1a1f', ox + 14, oy + 6, 1, 2);
        px(ctx, '#ffffff', ox + 14, oy + 6);
        px(ctx, skinDark, ox + 13, oy + 8);
      }
    }

    // selection ring
    if (a.selected) {
      ctx.strokeStyle = '#f5d048';
      ctx.lineWidth = 1;
      ctx.strokeRect(ox + 2.5, oy + 0.5, 17, 22);
    }
  }

  function drawHair(ctx, ox, oy, hair, hairDark, hairHi, style, facing) {
    if (style === 'afro') {
      // round big poof
      rect(ctx, hairDark, ox + 4, oy + 1, 14, 5);
      rect(ctx, hair, ox + 5, oy + 1, 12, 4);
      rect(ctx, hairHi, ox + 7, oy + 1, 2, 1);
      rect(ctx, hairHi, ox + 12, oy + 1, 2, 1);
      // side puffs
      rect(ctx, hair, ox + 3, oy + 3, 1, 4);
      rect(ctx, hair, ox + 18, oy + 3, 1, 4);
      rect(ctx, hairDark, ox + 4, oy + 2, 1, 4);
      rect(ctx, hairDark, ox + 17, oy + 2, 1, 4);
      // forehead bangs
      if (facing === 'down') {
        rect(ctx, hairDark, ox + 6, oy + 4, 10, 2);
        rect(ctx, hair, ox + 7, oy + 4, 8, 1);
      }
    } else if (style === 'curly') {
      // wavy curly hair, medium length
      rect(ctx, hairDark, ox + 5, oy + 1, 12, 5);
      rect(ctx, hair, ox + 5, oy + 1, 12, 4);
      // curl bumps
      px(ctx, hairHi, ox + 7, oy + 1);
      px(ctx, hairHi, ox + 11, oy + 1);
      px(ctx, hairHi, ox + 14, oy + 1);
      // side fluff
      rect(ctx, hair, ox + 4, oy + 3, 1, 5);
      rect(ctx, hair, ox + 17, oy + 3, 1, 5);
      if (facing === 'down') {
        rect(ctx, hairDark, ox + 6, oy + 3, 10, 2);
        rect(ctx, hair, ox + 7, oy + 3, 8, 1);
        px(ctx, hair, ox + 6, oy + 5);
        px(ctx, hair, ox + 15, oy + 5);
      }
    } else if (style === 'long') {
      // long flowing hair down sides
      rect(ctx, hairDark, ox + 5, oy + 1, 12, 4);
      rect(ctx, hair, ox + 5, oy + 1, 12, 3);
      rect(ctx, hairHi, ox + 7, oy + 1, 4, 1);
      // sides down to shoulders
      rect(ctx, hair, ox + 4, oy + 3, 2, 9);
      rect(ctx, hair, ox + 16, oy + 3, 2, 9);
      rect(ctx, hairDark, ox + 4, oy + 3, 1, 9);
      rect(ctx, hairDark, ox + 17, oy + 3, 1, 9);
      if (facing === 'down') {
        rect(ctx, hairDark, ox + 6, oy + 3, 10, 1);
        px(ctx, hair, ox + 7, oy + 5);
        px(ctx, hair, ox + 14, oy + 5);
      }
    } else if (style === 'bun') {
      // hair tied back with bun on top, side puff
      rect(ctx, hairDark, ox + 5, oy + 1, 12, 4);
      rect(ctx, hair, ox + 6, oy + 1, 10, 3);
      // bun
      rect(ctx, hair, ox + 9, oy - 2, 6, 3);
      rect(ctx, hairDark, ox + 9, oy - 2, 6, 1);
      rect(ctx, hairHi, ox + 10, oy - 2, 2, 1);
      if (facing === 'down') {
        rect(ctx, hairDark, ox + 6, oy + 3, 10, 1);
      }
    } else if (style === 'spiky') {
      // short messy spikes
      rect(ctx, hairDark, ox + 5, oy + 1, 12, 4);
      rect(ctx, hair, ox + 5, oy + 2, 12, 2);
      // spike points
      rect(ctx, hair, ox + 6, oy, 2, 2);
      rect(ctx, hair, ox + 9, oy, 2, 2);
      rect(ctx, hair, ox + 13, oy, 2, 2);
      px(ctx, hairHi, ox + 9, oy);
      // side
      rect(ctx, hair, ox + 4, oy + 3, 1, 3);
      rect(ctx, hair, ox + 17, oy + 3, 1, 3);
      if (facing === 'down') {
        rect(ctx, hairDark, ox + 6, oy + 3, 10, 1);
      }
    } else {
      // 'short' (default)
      rect(ctx, hairDark, ox + 5, oy + 1, 12, 4);
      rect(ctx, hair, ox + 6, oy + 1, 10, 3);
      rect(ctx, hairHi, ox + 7, oy + 1, 4, 1);
      // sides
      rect(ctx, hair, ox + 5, oy + 4, 1, 3);
      rect(ctx, hair, ox + 16, oy + 4, 1, 3);
      if (facing === 'down') {
        rect(ctx, hairDark, ox + 6, oy + 4, 10, 1);
        px(ctx, hair, ox + 8, oy + 5);
        px(ctx, hair, ox + 13, oy + 5);
      } else if (facing === 'up') {
        rect(ctx, hair, ox + 5, oy + 1, 12, 6);
      } else if (facing === 'left') {
        rect(ctx, hair, ox + 5, oy + 1, 10, 5);
        rect(ctx, hair, ox + 5, oy + 5, 2, 2);
      } else if (facing === 'right') {
        rect(ctx, hair, ox + 7, oy + 1, 10, 5);
        rect(ctx, hair, ox + 15, oy + 5, 2, 2);
      }
    }
  }

  // ----- speech bubble (Idle Ã style) -----
  function drawBubble(ctx, a, text) {
    const ox = a.tileX * TILE + Math.round(a.dx * TILE);
    const oy = a.tileY * TILE + Math.round(a.dy * TILE);
    ctx.font = 'bold 9px "JetBrains Mono", monospace';
    const tw = Math.ceil(ctx.measureText(text).width);
    const bw = tw + 16;
    const bh = 13;
    const bx = ox + TILE / 2 - bw / 2;
    const by = oy - bh - 4;
    rect(ctx, 'rgba(0,0,0,0.4)', bx + 1, by + 1, bw, bh);
    rect(ctx, '#1a1a1f', bx, by, bw, bh);
    rect(ctx, '#3b3742', bx, by, bw, 1);
    rect(ctx, '#3b3742', bx, by, 1, bh);
    ctx.fillStyle = '#ededed';
    ctx.fillText(text, bx + 4, by + 9);
    ctx.fillStyle = '#9a93a8';
    ctx.fillText('Ã', bx + bw - 9, by + 9);
    rect(ctx, '#1a1a1f', ox + TILE / 2 - 1, by + bh, 2, 2);
    rect(ctx, '#1a1a1f', ox + TILE / 2, by + bh + 2, 1, 1);
  }

  function drawZZZ(ctx, a, t) {
    const ox = a.tileX * TILE + Math.round(a.dx * TILE);
    const oy = a.tileY * TILE + Math.round(a.dy * TILE);
    const phase = Math.floor(t * 1.5) % 3;
    ctx.font = 'bold 10px "JetBrains Mono", monospace';
    ctx.fillStyle = '#9fb0d8';
    for (let i = 0; i <= phase; i++) {
      ctx.fillText('z', ox + 17 + i * 3, oy + 3 - i * 5);
    }
  }

  function drawNightOverlay(ctx, w, h, simMinute) {
    const hourFloat = (simMinute / 60) % 24;
    let r = 0, g = 0, b = 0, alpha = 0;
    if (hourFloat < 6) { r = 10; g = 16; b = 56; alpha = 0.55; }
    else if (hourFloat < 8) {
      const t = (hourFloat - 6) / 2;
      r = 60 * (1 - t) + 230 * t;
      g = 40 * (1 - t) + 140 * t;
      b = 80 * (1 - t) + 90 * t;
      alpha = 0.45 * (1 - t) + 0.18 * t;
    }
    else if (hourFloat < 17) { alpha = 0; }
    else if (hourFloat < 19) {
      const t = (hourFloat - 17) / 2;
      r = 230 * (1 - t) + 50 * t;
      g = 130 * (1 - t) + 30 * t;
      b = 80 * (1 - t) + 90 * t;
      alpha = 0.15 * (1 - t) + 0.45 * t;
    }
    else if (hourFloat < 22) { r = 30; g = 25; b = 70; alpha = 0.5; }
    else { r = 10; g = 16; b = 56; alpha = 0.55; }
    if (alpha <= 0) return;
    ctx.fillStyle = `rgba(${r|0},${g|0},${b|0},${alpha})`;
    ctx.fillRect(0, 0, w, h);
  }

  return { drawTile, F, drawChair, drawAgent, drawBubble, drawZZZ, drawNightOverlay };
})();

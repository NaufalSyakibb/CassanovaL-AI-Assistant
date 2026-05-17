// Boot, game loop, side panel, click handling, tweaks panel protocol.

(function () {
  const M = window.OfficeMap;
  const R = window.OfficeRender;
  const S = window.OfficeSim;

  const TWEAK_DEFAULTS = /*EDITMODE-BEGIN*/{
    "speed": 1,
    "showBubbles": true,
    "dayNight": true,
    "agentCount": 8,
    "startHour": 9,
    "tileZoom": 1
  }/*EDITMODE-END*/;

  let tweaks = { ...TWEAK_DEFAULTS };

  const canvas = document.getElementById('stage');
  const ctx = canvas.getContext('2d');
  canvas.width = M.COLS * M.TILE;
  canvas.height = M.ROWS * M.TILE;
  ctx.imageSmoothingEnabled = false;

  const state = {
    agents: S.createAgents(),
    simMinute: tweaks.startHour * 60,
    paused: false,
    log: [],
    selectedId: null,
    speed: tweaks.speed,
  };

  // Reduce/expand agent list according to tweak
  function applyAgentCount(n) {
    n = Math.max(1, Math.min(8, n));
    const fresh = S.createAgents();
    state.agents = fresh.slice(0, n);
    renderRoster();
  }

  applyAgentCount(tweaks.agentCount);

  function pushLog(msg) {
    const t = formatTime(state.simMinute);
    state.log.unshift(`${t}  ${msg}`);
    if (state.log.length > 60) state.log.pop();
    renderLog();
  }

  function formatTime(m) {
    const h = Math.floor((m / 60) % 24);
    const mm = Math.floor(m % 60);
    return String(h).padStart(2, '0') + ':' + String(mm).padStart(2, '0');
  }

  // ---------- Game loop ----------
  let lastT = performance.now();
  function loop() {
    const now = performance.now();
    const dtReal = Math.min(0.1, (now - lastT) / 1000);
    lastT = now;
    const dtSim = state.paused ? 0 : dtReal * state.speed;
    // Sim minute progression: 1 real sec = 30 sim sec at speed 1
    state.simMinute = (state.simMinute + dtSim * 0.5) % (24 * 60);

    if (!state.paused) {
      for (const a of state.agents) {
        S.updateAgent(a, dtReal, dtSim, state.agents, pushLog, state.simMinute);
      }
    }
    drawFrame(dtReal);
    updateClock();
  }
  setInterval(loop, 1000 / 60);
  loop();

  function drawFrame() {
    // floor + walls
    for (let r = 0; r < M.ROWS; r++) {
      for (let c = 0; c < M.COLS; c++) {
        R.drawTile(ctx, c, r, M.tiles[r][c]);
      }
    }
    // chairs first (under agents)
    // chairs in front of each desk - use seat facing
    for (const seat of M.stations.desks) {
      R.drawChair(ctx, seat.x, seat.y, seat.facing);
    }
    // furniture
    for (const f of M.furniture) {
      const fn = R.F[f.type];
      if (fn) fn(ctx, f);
    }
    // agents, sorted by y for proper overlap
    const sorted = [...state.agents].sort((a, b) => a.tileY - b.tileY);
    for (const a of sorted) {
      const frame = Math.floor(a.animPhase) % 2;
      R.drawAgent(ctx, a, frame);
      if (a.sleeping) R.drawZZZ(ctx, a, a.animPhase);
      if (tweaks.showBubbles && a.bubbleTimer > 0 && a.bubbleText) {
        R.drawBubble(ctx, a, a.bubbleText);
      } else if (tweaks.showBubbles && a.selected && a.bubbleText) {
        R.drawBubble(ctx, a, a.bubbleText);
      }
    }
    // overlay night
    if (tweaks.dayNight) {
      R.drawNightOverlay(ctx, canvas.width, canvas.height, state.simMinute);
    }
  }

  // ---------- Side panel ----------
  function renderRoster() {
    const root = document.getElementById('roster');
    root.innerHTML = '';
    for (const a of state.agents) {
      const item = document.createElement('div');
      item.className = 'agent-item' + (a.id === state.selectedId ? ' selected' : '');
      item.dataset.id = a.id;
      item.innerHTML = `
        <div class="avatar" style="background:${a.shirt}"></div>
        <div class="agent-meta">
          <div class="agent-name">${a.name}</div>
          <div class="agent-role">${a.role}</div>
        </div>
        <div class="agent-status" data-status-for="${a.id}">${labelFor(a)}</div>
      `;
      item.addEventListener('click', () => selectAgent(a.id));
      root.appendChild(item);
    }
  }

  function labelFor(a) {
    return S.ACTIVITY_LABELS[a.activity] || a.activity;
  }

  function renderLog() {
    const root = document.getElementById('log');
    root.innerHTML = state.log.slice(0, 30).map(l => `<div class="log-line">${l}</div>`).join('');
  }

  function updateRosterStatuses() {
    for (const a of state.agents) {
      const el = document.querySelector(`[data-status-for="${a.id}"]`);
      if (el) el.textContent = labelFor(a);
    }
  }

  function selectAgent(id) {
    state.selectedId = id;
    for (const a of state.agents) a.selected = (a.id === id);
    renderRoster();
    renderTaskPanel();
    document.dispatchEvent(new CustomEvent('agent-select', { detail: { id } }));
  }

  function renderTaskPanel() {
    const root = document.getElementById('task-panel');
    if (state.selectedId === null) {
      root.innerHTML = '<div class="task-hint">Pilih agent dengan klik di canvas atau di roster untuk assign task.</div>';
      return;
    }
    const a = state.agents.find(x => x.id === state.selectedId);
    if (!a) return;
    const tasks = [
      { key: 'coding', label: 'Code' },
      { key: 'researching', label: 'Research' },
      { key: 'writing', label: 'Write' },
      { key: 'reviewing', label: 'Review' },
      { key: 'meeting', label: 'Meet' },
      { key: 'lounging', label: 'Lounge' },
      { key: 'vending', label: 'Snack' },
      { key: 'water', label: 'Water' },
      { key: 'microwave', label: 'Heat' },
      { key: 'chatting', label: 'Chat' },
      { key: 'sleeping', label: 'Sleep' },
      { key: 'idle', label: 'Idle' },
    ];
    root.innerHTML = `
      <div class="task-head">
        <div class="task-name">${a.name}</div>
        <div class="task-sub">${a.role} Â· <span data-current-status="${a.id}">${labelFor(a)}</span></div>
      </div>
      <div class="task-grid">
        ${tasks.map(t => `<button class="task-btn" data-task="${t.key}">${t.label}</button>`).join('')}
      </div>
    `;
    root.querySelectorAll('.task-btn').forEach(btn => {
      btn.addEventListener('click', () => {
        S.assignTask(a, btn.dataset.task);
        pushLog(`${a.name} â task: ${S.ACTIVITY_LABELS[btn.dataset.task] || btn.dataset.task}`);
      });
    });
  }

  // ---------- Click handling on canvas ----------
  canvas.addEventListener('click', (e) => {
    const rect = canvas.getBoundingClientRect();
    const sx = (e.clientX - rect.left) * (canvas.width / rect.width);
    const sy = (e.clientY - rect.top) * (canvas.height / rect.height);
    const tx = Math.floor(sx / M.TILE);
    const ty = Math.floor(sy / M.TILE);
    // find agent at this tile (or adjacent if walking)
    let hit = null;
    for (const a of state.agents) {
      const ax = a.tileX + a.dx, ay = a.tileY + a.dy;
      const d = Math.abs(ax - tx + 0.5) + Math.abs(ay - ty + 0.5);
      if (Math.floor(ax) === tx && Math.floor(ay) === ty) { hit = a; break; }
      if (d < 1.2 && (!hit)) hit = a;
    }
    if (hit) selectAgent(hit.id);
    else { state.selectedId = null; for (const a of state.agents) a.selected = false; renderRoster(); renderTaskPanel(); }
  });

  // ---------- Clock ----------
  function updateClock() {
    document.getElementById('clock').textContent = formatTime(state.simMinute);
    document.getElementById('phase').textContent = phaseFor(state.simMinute);
    updateRosterStatuses();
    // update task panel header status
    if (state.selectedId !== null) {
      const a = state.agents.find(x => x.id === state.selectedId);
      const el = document.querySelector(`[data-current-status="${state.selectedId}"]`);
      if (a && el) el.textContent = labelFor(a);
    }
  }

  function phaseFor(m) {
    const h = (m / 60) % 24;
    if (h < 6) return 'Night';
    if (h < 8) return 'Dawn';
    if (h < 12) return 'Morning';
    if (h < 13) return 'Lunch';
    if (h < 17) return 'Afternoon';
    if (h < 19) return 'Dusk';
    if (h < 22) return 'Evening';
    return 'Night';
  }

  // ---------- Controls ----------
  document.getElementById('btn-pause').addEventListener('click', () => {
    state.paused = !state.paused;
    document.getElementById('btn-pause').textContent = state.paused ? 'â¶ Play' : 'â¸ Pause';
  });
  document.getElementById('btn-1x').addEventListener('click', () => setSpeed(1));
  document.getElementById('btn-2x').addEventListener('click', () => setSpeed(2));
  document.getElementById('btn-4x').addEventListener('click', () => setSpeed(4));
  document.getElementById('btn-8x').addEventListener('click', () => setSpeed(8));

  function setSpeed(s) {
    state.speed = s;
    tweaks.speed = s;
    for (const el of document.querySelectorAll('.speed-btn')) el.classList.remove('active');
    const map = { 1: 'btn-1x', 2: 'btn-2x', 4: 'btn-4x', 8: 'btn-8x' };
    const el = document.getElementById(map[s]);
    if (el) el.classList.add('active');
  }
  setSpeed(state.speed);

  // ---------- Tweaks panel (host protocol) ----------
  let tweaksPanelOpen = false;
  const tweaksPanel = document.getElementById('tweaks-panel');

  window.addEventListener('message', (e) => {
    const d = e.data;
    if (!d || typeof d !== 'object') return;
    if (d.type === '__activate_edit_mode') {
      tweaksPanelOpen = true;
      tweaksPanel.style.display = 'block';
    } else if (d.type === '__deactivate_edit_mode') {
      tweaksPanelOpen = false;
      tweaksPanel.style.display = 'none';
    }
  });
  window.parent.postMessage({ type: '__edit_mode_available' }, '*');

  function persistTweak(patch) {
    window.parent.postMessage({ type: '__edit_mode_set_keys', edits: patch }, '*');
  }

  function setupTweakControls() {
    // speed slider
    const sp = document.getElementById('tw-speed');
    sp.value = tweaks.speed;
    document.getElementById('tw-speed-val').textContent = tweaks.speed + 'Ã';
    sp.addEventListener('input', () => {
      const v = Number(sp.value);
      setSpeed(v);
      tweaks.speed = v;
      document.getElementById('tw-speed-val').textContent = v + 'Ã';
      persistTweak({ speed: v });
    });

    const sb = document.getElementById('tw-bubbles');
    sb.checked = tweaks.showBubbles;
    sb.addEventListener('change', () => {
      tweaks.showBubbles = sb.checked;
      persistTweak({ showBubbles: sb.checked });
    });

    const dn = document.getElementById('tw-daynight');
    dn.checked = tweaks.dayNight;
    dn.addEventListener('change', () => {
      tweaks.dayNight = dn.checked;
      persistTweak({ dayNight: dn.checked });
    });

    const ac = document.getElementById('tw-agents');
    ac.value = tweaks.agentCount;
    document.getElementById('tw-agents-val').textContent = tweaks.agentCount;
    ac.addEventListener('input', () => {
      const v = Number(ac.value);
      tweaks.agentCount = v;
      document.getElementById('tw-agents-val').textContent = v;
      applyAgentCount(v);
      persistTweak({ agentCount: v });
    });

    const hr = document.getElementById('tw-hour');
    hr.addEventListener('input', () => {
      const v = Number(hr.value);
      state.simMinute = v * 60;
      document.getElementById('tw-hour-val').textContent = String(v).padStart(2, '0') + ':00';
    });
    hr.value = Math.floor(state.simMinute / 60);
    document.getElementById('tw-hour-val').textContent = String(hr.value).padStart(2, '0') + ':00';

    const zm = document.getElementById('tw-zoom');
    zm.value = tweaks.tileZoom;
    document.getElementById('tw-zoom-val').textContent = tweaks.tileZoom + 'Ã';
    zm.addEventListener('input', () => {
      const v = Number(zm.value);
      tweaks.tileZoom = v;
      document.getElementById('tw-zoom-val').textContent = v + 'Ã';
      applyZoom();
      persistTweak({ tileZoom: v });
    });

    document.getElementById('tw-close').addEventListener('click', () => {
      tweaksPanel.style.display = 'none';
      window.parent.postMessage({ type: '__edit_mode_dismissed' }, '*');
    });
  }

  function applyZoom() {
    // zoom multiplies the CSS-fit base by 1..3
    const z = tweaks.tileZoom;
    if (z <= 1) {
      canvas.style.width = '';
      canvas.style.height = '';
    } else {
      canvas.style.width = `calc(min(100%, calc((100vh - 96px) * 1.667)) * ${z})`;
      canvas.style.height = 'auto';
    }
  }

  setupTweakControls();
  applyZoom();
  renderRoster();
  renderTaskPanel();
  pushLog('Office opened. Agents arriving.');
})();

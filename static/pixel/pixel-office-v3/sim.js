// Agent simulation v3: 8 agents, BFS pathfinding, activity state machine.

window.OfficeSim = (function () {
  const M = window.OfficeMap;
  const COLS = M.COLS, ROWS = M.ROWS;

  // 8 agents — visual design based on reference pixel art photo
  const AGENT_DEFS = [
    // Ferry: afro, deep dark-brown skin, orange-red jacket  (ref char 3)
    { name: 'Ferry',       role: 'Researcher', shirt: '#c85428', hair: '#181010', skin: '#543020', pants: '#2a2730', hairStyle: 'afro' },
    // Linus: short brown hair, warm tan skin, white tee + dark-blue tie  (ref char 6)
    { name: 'Linus',       role: 'Coder',      shirt: '#ece8e0', hair: '#7a4a2a', skin: '#d0a070', pants: '#2a2f4a', hairStyle: 'short', tie: '#1a3a6e' },
    // Dostoyevsky: silver-white short hair, very pale skin, cream outfit  (ref char 5)
    { name: 'Dostoyevsky', role: 'Writer',     shirt: '#e4e0d8', hair: '#ccc8be', skin: '#f2ece4', pants: '#3a3a44', hairStyle: 'short' },
    // Cicero: black short hair, light-olive skin, crimson outfit  (ref char 4)
    { name: 'Cicero',      role: 'Reviewer',   shirt: '#c03838', hair: '#181010', skin: '#e8be98', pants: '#3a1f0e', hairStyle: 'short' },
    // Najwa: honey-gold bun, warm brown skin, caramel layered outfit  (ref char 2)
    { name: 'Najwa',       role: 'Researcher', shirt: '#b07840', hair: '#c08a28', skin: '#b87848', pants: '#7a4a20', hairStyle: 'bun' },
    // Alfred: short warm-brown hair, medium tan skin, deep-blue shirt  (ref char 1)
    { name: 'Alfred',      role: 'Coder',      shirt: '#3a5a8a', hair: '#8a5a3a', skin: '#d4a878', pants: '#2a2f4a', hairStyle: 'short' },
    // Da Vinci: curly amber hair, golden-olive skin, ochre shirt  (unique, artistic)
    { name: 'Da Vinci',    role: 'Writer',     shirt: '#d4a038', hair: '#a07018', skin: '#c89068', pants: '#3a1f0e', hairStyle: 'curly' },
    // Mansa: spiky black hair, warm-tan skin, cobalt blue shirt  (unique, distinguished)
    { name: 'Mansa',       role: 'Reviewer',   shirt: '#2858a0', hair: '#181010', skin: '#dcaa78', pants: '#1e1e28', hairStyle: 'spiky' },
  ];

  const ACTIVITY_LABELS = {
    working: 'Working',
    coding: 'Coding',
    researching: 'Researching',
    writing: 'Writing',
    reviewing: 'Reviewing',
    walking: 'Walking',
    chatting: 'Chatting',
    lounging: 'Lounging',
    meeting: 'Meeting',
    vending: 'Snack',
    water: 'Water',
    microwave: 'Heating',
    idle: 'Idle',
    sleeping: 'Zzz',
  };

  const ROLE_ACTIVITY = {
    Researcher: 'researching',
    Coder: 'coding',
    Writer: 'writing',
    Reviewer: 'reviewing',
  };

  function createAgents() {
    return AGENT_DEFS.map((def, i) => {
      const seat = M.stations.desks[i % M.stations.desks.length];
      return {
        id: i,
        name: def.name, role: def.role,
        shirt: def.shirt, hair: def.hair, skin: def.skin, pants: def.pants,
        hairStyle: def.hairStyle, tie: def.tie,
        homeDesk: seat,
        tileX: seat.x, tileY: seat.y,
        dx: 0, dy: 0,
        path: [],
        facing: seat.facing || 'up',
        sitting: true,
        sleeping: false,
        activity: ROLE_ACTIVITY[def.role],
        activityTimer: 8 + Math.random() * 8,
        bubbleText: null,
        bubbleTimer: 0,
        animPhase: Math.random() * 10,
        selected: false,
        forcedNext: null,
      };
    });
  }

  function bfsPath(sx, sy, tx, ty, walkable, occupied) {
    if (sx === tx && sy === ty) return [];
    const cameFrom = new Map();
    cameFrom.set(sx + ',' + sy, null);
    const q = [[sx, sy]];
    let head = 0;
    while (head < q.length) {
      const [x, y] = q[head++];
      if (x === tx && y === ty) {
        const path = [];
        let cur = x + ',' + y;
        while (cur && cur !== sx + ',' + sy) {
          const [cx, cy] = cur.split(',').map(Number);
          path.push({ x: cx, y: cy });
          cur = cameFrom.get(cur);
        }
        path.reverse();
        return path;
      }
      for (const [dx, dy] of [[1, 0], [-1, 0], [0, 1], [0, -1]]) {
        const nx = x + dx, ny = y + dy;
        const key = nx + ',' + ny;
        if (cameFrom.has(key)) continue;
        if (nx < 0 || ny < 0 || nx >= COLS || ny >= ROWS) continue;
        if (!walkable[ny][nx] && !(nx === tx && ny === ty)) continue;
        if (occupied && occupied.has(key) && !(nx === tx && ny === ty)) continue;
        cameFrom.set(key, x + ',' + y);
        q.push([nx, ny]);
      }
    }
    if (occupied && occupied.size) return bfsPath(sx, sy, tx, ty, walkable, null);
    return null;
  }

  function setPath(agent, target, agents) {
    const occupied = new Set();
    for (const o of agents) {
      if (o.id === agent.id) continue;
      occupied.add(o.tileX + ',' + o.tileY);
    }
    const path = bfsPath(agent.tileX, agent.tileY, target.x, target.y, M.walkable, occupied);
    if (path === null) return false;
    agent.path = path;
    agent.dx = 0; agent.dy = 0;
    agent.sitting = false;
    agent.sleeping = false;
    return true;
  }

  function pickActivity(agent, simMinute) {
    if (agent.forcedNext) {
      const f = agent.forcedNext;
      agent.forcedNext = null;
      return f;
    }
    const hour = (simMinute / 60) % 24;
    if (hour >= 19 || hour < 7) {
      return Math.random() < 0.85 ? 'sleeping' : 'idle';
    }
    if (hour >= 12 && hour < 13) {
      const r = Math.random();
      if (r < 0.3) return 'microwave';
      if (r < 0.55) return 'lounging';
      if (r < 0.75) return 'chatting';
      return 'water';
    }
    if ((hour >= 10 && hour < 10.5) || (hour >= 15 && hour < 15.5)) {
      return Math.random() < 0.5 ? 'meeting' : ROLE_ACTIVITY[agent.role];
    }
    const r = Math.random();
    if (r < 0.55) return ROLE_ACTIVITY[agent.role];
    if (r < 0.63) return 'water';
    if (r < 0.70) return 'vending';
    if (r < 0.77) return 'chatting';
    if (r < 0.84) return 'lounging';
    if (r < 0.92) return 'meeting';
    return 'idle';
  }

  function planActivity(agent, activity, agents) {
    let target = null;
    let facing = 'down';
    let sitting = false;
    let sleeping = false;
    let duration = 6 + Math.random() * 8;

    switch (activity) {
      case 'coding':
      case 'researching':
      case 'writing':
      case 'reviewing':
      case 'working':
        target = agent.homeDesk;
        facing = agent.homeDesk.facing || 'up';
        sitting = true;
        duration = 12 + Math.random() * 18;
        break;
      case 'vending':
        target = M.stations.vending;
        facing = 'up';
        duration = 4 + Math.random() * 3;
        break;
      case 'water':
        target = M.stations.water;
        facing = 'up';
        duration = 3 + Math.random() * 2;
        break;
      case 'microwave':
        target = M.stations.microwave;
        facing = 'up';
        duration = 5 + Math.random() * 3;
        break;
      case 'meeting':
      case 'lounging': {
        const taken = new Set(agents.filter(a => a.id !== agent.id).map(a => a.tileX + ',' + a.tileY));
        const open = M.stations.sofas.filter(s => !taken.has(s.x + ',' + s.y));
        const pick = open.length ? open[Math.floor(Math.random() * open.length)] : M.stations.sofas[0];
        target = { x: pick.x, y: pick.y };
        facing = pick.facing;
        sitting = true;
        duration = activity === 'meeting' ? 14 + Math.random() * 10 : 8 + Math.random() * 6;
        break;
      }
      case 'chatting': {
        const stools = M.stations.stools;
        const taken = new Set(agents.filter(a => a.id !== agent.id).map(a => a.tileX + ',' + a.tileY));
        const openStools = stools.filter(s => !taken.has(s.x + ',' + s.y));
        if (openStools.length) {
          const pick = openStools[Math.floor(Math.random() * openStools.length)];
          target = pick;
          sitting = true;
        } else {
          const pick = M.stations.chatSpots[Math.floor(Math.random() * M.stations.chatSpots.length)];
          target = pick;
          sitting = false;
        }
        facing = ['down', 'up', 'left', 'right'][Math.floor(Math.random() * 4)];
        duration = 5 + Math.random() * 5;
        break;
      }
      case 'sleeping':
        target = agent.homeDesk;
        facing = agent.homeDesk.facing || 'up';
        sitting = true;
        sleeping = true;
        duration = 30 + Math.random() * 30;
        break;
      case 'idle':
      default: {
        let pick = null;
        for (let i = 0; i < 30; i++) {
          const x = 1 + Math.floor(Math.random() * 17);
          const y = 1 + Math.floor(Math.random() * 16);
          if (M.walkable[y][x]) { pick = { x, y }; break; }
        }
        target = pick || agent.homeDesk;
        facing = 'down';
        duration = 5 + Math.random() * 5;
      }
    }
    return { target, facing, sitting, sleeping, duration, activity };
  }

  function setActivity(agent, plan, agents) {
    const ok = setPath(agent, plan.target, agents);
    if (!ok) return false;
    agent.pendingActivity = plan;
    if (agent.path.length === 0) arrive(agent);
    else agent.activity = 'walking';
    return true;
  }

  function arrive(agent) {
    const p = agent.pendingActivity;
    if (!p) return;
    agent.activity = p.activity;
    agent.facing = p.facing;
    agent.sitting = p.sitting;
    agent.sleeping = p.sleeping;
    agent.activityTimer = p.duration;
    agent.pendingActivity = null;
    agent.bubbleText = ACTIVITY_LABELS[p.activity] || p.activity;
    agent.bubbleTimer = 2.5;
  }

  const STEP_SEC = 0.35;

  function updateAgent(agent, dtReal, dtSim, agents, log, simMinute) {
    agent.animPhase += dtReal * 4;
    if (agent.bubbleTimer > 0) agent.bubbleTimer -= dtReal;

    if (agent.path && agent.path.length) {
      const next = agent.path[0];
      const dirX = next.x - agent.tileX;
      const dirY = next.y - agent.tileY;
      if (dirX > 0) agent.facing = 'right';
      else if (dirX < 0) agent.facing = 'left';
      else if (dirY > 0) agent.facing = 'down';
      else if (dirY < 0) agent.facing = 'up';

      const step = dtSim / STEP_SEC;
      agent.dx += step * dirX;
      agent.dy += step * dirY;
      if ((dirX > 0 && agent.dx >= 1) || (dirX < 0 && agent.dx <= -1) ||
          (dirY > 0 && agent.dy >= 1) || (dirY < 0 && agent.dy <= -1)) {
        agent.tileX = next.x; agent.tileY = next.y;
        agent.dx = 0; agent.dy = 0;
        agent.path.shift();
        if (agent.path.length === 0) {
          arrive(agent);
          if (log) log(`${agent.name} â ${ACTIVITY_LABELS[agent.activity] || agent.activity}`);
        }
      }
    } else {
      agent.activityTimer -= dtSim;
      if (agent.activityTimer <= 0) {
        const next = pickActivity(agent, simMinute);
        const plan = planActivity(agent, next, agents);
        const ok = setActivity(agent, plan, agents);
        if (!ok) agent.activityTimer = 2;
        else if (agent.path.length === 0 && log) {
          log(`${agent.name} â ${ACTIVITY_LABELS[agent.activity] || agent.activity}`);
        }
      }
    }
  }

  function assignTask(agent, key) {
    agent.forcedNext = key;
    agent.activityTimer = 0.05;
  }

  return {
    AGENT_DEFS, ACTIVITY_LABELS, ROLE_ACTIVITY,
    createAgents, updateAgent, assignTask, planActivity, setActivity,
  };
})();

/* ============================================================
   App — state, tweaks, theme, keyboard
   ============================================================ */
const { Sidebar, Masthead, ChatView, DashboardView, AgentOverview, RightPanel } = window.CLViews;
const { CommandPalette, CrewDrawer, NotifPopover } = window.CLOverlays;

// Cross-tab sync: broadcast which agent wrote data so dashboard tabs refresh
const _syncBC = typeof BroadcastChannel !== 'undefined'
  ? new BroadcastChannel('cassanoval-sync') : null;

const TWEAK_DEFAULTS = /*EDITMODE-BEGIN*/{
  "theme": "light",
  "startAgent": "task",
  "startTab": "chat",
  "useMockData": false
}/*EDITMODE-END*/;

function App() {
  const { AGENTS, AGENT_ORDER, MOCK, chatAPI, tasksAPI, notesAPI, budgetAPI } = window.CLData;

  const [tweaks, setTweaks] = React.useState(TWEAK_DEFAULTS);
  const [editMode, setEditMode] = React.useState(false);

  const [agKey, setAgKey] = React.useState(tweaks.startAgent || 'task');
  const [tab, setTab] = React.useState(tweaks.startTab || 'chat');
  const [msgs, setMsgs] = React.useState(() => Object.fromEntries(AGENT_ORDER.map(k => [k, []])));
  const [loading, setLoad] = React.useState(false);
  const [showCmd, setShowCmd] = React.useState(false);
  const [showCrew, setShowCrew] = React.useState(false);
  const [panelOpen, setPanelOpen] = React.useState(() => window.innerWidth >= 1100);
  const [dash, setDash] = React.useState({ tStats: null, tasks: [], budget: null, notes: [], notesTotal: 0, recentTx: [] });
  const [dashLoading, setDashLoading] = React.useState(true);
  const [notifs, setNotifs] = React.useState([]);
  const [notifOpen, setNotifOpen] = React.useState(false);
  const briefInjectedRef = React.useRef(false);

  /* Theme on root */
  React.useEffect(() => {
    document.body.dataset.theme = tweaks.theme;
  }, [tweaks.theme]);

  const updateTweak = React.useCallback((patch) => {
    setTweaks(t => {
      const next = { ...t, ...patch };
      try { window.parent.postMessage({ type: '__edit_mode_set_keys', edits: patch }, '*'); } catch {}
      return next;
    });
  }, []);

  const toggleTheme = React.useCallback(() => {
    updateTweak({ theme: tweaks.theme === 'dark' ? 'light' : 'dark' });
  }, [tweaks.theme, updateTweak]);

  /* Tweaks edit-mode wiring */
  React.useEffect(() => {
    const handle = (e) => {
      const d = e.data || {};
      if (d.type === '__activate_edit_mode') setEditMode(true);
      else if (d.type === '__deactivate_edit_mode') setEditMode(false);
    };
    window.addEventListener('message', handle);
    try { window.parent.postMessage({ type: '__edit_mode_available' }, '*'); } catch {}
    return () => window.removeEventListener('message', handle);
  }, []);

  /* Dashboard data */
  const loadDash = React.useCallback(() => {
    setDashLoading(true);
    if (tweaks.useMockData) {
      setDash({
        tStats: MOCK.tStats, tasks: MOCK.tasks, budget: MOCK.budget,
        notes: MOCK.notes, notesTotal: MOCK.notesTotal,
        recentTx: MOCK.budget.recent_transactions,
      });
      setDashLoading(false);
      return;
    }
    Promise.all([tasksAPI(), notesAPI(), budgetAPI()])
      .then(([t, n, b]) => {
        setDash({
          tStats: t.stats, tasks: t.tasks ?? [], budget: b,
          notes: n.notes ?? [], notesTotal: n.total ?? 0,
          recentTx: b?.recent_transactions ?? [],
        });
        setDashLoading(false);
      }).catch(() => {
        setDash({
          tStats: MOCK.tStats, tasks: MOCK.tasks, budget: MOCK.budget,
          notes: MOCK.notes, notesTotal: MOCK.notesTotal,
          recentTx: MOCK.budget.recent_transactions,
        });
        setDashLoading(false);
      });
  }, [tweaks.useMockData]);

  React.useEffect(() => { loadDash(); }, [loadDash]);

  // 30-second polling to keep dashboard fresh
  React.useEffect(() => {
    const id = setInterval(loadDash, 30000);
    return () => clearInterval(id);
  }, [loadDash]);

  /* BroadcastChannel — refresh hub sidebar when another tab's chat writes data */
  React.useEffect(() => {
    if (!_syncBC) return;
    const h = () => loadDash();
    _syncBC.addEventListener('message', h);
    return () => _syncBC.removeEventListener('message', h);
  }, [loadDash]);

  /* Notification bell — poll every 5 minutes */
  const loadNotifs = React.useCallback(async () => {
    try {
      const r = await fetch('/api/alfred/notifications');
      const data = await r.json();
      setNotifs(data.notifications || []);
    } catch (_) {}
  }, []);

  React.useEffect(() => {
    loadNotifs();
    const id = setInterval(loadNotifs, 5 * 60 * 1000);
    return () => clearInterval(id);
  }, [loadNotifs]);

  /* Auto-inject morning brief when Alfred's chat is first opened today */
  React.useEffect(() => {
    if (agKey !== 'task' || tweaks.useMockData) return;
    const today = new Date().toISOString().slice(0, 10);
    const stored = localStorage.getItem('alfred_brief_date');
    if (stored === today || briefInjectedRef.current) return;
    briefInjectedRef.current = true;
    fetch('/api/alfred/brief/today')
      .then(r => r.json())
      .then(data => {
        if (data.brief) {
          setMsgs(p => ({
            ...p,
            task: [{ role: 'assistant', content: data.brief, ts: new Date().toISOString() }, ...p.task],
          }));
          localStorage.setItem('alfred_brief_date', today);
          loadNotifs();
        }
      })
      .catch(() => {});
  }, [agKey, tweaks.useMockData, loadNotifs]);

  /* Keyboard shortcuts */
  React.useEffect(() => {
    const h = e => {
      if ((e.ctrlKey || e.metaKey) && e.key === 'k') { e.preventDefault(); setShowCmd(p => !p); }
      if (e.key === 'Escape') { setShowCmd(false); setShowCrew(false); }
    };
    window.addEventListener('keydown', h);
    return () => window.removeEventListener('keydown', h);
  }, []);

  const send = React.useCallback(async text => {
    const ts = new Date().toISOString();
    setMsgs(p => ({ ...p, [agKey]: [...p[agKey], { role: 'user', content: text, ts }] }));
    setLoad(true);
    try {
      if (tweaks.useMockData) {
        await new Promise(r => setTimeout(r, 900 + Math.random()*800));
        const reply = mockReply(agKey, text);
        setMsgs(p => ({ ...p, [agKey]: [...p[agKey], { role: 'assistant', content: reply, ts: new Date().toISOString() }] }));
      } else {
        const r = await chatAPI(text, agKey);
        setMsgs(p => ({ ...p, [agKey]: [...p[agKey], { role: 'assistant', content: r.response, ts: new Date().toISOString() }] }));
        // Notify other open tabs (finance, fitness dashboards) that data changed
        if (_syncBC) _syncBC.postMessage({ agent: agKey, ts: Date.now() });
      }
    } catch (e) {
      setMsgs(p => ({ ...p, [agKey]: [...p[agKey], {
        role: 'assistant',
        content: `*The wire is quiet.* Backend unreachable — ensure the service is running on localhost:8000. (${e.message})`,
        ts: new Date().toISOString()
      }] }));
    }
    setLoad(false);
    if (!tweaks.useMockData) loadDash();
  }, [agKey, loadDash, tweaks.useMockData]);

  const switchAgent = k => { setAgKey(k); setTab('chat'); };

  /* Bell click — open popover */
  const handleBellClick = () => setNotifOpen(p => !p);

  const handleMarkAllRead = () => {
    fetch('/api/alfred/notifications/read', { method: 'POST' })
      .then(() => loadNotifs())
      .catch(() => {});
  };

  const unreadCount = notifs.filter(n => !n.read).length;

  return (
    <div className={`app ${panelOpen ? 'panel-open' : ''}`}>
      <Sidebar
        active={agKey} setActive={switchAgent}
        onCmd={() => setShowCmd(true)} onCrew={() => setShowCrew(true)}
        theme={tweaks.theme} toggleTheme={toggleTheme}/>
      <main className="main">
        <Masthead
          agKey={agKey} tab={tab} setTab={setTab}
          panelOpen={panelOpen} setPanelOpen={setPanelOpen}
          notifCount={unreadCount} onBellClick={handleBellClick}/>
        {tab === 'chat'
          ? <ChatView agKey={agKey} messages={msgs[agKey]} loading={loading} onSend={send}/>
          : tab === 'overview'
            ? <AgentOverview agKey={agKey}/>
            : <DashboardView dash={dash} setAgent={switchAgent} loading={dashLoading}/>}
      </main>
      <RightPanel agKey={agKey} dash={dash} panelOpen={panelOpen}/>

      {showCmd && <CommandPalette
        onClose={() => setShowCmd(false)}
        setAgent={switchAgent} setTab={setTab}
        theme={tweaks.theme} toggleTheme={toggleTheme}/>}
      {showCrew && <CrewDrawer onClose={() => setShowCrew(false)}/>}
      {notifOpen && <NotifPopover
        notifs={notifs}
        onClose={() => setNotifOpen(false)}
        onMarkRead={handleMarkAllRead}
        onOpenAlfred={() => switchAgent('task')}/>}

      {editMode && <TweakPanel tweaks={tweaks} update={updateTweak} onClose={() => setEditMode(false)}/>}
    </div>
  );
}

/* ── Mock reply generator ────────────────────────────────── */
function mockReply(agKey, text) {
  const { AGENTS } = window.CLData;
  const ag = AGENTS[agKey];
  const first = ag.name.split(' ')[0];
  const lower = text.toLowerCase();

  if (agKey === 'task') {
    if (lower.includes('add')) return `Marked. **"${text.replace(/add\s*(a\s*)?task:?\s*/i,'')}"** is now in your queue — filed under *today*, priority *medium* unless you say otherwise.`;
    if (lower.includes('list') || lower.includes('pending')) return `You have **7 pending** — two marked *high priority*:\n\n- Draft the Q2 research memo\n- Reply to scheduling request\n\nShall I read the rest?`;
    return `Noted. I'll take it as a task and keep it close at hand. Say the word when you want it complete.`;
  }
  if (agKey === 'coding') {
    return `Looking at this — likely a scope issue. Try:\n\n\`\`\`js\nconst items = arr.filter(x => x.active)\n  .map(x => ({ ...x, ready: true }));\n\`\`\`\n\nIf that still fails, paste the stack trace. Talk is cheap.`;
  }
  if (agKey === 'schedule') {
    return `You have **3 items** today: a design review at 10:00, lunch with J. at 12:30, and a standing call at 15:00. Shall I hold the 16:00 slot for deep work?`;
  }
  if (agKey === 'budget') {
    return `Logged. The ledger reflects **Rp ${Math.round(Math.random()*200)+50}K** against *Food*. Your balance holds at Rp 18.4M — well within the month's bounds.`;
  }
  if (agKey === 'fitness') {
    return `Recorded — 45 minutes, moderate intensity, ~420 kcal. You're on pace for your weekly target. Recovery looks good; sleep data from last night was sufficient.`;
  }
  if (agKey === 'journal') {
    return `*Noted. No edits, no corrections.*\n\nThe page is kept. Would you like me to surface a related entry from last month, or leave this one to breathe?`;
  }
  if (agKey === 'davinci') {
    return `An oblique angle: what if the constraint you're naming is the feature? Let's sketch three versions where the limitation becomes the method. I'll draft them.`;
  }
  return `Noted.`;
}

/* ── Tweak panel ─────────────────────────────────────────── */
function TweakPanel({ tweaks, update, onClose }) {
  const { AGENTS, AGENT_ORDER } = window.CLData;
  const { IcoX } = window.Icons;
  return (
    <div style={{
      position:'fixed', right:24, bottom:24, zIndex:200,
      width:280, background:'var(--surface-2)', border:'1px solid var(--rule)',
      borderRadius:16, padding:18, boxShadow:'var(--shadow-3)',
      fontFamily:'Inter, sans-serif', fontSize:13, color:'var(--ink)',
    }}>
      <div style={{display:'flex', justifyContent:'space-between', alignItems:'baseline', marginBottom:14}}>
        <div style={{fontFamily:"'Instrument Serif', serif", fontSize:24, letterSpacing:'-0.02em'}}>
          Tweaks
        </div>
        <button onClick={onClose}
          style={{background:'transparent', border:'none', color:'var(--ink-3)', cursor:'pointer'}}>
          <IcoX/>
        </button>
      </div>

      <div style={{marginBottom:14}}>
        <div className="small-caps" style={{color:'var(--ink-3)', marginBottom:6}}>Theme</div>
        <div style={{display:'flex', gap:6}}>
          {['light','dark'].map(t => (
            <button key={t} onClick={() => update({ theme: t })}
              style={{
                flex:1, padding:'8px 10px', border:'1px solid var(--rule)',
                borderRadius:8, background: tweaks.theme===t ? 'var(--ink)':'transparent',
                color: tweaks.theme===t ? 'var(--paper)':'var(--ink)',
                cursor:'pointer', fontSize:12, textTransform:'capitalize',
              }}>{t}</button>
          ))}
        </div>
      </div>

      <div style={{marginBottom:14}}>
        <div className="small-caps" style={{color:'var(--ink-3)', marginBottom:6}}>Starting Agent</div>
        <select value={tweaks.startAgent}
          onChange={e => update({ startAgent: e.target.value })}
          style={{
            width:'100%', padding:'8px 10px', border:'1px solid var(--rule)',
            borderRadius:8, background:'var(--surface)', color:'var(--ink)', fontSize:12,
          }}>
          {AGENT_ORDER.map(k => <option key={k} value={k}>{AGENTS[k].name} — {AGENTS[k].sub}</option>)}
        </select>
      </div>

      <div>
        <div className="small-caps" style={{color:'var(--ink-3)', marginBottom:6}}>Data Source</div>
        <div style={{display:'flex', gap:6}}>
          {[{k:true,l:'Demo data'},{k:false,l:'Live API'}].map(o => (
            <button key={o.l} onClick={() => update({ useMockData: o.k })}
              style={{
                flex:1, padding:'8px 10px', border:'1px solid var(--rule)',
                borderRadius:8, background: tweaks.useMockData===o.k ? 'var(--ink)':'transparent',
                color: tweaks.useMockData===o.k ? 'var(--paper)':'var(--ink)',
                cursor:'pointer', fontSize:12,
              }}>{o.l}</button>
          ))}
        </div>
      </div>
    </div>
  );
}

ReactDOM.createRoot(document.getElementById('root')).render(<App/>);

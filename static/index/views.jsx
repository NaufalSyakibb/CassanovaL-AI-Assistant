/* ============================================================
   Views — Sidebar, Masthead, Chat, Dashboard, RightPanel
   ============================================================ */
const { useState: _useState, useEffect: _useEffect, useRef: _useRef, useCallback: _useCallback, useMemo: _useMemo } = React;

/* ── Sidebar ──────────────────────────────────────────────── */
function Sidebar({ active, setActive, onCmd, onCrew, theme, toggleTheme }) {
  const { AGENTS, AGENT_ORDER, AGENT_CLUSTERS, CLUSTER_ORDER } = window.CLData;
  const { IcoCmd, IcoUsers, IcoSun, IcoMoon, IcoCandlestick, IcoPixel } = window.Icons;
  const [cluster, setCluster] = _useState('all');

  const filteredKeys = cluster === 'all'
    ? AGENT_ORDER
    : AGENT_ORDER.filter(k => AGENTS[k].cluster === cluster);

  return (
    <aside className="sidebar">
      <div className="brand">
        <div className="brand-mark">Cassanova<em>L</em></div>
      </div>
      <div className="cluster-tabs">
        {CLUSTER_ORDER.map(c => (
          <button
            key={c}
            className={`cluster-tab ${cluster === c ? 'active' : ''}`}
            style={{ '--cluster-accent': AGENT_CLUSTERS[c].accent }}
            onClick={() => setCluster(c)}
            title={AGENT_CLUSTERS[c].label}
          >
            {AGENT_CLUSTERS[c].label}
          </button>
        ))}
      </div>
      <div className="roster-heading">
        <div className="small-caps">
          {cluster === 'all' ? 'The Roster' : AGENT_CLUSTERS[cluster].label}
        </div>
        <div className="roster-count">{filteredKeys.length}</div>
      </div>
      <div className="roster scroll">
        {filteredKeys.length > 0 ? filteredKeys.map((k, i) => {
          const ag = AGENTS[k];
          const isAct = active === k;
          const isExternal = !!ag.url;
          const inner = (
            <>
              <span className="roster-num">{String(i+1).padStart(2,'0')}</span>
              <div className="roster-body">
                <div className="roster-name">
                  {ag.name.split(' ')[0]}<em>{ag.name.includes(' ') ? ' ' + ag.name.split(' ').slice(1).join(' ') : ''}</em>
                </div>
                <div className="roster-role">{ag.sub}</div>
              </div>
              {isExternal ? <span className="roster-ext-arrow">↗</span> : <span className="roster-dot"/>}
            </>
          );
          return isExternal ? (
            <a key={k} href={ag.url}
              className={`roster-row roster-row-external`}
              style={{ '--agent-hue': ag.hue }}>
              {inner}
            </a>
          ) : (
            <button key={k}
              className={`roster-row ${isAct ? 'active' : ''}`}
              style={{ '--agent-hue': ag.hue }}
              onClick={() => setActive(k)}>
              {inner}
            </button>
          );
        }) : (
          <div className="roster-empty">
            <div className="roster-empty-label">No agents yet</div>
            {cluster === 'trading' && (
              <a className="roster-empty-link" href="/stock" target="_blank" rel="noopener noreferrer">
                Open Stock Terminal →
              </a>
            )}
          </div>
        )}
      </div>
      <a className="terminal-nav-btn" href="/stock">
        <IcoCandlestick/>
        <span className="terminal-nav-label">Stock Terminal</span>
        <span className="terminal-nav-arrow">→</span>
      </a>

      <a className="pixel-nav-btn" href="/pixel">
        <IcoPixel/>
        <span className="pixel-nav-label">Pixel Mode</span>
        <span className="pixel-nav-arrow">→</span>
      </a>

      <a className="pixel-nav-btn" href="/wrap" style={{background:'linear-gradient(90deg,rgba(107,94,138,.15),rgba(166,138,62,.15))'}}>
        <span style={{fontSize:'13px'}}>✦</span>
        <span className="pixel-nav-label">Monthly Wrap</span>
        <span className="pixel-nav-arrow">→</span>
      </a>

      <div className="sidebar-footer">
        <button className="side-btn" onClick={onCmd} title="Command Palette (⌘K)"><IcoCmd/></button>
        <button className="side-btn" onClick={onCrew} title="Crew Mode"><IcoUsers/></button>
        <button className="side-btn" onClick={toggleTheme} title="Toggle theme">
          {theme === 'dark' ? <IcoSun/> : <IcoMoon/>}
        </button>
        <div className="side-btn me" title="Naufal">N</div>
      </div>
    </aside>
  );
}

/* ── Masthead ─────────────────────────────────────────────── */
function Masthead({ agKey, tab, setTab, panelOpen, setPanelOpen, notifCount = 0, onBellClick }) {
  const { AGENTS, fmtIssue, fmtLongDate } = window.CLData;
  const { IcoPanelClose, IcoPanelOpen, IcoBell } = window.Icons;
  const ag = AGENTS[agKey];
  const [first, ...rest] = ag.name.split(' ');
  return (
    <>
      <header className="masthead" style={{ '--agent-hue': ag.hue }}>
        <div className="masthead-left">
          <div className="masthead-eyebrow">
            <span className="small-caps">{ag.issue}</span>
            <span className="masthead-sep"/>
            <span className="small-caps">{ag.sub}</span>
          </div>
          <h1 className="masthead-title">
            {first}<em>{rest.length ? ' ' + rest.join(' ') : ''}</em>
          </h1>
        </div>
        <div className="masthead-center">
          <nav className="tab-rail">
            <button className={`tab ${tab==='chat'?'active':''}`} onClick={()=>setTab('chat')}>Dialogue</button>
            <button className={`tab ${tab==='overview'?'active':''}`} onClick={()=>setTab('overview')}>Overview</button>
            <button className={`tab ${tab==='ledger'?'active':''}`} onClick={()=>setTab('ledger')}>Ledger</button>
          </nav>
        </div>
        <div className="masthead-right">
          <button className="mast-btn mast-bell" onClick={onBellClick}
            title={notifCount > 0 ? `${notifCount} unread brief` : 'Morning Brief'}>
            <IcoBell/>
            {notifCount > 0 && <span className="notif-badge">{notifCount}</span>}
          </button>
          <button className="mast-btn" onClick={()=>setPanelOpen(p=>!p)}
            title={panelOpen ? 'Close panel' : 'Open panel'}>
            {panelOpen ? <IcoPanelClose/> : <IcoPanelOpen/>}
          </button>
        </div>
      </header>
      <div className="date-strip small-caps" style={{ '--agent-hue': ag.hue }}>
        <div className="date-strip-left">
          <span><span className="status-dot"/>Online · In session</span>
          <span>{fmtIssue()}</span>
        </div>
        <div className="date-strip-right">
          <span>{fmtLongDate()}</span>
          <span>⌘K to search</span>
        </div>
      </div>
    </>
  );
}

/* ── Chat View ────────────────────────────────────────────── */
function ChatView({ agKey, messages, loading, onSend }) {
  const { AGENTS, CHIPS, renderMd, fmtTime, fmtIssue, MOCK } = window.CLData;
  const { IcoSend, IcoClip, IcoPlus, IcoReceipt, IcoMic, IcoMicOff } = window.Icons;
  const ag = AGENTS[agKey];
  const [val, setVal] = _useState('');
  const [listening, setListening] = _useState(false);
  const [voiceSupported] = _useState(() => !!(window.SpeechRecognition || window.webkitSpeechRecognition));
  const endRef = _useRef(null);
  const taRef = _useRef(null);
  const recRef = _useRef(null);
  const srRef = _useRef(null);

  _useEffect(() => { endRef.current?.scrollIntoView({ behavior: 'smooth' }); }, [messages, loading]);

  const send = _useCallback(() => {
    const t = val.trim(); if (!t || loading) return;
    setVal(''); if (taRef.current) taRef.current.style.height = 'auto';
    onSend(t);
  }, [val, loading, onSend]);

  const onKey = e => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); send(); } };
  const onInput = e => {
    setVal(e.target.value);
    e.target.style.height = 'auto';
    e.target.style.height = Math.min(e.target.scrollHeight, 180) + 'px';
  };

  const startVoice = () => {
    const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
    const r = new SR();
    r.lang = 'id-ID';
    r.interimResults = false;
    r.maxAlternatives = 1;
    r.onresult = e => {
      const transcript = e.results[0][0].transcript;
      setListening(false);
      if (transcript.trim()) onSend(transcript);
    };
    r.onerror = () => setListening(false);
    r.onend   = () => setListening(false);
    r.start();
    srRef.current = r;
    setListening(true);
  };

  const stopVoice = () => { srRef.current?.stop(); setListening(false); };

  const firstName = ag.name.split(' ')[0];
  const lastName  = ag.name.split(' ').slice(1).join(' ');

  return (
    <div className="chat" style={{ '--agent-hue': ag.hue }}>
      <div className="chat-scroll scroll">
        {messages.length === 0 && (
          <div className="cover">
            <div className="cover-meta">
              <span className="small-caps cover-issue">{ag.issue} — {ag.sub}</span>
              <span className="small-caps">{fmtIssue()}</span>
            </div>
            <h2 className="cover-title">
              {firstName}{lastName ? <><br/><em>{lastName}</em></> : null}
            </h2>
            <p className="cover-tagline">{ag.tagline}</p>
            <div className="cover-body">
              <div className="cover-greeting">{ag.greeting}</div>
              <div className="cover-side">
                <div className="cover-side-card">
                  <div className="cover-side-label small-caps">Suggested openings</div>
                  <ul className="cover-side-list">
                    {(CHIPS[agKey]||[]).map((c, i) => (
                      <li key={i} onClick={()=>onSend(c)} style={{cursor:'pointer'}}>
                        <span>{c}</span>
                        <span className="mono" style={{color:'var(--ink-4)'}}>→</span>
                      </li>
                    ))}
                  </ul>
                </div>
                <div className="cover-side-card">
                  <div className="cover-side-label small-caps">Session</div>
                  <ul className="cover-side-list">
                    <li><span>Agent</span><span className="mono">{ag.name}</span></li>
                    <li><span>Status</span><span className="mono" style={{color:ag.hue}}>● Online</span></li>
                    <li><span>Model</span><span className="mono">mistral-large</span></li>
                  </ul>
                </div>
              </div>
            </div>
          </div>
        )}

        {messages.length > 0 && (
          <div className="chat-col">
            {messages.map((m, i) => {
              const isUser = m.role === 'user';
              return (
                <article key={i} className={`msg ${isUser ? 'user' : 'agent'}`}>
                  <div className="msg-head">
                    <span className="msg-author">
                      {isUser ? 'You' : <>{firstName}<em>{lastName ? ' '+lastName : ''}</em></>}
                    </span>
                    <span className="msg-role">{isUser ? 'Correspondent' : ag.sub}</span>
                    <span className="msg-time">{m.ts ? fmtTime(m.ts) : ''}</span>
                  </div>
                  <div className="msg-body" dangerouslySetInnerHTML={{ __html: `<p>${renderMd(m.content)}</p>` }}/>
                </article>
              );
            })}
            {loading && (
              <div className="typing">
                <div className="typing-dots">
                  <div className="typing-dot"/><div className="typing-dot"/><div className="typing-dot"/>
                </div>
                <span className="serif" style={{fontStyle:'italic',fontSize:'15px'}}>
                  {firstName} is composing a reply…
                </span>
              </div>
            )}
            <div ref={endRef}/>
          </div>
        )}
      </div>

      <div className="composer-shell">
        <div className="composer">
          <div className="prompt-row">
            {(CHIPS[agKey]||[]).map((c, i) => (
              <button key={i} className="prompt-chip" onClick={()=>onSend(c)}>
                <span className="mono">/{String(i+1)}</span>{c}
              </button>
            ))}
          </div>
          <div className="composer-box">
            {agKey === 'budget' && (
              <>
                <button className="composer-btn" title="Scan receipt"
                  onClick={()=>recRef.current?.click()}><IcoReceipt size={18}/></button>
                <input ref={recRef} type="file" accept="image/*" style={{display:'none'}}
                  onChange={e => { if (e.target.files[0]) onSend(`[RECEIPT:${e.target.files[0].name}]`); }}/>
              </>
            )}
            {agKey !== 'budget' && (
              <button className="composer-btn" title="Attach"><IcoClip size={17}/></button>
            )}
            <textarea ref={taRef} className="composer-input" rows="1"
              placeholder={`Write to ${firstName}…`}
              value={val} onChange={onInput} onKeyDown={onKey}/>
            {voiceSupported && (
              <button className={`composer-btn mic-btn${listening ? ' listening' : ''}`}
                onClick={listening ? stopVoice : startVoice}
                title={listening ? 'Stop listening' : 'Voice input (id-ID)'}
                type="button">
                {listening ? <IcoMicOff size={15}/> : <IcoMic size={15}/>}
              </button>
            )}
            <button className="composer-btn composer-send"
              onClick={send} disabled={!val.trim() || loading}>
              {loading ? <span className="spinner"/> : <IcoSend size={15}/>}
            </button>
          </div>
          <div className="composer-hint small-caps">
            Enter to send · Shift + Enter for a new line
          </div>
        </div>
      </div>
    </div>
  );
}

/* ── Dashboard View ───────────────────────────────────────── */
function DashboardView({ dash, setAgent, loading }) {
  const { AGENTS, AGENT_ORDER, fmtMoney, fmtDate, fmtIssue, fmtLongDate, patternsAPI, contradictionsAPI } = window.CLData;
  const { tStats, budget, notesTotal, notes = [], recentTx = [] } = dash;
  const [patterns, setPatterns] = _useState(null);
  const [conflicts, setConflicts] = _useState(null);

  _useEffect(() => {
    Promise.all([
      patternsAPI().catch(() => null),
      contradictionsAPI().catch(() => null),
    ]).then(([p, c]) => {
      setPatterns(p);
      setConflicts(Array.isArray(c) ? c : (c?.conflicts ?? c?.contradictions ?? []));
    });
  }, []);

  // Fake sparkline values
  const spark = (seed) => Array.from({length:12}, (_,i) => 0.3 + 0.7*Math.abs(Math.sin(i*1.3 + seed)));

  if (loading) return (
    <div className="dashboard scroll">
      <div className="dash-container">
        <div className="dash-hero">
          <div>
            <span className="skeleton skeleton-label"/>
            <span className="skeleton skeleton-hero" style={{marginTop:12,width:320,height:48}}/>
            <span className="skeleton skeleton-sub" style={{marginTop:14,width:'60%',height:13}}/>
          </div>
        </div>
        <div className="stats-row">
          {[1,2,3,4].map(i => (
            <div key={i} className="stat">
              <span className="skeleton skeleton-label"/>
              <span className="skeleton skeleton-hero"/>
              <span className="skeleton skeleton-sub"/>
            </div>
          ))}
        </div>
        <div className="dash-grid">
          <div className="dash-col">
            <div className="dash-section">
              <span className="skeleton skeleton-label" style={{width:160,marginBottom:14}}/>
              {[1,2,3,4].map(i => <span key={i} className="skeleton skeleton-card" style={{display:'block',marginBottom:8}}/>)}
            </div>
          </div>
          <div className="dash-col">
            <div className="dash-section">
              <span className="skeleton skeleton-label" style={{width:120,marginBottom:14}}/>
              {[1,2,3,4].map(i => <span key={i} className="skeleton" style={{display:'block',height:44,marginBottom:6}}/>)}
            </div>
          </div>
        </div>
      </div>
    </div>
  );

  return (
    <div className="dashboard scroll">
      <div className="dash-container">
        <div className="dash-hero">
          <div>
            <div className="dash-eyebrow small-caps">The Daily Ledger · {fmtLongDate()}</div>
            <h1 className="dash-title">Welcome back,<br/><em>Cassanova.</em></h1>
            <p className="dash-subtitle">
              {AGENT_ORDER.length} agents stand ready. The ledger balances. A quiet day, should you wish to keep it so.
            </p>
          </div>
          <div className="dash-meta">
            <div className="small-caps" style={{marginBottom:6}}>Issue</div>
            <div className="dash-meta-big">{fmtIssue().split('·')[1].trim()}</div>
            <div className="small-caps" style={{marginTop:8}}>{fmtIssue().split('·')[0].trim()}</div>
          </div>
        </div>

        <div className="stats-row">
          {[
            { label:'Tasks Pending', val: tStats?.pending ?? 0, sub:`${tStats?.high_priority ?? 0} marked high priority`, hue:'var(--hue-alfred)', seed:1 },
            { label:'Balance',       val: `Rp ${fmtMoney(budget?.balance)}`, sub:`Rp ${fmtMoney(budget?.monthly_expense)} spent this month`, hue:'var(--hue-mansa)', seed:2, unit:'' },
            { label:'Notes',         val: notesTotal ?? 0, sub:'Entries in the knowledge base', hue:'var(--hue-cicero)', seed:3 },
            { label:'Monthly Income',val: `Rp ${fmtMoney(budget?.monthly_income)}`, sub:'Through today', hue:'var(--hue-miyamoto)', seed:4 },
          ].map((s, i) => (
            <div key={i} className="stat" style={{'--agent-hue': s.hue}}>
              <div className="stat-label small-caps">{String(i+1).padStart(2,'0')} · {s.label}</div>
              <div className="stat-value">
                {typeof s.val === 'string' && s.val.startsWith('Rp')
                  ? <><span className="unit">Rp</span>{s.val.replace('Rp ','')}</>
                  : s.val}
              </div>
              <div className="stat-sub">{s.sub}</div>
              <div className="stat-spark">
                {spark(s.seed).map((v,j) => (
                  <div key={j} className="stat-spark-bar" style={{height:`${v*22}px`, opacity: 0.25 + v*0.55}}/>
                ))}
              </div>
            </div>
          ))}
        </div>

        <div className="dash-grid">
          <div className="dash-col">
            <div className="dash-section">
              <div className="dash-kicker small-caps">§ Recent Transactions</div>
              <h3>The <em>ledger</em>, lately.</h3>
              <div className="txn-list" style={{marginTop:16}}>
                {(recentTx.length ? recentTx : []).map((tx, i) => (
                  <div key={i} className="txn">
                    <div className="txn-date">{fmtDate(tx.date).toUpperCase()}</div>
                    <div>
                      <div className="txn-desc">{tx.description}</div>
                      <div className="txn-cat small-caps" style={{marginTop:3}}>{tx.category}</div>
                    </div>
                    <div className={`txn-amt ${tx.type==='income'?'pos':'neg'}`}>
                      {tx.type === 'income' ? '+' : '−'} Rp {fmtMoney(tx.amount)}
                    </div>
                    <div style={{width:4,height:4,borderRadius:'50%',background:tx.type==='income'?'var(--hue-miyamoto)':'var(--hue-lavoiser)',alignSelf:'center'}}/>
                  </div>
                ))}
                {recentTx.length === 0 && (
                  <div style={{padding:'18px 0', color:'var(--ink-3)', fontStyle:'italic', fontFamily:"'Instrument Serif', serif", fontSize:17}}>
                    The ledger is quiet today.
                  </div>
                )}
              </div>
            </div>
          </div>

          <div className="dash-col">
            <div className="dash-section">
              <div className="dash-kicker small-caps">§ The Roster</div>
              <h3>Agents <em>in residence.</em></h3>
              <div className="agent-index" style={{marginTop:16}}>
                {AGENT_ORDER.map((k, i) => {
                  const ag = AGENTS[k];
                  const first = ag.name.split(' ')[0];
                  const rest = ag.name.split(' ').slice(1).join(' ');
                  return (
                    <div key={k} className="agent-index-row"
                      style={{'--agent-hue': ag.hue}}
                      onClick={() => setAgent(k)}>
                      <span className="agent-index-num">{String(i+1).padStart(2,'0')}</span>
                      <span className="agent-index-name">
                        {first}<em>{rest ? ' '+rest : ''}</em>
                      </span>
                      <span className="agent-index-role">{ag.sub}</span>
                    </div>
                  );
                })}
              </div>
            </div>

            <div className="dash-section">
              <div className="dash-kicker small-caps">§ Recent Pages</div>
              <h3>From the <em>notebook.</em></h3>
              <div style={{marginTop:16, borderTop:'1px solid var(--rule)'}}>
                {notes.slice(0,4).map((n, i) => (
                  <div key={i} className="txn" style={{gridTemplateColumns:'54px 1fr auto'}}>
                    <div className="txn-date">{fmtDate(n.updated_at).toUpperCase()}</div>
                    <div className="txn-desc">{n.title}</div>
                    <div className="small-caps" style={{color:'var(--ink-4)'}}>Notes</div>
                  </div>
                ))}
                {notes.length === 0 && (
                  <div style={{padding:'18px 0', color:'var(--ink-3)', fontStyle:'italic', fontFamily:"'Instrument Serif', serif", fontSize:17}}>
                    No entries yet. A blank page invites.
                  </div>
                )}
              </div>
            </div>
          </div>
        </div>

        {/* Life Insights — patterns + contradictions */}
        {(conflicts !== null || patterns !== null) && (
          (() => {
            const conflictList = conflicts || [];
            const patternInsights = patterns?.insights || [];
            const hasContent = conflictList.length > 0 || (patternInsights.length > 0 && !patternInsights[0].toLowerCase().includes('not enough'));
            const notEnough = patternInsights.length > 0 && patternInsights[0].toLowerCase().includes('not enough');
            if (!hasContent && !notEnough) return null;
            return (
              <div className="insights-section">
                <div className="dash-kicker small-caps insights-kicker">§ Life Insights</div>
                <h3 style={{fontFamily:"'Instrument Serif', serif", fontSize:28, letterSpacing:'-0.02em', fontWeight:400, margin:'0 0 4px'}}>
                  Patterns & <em>conflicts.</em>
                </h3>
                <div className="insights-grid">
                  {conflictList.map((c, i) => (
                    <div key={i} className="conflict-card">⚠ {c}</div>
                  ))}
                  {hasContent && patternInsights.map((p, i) => (
                    <div key={i} className="insight-card">→ {p}</div>
                  ))}
                  {notEnough && conflictList.length === 0 && (
                    <div className="insights-empty">{patternInsights[0]}</div>
                  )}
                </div>
              </div>
            );
          })()
        )}
      </div>
    </div>
  );
}


/* ── Intelligence Dashboard (inside Alfred Overview) ─────── */
function IntelAgentCard({ agent }) {
  const { KEEP: k, DISCARD: d, INCONCLUSIVE: i, total } = agent.experiments;
  const dot = total === 0         ? 'grey'
            : k / total >= 0.6   ? 'green'
            : d / total >= 0.6   ? 'red'
            : 'yellow';
  const name = agent.folder.replace(' Agent', '').replace('TaskCore', 'Alfred');
  const hyp  = agent.hypothesis
    ? (agent.hypothesis.length > 95 ? agent.hypothesis.slice(0, 95) + '…' : agent.hypothesis)
    : 'No experiments yet.';
  return (
    <div className="intel-agent-card">
      <div className="intel-agent-head">
        <span className={`intel-dot intel-dot--${dot}`} />
        <span className="intel-agent-name">{name}</span>
      </div>
      <p className="intel-agent-hypothesis">{hyp}</p>
      <div className="intel-agent-pills">
        <span className="intel-pill intel-pill--k">{k}K</span>
        <span className="intel-pill intel-pill--d">{d}D</span>
        <span className="intel-pill intel-pill--i">{i}I</span>
      </div>
    </div>
  );
}

function IntelligenceDashboard() {
  const { intelligenceAPI, refreshIntelligenceAPI, renderMd, fmtDate } = window.CLData;
  const { IcoRefresh } = window.Icons;
  const [intel,    setIntel]    = _useState(null);
  const [loading,  setLoading]  = _useState(true);
  const [spinning, setSpinning] = _useState(false);
  const [expanded, setExpanded] = _useState(false);

  _useEffect(() => {
    intelligenceAPI()
      .then(setIntel)
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  const handleRefresh = async () => {
    setSpinning(true);
    await refreshIntelligenceAPI();
    const prev = intel?.generated_at;
    for (let i = 0; i < 10; i++) {
      await new Promise(r => setTimeout(r, 3000));
      try {
        const fresh = await intelligenceAPI();
        if (fresh.generated_at !== prev) { setIntel(fresh); break; }
      } catch {}
    }
    setSpinning(false);
  };

  return (
    <div className="intel-section">
      <div className="intel-header">
        <span className="intel-header-label">CassanovaL Intelligence</span>
        {intel?.generated_at && (
          <span className="intel-date">Last analyzed: {fmtDate(intel.generated_at)}</span>
        )}
        <button className={`intel-refresh-btn${spinning ? ' spinning' : ''}`}
          onClick={handleRefresh} disabled={spinning} type="button">
          <IcoRefresh size={12} />
          {spinning ? 'Generating…' : 'Refresh'}
        </button>
      </div>
      {loading && (
        <div>
          <div className="skeleton skeleton-line" style={{width:'90%', marginBottom:10}}/>
          <div className="skeleton skeleton-line" style={{width:'75%', marginBottom:10}}/>
          <div className="skeleton skeleton-line" style={{width:'85%'}}/>
        </div>
      )}
      {!loading && intel?.synthesis && (
        <div className="intel-synthesis"
          dangerouslySetInnerHTML={{ __html: renderMd(intel.synthesis) }} />
      )}
      {!loading && !intel?.synthesis && (
        <p className="intel-no-data">
          No synthesis yet. Click Refresh or wait for Sunday's auto-run.
        </p>
      )}
      {!loading && intel?.agents?.length > 0 && (
        <>
          <div className="intel-agents-toggle" onClick={() => setExpanded(e => !e)}>
            <span>{expanded ? '▾' : '▸'}</span>
            Per-agent details
          </div>
          {expanded && (
            <div className="intel-agents-grid">
              {intel.agents.map(a => <IntelAgentCard key={a.agent_key} agent={a} />)}
            </div>
          )}
        </>
      )}
    </div>
  );
}

/* ── Agent Overview Tab ───────────────────────────────────── */
function AgentOverview({ agKey }) {
  const { AGENTS, fmtMoney, fmtDate, fitnessDashAPI, journalDashAPI, tasksAPI, patternsAPI } = window.CLData;
  const ag = AGENTS[agKey];
  const [data, setData] = _useState(null);
  const [loading, setLoading] = _useState(true);

  _useEffect(() => {
    setData(null); setLoading(true);
    const fetch = {
      task:    () => tasksAPI(),
      fitness: () => fitnessDashAPI(),
      journal: () => journalDashAPI(),
      budget:  () => window.CLData.budgetAPI ? window.CLData.budgetAPI() : Promise.resolve(null),
    }[agKey] || (() => Promise.resolve(null));

    fetch().then(d => { setData(d); setLoading(false); }).catch(() => setLoading(false));
  }, [agKey]);

  const [firstName, ...rest] = ag.name.split(' ');

  return (
    <div className="overview-wrap scroll">
      <div className="overview-eyebrow small-caps">{ag.issue} · {ag.sub}</div>
      <h1 className="overview-title" style={{'--agent-hue': ag.hue}}>
        {firstName}<em>{rest.length ? ' ' + rest.join(' ') : ''}</em><br/>
        <span style={{fontSize:'0.55em', color:'var(--ink-3)', fontStyle:'normal'}}>Overview</span>
      </h1>

      {loading && (
        <div className="overview-grid">
          {[1,2,3].map(i => (
            <div key={i} className="overview-card">
              <span className="skeleton skeleton-label"/>
              <span className="skeleton skeleton-hero" style={{marginTop:8}}/>
            </div>
          ))}
        </div>
      )}

      {!loading && agKey === 'task' && data && (
        <>
          <div className="overview-grid">
            <div className="overview-card">
              <div className="overview-card-label">Pending</div>
              <div className="overview-card-value" style={{color:'var(--hue-alfred)'}}>{data.stats?.pending ?? 0}</div>
              <div className="overview-card-sub">tasks in queue</div>
            </div>
            <div className="overview-card">
              <div className="overview-card-label">High Priority</div>
              <div className="overview-card-value" style={{color:'var(--hue-lavoiser)'}}>{data.stats?.high_priority ?? 0}</div>
              <div className="overview-card-sub">need attention</div>
            </div>
            <div className="overview-card">
              <div className="overview-card-label">Done Today</div>
              <div className="overview-card-value" style={{color:'var(--hue-miyamoto)'}}>{data.stats?.completed_today ?? 0}</div>
              <div className="overview-card-sub">completed</div>
            </div>
          </div>
          <div className="overview-bar-section">
            <div className="overview-bar-section-title">Next up</div>
            <div className="overview-items">
              {(data.tasks || []).filter(t => t.status === 'pending').slice(0, 5).map((t, i) => (
                <div key={i} className="overview-item">
                  <div className="overview-item-title">{t.title}</div>
                  <div className="overview-item-meta" style={{
                    color: t.priority === 'high' ? 'var(--hue-lavoiser)' :
                           t.priority === 'medium' ? 'var(--hue-mansa)' : 'var(--ink-4)'
                  }}>{t.priority || 'normal'}</div>
                </div>
              ))}
              {!(data.tasks || []).some(t => t.status === 'pending') && (
                <div className="overview-empty">Nothing pending. A rare and welcome moment.</div>
              )}
            </div>
          </div>
          <IntelligenceDashboard />
        </>
      )}

      {!loading && agKey === 'fitness' && data && (
        <>
          <div className="overview-grid">
            {[
              { label: "Today's Calories", val: data.today_calories ?? '—', sub: `target: ${data.calorie_target ?? 2000} kcal` },
              { label: 'Protein Today',    val: data.today_protein ? `${data.today_protein}g` : '—', sub: `target: ${data.protein_target ?? 150}g` },
              { label: 'Log Streak',       val: data.streak_days ?? 0, sub: 'consecutive days logged' },
            ].map((c, i) => (
              <div key={i} className="overview-card">
                <div className="overview-card-label">{c.label}</div>
                <div className="overview-card-value" style={{color: ag.hue}}>{c.val}</div>
                <div className="overview-card-sub">{c.sub}</div>
              </div>
            ))}
          </div>
          {data.today_calories != null && data.calorie_target != null && (
            <div className="overview-bar-section">
              <div className="overview-bar-section-title">Today's progress</div>
              {[
                { label: 'Calories', cur: data.today_calories, max: data.calorie_target },
                { label: 'Protein',  cur: data.today_protein,  max: data.protein_target ?? 150 },
              ].map((b, i) => (
                <div key={i} className="panel-bar-row" style={{marginBottom:20}}>
                  <div className="panel-bar-label">
                    <span>{b.label}</span>
                    <span>{b.cur ?? 0} / {b.max}</span>
                  </div>
                  <div className="panel-bar-wrap">
                    <div className="panel-bar-fill" style={{width: `${Math.min(100, ((b.cur ?? 0)/b.max)*100)}%`, '--agent-hue': ag.hue}}/>
                  </div>
                </div>
              ))}
            </div>
          )}
          {(data.recent_logs || []).length > 0 && (
            <div className="overview-bar-section">
              <div className="overview-bar-section-title">Recent food logs</div>
              <div className="overview-items">
                {data.recent_logs.slice(0, 5).map((l, i) => (
                  <div key={i} className="overview-item">
                    <div className="overview-item-title">{l.food}</div>
                    <div className="overview-item-meta">{l.calories} kcal · {l.date}</div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </>
      )}

      {!loading && agKey === 'journal' && data && (
        <>
          <div className="overview-grid">
            <div className="overview-card">
              <div className="overview-card-label">Entries</div>
              <div className="overview-card-value" style={{color: ag.hue}}>{data.total ?? 0}</div>
              <div className="overview-card-sub">in the journal</div>
            </div>
            <div className="overview-card">
              <div className="overview-card-label">This Month</div>
              <div className="overview-card-value" style={{color: ag.hue}}>{data.this_month ?? 0}</div>
              <div className="overview-card-sub">entries written</div>
            </div>
          </div>
          {(data.recent || []).length > 0 && (
            <div className="overview-bar-section">
              <div className="overview-bar-section-title">Recent entries</div>
              <div className="overview-items">
                {data.recent.slice(0, 5).map((e, i) => (
                  <div key={i} className="overview-item">
                    <div>
                      <div className="overview-item-title">{e.title || fmtDate(e.date)}</div>
                      {e.preview && <div className="overview-item-meta" style={{marginTop:3,maxWidth:440,overflow:'hidden',textOverflow:'ellipsis',whiteSpace:'nowrap'}}>{e.preview}</div>}
                    </div>
                    <div className="overview-item-meta">{fmtDate(e.date)}</div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </>
      )}

      {!loading && !['task','fitness','journal'].includes(agKey) && (
        <div className="overview-empty">
          <p>{ag.tagline}</p>
          <p style={{marginTop:16, fontSize:14, color:'var(--ink-4)'}}>Switch to Dialogue to chat with {firstName}.</p>
        </div>
      )}
    </div>
  );
}


/* ── Right Panel ──────────────────────────────────────────── */
function RightPanel({ agKey, dash, panelOpen }) {
  const { AGENTS, fmtMoney, fmtDate, daFilesAPI, uploadDAAPI, receiptAPI } = window.CLData;
  const { IcoUpload, IcoReceipt, IcoDownload, IcoFile, IcoCheck } = window.Icons;
  const ag = AGENTS[agKey];
  const [tab, setTab] = _useState('tasks');
  const [scanning, setScanning] = _useState(false);
  const [scanRes, setScanRes] = _useState(null);
  const [daFiles, setDAFiles] = _useState([]);
  const [dragging, setDragging] = _useState(false);
  const recRef = _useRef(null);

  _useEffect(() => {
    if (agKey === 'coding') daFilesAPI().then(d => setDAFiles(d.files||[])).catch(() => {});
    setScanRes(null);
  }, [agKey]);

  const doReceipt = async f => {
    setScanning(true); setScanRes(null);
    try { setScanRes(await receiptAPI(f)); }
    catch { setScanRes({ error: 'Could not read receipt.' }); }
    setScanning(false);
  };
  const doDAUpload = async f => {
    try {
      const r = await uploadDAAPI(f);
      setDAFiles(p => [{ name: r.filename, size_kb: r.size_kb, modified: 'just now' }, ...p]);
    } catch {}
  };

  if (!panelOpen) return null;

  const first = ag.name.split(' ')[0];
  const rest = ag.name.split(' ').slice(1).join(' ');

  /* Budget panel — finance-specific */
  if (agKey === 'budget') return (
    <aside className="panel" style={{'--agent-hue': ag.hue}}>
      <div className="panel-head">
        <div className="small-caps" style={{color:ag.hue, marginBottom:4}}>Finance · Companion</div>
        <div className="panel-title">The <em>Ledger</em></div>
        <div className="panel-sub small-caps">Kept by Mansa</div>
      </div>
      <div className="panel-body scroll">
        <div className="panel-figure">
          <div className="panel-figure-value"><span className="unit">Rp</span>{fmtMoney(dash.budget?.balance)}</div>
          <div className="panel-figure-label small-caps">Available Balance</div>
          <div className="panel-figure-grid">
            <div>
              <div className="panel-mini-label small-caps">Income</div>
              <div className="panel-mini-value" style={{color:'var(--hue-miyamoto)'}}>+{fmtMoney(dash.budget?.monthly_income)}</div>
            </div>
            <div>
              <div className="panel-mini-label small-caps">Expense</div>
              <div className="panel-mini-value" style={{color:'var(--hue-lavoiser)'}}>−{fmtMoney(dash.budget?.monthly_expense)}</div>
            </div>
          </div>
        </div>

        <div className="panel-section">
          <div className="panel-section-head">
            <span className="small-caps">Scan Receipt</span>
            <span className="panel-count">Pixtral</span>
          </div>
          <div className={`panel-dropzone`}
            onDragOver={e => { e.preventDefault(); setDragging(true); }}
            onDragLeave={() => setDragging(false)}
            onDrop={e => { e.preventDefault(); setDragging(false); const f = e.dataTransfer.files[0]; if (f) doReceipt(f); }}
            onClick={() => recRef.current?.click()}>
            <input ref={recRef} type="file" accept="image/*" style={{display:'none'}}
              onChange={e => { if (e.target.files[0]) doReceipt(e.target.files[0]); }}/>
            <div className="panel-dropzone-ico">
              {scanning ? <span className="spinner"/> : <IcoReceipt size={22}/>}
            </div>
            <div className="panel-dropzone-text">
              {scanning ? 'Reading the receipt…' : 'Drop a receipt, or choose a file'}
            </div>
            <div className="panel-dropzone-sub">JPG · PNG · HEIC</div>
          </div>
          {scanRes && !scanRes.error && (
            <div className="panel-receipt-result">
              <div style={{fontFamily:"'Instrument Serif', serif", fontSize:19, letterSpacing:'-0.01em'}}>
                {scanRes.description}
              </div>
              <div style={{fontFamily:"'Instrument Serif', serif", fontSize:22, color: scanRes.type==='income'?'var(--hue-miyamoto)':'var(--hue-lavoiser)', marginTop:4}}>
                {scanRes.type==='income' ? '+' : '−'} Rp {fmtMoney(scanRes.amount)}
              </div>
              <div className="small-caps" style={{marginTop:6, color:'var(--ink-3)'}}>
                {scanRes.category} · {scanRes.date}
              </div>
            </div>
          )}
          {scanRes?.error && (
            <div style={{marginTop:10, color:'var(--hue-lavoiser)', fontStyle:'italic', fontFamily:"'Instrument Serif', serif"}}>
              {scanRes.error}
            </div>
          )}
        </div>
      </div>
    </aside>
  );

  /* Coding — data files */
  if (agKey === 'coding') return (
    <aside className="panel" style={{'--agent-hue': ag.hue}}>
      <div className="panel-head">
        <div className="small-caps" style={{color:ag.hue, marginBottom:4}}>Data · Analyst</div>
        <div className="panel-title">The <em>Workbench</em></div>
        <div className="panel-sub small-caps">Linus · CSV · JSON · Excel</div>
      </div>
      <div className="panel-body scroll">
        <div className="panel-section">
          <div className="panel-section-head">
            <span className="small-caps">Upload Dataset</span>
          </div>
          <div className="panel-dropzone"
            onDragOver={e => { e.preventDefault(); setDragging(true); }}
            onDragLeave={() => setDragging(false)}
            onDrop={e => { e.preventDefault(); setDragging(false); const f = e.dataTransfer.files[0]; if (f) doDAUpload(f); }}
            onClick={() => {
              const i = document.createElement('input');
              i.type='file'; i.accept='.csv,.xlsx,.xls,.json';
              i.onchange = e => doDAUpload(e.target.files[0]); i.click();
            }}>
            <div className="panel-dropzone-ico"><IcoUpload size={22}/></div>
            <div className="panel-dropzone-text">Drop a dataset, or browse</div>
            <div className="panel-dropzone-sub">CSV · XLSX · JSON</div>
          </div>
        </div>
        {daFiles.length > 0 && (
          <div className="panel-section">
            <div className="panel-section-head">
              <span className="small-caps">Available Files</span>
              <span className="panel-count">{daFiles.length}</span>
            </div>
            {daFiles.map((f, i) => (
              <div key={i} className="panel-file">
                <IcoFile/>
                <div style={{flex:1}}>
                  <div className="panel-file-name">{f.name}</div>
                  <div className="panel-file-meta">{f.size_kb} KB · {f.modified}</div>
                </div>
                <a href={`/api/dataanalyst/download/${encodeURIComponent(f.name)}`}
                  download className="panel-file-dl"><IcoDownload/></a>
              </div>
            ))}
          </div>
        )}
      </div>
    </aside>
  );

  /* Fitness panel */
  if (agKey === 'fitness') return (
    <aside className="panel" style={{'--agent-hue': ag.hue}}>
      <div className="panel-head">
        <div className="small-caps" style={{color:ag.hue, marginBottom:4}}>Fitness · Today</div>
        <div className="panel-title">The <em>Body</em></div>
        <div className="panel-sub small-caps">Kept by Lavoisier</div>
      </div>
      <div className="panel-body scroll">
        <FitnessPanel agHue={ag.hue}/>
      </div>
    </aside>
  );

  /* Journal panel */
  if (agKey === 'journal') return (
    <aside className="panel" style={{'--agent-hue': ag.hue}}>
      <div className="panel-head">
        <div className="small-caps" style={{color:ag.hue, marginBottom:4}}>Journal · Recent</div>
        <div className="panel-title">The <em>Page</em></div>
        <div className="panel-sub small-caps">Kept by Dostoyevsky</div>
      </div>
      <div className="panel-body scroll">
        <JournalPanel agHue={ag.hue}/>
      </div>
    </aside>
  );

  /* News panel */
  if (agKey === 'news') return (
    <aside className="panel" style={{'--agent-hue': ag.hue}}>
      <div className="panel-head">
        <div className="small-caps" style={{color:ag.hue, marginBottom:4}}>News · Live</div>
        <div className="panel-title">The <em>Wire</em></div>
        <div className="panel-sub small-caps">Via Najwa</div>
      </div>
      <div className="panel-body scroll">
        <NewsPanel agHue={ag.hue}/>
      </div>
    </aside>
  );

  /* Default — tasks / notes */
  const pendingTasks = (dash.tasks || []).filter(t => t.status === 'pending').slice(0, 6);
  const recentNotes  = (dash.notes || []).slice(0, 6);

  return (
    <aside className="panel" style={{'--agent-hue': ag.hue}}>
      <div className="panel-head">
        <div className="small-caps" style={{color:ag.hue, marginBottom:4}}>In Residence · {ag.sub}</div>
        <div className="panel-title">{first}<em>{rest?' '+rest:''}</em></div>
        <div className="panel-sub">{ag.tagline}</div>
      </div>
      <div className="panel-body scroll">
        {tab === 'tasks' && (
          <div className="panel-section">
            <div className="panel-section-head">
              <span className="small-caps">Pending</span>
              <span className="panel-count">{pendingTasks.length} open</span>
            </div>
            {pendingTasks.length === 0 ? (
              <div style={{padding:'14px 0', color:'var(--ink-3)', fontStyle:'italic', fontFamily:"'Instrument Serif', serif", fontSize:17}}>
                Nothing pending. A rare and welcome moment.
              </div>
            ) : pendingTasks.map((t, i) => (
              <div key={i} className="panel-item">
                <span className="panel-item-check"/>
                <div>
                  <div className="panel-item-title">{t.title}</div>
                  <div className="panel-item-meta">
                    <span className="priority-mark" style={{background:
                      t.priority==='high' ? 'var(--hue-lavoiser)' :
                      t.priority==='medium' ? 'var(--hue-mansa)' : 'var(--ink-4)'}}/>
                    {t.priority || 'normal'}
                  </div>
                </div>
                <span className="panel-item-right">#{String(i+1).padStart(2,'0')}</span>
              </div>
            ))}
          </div>
        )}
        {tab === 'notes' && (
          <div className="panel-section">
            <div className="panel-section-head">
              <span className="small-caps">Recent Notes</span>
              <span className="panel-count">{recentNotes.length}</span>
            </div>
            {recentNotes.length === 0 ? (
              <div style={{padding:'14px 0', color:'var(--ink-3)', fontStyle:'italic', fontFamily:"'Instrument Serif', serif", fontSize:17}}>
                No notes yet.
              </div>
            ) : recentNotes.map((n, i) => (
              <div key={i} className="panel-item">
                <IcoFile/>
                <div>
                  <div className="panel-item-title">{n.title}</div>
                  <div className="panel-item-meta">{fmtDate(n.updated_at)}</div>
                </div>
                <span className="panel-item-right">→</span>
              </div>
            ))}
          </div>
        )}
      </div>
      <div className="panel-tabs">
        <button className={`panel-tab ${tab==='tasks'?'active':''}`} onClick={()=>setTab('tasks')}>Tasks</button>
        <button className={`panel-tab ${tab==='notes'?'active':''}`} onClick={()=>setTab('notes')}>Notes</button>
      </div>
    </aside>
  );
}

/* ── Fitness Right Panel sub-component ───────────────────── */
function FitnessPanel({ agHue }) {
  const { fitnessDashAPI, fmtDate } = window.CLData;
  const [data, setData] = _useState(null);
  _useEffect(() => { fitnessDashAPI().then(setData).catch(() => {}); }, []);

  if (!data) return (
    <div className="panel-section">
      {[1,2].map(i => (
        <div key={i} className="panel-bar-row">
          <span className="skeleton skeleton-label" style={{marginBottom:10,display:'block'}}/>
          <span className="skeleton" style={{display:'block',height:6,borderRadius:3}}/>
        </div>
      ))}
    </div>
  );

  const kcal = data.today_calories ?? 0;
  const kcalTarget = data.calorie_target ?? 2000;
  const prot = data.today_protein ?? 0;
  const protTarget = data.protein_target ?? 150;

  return (
    <div className="panel-section">
      <div className="panel-section-head">
        <span className="small-caps">Today's Targets</span>
        <span className="panel-count">{data.streak_days ?? 0}d streak</span>
      </div>
      {[
        { label:'Calories', cur: kcal, max: kcalTarget, unit:'kcal' },
        { label:'Protein',  cur: prot, max: protTarget,  unit:'g' },
      ].map((b, i) => (
        <div key={i} className="panel-bar-row">
          <div className="panel-bar-label">
            <span>{b.label}</span>
            <span>{b.cur} / {b.max}{b.unit}</span>
          </div>
          <div className="panel-bar-wrap">
            <div className="panel-bar-fill" style={{width:`${Math.min(100,(b.cur/b.max)*100)}%`,'--agent-hue':agHue}}/>
          </div>
        </div>
      ))}
      {(data.recent_logs || []).length > 0 && (
        <div className="panel-section" style={{marginTop:18}}>
          <div className="panel-section-head"><span className="small-caps">Recent Logs</span></div>
          {data.recent_logs.slice(0, 4).map((l, i) => (
            <div key={i} className="panel-entry">
              <div className="panel-entry-title">{l.food}</div>
              <div className="panel-entry-meta">{l.calories} kcal · {fmtDate(l.date)}</div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

/* ── Journal Right Panel sub-component ───────────────────── */
function JournalPanel({ agHue }) {
  const { journalDashAPI, fmtDate } = window.CLData;
  const [data, setData] = _useState(null);
  _useEffect(() => { journalDashAPI().then(setData).catch(() => {}); }, []);

  if (!data) return (
    <div className="panel-section">
      {[1,2,3].map(i => (
        <div key={i} style={{padding:'12px 0', borderBottom:'1px solid var(--rule-soft)'}}>
          <span className="skeleton skeleton-line" style={{display:'block'}}/>
          <span className="skeleton skeleton-line-sm" style={{display:'block',marginTop:6}}/>
        </div>
      ))}
    </div>
  );

  const entries = data.recent || [];
  return (
    <div className="panel-section">
      <div className="panel-section-head">
        <span className="small-caps">Recent Entries</span>
        <span className="panel-count">{data.total ?? 0} total</span>
      </div>
      {entries.length === 0 ? (
        <div style={{padding:'14px 0', color:'var(--ink-3)', fontStyle:'italic', fontFamily:"'Instrument Serif', serif", fontSize:17}}>
          The page is empty. Begin anywhere.
        </div>
      ) : entries.slice(0, 5).map((e, i) => (
        <div key={i} className="panel-entry">
          <div className="panel-entry-title">{e.title || fmtDate(e.date)}</div>
          <div className="panel-entry-meta">{fmtDate(e.date)}{e.mood ? ' · ' + e.mood : ''}</div>
        </div>
      ))}
    </div>
  );
}

/* ── News Right Panel sub-component ──────────────────────── */
function NewsPanel({ agHue }) {
  const { newsFeedAPI } = window.CLData;
  const [items, setItems] = _useState(null);
  _useEffect(() => { newsFeedAPI().then(d => setItems(d.articles || d.items || d || [])).catch(() => setItems([])); }, []);

  if (!items) return (
    <div className="panel-section">
      {[1,2,3,4,5].map(i => (
        <div key={i} style={{padding:'11px 0', borderBottom:'1px solid var(--rule-soft)'}}>
          <span className="skeleton skeleton-line" style={{display:'block'}}/>
          <span className="skeleton skeleton-label" style={{display:'block',marginTop:6}}/>
        </div>
      ))}
    </div>
  );

  return (
    <div className="panel-section">
      <div className="panel-section-head">
        <span className="small-caps">Latest</span>
        <span className="panel-count">{items.length}</span>
      </div>
      {items.length === 0 ? (
        <div style={{padding:'14px 0', color:'var(--ink-3)', fontStyle:'italic', fontFamily:"'Instrument Serif', serif", fontSize:17}}>
          The wires are quiet.
        </div>
      ) : items.slice(0, 7).map((a, i) => (
        <div key={i} className="panel-headline">
          <div className="panel-headline-title">{a.title || a.headline || a.text || ''}</div>
          {(a.source || a.url) && (
            <div className="panel-headline-source">{a.source || new URL(a.url).hostname}</div>
          )}
        </div>
      ))}
    </div>
  );
}

window.CLViews = { Sidebar, Masthead, ChatView, DashboardView, AgentOverview, RightPanel };

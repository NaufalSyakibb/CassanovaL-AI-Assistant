/* ============================================================
   Views — Sidebar, Masthead, Chat, Dashboard, RightPanel
   ============================================================ */
const { useState: _useState, useEffect: _useEffect, useRef: _useRef, useCallback: _useCallback, useMemo: _useMemo } = React;

/* ── Sidebar ──────────────────────────────────────────────── */
function Sidebar({ active, setActive, onCmd, onCrew, theme, toggleTheme }) {
  const { AGENTS, AGENT_ORDER } = window.CLData;
  const { IcoCmd, IcoUsers, IcoSun, IcoMoon, IcoCandlestick, IcoNewspaper, IcoFeather } = window.Icons;
  return (
    <aside className="sidebar">
      <div className="brand">
        <div className="brand-mark">Cassanova<em>L</em></div>
      </div>
      <div className="roster-heading">
        <div className="small-caps">The Roster</div>
        <div className="roster-count">{AGENT_ORDER.length}</div>
      </div>
      <div className="roster scroll">
        {AGENT_ORDER.map((k, i) => {
          const ag = AGENTS[k];
          const isAct = active === k;
          return (
            <button key={k}
              className={`roster-row ${isAct ? 'active' : ''}`}
              style={{ '--agent-hue': ag.hue }}
              onClick={() => setActive(k)}>
              <span className="roster-num">{String(i+1).padStart(2,'0')}</span>
              <div className="roster-body">
                <div className="roster-name">
                  {ag.name.split(' ')[0]}<em>{ag.name.includes(' ') ? ' ' + ag.name.split(' ').slice(1).join(' ') : ''}</em>
                </div>
                <div className="roster-role">{ag.sub}</div>
              </div>
              <span className="roster-dot"/>
            </button>
          );
        })}
      </div>
      <div className="sidebar-footer">
        <button className="side-btn" onClick={onCmd} title="Command Palette (⌘K)"><IcoCmd/></button>
        <button className="side-btn" onClick={onCrew} title="Crew Mode"><IcoUsers/></button>
        <a className="side-btn" href="/stock" target="_blank" rel="noopener noreferrer" title="Stock Terminal"><IcoCandlestick/></a>
        <button className="side-btn" onClick={toggleTheme} title="Toggle theme">
          {theme === 'dark' ? <IcoSun/> : <IcoMoon/>}
        </button>
        <div className="side-btn me" title="Naufal">N</div>
      </div>
    </aside>
  );
}

/* ── Masthead ─────────────────────────────────────────────── */
function Masthead({ agKey, tab, setTab, panelOpen, setPanelOpen }) {
  const { AGENTS, fmtIssue, fmtLongDate } = window.CLData;
  const { IcoPanelClose, IcoPanelOpen } = window.Icons;
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
          </nav>
        </div>
        <div className="masthead-right">
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
  const { IcoSend, IcoClip, IcoPlus, IcoReceipt } = window.Icons;
  const ag = AGENTS[agKey];
  const [val, setVal] = _useState('');
  const endRef = _useRef(null);
  const taRef = _useRef(null);
  const recRef = _useRef(null);

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
function DashboardView({ dash, setAgent }) {
  const { AGENTS, AGENT_ORDER, fmtMoney, fmtDate, fmtIssue, fmtLongDate } = window.CLData;
  const { tStats, budget, notesTotal, notes = [], recentTx = [] } = dash;

  // Fake sparkline values
  const spark = (seed) => Array.from({length:12}, (_,i) => 0.3 + 0.7*Math.abs(Math.sin(i*1.3 + seed)));

  return (
    <div className="dashboard scroll">
      <div className="dash-container">
        <div className="dash-hero">
          <div>
            <div className="dash-eyebrow small-caps">The Daily Ledger · {fmtLongDate()}</div>
            <h1 className="dash-title">Welcome back,<br/><em>Cassanova.</em></h1>
            <p className="dash-subtitle">
              Nine agents stand ready. The ledger balances. A quiet day, should you wish to keep it so.
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
      </div>
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

window.CLViews = { Sidebar, Masthead, ChatView, DashboardView, RightPanel };

/* ============================================================
   Overlays — CommandPalette, CrewDrawer, ResultModal
   ============================================================ */

function CommandPalette({ onClose, setAgent, setTab, toggleTheme, theme }) {
  const { AGENTS, AGENT_ORDER } = window.CLData;
  const { IcoSearch, IcoSun, IcoMoon } = window.Icons;
  const [q, setQ] = _useState('');
  const [idx, setIdx] = _useState(0);
  const inRef = _useRef(null);

  _useEffect(() => { inRef.current?.focus(); }, []);

  const items = _useMemo(() => {
    const base = [
      ...AGENT_ORDER.map(k => ({
        type:'agent', key:k,
        label:`Switch to ${AGENTS[k].name}`,
        sub: AGENTS[k].sub,
        hue: AGENTS[k].hue,
      })),
      { type:'tab',    key:'overview', label:'Open the Dashboard',     sub:'Ledger · roster · recent' },
      { type:'tab',    key:'chat',     label:'Open the Dialogue',       sub:'Return to the active agent' },
      { type:'link',   key:'/notes',   label:'Open Study Page',         sub:'Cicero · flashcards · notes · quizzes' },
      { type:'link',   key:'/news',    label:'Open News Feed',          sub:'Najwa · live headlines · briefings' },
      { type:'link',   key:'/stock',   label:'Open Stock Terminal',     sub:'Bloomberg-style analysis terminal' },
      { type:'link',   key:'/stock/v2',label:'Open Pixel Terminal v2',  sub:'Retro pixel stock terminal' },
      { type:'theme',  key:'theme',    label: theme==='dark' ? 'Switch to light mode' : 'Switch to dark mode',
        sub:'Adjust the room' },
    ];
    if (!q) return base;
    const qq = q.toLowerCase();
    return base.filter(i => i.label.toLowerCase().includes(qq) || i.sub.toLowerCase().includes(qq));
  }, [q, theme]);

  const pick = (it) => {
    if (it.type === 'agent') { setAgent(it.key); setTab('chat'); }
    else if (it.type === 'tab') setTab(it.key);
    else if (it.type === 'theme') toggleTheme();
    else if (it.type === 'link') { window.open(it.key, '_blank', 'noopener'); }
    onClose();
  };

  const onKey = (e) => {
    if (e.key === 'Escape') onClose();
    else if (e.key === 'ArrowDown') { e.preventDefault(); setIdx(i => Math.min(i+1, items.length-1)); }
    else if (e.key === 'ArrowUp') { e.preventDefault(); setIdx(i => Math.max(i-1, 0)); }
    else if (e.key === 'Enter' && items[idx]) pick(items[idx]);
  };

  const agents = items.filter(i => i.type === 'agent');
  const actions = items.filter(i => i.type !== 'agent');

  return (
    <div className="backdrop" onClick={onClose}>
      <div className="cmd-center" onClick={e=>e.stopPropagation()}>
        <div className="cmd-modal">
          <div className="cmd-search">
            <span className="cmd-search-ico"><IcoSearch size={17}/></span>
            <input ref={inRef} className="cmd-input"
              placeholder="Search agents, actions…"
              value={q} onChange={e=>{ setQ(e.target.value); setIdx(0); }}
              onKeyDown={onKey}/>
            <span className="cmd-esc">ESC</span>
          </div>
          <div className="cmd-results scroll">
            {agents.length > 0 && <div className="cmd-section small-caps">The Roster</div>}
            {agents.map((it, i) => {
              const globalIdx = items.indexOf(it);
              const first = AGENTS[it.key].name.split(' ')[0];
              const rest  = AGENTS[it.key].name.split(' ').slice(1).join(' ');
              return (
                <div key={it.key}
                  className={`cmd-item ${globalIdx === idx ? 'selected' : ''}`}
                  style={{'--agent-hue': it.hue}}
                  onClick={()=>pick(it)} onMouseEnter={()=>setIdx(globalIdx)}>
                  <span className="cmd-item-num">{String(i+1).padStart(2,'0')}</span>
                  <div className="cmd-item-body">
                    <div className="cmd-item-label">
                      Switch to {first}<em>{rest?' '+rest:''}</em>
                    </div>
                    <div className="cmd-item-sub">{it.sub}</div>
                  </div>
                  <span className="cmd-item-kbd">→</span>
                </div>
              );
            })}
            {actions.length > 0 && <div className="cmd-section small-caps">Actions</div>}
            {actions.map((it) => {
              const globalIdx = items.indexOf(it);
              return (
                <div key={it.key+it.type}
                  className={`cmd-item ${globalIdx === idx ? 'selected' : ''}`}
                  onClick={()=>pick(it)} onMouseEnter={()=>setIdx(globalIdx)}>
                  <span className="cmd-item-num">§</span>
                  <div className="cmd-item-body">
                    <div className="cmd-item-label">{it.label}</div>
                    <div className="cmd-item-sub">{it.sub}</div>
                  </div>
                  <span className="cmd-item-kbd">↵</span>
                </div>
              );
            })}
            {items.length === 0 && (
              <div style={{padding:'40px 20px', textAlign:'center', color:'var(--ink-3)', fontFamily:"'Instrument Serif', serif", fontStyle:'italic', fontSize:19}}>
                Nothing matches. The archive is quiet.
              </div>
            )}
          </div>
          <div className="cmd-footer">
            <div className="cmd-footer-hints small-caps">
              <span>↑↓ Navigate</span>
              <span>↵ Select</span>
              <span>ESC Close</span>
            </div>
            <span className="mono" style={{fontSize:10}}>CassanovaL · v3.0</span>
          </div>
        </div>
      </div>
    </div>
  );
}

/* ── Crew Drawer ──────────────────────────────────────────── */
function CrewDrawer({ onClose }) {
  const { daFilesAPI, uploadDAAPI, crewKick, crewPoll } = window.CLData;
  const { IcoX, IcoRocket, IcoCheck } = window.Icons;
  const [crewType, setCrewType] = _useState('research');
  const [topic, setTopic] = _useState('');
  const [cvText, setCvText] = _useState('');
  const [filename, setFilename] = _useState('');
  const [daFiles, setDAFiles] = _useState([]);
  const [uploading, setUploading] = _useState(false);
  const [uploadError, setUploadError] = _useState('');
  const [status, setStatus] = _useState('idle');
  const [logs, setLogs] = _useState([]);
  const [outputs, setOutputs] = _useState({});
  const [showResult, setShowResult] = _useState(false);
  const logsEndRef = _useRef(null);
  const pollRef = _useRef(null);

  _useEffect(() => {
    daFilesAPI().then(d => setDAFiles(d.files || [])).catch(() => {});
    return () => { if (pollRef.current) clearInterval(pollRef.current); };
  }, []);

  _useEffect(() => { logsEndRef.current?.scrollIntoView({ behavior: 'smooth' }); }, [logs]);

  const launch = async () => {
    if (!topic.trim()) return;
    if (crewType === 'dataanalyst' && !filename) return;
    setStatus('running');
    setLogs(['[SYSTEM] Initializing the crew pipeline…']);
    setOutputs({}); setShowResult(false);
    try {
      const res = await crewKick(
        topic.trim(), crewType,
        crewType === 'dataanalyst' ? filename : undefined,
        crewType === 'career' ? cvText.trim() || undefined : undefined,
      );
      const id = res.job_id;
      pollRef.current = setInterval(async () => {
        try {
          const s = await crewPoll(id);
          if (s.logs?.length) setLogs(s.logs);
          if (s.status === 'done') {
            clearInterval(pollRef.current);
            setStatus('done'); setOutputs(s.outputs || {});
            setLogs(p => [...p, '[SYSTEM] Pipeline complete.']);
          } else if (s.status === 'error') {
            clearInterval(pollRef.current);
            setStatus('error');
            setLogs(p => [...p, `[ERROR] ${(s.error || 'Unknown').split('\n')[0]}`]);
          }
        } catch {}
      }, 2500);
    } catch (e) {
      setStatus('error');
      setLogs(p => [...p, `[ERROR] ${e.message}`]);
    }
  };

  const handleUpload = async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setUploading(true);
    setUploadError('');
    try {
      await uploadDAAPI(file);
      const d = await daFilesAPI();
      setDAFiles(d.files || []);
      setFilename(file.name);
    } catch (err) {
      setUploadError(err.message || 'Upload failed');
    } finally {
      setUploading(false);
      e.target.value = '';
    }
  };

  const nodes = crewType === 'career'
    ? [
        { num:'1', name:'Archetype Classifier', role:'Detect role type + extract signals', llm:'mistral-small', phase:'Phase 1', hue:'var(--hue-alfred)' },
        { num:'2', name:'Job Evaluator',         role:'Score A–G across 7 dimensions',      llm:'mistral-large', phase:'Phase 2', hue:'var(--hue-linus)' },
        { num:'3', name:'CV Advisor',            role:'Tailor CV to the role',              llm:'mistral-large', phase:'Phase 2', hue:'var(--hue-cicero)' },
        { num:'4', name:'Report Writer',         role:'Compile final evaluation report',    llm:'mistral-large', phase:'Phase 3', hue:'var(--hue-najwa)' },
      ]
    : crewType === 'research'
    ? [
        { num:'1', name:'Scout',       role:'Topic map + mode detect', llm:'mistral-small', phase:'Phase 1', hue:'var(--hue-alfred)' },
        { num:'2', name:'Filter',      role:'Source curation',         llm:'mistral-small', phase:'Phase 1', hue:'var(--hue-alfred)' },
        { num:'3', name:'IdeaGen',     role:'Hypotheses + angles',     llm:'mistral-large', phase:'Phase 2', parallel:true, hue:'var(--hue-linus)' },
        { num:'4', name:'Validator',   role:'Cross-check + flag weak', llm:'mistral-large', phase:'Phase 2', parallel:true, hue:'var(--hue-linus)' },
        { num:'5', name:'Synthesizer', role:'Unified narrative',       llm:'mistral-large', phase:'Phase 3', hue:'var(--hue-cicero)' },
        { num:'6', name:'Critic',      role:'Logic review',            llm:'mistral-large', phase:'Phase 3', hue:'var(--hue-cicero)' },
        { num:'7', name:'Writer',      role:'Final article',           llm:'mistral-large', phase:'Phase 3', hue:'var(--hue-cicero)' },
      ]
    : crewType === 'academic_swarm'
    ? [
        { num:'0', name:'Al-Biruni', role:'Classify depth: Quick/Deep/Academic', llm:'mistral-small', phase:'Phase 0', hue:'var(--hue-alfred)' },
        { num:'1', name:'Hypatia',   role:'Broad academic search',                llm:'mistral-small', phase:'Phase 1', hue:'var(--hue-cicero)' },
        { num:'2', name:'Bacon',     role:'Deep paper analysis',                  llm:'mistral-large', phase:'Phase 2', hue:'var(--hue-linus)' },
        { num:'3', name:'Popper',    role:'Evidence cross-check',                 llm:'mistral-large', phase:'Phase 2', parallel:true, hue:'var(--hue-linus)' },
        { num:'4', name:'Leibniz',   role:'Citation chain tracer',                llm:'mistral-small', phase:'Phase 3', hue:'var(--hue-najwa)' },
        { num:'5', name:'Averroes',  role:'Synthesize findings + citations',      llm:'mistral-large', phase:'Phase 4', hue:'var(--hue-cicero)' },
        { num:'6', name:'Sokrates',  role:'Critic loop (up to 3×)',               llm:'mistral-large', phase:'Phase 5', hue:'var(--hue-alfred)' },
        { num:'7', name:'Darwin',    role:'Final academic report',                llm:'mistral-large', phase:'Phase 6', hue:'var(--hue-najwa)' },
      ]
    : /* dataanalyst */ [
        { num:'I',   name:'The Cleaner',      role:'Preprocessing',     hue:'var(--hue-miyamoto)' },
        { num:'II',  name:'The Statistician', role:'Analysis',          hue:'var(--hue-cicero)' },
        { num:'III', name:'The Visualizer',   role:'Chart Composition', hue:'var(--hue-najwa)' },
      ];

  const logClass = l =>
    l.startsWith('[SYSTEM]') || l.startsWith('[ERROR]') ? 'log-sys' :
    l.includes('>>') || l.includes('→') ? 'log-analysis' : 'log-info';

  return (
    <>
      {showResult && Object.keys(outputs).length > 0 && (
        <ResultModal outputs={outputs} onClose={() => setShowResult(false)}/>
      )}
      <div className="backdrop" onClick={onClose}>
        <div className="crew-drawer" onClick={e => e.stopPropagation()}>
          <div className="crew-head">
            <div className="crew-eyebrow">
              <span className="small-caps">The Feature · Crew Mode</span>
              <button className="crew-close" onClick={onClose}><IcoX/></button>
            </div>
            <div className="crew-title">A <em>pipeline</em> of many hands.</div>
            <div className="crew-tagline">
              Commission a chain of specialists to research, critique, and synthesize — while you watch the work unfold.
            </div>
          </div>

          <div className="crew-body scroll">
            <div className="crew-section">
              <div className="crew-label small-caps">§ Choose a Pipeline</div>
              <div className="crew-type-row">
                <button className={`crew-type ${crewType==='research'?'active':''}`} onClick={() => setCrewType('research')}>
                  <div className="crew-type-title">Research</div>
                  <div className="crew-type-sub">Scout → [IdeaGen ‖ Validator] → Writer</div>
                </button>
                <button className={`crew-type ${crewType==='dataanalyst'?'active':''}`} onClick={() => setCrewType('dataanalyst')}>
                  <div className="crew-type-title">Data Analyst</div>
                  <div className="crew-type-sub">Clean → Analyze → Visualize</div>
                </button>
                <button className={`crew-type ${crewType==='career'?'active':''}`} onClick={() => setCrewType('career')}>
                  <div className="crew-type-title">Career Ops</div>
                  <div className="crew-type-sub">Classify → Evaluate A–G → Tailor CV</div>
                </button>
                <button className={`crew-type ${crewType==='academic_swarm'?'active':''}`} onClick={() => setCrewType('academic_swarm')}>
                  <div className="crew-type-title">Academic Swarm</div>
                  <div className="crew-type-sub">Al-Biruni → [Hypatia…Darwin]</div>
                </button>
              </div>
            </div>

            <div className="crew-section">
              {crewType === 'career' ? (
                <>
                  <div className="crew-label small-caps">§ Job Description</div>
                  <textarea className="crew-field" style={{minHeight:120}}
                    placeholder="Paste the full job description here…"
                    value={topic} onChange={e => setTopic(e.target.value)}/>
                  <div className="crew-label small-caps" style={{marginTop:16}}>§ Your CV / Resume <span style={{color:'var(--ink-4)', fontWeight:400}}>(optional — paste plain text)</span></div>
                  <textarea className="crew-field" style={{minHeight:100}}
                    placeholder="Paste your CV here for a personalized A–G score and tailored advice…"
                    value={cvText} onChange={e => setCvText(e.target.value)}/>
                </>
              ) : crewType === 'research' || crewType === 'academic_swarm' ? (
                <>
                  <div className="crew-label small-caps">§ Research Topic</div>
                  <textarea className="crew-field"
                    placeholder={crewType === 'academic_swarm' ? 'Academic topic to investigate…' : 'A question worth pursuing…'}
                    value={topic} onChange={e => setTopic(e.target.value)}/>
                </>
              ) : (
                <>
                  <div className="crew-label small-caps">§ Dataset</div>
                  <div className="crew-upload-row">
                    <select className="crew-field" value={filename} onChange={e => setFilename(e.target.value)}>
                      <option value="">Select a file…</option>
                      {daFiles.map((f, i) => (
                        <option key={i} value={f.name}>{f.name} ({f.size_kb} KB)</option>
                      ))}
                    </select>
                    <label className={`crew-upload-btn${uploading ? ' uploading' : ''}`}>
                      {uploading ? 'Uploading…' : 'Import file'}
                      <input type="file" accept=".csv,.xlsx,.xls,.json" hidden
                        onChange={handleUpload} disabled={uploading}/>
                    </label>
                  </div>
                  {uploadError && <div className="crew-upload-error">{uploadError}</div>}
                  <div className="crew-label small-caps" style={{marginTop:16}}>§ Analysis Goal</div>
                  <textarea className="crew-field"
                    placeholder="What shall we ask of the data?"
                    value={topic} onChange={e => setTopic(e.target.value)}/>
                </>
              )}
            </div>

            <div className="crew-section">
              <div className="crew-label">
                <span className="small-caps">§ The Crew</span>
                <span className="small-caps" style={{color:'var(--clay)'}}>
                  <span className="status-dot" style={{background:'var(--clay)', animation: status==='running'?'inkPulse 1s infinite':'none'}}/>
                  {nodes.length} agents
                </span>
              </div>
              {nodes.reduce((acc, n, i) => {
                const prev = nodes[i - 1];
                if (!prev || prev.phase !== n.phase) {
                  acc.push(
                    <div key={`sep-${i}`} className="crew-phase-sep small-caps">
                      {n.phase || ''}
                      {n.parallel && <span className="crew-parallel-badge">parallel</span>}
                    </div>
                  );
                }
                acc.push(
                  <div key={i} className="crew-node" style={{'--node-hue': n.hue}}>
                    <div className="crew-node-num">{n.num}</div>
                    <div style={{flex:1}}>
                      <div className="crew-node-title"><em>{n.name}</em></div>
                      <div className="crew-node-role">{n.role}</div>
                    </div>
                    {n.llm && <span className="crew-node-llm">{n.llm}</span>}
                    {status === 'done' && <span className="crew-node-check"><IcoCheck/></span>}
                  </div>
                );
                return acc;
              }, [])}
            </div>

            <div className="crew-section">
              <div className="crew-label small-caps">§ Dispatch Log</div>
              <div className="crew-logs scroll">
                {logs.length === 0
                  ? <span style={{color:'var(--ink-4)'}}>&gt; Awaiting launch…</span>
                  : logs.map((l, i) => <div key={i} className={logClass(l)}>{l}</div>)}
                {status === 'running' && <span className="log-cursor"/>}
                <div ref={logsEndRef}/>
              </div>
            </div>

            {status === 'done' && Object.keys(outputs).length > 0 && (
              <div className="crew-section">
                <div className="crew-label small-caps">§ Results Ready</div>
                <button className="view-result-btn" onClick={() => setShowResult(true)}>
                  View full output · {Object.keys(outputs).length} file{Object.keys(outputs).length!==1?'s':''}
                </button>
              </div>
            )}
          </div>

          <div className="crew-foot">
            <button className="crew-launch" onClick={launch}
              disabled={status === 'running' || !topic.trim() || (crewType === 'dataanalyst' && !filename) || (crewType === 'career' && !topic.trim())}>
              {status === 'running'
                ? <><span className="spinner"/>Running pipeline…</>
                : <><IcoRocket size={15}/><span className="crew-launch-serif">Launch the crew</span></>}
            </button>
            <div className="crew-meta-line small-caps">
              {status === 'done' ? 'Pipeline complete'
                : status === 'error' ? 'Pipeline failed'
                : crewType === 'research'       ? 'Estimated 3–6 min · Mistral LLM'
                : crewType === 'career'         ? 'Estimated 2–4 min · Mistral LLM'
                : crewType === 'academic_swarm' ? 'Estimated 2–10 min · Quick/Deep/Academic'
                : 'Estimated 1–3 min · Mistral LLM'}
            </div>
          </div>
        </div>
      </div>
    </>
  );
}

/* ── Result Modal ─────────────────────────────────────────── */
function ResultModal({ outputs, onClose }) {
  const { renderMd } = window.CLData;
  const { IcoX } = window.Icons;
  const files = Object.keys(outputs);
  const [activeFile, setActiveFile] = _useState(files[0] || '');
  const [mode, setMode] = _useState('rendered');
  const content = outputs[activeFile] || '';

  const downloadFile = (filename, text) => {
    const ext = filename.split('.').pop().toLowerCase();
    const mime = { md:'text/markdown', txt:'text/plain', py:'text/x-python', csv:'text/csv', json:'application/json' }[ext] || 'text/plain';
    const blob = new Blob([text], { type: mime + ';charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url; a.download = filename;
    document.body.appendChild(a); a.click();
    document.body.removeChild(a); URL.revokeObjectURL(url);
  };

  const downloadAll = () => {
    files.forEach((f, i) => setTimeout(() => downloadFile(f, outputs[f]), i * 300));
  };

  return (
    <div className="backdrop" onClick={onClose} style={{zIndex:120}}>
      <div className="result-shell" onClick={e => e.stopPropagation()}>
        <div className="result-modal">
          <div className="result-head">
            <div>
              <div className="small-caps" style={{color:'var(--clay)', marginBottom:6}}>§ Pipeline Output</div>
              <div className="result-title">The <em>Finished</em> Work</div>
              <div className="result-sub">{files.length} file{files.length !== 1 ? 's' : ''} generated</div>
            </div>
            <div style={{display:'flex', alignItems:'center', gap:8}}>
              <div className="result-tabs">
                <button className={`result-tab ${mode==='rendered'?'active':''}`} onClick={() => setMode('rendered')}>Rendered</button>
                <button className={`result-tab ${mode==='raw'?'active':''}`} onClick={() => setMode('raw')}>Raw</button>
              </div>
              <button className="result-dl-btn" onClick={() => downloadFile(activeFile, content)}>Export</button>
              {files.length > 1 && (
                <button className="result-dl-btn result-dl-all" onClick={downloadAll}>Export all</button>
              )}
              <button className="crew-close" onClick={onClose}><IcoX/></button>
            </div>
          </div>
          {files.length > 1 && (
            <div className="result-file-row">
              {files.map(f => (
                <button key={f}
                  className={`result-file-chip ${activeFile===f?'active':''}`}
                  onClick={() => setActiveFile(f)}>
                  {f}
                </button>
              ))}
            </div>
          )}
          <div className="result-body scroll">
            {mode === 'rendered'
              ? <div className="result-article" dangerouslySetInnerHTML={{__html: `<p>${renderMd(content)}</p>`}}/>
              : <pre className="result-raw">{content}</pre>}
          </div>
        </div>
      </div>
    </div>
  );
}

window.CLOverlays = { CommandPalette, CrewDrawer, ResultModal };

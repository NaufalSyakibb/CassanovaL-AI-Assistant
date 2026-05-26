/* ============================================================
   Agents, prompts, helpers, markdown
   ============================================================ */
const AGENTS = {
  task: {
    name: 'Alfred', sub: 'Task Manager', hue: 'var(--hue-alfred)',
    issue: 'I.', cluster: 'personal', url: '/alfred',
    tagline: "An unflappable steward of the day's obligations, counted and kept.",
    greeting: 'Good morning. I have your tasks in hand. Shall we bring order to the day, or is there something specific I may see to first?',
    Ico: () => { const {IcoCheck} = window.Icons; return <IcoCheck/>; },
  },
  notes: {
    name: 'Cicero', sub: 'Study Assistant', hue: 'var(--hue-cicero)',
    issue: 'II.', cluster: 'academic', url: '/study',
    tagline: 'Your personal tutor — explains concepts, builds quizzes, creates flashcards, and prepares you for exams.',
    greeting: 'Apa yang ingin kita pelajari hari ini? Aku bisa jelaskan konsep, buatkan soal latihan, atau bantu persiapan ujian.',
    Ico: () => { const {IcoFeather} = window.Icons; return <IcoFeather/>; },
  },
  news: {
    name: 'Najwa', sub: 'News Feed', hue: 'var(--hue-najwa)',
    issue: 'III.', cluster: 'research', url: '/news',
    tagline: 'The morning read, digested. Reportage without the noise.',
    greeting: 'The wires are open. Tell me the subject, the region, or the question — I will bring back a briefing.',
    Ico: () => { const {IcoNewspaper} = window.Icons; return <IcoNewspaper/>; },
  },
  coding: {
    name: 'Linus', sub: 'Code Assistant', hue: 'var(--hue-linus)',
    issue: 'IV.', cluster: 'academic', url: '/coding',
    tagline: 'Pragmatic, occasionally blunt. Debugs the problem, then the assumptions.',
    greeting: 'Show me the code — or describe the failure. I will tell you what it wants.',
    Ico: () => { const {IcoCode} = window.Icons; return <IcoCode/>; },
  },
  schedule: {
    name: 'Miyamoto', sub: 'Schedule', hue: 'var(--hue-miyamoto)',
    issue: 'V.', cluster: 'personal', url: '/productivity',
    tagline: 'A discipline of time — each commitment placed with deliberation.',
    greeting: 'Time is the only estate you cannot reclaim. Tell me how to spend it.',
    Ico: () => { const {IcoCalendar} = window.Icons; return <IcoCalendar/>; },
  },
  budget: {
    name: 'Mansa', sub: 'Finance Dashboard', hue: 'var(--hue-mansa)',
    issue: 'VI.', cluster: 'personal',
    url: '/finance',
    tagline: 'Multi-account wealth tracker — net worth, budgets, portfolio, recurring bills.',
    greeting: 'Every coin has a place in the ledger. Shall we mark one, or take the measure of the month?',
    Ico: () => { const {IcoCoin} = window.Icons; return <IcoCoin/>; },
  },
  fitness: {
    name: 'Lavoisier', sub: 'Fitness & Health', hue: 'var(--hue-lavoiser)',
    issue: 'VII.', cluster: 'personal', url: '/fitness',
    tagline: 'Chemistry of the body — calories, loads, recovery, in balance.',
    greeting: 'The body is a system of inputs and work. What shall we measure today?',
    Ico: () => { const {IcoHeart} = window.Icons; return <IcoHeart/>; },
  },
  journal: {
    name: 'Dostoyevsky', sub: 'Personal Journal', hue: 'var(--hue-dostoy)',
    issue: 'VIII.', cluster: 'personal',
    url: '/journal',
    tagline: 'A confessional page, held without judgment.',
    greeting: 'This page is yours. Begin anywhere. Begin badly, if you must.',
    Ico: () => { const {IcoBook} = window.Icons; return <IcoBook/>; },
  },
  davinci: {
    name: 'Da Vinci', sub: 'Ideas Lab', hue: 'var(--hue-davinci)',
    issue: 'IX.', cluster: 'personal', url: '/davinci',
    tagline: 'A workshop of half-finished inventions and stubborn sketches.',
    greeting: 'Curiosity first. Let us sketch something improbable and see where it leads.',
    Ico: () => { const {IcoLamp} = window.Icons; return <IcoLamp/>; },
  },
  euler: {
    name: 'Euler', sub: 'Math Tutor', hue: 'var(--hue-euler)',
    issue: 'X.', cluster: 'academic',
    tagline: 'Step-by-step from first principles — calculus, linear algebra, statistics, probability.',
    greeting: 'Tunjukkan soalnya. Kita selesaikan langkah demi langkah — tidak ada yang di-skip.',
    Ico: () => { const {IcoChart} = window.Icons; return <IcoChart/>; },
  },
  orwell: {
    name: 'Orwell', sub: 'Writing Coach', hue: 'var(--hue-orwell)',
    issue: 'XI.', cluster: 'academic',
    tagline: 'Clear prose, sharp arguments — essays, reports, emails, or creative writing.',
    greeting: 'Apa yang perlu ditulis? Dari awal, atau ada draft yang perlu dipertajam?',
    Ico: () => { const {IcoFeather} = window.Icons; return <IcoFeather/>; },
  },
  nostradamus: {
    name: 'Nostradamus', sub: 'Prophetic Intelligence', hue: 'var(--hue-nostradamus)',
    issue: 'XII.', cluster: 'research', url: '/nostradamus',
    tagline: 'Five minds, one verdict — predicting what current events foretell.',
    greeting: 'Name the event. Five prophets will read the signs.',
    Ico: () => { const {IcoSparkle} = window.Icons; return <IcoSparkle/>; },
  },
};
const AGENT_ORDER = ['task','notes','news','coding','schedule','budget','fitness','journal','davinci','euler','orwell','nostradamus'];

const AGENT_CLUSTERS = {
  all:      { label: 'All',       accent: 'var(--c-fg)' },
  personal:  { label: 'Personal',  accent: 'var(--hue-alfred)' },
  research:  { label: 'Research',  accent: 'var(--hue-najwa)' },
  academic:  { label: 'Academic',  accent: 'var(--hue-euler)' },
};
const CLUSTER_ORDER = ['all', 'personal', 'research', 'academic'];

const CHIPS = {
  task:     ['Add a task', 'List pending', 'Mark complete', 'Clear done'],
  notes:    ['Jelaskan konsep', 'Buat soal latihan', 'Buat flashcard', 'Ringkasan materi'],
  news:     ['Briefing hari ini', 'World news', 'Tech & AI', 'Indonesia today'],
  coding:   ['Debug this', 'Explain code', 'Suggest fix', 'Write tests'],
  schedule: ["Today's events", 'Add event', 'This week', 'Remove event'],
  budget:   ['Add expense', 'Monthly summary', 'Add income', 'This month'],
  fitness:  ['Log workout', 'Track nutrition', 'My progress', 'Exercise wiki'],
  journal:  ["Today's entry", 'Reflect', 'Vent mode', 'Review the week'],
  davinci:  ['Brainstorm', 'Creative brief', 'Remix an idea', 'Random prompt'],
  euler:    ['Jelaskan integral', 'Soal kalkulus', 'Aljabar linear', 'Statistik & peluang'],
  orwell:   ['Tulis esai', 'Perbaiki teks ini', 'Cover letter', 'Email profesional'],
};

/* ── Formatters ──────────────────────────────────────────── */
const fmtTime = d => new Date(d).toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit', hour12: false });
const fmtDate = s => s ? new Date(s).toLocaleDateString('en-US', { day: 'numeric', month: 'short' }) : '';
const fmtLongDate = () => new Date().toLocaleDateString('en-US', { weekday: 'long', month: 'long', day: 'numeric', year: 'numeric' });
const fmtMoney = n => {
  if (n == null || isNaN(n)) return '—';
  if (n >= 1_000_000) return `${(n/1_000_000).toFixed(1)}M`;
  if (n >= 1_000) return `${(n/1_000).toFixed(0)}K`;
  return String(Math.round(n));
};
const fmtIssue = () => {
  const d = new Date();
  return `Vol. ${d.getFullYear()} · No. ${String(d.getMonth()*30 + d.getDate()).padStart(3,'0')}`;
};

const renderMd = t => {
  if (!t) return '';
  return t
    .replace(/```[\w]*\n([\s\S]*?)```/g, '<pre><code>$1</code></pre>')
    .replace(/`([^`]+)`/g, '<code>$1</code>')
    .replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>')
    .replace(/\*([^*]+)\*/g, '<em>$1</em>')
    .replace(/^### (.+)$/gm, '<h3>$1</h3>')
    .replace(/^## (.+)$/gm, '<h2>$1</h2>')
    .replace(/^- (.+)$/gm, '<li>$1</li>')
    .replace(/(<li>.*<\/li>)/gs, m => `<ul>${m}</ul>`)
    .replace(/<\/ul>\s*<ul>/g, '')
    .replace(/\n\n/g, '</p><p>')
    .replace(/^([^<].+)$/gm, (m) => m.startsWith('<') ? m : m)
    .replace(/\n/g, '<br/>');
};

/* ── API helpers (unchanged — preserve backend contract) ── */
const apiFetch = async (path, opts={}) => {
  const r = await fetch(path, opts);
  if (!r.ok) throw new Error(`HTTP ${r.status}`);
  return r.json();
};
const chatAPI    = (msg, agent) => apiFetch('/api/chat', { method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({ message: msg, agent }) });
const tasksAPI   = () => apiFetch('/api/tasks');
const notesAPI   = () => apiFetch('/api/notes');
const budgetAPI  = () => apiFetch('/api/budget/summary');
const daFilesAPI = () => apiFetch('/api/dataanalyst/files');
const uploadDAAPI= f => { const fd = new FormData(); fd.append('file', f); return apiFetch('/api/dataanalyst/upload', { method:'POST', body: fd }); };
const receiptAPI = f => { const fd = new FormData(); fd.append('file', f); return apiFetch('/api/budget/scan-receipt', { method:'POST', body: fd }); };
const crewKick   = (topic, crew_type, filename, cv_text, platforms, translate, target_lang) => apiFetch('/api/crew/kickoff', { method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({ topic, crew_type, filename, cv_text, platforms, translate, target_lang }) });
const crewPoll   = id => apiFetch(`/api/crew/status/${id}`);
const patternsAPI       = () => apiFetch('/api/alfred/patterns');
const contradictionsAPI = () => apiFetch('/api/alfred/contradictions');
const fitnessDashAPI    = () => apiFetch('/api/fitness/dashboard');
const newsFeedAPI       = () => apiFetch('/api/news/feed');
const journalDashAPI    = () => apiFetch('/api/journal/dashboard');
const intelligenceAPI        = () => apiFetch('/api/alfred/intelligence');
const refreshIntelligenceAPI = () => fetch('/api/alfred/intelligence/refresh', { method: 'POST' }).then(r => r.json());

const SCRAPER_PLATFORMS = [
  { key: 'youtube',    label: 'YouTube' },
  { key: 'tiktok',     label: 'TikTok' },
  { key: 'facebook',   label: 'Facebook' },
  { key: 'instagram',  label: 'Instagram' },
  { key: 'twitter',    label: 'Twitter / X' },
  { key: 'reddit',     label: 'Reddit' },
  { key: 'linkedin',   label: 'LinkedIn' },
  { key: 'medium',     label: 'Medium' },
  { key: 'twitch',     label: 'Twitch' },
  { key: 'pinterest',  label: 'Pinterest' },
  { key: 'quora',      label: 'Quora' },
  { key: 'soundcloud', label: 'SoundCloud' },
];

/* Mock data — used when API offline so the design looks alive */
const MOCK = {
  tStats: { pending: 7, high_priority: 2, completed_today: 4 },
  tasks: [
    { id:1, title:'Draft the Q2 research memo',    status:'pending', priority:'high' },
    { id:2, title:'Review Cicero\'s latest note',   status:'pending', priority:'medium' },
    { id:3, title:'Reply to scheduling request',    status:'pending', priority:'high' },
    { id:4, title:'Refactor data-analyst pipeline', status:'pending', priority:'low' },
    { id:5, title:'Re-read Dostoyevsky entry',      status:'pending', priority:'medium' },
    { id:6, title:'Prepare weekly briefing',        status:'pending', priority:'low' },
  ],
  notes: [
    { id:1, title:'On the architecture of attention', updated_at: new Date(Date.now() - 3600e3).toISOString() },
    { id:2, title:'Fragments — early April',           updated_at: new Date(Date.now() - 86400e3).toISOString() },
    { id:3, title:'Reading list, Q2',                  updated_at: new Date(Date.now() - 2*86400e3).toISOString() },
    { id:4, title:'Letter to J., unsent',              updated_at: new Date(Date.now() - 4*86400e3).toISOString() },
  ],
  notesTotal: 48,
  budget: {
    balance: 18_450_000,
    monthly_income: 22_000_000,
    monthly_expense: 7_320_000,
    recent_transactions: [
      { description:'Monthly salary',        category:'Income',     amount: 22_000_000, type:'income',  date: new Date().toISOString() },
      { description:'Rent, April',           category:'Housing',    amount:  4_500_000, type:'expense', date: new Date(Date.now() - 2*86400e3).toISOString() },
      { description:'Groceries — Market 99', category:'Food',       amount:    620_000, type:'expense', date: new Date(Date.now() - 3*86400e3).toISOString() },
      { description:'Book: "Seeing Like a State"', category:'Books', amount:     315_000, type:'expense', date: new Date(Date.now() - 5*86400e3).toISOString() },
      { description:'Client retainer',       category:'Income',     amount:  5_200_000, type:'income',  date: new Date(Date.now() - 6*86400e3).toISOString() },
    ],
  },
};

window.CLData = {
  AGENTS, AGENT_ORDER, AGENT_CLUSTERS, CLUSTER_ORDER, CHIPS, MOCK,
  SCRAPER_PLATFORMS,
  fmtTime, fmtDate, fmtLongDate, fmtMoney, fmtIssue,
  renderMd,
  chatAPI, tasksAPI, notesAPI, budgetAPI, daFilesAPI,
  uploadDAAPI, receiptAPI, crewKick, crewPoll,
  patternsAPI, contradictionsAPI, fitnessDashAPI, newsFeedAPI, journalDashAPI,
  intelligenceAPI, refreshIntelligenceAPI,
};

/* Dostoyevsky journal — live data adapter.
 * Replaces the standalone design's mock data. Fetches the real journal
 * from /api/journal/dashboard and shapes it into window.JOURNAL_DATA,
 * the structure the editorial redesign app expects. Defines (does NOT
 * auto-run) window.loadJournalData so the bootstrap can await it and the
 * chat handler can refresh after a new entry is written. */
(function () {
  const MONTHS_ID = ['Januari', 'Februari', 'Maret', 'April', 'Mei', 'Juni',
    'Juli', 'Agustus', 'September', 'Oktober', 'November', 'Desember'];
  const DAYS_ID = ['Minggu', 'Senin', 'Selasa', 'Rabu', 'Kamis', 'Jumat', 'Sabtu'];

  function ymd(d) {
    const y = d.getFullYear();
    const m = String(d.getMonth() + 1).padStart(2, '0');
    const day = String(d.getDate()).padStart(2, '0');
    return `${y}-${m}-${day}`;
  }
  function parseDate(s) {
    const [y, m, day] = String(s).split('-').map(Number);
    return new Date(y, (m || 1) - 1, day || 1);
  }
  function dLabel(d) { return `${d.getDate()} ${MONTHS_ID[d.getMonth()]}`; }
  function dayName(d) { return DAYS_ID[d.getDay()]; }

  // Map one API entry into the shape the redesign consumes, deriving the
  // fields the design adds client-side (month_key, month_label, js_date).
  function shape(e) {
    const d = parseDate(e.date);
    return {
      date: e.date,
      date_label: e.date_label || `${d.getDate()} ${MONTHS_ID[d.getMonth()]} ${d.getFullYear()}`,
      day_name: e.day_name || DAYS_ID[d.getDay()],
      month_key: String(e.date).slice(0, 7),
      month_label: `${MONTHS_ID[d.getMonth()]} ${d.getFullYear()}`,
      mood: e.mood || 'unspecified',
      mood_cat: e.mood_cat || 'neutral',
      content: e.content || '',
      preview: e.preview || '',
      word_count: e.word_count || 0,
      emotion: e.emotion || null,
      js_date: d,
    };
  }

  async function load() {
    let api;
    try {
      const res = await fetch('/api/journal/dashboard', { headers: { 'Cache-Control': 'no-cache' } });
      api = await res.json();
    } catch (err) {
      console.error('[journal] dashboard fetch failed:', err);
      api = null;
    }
    api = api || {};
    const entries = (api.entries || []).map(shape);
    const TODAY = new Date();
    TODAY.setHours(0, 0, 0, 0);

    const payload = {
      streak: api.streak || 0,
      total_entries: typeof api.total_entries === 'number' ? api.total_entries : entries.length,
      this_month_count: api.this_month_count || 0,
      today: api.today ? shape(api.today) : (entries[0] || null),
      entries,
      mood_history: api.mood_history || [],
      tags: api.tags || [],
      current_month_label: api.current_month_label || `${MONTHS_ID[TODAY.getMonth()]} ${TODAY.getFullYear()}`,
      emotion_today: api.emotion_today || null,
      TODAY,
      DAYS_ID,
      MONTHS_ID,
      ymd,
      dLabel,
      dayName,
    };

    // Mutate the existing singleton in place so the app's module-level
    // `const D = window.JOURNAL_DATA` reference stays valid across refreshes.
    if (window.JOURNAL_DATA) {
      Object.keys(window.JOURNAL_DATA).forEach((k) => {
        if (!(k in payload)) delete window.JOURNAL_DATA[k];
      });
      Object.assign(window.JOURNAL_DATA, payload);
    } else {
      window.JOURNAL_DATA = payload;
    }
    return window.JOURNAL_DATA;
  }

  window.loadJournalData = load;
})();

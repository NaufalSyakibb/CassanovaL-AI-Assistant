/* Shared "Conversation History" widget — framework-agnostic.
 *
 * Usage on any agent page:
 *   <link rel="stylesheet" href="/static/shared/convo-history.css">
 *   <script src="/static/shared/convo-history.js"></script>
 *   <script>
 *     ConvoHistory.mount({ agent: 'task', label: 'Alfred', accent: '#f5d048' });
 *   </script>
 *
 * `agent` may be a string or a function returning the current agent key
 * (for multi-agent pages). The widget injects a floating button that opens a
 * drawer listing past conversations from /api/conversations/<agent>; clicking
 * one shows the full transcript (read-only). No host-page code is required
 * beyond the mount call.
 */
(function () {
  "use strict";

  var ICONS = {
    history: '<svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.4" stroke-linecap="round" stroke-linejoin="round"><path d="M2.4 8a5.6 5.6 0 1 0 1.7-4"/><path d="M2.2 2.4v3.2h3.2"/><path d="M8 5.2V8l2 1.4"/></svg>',
    back: '<svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M10 3.5 5.5 8 10 12.5"/></svg>'
  };

  function el(tag, cls, text) {
    var n = document.createElement(tag);
    if (cls) n.className = cls;
    if (text != null) n.textContent = text; // textContent = XSS-safe
    return n;
  }

  function resolveAgent(agent) {
    return typeof agent === "function" ? agent() : agent;
  }

  function mount(opts) {
    opts = opts || {};
    var label = opts.label || "Assistant";
    var accent = opts.accent || null;
    var buttonText = opts.buttonText || "History";

    // ── floating trigger button ──────────────────────────────────────────
    var btn = el("button", "cvh-btn");
    btn.type = "button";
    btn.setAttribute("aria-label", "Past conversations");
    btn.innerHTML = ICONS.history;
    btn.appendChild(el("span", null, buttonText));
    if (accent) btn.style.setProperty("--cvh-accent", accent);

    // ── overlay + drawer ─────────────────────────────────────────────────
    var overlay = el("div", "cvh-overlay");
    if (accent) overlay.style.setProperty("--cvh-accent", accent);
    var drawer = el("div", "cvh-drawer");
    overlay.appendChild(drawer);

    var head = el("div", "cvh-head");
    var titles = el("div", "cvh-head-titles");
    var eyebrow = el("div", "cvh-eyebrow", "past conversations");
    var title = el("div", "cvh-title", label);
    titles.appendChild(eyebrow);
    titles.appendChild(title);

    var actions = el("div", "cvh-actions");
    var backBtn = el("button", "cvh-iconbtn");
    backBtn.type = "button";
    backBtn.setAttribute("aria-label", "Back to list");
    backBtn.innerHTML = ICONS.back;
    backBtn.style.display = "none";
    var closeBtn = el("button", "cvh-iconbtn", "×");
    closeBtn.type = "button";
    closeBtn.setAttribute("aria-label", "Close");
    actions.appendChild(backBtn);
    actions.appendChild(closeBtn);

    head.appendChild(titles);
    head.appendChild(actions);

    var body = el("div", "cvh-body");
    drawer.appendChild(head);
    drawer.appendChild(body);

    document.body.appendChild(btn);
    document.body.appendChild(overlay);

    // ── state + rendering ────────────────────────────────────────────────
    var conversations = [];

    function clearBody() { while (body.firstChild) body.removeChild(body.firstChild); }

    function showState(strongText, subText) {
      clearBody();
      var s = el("div", "cvh-state");
      if (strongText) s.appendChild(el("strong", null, strongText));
      if (subText) s.appendChild(document.createTextNode(subText));
      body.appendChild(s);
    }

    function renderList() {
      backBtn.style.display = "none";
      eyebrow.textContent = "past conversations";
      title.textContent = label;
      clearBody();
      if (!conversations.length) {
        showState("No conversations yet", "Chat with " + label + " and they'll appear here.");
        return;
      }
      conversations.forEach(function (c) {
        var card = el("button", "cvh-card");
        card.type = "button";
        var top = el("div", "cvh-card-top");
        top.appendChild(el("span", "cvh-card-date", (c.date_label || "") + " · " + (c.time || "")));
        var n = c.turn_count || 0;
        top.appendChild(el("span", "cvh-card-count", n + (n === 1 ? " turn" : " turns")));
        card.appendChild(top);
        card.appendChild(el("div", "cvh-card-title", c.title || "Conversation"));
        card.addEventListener("click", function () { renderTranscript(c); });
        body.appendChild(card);
      });
    }

    function renderTranscript(c) {
      backBtn.style.display = "";
      eyebrow.textContent = (c.date_label || "") + " · " + (c.time || "");
      title.textContent = label;
      clearBody();
      (c.messages || []).forEach(function (m) {
        var wrap = el("div", "cvh-msg " + (m.role === "user" ? "cvh-user" : "cvh-agent"));
        wrap.appendChild(el("div", "cvh-msg-meta", (m.role === "user" ? "you" : label.toLowerCase()) + " · " + (m.time || "")));
        wrap.appendChild(el("div", "cvh-bubble", m.text || ""));
        body.appendChild(wrap);
      });
      body.scrollTop = 0;
    }

    function load() {
      var agent = resolveAgent(opts.agent);
      if (!agent) { showState("No agent selected", null); return; }
      showState(null, "Loading…");
      fetch("/api/conversations/" + encodeURIComponent(agent), { headers: { "Cache-Control": "no-cache" } })
        .then(function (r) { return r.json(); })
        .then(function (data) {
          conversations = (data && Array.isArray(data.conversations)) ? data.conversations : [];
          renderList();
        })
        .catch(function (e) {
          showState("Couldn't load history", String(e && e.message || e));
        });
    }

    // ── open / close ─────────────────────────────────────────────────────
    function open() {
      overlay.style.display = "block";
      // force reflow so the transition runs
      void overlay.offsetWidth;
      overlay.classList.add("cvh-open");
      document.addEventListener("keydown", onKey);
      load();
    }
    function close() {
      overlay.classList.remove("cvh-open");
      document.removeEventListener("keydown", onKey);
      setTimeout(function () { overlay.style.display = "none"; }, 220);
    }
    function onKey(e) { if (e.key === "Escape") close(); }

    overlay.style.display = "none";
    btn.addEventListener("click", open);
    closeBtn.addEventListener("click", close);
    backBtn.addEventListener("click", renderList);
    overlay.addEventListener("click", function (e) { if (e.target === overlay) close(); });

    return { open: open, close: close, reload: load };
  }

  window.ConvoHistory = { mount: mount };
})();

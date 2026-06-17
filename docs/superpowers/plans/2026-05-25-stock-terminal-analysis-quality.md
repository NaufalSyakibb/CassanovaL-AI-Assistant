# Stock Terminal — Analysis Quality Upgrade Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a TechnicalAnalyst agent and feed live RSI/MACD/BB/support/resistance data into Strategy and FinalVerdict so entry zones are anchored to real technical levels, not LLM guesses.

**Architecture:** Call `get_technical_indicators()` directly after DeepResearch (no LLM, pure yfinance math), then run NewsIntelligence and a new TechnicalAnalyst agent in parallel. Both results flow into Strategy and FinalVerdict as enriched context. A new TECHNICALS tab in the terminal frontend displays the raw indicators and narrative analysis.

**Tech Stack:** Python (LangChain/LangGraph, yfinance), FastAPI SSE, vanilla JS (no build step), pytest with unittest.mock

---

## File Map

| File | Change |
|------|--------|
| `tools/stock_tools.py` | Fix `bg="#000000"` → `"#0a0a0f"` in `build_candlestick_json` and `build_heatmap_json` |
| `agents/stock_agents.py` | Add `_TECHNICAL_ANALYST_PROMPT`, `run_technical_analyst()`; update `run_strategy()` and `run_final_verdict()` signatures and prompts |
| `server.py` | Add Phase 1.5 (direct tool call), parallel Phase 2, updated Strategy/FinalVerdict calls, new SSE events |
| `static/CassanovaL Terminal v2.html` | Add TechnicalAnalyst agent row, TECHNICALS tab + panel, JS handlers, BuyTiming signals display |
| `tests/test_stock_tools.py` | Passes automatically after color fix (no edits needed) |
| `tests/test_stock_agents.py` | Add `test_run_technical_analyst_returns_expected_keys`; update `test_run_strategy_*` and `test_run_final_verdict_*` for new params |

---

## Task 1: Fix candlestick and heatmap background color

**Files:**
- Modify: `tools/stock_tools.py` (lines 456, 562, 579)
- Test: `tests/test_stock_tools.py` (no edits — test passes after fix)

- [ ] **Step 1: Run the failing test to confirm the baseline**

```powershell
cd "c:\Users\muham\OneDrive\Dokumen\Python\ai_python"
pytest tests/test_stock_tools.py::test_build_candlestick_json_structure -v
```
Expected: FAIL — `assert '#000000' == '#0a0a0f'`

- [ ] **Step 2: Fix the three color constants in `tools/stock_tools.py`**

Change line 456 (inside `build_candlestick_json`):
```python
# Before:
    bg = "#000000"
# After:
    bg = "#0a0a0f"
```

Change line 562 (inside `build_heatmap_json`, the empty-corr fallback):
```python
# Before:
                "paper_bgcolor": "#000000",
# After:
                "paper_bgcolor": "#0a0a0f",
```

Change line 579 (inside `build_heatmap_json`, normal path):
```python
# Before:
    bg = "#000000"
# After:
    bg = "#0a0a0f"
```

- [ ] **Step 3: Run the test to confirm it passes**

```powershell
pytest tests/test_stock_tools.py::test_build_candlestick_json_structure -v
```
Expected: PASS

- [ ] **Step 4: Run the full stock tools test suite**

```powershell
pytest tests/test_stock_tools.py -v
```
Expected: all pass (no regressions)

- [ ] **Step 5: Commit**

```powershell
git add tools/stock_tools.py
git commit -m "fix(stock): candlestick/heatmap paper_bgcolor #000000 → #0a0a0f"
```

---

## Task 2: Add `run_technical_analyst` to agents/stock_agents.py

**Files:**
- Modify: `agents/stock_agents.py`
- Test: `tests/test_stock_agents.py`

- [ ] **Step 1: Write the failing test in `tests/test_stock_agents.py`**

Add this test at the end of the file:

```python
# ── run_technical_analyst ──────────────────────────────────────

def test_run_technical_analyst_returns_expected_keys():
    from agents.stock_agents import run_technical_analyst
    fake_out = {
        "trend_assessment": "Tren bullish — harga di atas MA20, MA50, MA200",
        "momentum_reading": "RSI 38 mendekati oversold, MACD bullish crossover",
        "key_levels": "Support 60d: 9,200 — Resistance 60d: 10,500",
        "entry_quality": "good",
    }
    tech_data = {
        "ticker": "BBCA.JK",
        "rsi_14": 38.0,
        "rsi_status": "approaching_oversold",
        "macd_signal": "bullish_crossover",
        "macd_histogram": 0.12,
        "bb_position": "near_lower_band",
        "support_60d": 9200.0,
        "resistance_60d": 10500.0,
        "cross_signal": None,
        "volume_trend": "expanding",
        "current_price": 9750.0,
    }

    with patch("agents.stock_agents.build_agent") as mock_build:
        mock_agent = MagicMock()
        mock_agent.invoke.return_value = _fake_agent_result(fake_out)
        mock_build.return_value = mock_agent
        result = run_technical_analyst("BBCA.JK", tech_data)

    assert "trend_assessment" in result
    assert "momentum_reading" in result
    assert "key_levels" in result
    assert result["entry_quality"] in ("good", "neutral", "poor")
```

- [ ] **Step 2: Run the test to confirm it fails**

```powershell
pytest tests/test_stock_agents.py::test_run_technical_analyst_returns_expected_keys -v
```
Expected: FAIL — `ImportError: cannot import name 'run_technical_analyst'`

- [ ] **Step 3: Add `_TECHNICAL_ANALYST_PROMPT` constant in `agents/stock_agents.py`**

Insert after `_FINAL_VERDICT_PROMPT` (after line 147, before `def run_deep_research`):

```python
_TECHNICAL_ANALYST_PROMPT = """Kamu adalah TechnicalAnalyst Agent — spesialis analisis teknikal yang membaca data indikator secara kuantitatif dan tepat.
Kamu menerima data teknikal terstruktur (RSI, MACD, Bollinger Bands, Moving Averages, support/resistance, volume) sebagai konteks dalam pesan.
Tugasmu: Baca data tersebut dan hasilkan narasi analisis teknikal yang terse, kuantitatif, dan actionable dalam Bahasa Indonesia profesional.

Kembalikan HANYA JSON dengan format berikut (tanpa teks lain):
{
  "trend_assessment": "tren keseluruhan — bullish/bearish/ranging dengan penjelasan berdasarkan MA dan cross_signal",
  "momentum_reading": "kondisi momentum berdasarkan RSI dan MACD — apakah oversold/overbought/netral dengan angka aktual",
  "key_levels": "narasi support dan resistance spesifik berdasarkan support_60d dan resistance_60d dengan harga aktual",
  "entry_quality": "good|neutral|poor"
}

entry_quality:
  good    → RSI oversold atau approaching_oversold DAN MACD bullish, ATAU bb_position at_lower_band/near_lower_band
  poor    → RSI overbought atau approaching_overbought, ATAU bb_position at_upper_band, ATAU death_cross aktif
  neutral → kondisi selain di atas

Semua klaim HARUS merujuk angka aktual dari data yang diberikan. Jangan mengarang angka.
"""
```

- [ ] **Step 4: Add `run_technical_analyst` function in `agents/stock_agents.py`**

Insert after `run_news_intelligence` function (after line 163):

```python
def run_technical_analyst(ticker: str, technical_data: dict) -> dict:
    agent = build_agent(_TECHNICAL_ANALYST_PROMPT, [])
    context = json.dumps({
        "ticker":         ticker,
        "rsi_14":         technical_data.get("rsi_14"),
        "rsi_status":     technical_data.get("rsi_status"),
        "macd_signal":    technical_data.get("macd_signal"),
        "macd_histogram": technical_data.get("macd_histogram"),
        "bb_position":    technical_data.get("bb_position"),
        "price_vs_ma20":  technical_data.get("price_vs_ma20"),
        "price_vs_ma50":  technical_data.get("price_vs_ma50"),
        "price_vs_ma200": technical_data.get("price_vs_ma200"),
        "cross_signal":   technical_data.get("cross_signal"),
        "support_60d":    technical_data.get("support_60d"),
        "resistance_60d": technical_data.get("resistance_60d"),
        "volume_trend":   technical_data.get("volume_trend"),
        "current_price":  technical_data.get("current_price"),
    }, ensure_ascii=False)
    result = _invoke_with_retry(agent, {
        "messages": [{"role": "user", "content": f"Analisis teknikal untuk {ticker} berdasarkan data ini: {context}"}]
    })
    return _parse_json_output(result)
```

- [ ] **Step 5: Run the test to confirm it passes**

```powershell
pytest tests/test_stock_agents.py::test_run_technical_analyst_returns_expected_keys -v
```
Expected: PASS

- [ ] **Step 6: Run the full agents test suite**

```powershell
pytest tests/test_stock_agents.py -v
```
Expected: all existing tests pass + new test passes

- [ ] **Step 7: Commit**

```powershell
git add agents/stock_agents.py tests/test_stock_agents.py
git commit -m "feat(stock): add TechnicalAnalyst agent — RSI/MACD/BB narrative from pre-computed data"
```

---

## Task 3: Update `run_strategy` to accept technical data

**Files:**
- Modify: `agents/stock_agents.py` (`_STRATEGY_PROMPT` constant + `run_strategy` function)
- Test: `tests/test_stock_agents.py` (update existing strategy tests)

- [ ] **Step 1: Update `test_run_strategy_returns_expected_keys` to pass new params**

The test currently calls `run_strategy(dr, ni)`. Update it so it also passes the two new optional params (they are `None` by default, so this just validates backward compat too):

```python
def test_run_strategy_returns_expected_keys():
    from agents.stock_agents import run_strategy
    fake_out = {
        "entry_zone": "9500-9800",
        "exit_target": "11000",
        "stop_loss": "9000",
        "stop_loss_pct": 5.0,
        "time_horizon": "medium",
        "time_horizon_detail": "3-6 bulan",
        "position_size": "5%",
        "risk_reward_ratio": "1:3.0",
        "rationale": "Support kuat di 9500, RSI 38 approaching oversold",
    }
    dr = {"summary": "ok", "ohlcv": {}, "current_price": 9700.0}
    ni = {"summary": "ok", "sentiment_score": 0.5}
    ta = {"trend_assessment": "bullish", "momentum_reading": "RSI 38", "key_levels": "support 9200", "entry_quality": "good"}
    td = {"support_60d": 9200.0, "resistance_60d": 10500.0, "rsi_14": 38.0, "rsi_status": "approaching_oversold"}

    with patch("agents.stock_agents.build_agent") as mock_build:
        mock_agent = MagicMock()
        mock_agent.invoke.return_value = _fake_agent_result(fake_out)
        mock_build.return_value = mock_agent
        result = run_strategy(dr, ni, ta, td)

    assert "entry_zone" in result
    assert "exit_target" in result
    assert "stop_loss" in result
    assert "risk_reward_ratio" in result
```

Also update `test_run_strategy_strips_ohlcv_from_context` — replace `run_strategy(dr, ni)` with `run_strategy(dr, ni, {}, {})`:

```python
        run_strategy(dr, ni, {}, {})
```

- [ ] **Step 2: Run the tests to confirm current state (should still pass with old implementation)**

```powershell
pytest tests/test_stock_agents.py::test_run_strategy_returns_expected_keys tests/test_stock_agents.py::test_run_strategy_strips_ohlcv_from_context -v
```

- [ ] **Step 3: Update `_STRATEGY_PROMPT` in `agents/stock_agents.py`**

Replace the existing `_STRATEGY_PROMPT` with:

```python
_STRATEGY_PROMPT = """Kamu adalah Strategy Agent — ahli strategi trading yang terinspirasi dari metodologi ValueCell.
Kamu menerima output dari DeepResearch, NewsIntelligence, TechnicalAnalyst, dan data teknikal mentah sebagai konteks dalam pesan.
Tugasmu: Berdasarkan analisis fundamental, teknikal, dan sentimen, susun strategi trading yang konkret dan actionable dalam Bahasa Indonesia profesional.

PENTING — jika technical_data tersedia (support_60d dan resistance_60d bukan null):
- entry_zone HARUS mencakup nilai support_60d aktual dari technical_data
- stop_loss HARUS ditetapkan di bawah support_60d (untuk sinyal beli) atau di atas resistance_60d (untuk sinyal jual)
- Gunakan cross_signal dan bb_position untuk menentukan kualitas entry

Kembalikan HANYA JSON dengan format berikut (tanpa teks lain):
{
  "entry_zone": "zona harga entry berdasarkan support_60d aktual (mis. 9200-9500)",
  "exit_target": "target harga keluar berdasarkan resistance_60d dan target analis",
  "stop_loss": "level stop loss di bawah support_60d",
  "stop_loss_pct": 0.0,
  "time_horizon": "short|medium|long",
  "time_horizon_detail": "estimasi durasi investasi (mis. 3-6 bulan)",
  "position_size": "rekomendasi % portofolio (mis. 5%)",
  "risk_reward_ratio": "rasio risk/reward (mis. 1:3.5)",
  "rationale": "1-2 kalimat alasan strategi berdasarkan data teknikal dan fundamental"
}

time_horizon: gunakan short (< 1 bulan), medium (1-6 bulan), atau long (> 6 bulan).
stop_loss_pct: persentase penurunan dari entry price sebagai stop loss (angka positif).
"""
```

- [ ] **Step 4: Update `run_strategy` signature and context in `agents/stock_agents.py`**

Replace the existing `run_strategy` function:

```python
def run_strategy(deep_research: dict, news_intelligence: dict,
                 technical_analyst: dict = None, technical_data: dict = None) -> dict:
    agent = build_agent(_STRATEGY_PROMPT, [])
    td = technical_data or {}
    context = json.dumps({
        "deep_research":     {k: v for k, v in deep_research.items() if k != "ohlcv"},
        "news_intelligence": news_intelligence,
        "technical_analyst": technical_analyst or {},
        "technical_data": {
            "rsi_14":         td.get("rsi_14"),
            "rsi_status":     td.get("rsi_status"),
            "macd_signal":    td.get("macd_signal"),
            "bb_position":    td.get("bb_position"),
            "support_60d":    td.get("support_60d"),
            "resistance_60d": td.get("resistance_60d"),
            "cross_signal":   td.get("cross_signal"),
            "volume_trend":   td.get("volume_trend"),
        },
    }, ensure_ascii=False)
    result = _invoke_with_retry(agent, {
        "messages": [{"role": "user", "content": f"Susun strategi trading berdasarkan data ini: {context}"}]
    })
    return _parse_json_output(result)
```

- [ ] **Step 5: Run the strategy tests to confirm they pass**

```powershell
pytest tests/test_stock_agents.py::test_run_strategy_returns_expected_keys tests/test_stock_agents.py::test_run_strategy_strips_ohlcv_from_context -v
```
Expected: both PASS

- [ ] **Step 6: Commit**

```powershell
git add agents/stock_agents.py tests/test_stock_agents.py
git commit -m "feat(stock): run_strategy accepts technical_analyst + technical_data — entry zones anchored to real support/resistance"
```

---

## Task 4: Update `run_final_verdict` to accept technical data

**Files:**
- Modify: `agents/stock_agents.py` (`run_final_verdict` function)
- Test: `tests/test_stock_agents.py` (update existing verdict test)

- [ ] **Step 1: Update `test_run_final_verdict_returns_expected_keys` to pass new params**

Replace the existing test:

```python
def test_run_final_verdict_returns_expected_keys():
    from agents.stock_agents import run_final_verdict
    fake_out = {
        "executive_summary": "saham menarik",
        "fundamental_analysis": "fundamental solid",
        "sentiment_macro": "berita positif",
        "risk_assessment": ["Risiko 1", "Risiko 2"],
        "counter_arguments": "valuasi sudah mahal",
        "bull_case": ["Pertumbuhan kuat"],
        "bear_case": ["Tekanan margin"],
        "verdict": "BUY",
        "conviction_score": 7,
        "risk_reward": "1:3.5",
        "investment_memo": "Tesis investasi solid",
    }
    dr = {"summary": "ok", "ohlcv": {}}
    ni = {"summary": "ok", "sentiment_score": 0.5}
    st = {"entry_zone": "9200-9500", "exit_target": "10500"}
    ta = {"trend_assessment": "bullish", "entry_quality": "good"}
    td = {"support_60d": 9200.0, "resistance_60d": 10500.0}

    with patch("agents.stock_agents.build_agent") as mock_build:
        mock_agent = MagicMock()
        mock_agent.invoke.return_value = _fake_agent_result(fake_out)
        mock_build.return_value = mock_agent
        result = run_final_verdict("BBCA.JK", dr, ni, st, ta, td)

    assert result["verdict"] in ("BUY", "HOLD", "SELL")
    assert isinstance(result["conviction_score"], int)
    assert "bull_case" in result
    assert "bear_case" in result
    assert "investment_memo" in result
```

- [ ] **Step 2: Run the test to confirm it fails with new signature**

```powershell
pytest tests/test_stock_agents.py::test_run_final_verdict_returns_expected_keys -v
```
Expected: FAIL — `TypeError: run_final_verdict() takes 4 positional arguments but 6 were given`

- [ ] **Step 3: Update `run_final_verdict` in `agents/stock_agents.py`**

Replace the existing function:

```python
def run_final_verdict(ticker: str, deep_research: dict, news_intelligence: dict,
                      strategy: dict, technical_analyst: dict = None,
                      technical_data: dict = None) -> dict:
    agent = build_agent(_FINAL_VERDICT_PROMPT, [])
    td = technical_data or {}
    combined = json.dumps({
        "ticker":               ticker,
        "deep_research":        {k: v for k, v in deep_research.items() if k != "ohlcv"},
        "news_intelligence":    news_intelligence,
        "strategy":             strategy,
        "technical_analyst":    technical_analyst or {},
        "technical_support":    td.get("support_60d"),
        "technical_resistance": td.get("resistance_60d"),
        "rsi_status":           td.get("rsi_status"),
    }, ensure_ascii=False)
    result = _invoke_with_retry(agent, {
        "messages": [{"role": "user", "content": f"Buat laporan investasi final: {combined}"}]
    })
    return _parse_json_output(result)
```

- [ ] **Step 4: Run the verdict test to confirm it passes**

```powershell
pytest tests/test_stock_agents.py::test_run_final_verdict_returns_expected_keys -v
```
Expected: PASS

- [ ] **Step 5: Run the full test suite to confirm no regressions**

```powershell
pytest tests/test_stock_agents.py tests/test_stock_tools.py -v
```
Expected: all pass

- [ ] **Step 6: Commit**

```powershell
git add agents/stock_agents.py tests/test_stock_agents.py
git commit -m "feat(stock): run_final_verdict accepts technical_analyst + technical_data context"
```

---

## Task 5: Update `server.py` SSE endpoint

**Files:**
- Modify: `server.py` (lines 1254–1333, the `/api/stock/analyze` SSE generator)

- [ ] **Step 1: Update the imports inside `generate()` (line 1255)**

Change:
```python
            from agents.stock_agents import (
                run_deep_research, run_news_intelligence,
                run_strategy, run_final_verdict, run_buy_timing,
            )
```
To:
```python
            from agents.stock_agents import (
                run_deep_research, run_news_intelligence, run_technical_analyst,
                run_strategy, run_final_verdict, run_buy_timing,
            )
            from tools.stock_tools import get_technical_indicators
```

(Note: `get_technical_indicators` import moves up here from the existing `from tools.stock_tools import build_candlestick_json ...` line — keep the build imports on that line too.)

- [ ] **Step 2: Add Phase 1.5 after DeepResearch (after line 1268)**

After the line `yield _sse({"event": "step", "agent": "DeepResearch", "status": "done"})`, insert:

```python
            # ── Phase 1.5: Technical Indicators (direct call, no LLM) ─────
            try:
                tech_raw = get_technical_indicators.invoke({"ticker": ticker})
                technical_data = json.loads(tech_raw) if isinstance(tech_raw, str) else tech_raw
            except Exception:
                technical_data = {}
            yield _sse({"event": "technicals", "data": technical_data})
```

- [ ] **Step 3: Replace Phase 2 (sequential NewsIntelligence) with parallel Phase 2**

Replace the existing Phase 2 block (lines 1295–1303):

```python
            # ── Phase 2: NewsIntelligence ─────────────────────────────────
            yield _sse({"event": "step", "agent": "NewsIntelligence", "status": "running"})
            news_data = await _run_agent(loop, run_news_intelligence, ticker)
            sentiment  = news_data.get("sentiment_score", "N/A")
            event_type = news_data.get("event_type", "N/A")
            yield _sse({"event": "log", "text": f"Sentimen: {sentiment} | Event: {event_type}"})
            yield _sse({"event": "step", "agent": "NewsIntelligence", "status": "done"})

            await asyncio.sleep(5)
```

With:

```python
            await asyncio.sleep(5)

            # ── Phase 2: NewsIntelligence + TechnicalAnalyst (parallel) ───
            yield _sse({"event": "step", "agent": "NewsIntelligence", "status": "running"})
            yield _sse({"event": "step", "agent": "TechnicalAnalyst", "status": "running"})
            news_data, technical_analyst_data = await asyncio.gather(
                _run_agent(loop, run_news_intelligence, ticker),
                _run_agent(loop, run_technical_analyst, ticker, technical_data),
            )
            sentiment  = news_data.get("sentiment_score", "N/A")
            event_type = news_data.get("event_type", "N/A")
            yield _sse({"event": "log", "text": f"Sentimen: {sentiment} | Event: {event_type}"})
            yield _sse({"event": "step", "agent": "NewsIntelligence", "status": "done"})
            trend = str(technical_analyst_data.get("trend_assessment", ""))[:60]
            yield _sse({"event": "log", "text": f"Teknikal: {trend}"})
            yield _sse({"event": "step", "agent": "TechnicalAnalyst", "status": "done"})
            yield _sse({"event": "technicals_analysis", "data": technical_analyst_data})

            await asyncio.sleep(5)
```

- [ ] **Step 4: Update Phase 3 (Strategy) call to pass technical context**

Change line 1307:
```python
            strategy_data = await _run_agent(loop, run_strategy, deep_research_data, news_data)
```
To:
```python
            strategy_data = await _run_agent(
                loop, run_strategy, deep_research_data, news_data,
                technical_analyst_data, technical_data,
            )
```

- [ ] **Step 5: Update Phase 4 (FinalVerdict) call to pass technical context**

Change lines 1318–1320:
```python
            verdict_data = await _run_agent(
                loop, run_final_verdict, ticker, deep_research_data, news_data, strategy_data
            )
```
To:
```python
            verdict_data = await _run_agent(
                loop, run_final_verdict, ticker, deep_research_data, news_data,
                strategy_data, technical_analyst_data, technical_data,
            )
```

- [ ] **Step 6: Verify the server starts without error**

```powershell
$env:PYTHONUTF8=1; python -c "import server; print('server imports OK')"
```
Expected: `server imports OK`

- [ ] **Step 7: Commit**

```powershell
git add server.py
git commit -m "feat(stock): Phase 1.5 direct technical indicators + parallel Phase 2 with TechnicalAnalyst"
```

---

## Task 6: Update frontend HTML

**Files:**
- Modify: `static/CassanovaL Terminal v2.html`

The file is one large HTML file. All changes are additive (new HTML blocks + new JS functions). Read the file before editing to confirm line numbers match.

- [ ] **Step 1: Add TechnicalAnalyst agent row after NewsIntelligence row**

Find the NewsIntelligence `</div>` closing tag (currently lines 390–397):
```html
      <div class="arow" id="r-NewsIntelligence">
        ...
        <div class="aright" id="rt-NewsIntelligence">IDLE</div>
      </div>
```

Insert immediately after it:
```html
      <div class="arow" id="r-TechnicalAnalyst">
        <div class="astatus"></div>
        <div>
          <div class="aname">TECHNICALANALYST</div>
          <div class="adesc">RSI · MACD · Bollinger · Support/Resistance</div>
        </div>
        <div class="aright" id="rt-TechnicalAnalyst">IDLE</div>
      </div>
```

- [ ] **Step 2: Add TECHNICALS tab button in tabbar**

Find the tabbar (lines 434–440):
```html
    <div id="tabbar">
      <button class="tbtn on" data-t="summary">F1 SUMMARY...
      <button class="tbtn" data-t="strategy">F2 STRATEGY...
      <button class="tbtn" data-t="charts">F3 CHARTS...
```

Insert a new button after F2 STRATEGY (before F3 CHARTS):
```html
      <button class="tbtn" data-t="technicals">T TECHNICALS<span class="tdot" id="d-technicals"></span></button>
```

- [ ] **Step 3: Add TECHNICALS tab panel after the STRATEGY panel**

Find the closing `</div>` of the STRATEGY tab panel (`id="tc-strategy"`). After it, insert:

```html
    <!-- TECHNICALS -->
    <div class="tc" id="tc-technicals">
      <div id="tech-ph" style="flex:1;display:flex;align-items:center;justify-content:center;color:var(--border2);font-size:11px;letter-spacing:1px">TECHNICALANALYST NOT YET RUN</div>
      <div id="tech-body" style="display:none;padding:12px;overflow-y:auto">
        <!-- Indicator cards row -->
        <div style="display:grid;grid-template-columns:repeat(5,1fr);gap:8px;margin-bottom:16px">
          <div class="strat-block" style="margin:0">
            <div class="sb-hdr or">RSI 14</div>
            <div class="sb-body">
              <div class="big-val" id="ti-rsi" style="font-size:22px">—</div>
              <div class="big-sub" id="ti-rsi-status">—</div>
            </div>
          </div>
          <div class="strat-block" style="margin:0">
            <div class="sb-hdr">MACD</div>
            <div class="sb-body">
              <div class="big-val" id="ti-macd" style="font-size:14px">—</div>
              <div class="big-sub" id="ti-macd-hist">—</div>
            </div>
          </div>
          <div class="strat-block" style="margin:0">
            <div class="sb-hdr cy">BOLLINGER</div>
            <div class="sb-body">
              <div class="big-val cy" id="ti-bb" style="font-size:13px">—</div>
              <div class="big-sub">BAND POSITION</div>
            </div>
          </div>
          <div class="strat-block" style="margin:0">
            <div class="sb-hdr gr">MA ALIGNMENT</div>
            <div class="sb-body">
              <div class="big-val" id="ti-cross" style="font-size:13px">—</div>
              <div class="big-sub" id="ti-ma20">—</div>
            </div>
          </div>
          <div class="strat-block" style="margin:0">
            <div class="sb-hdr">VOLUME</div>
            <div class="sb-body">
              <div class="big-val" id="ti-vol" style="font-size:16px">—</div>
              <div class="big-sub" id="ti-vol-ratio">—</div>
            </div>
          </div>
        </div>
        <!-- Support / Resistance -->
        <div style="display:grid;grid-template-columns:1fr 1fr;gap:8px;margin-bottom:16px">
          <div class="strat-block" style="margin:0">
            <div class="sb-hdr gr">SUPPORT 60D</div>
            <div class="sb-body"><div class="big-val gr" id="ti-sup">—</div><div class="big-sub">FLOOR LEVEL</div></div>
          </div>
          <div class="strat-block" style="margin:0">
            <div class="sb-hdr re">RESISTANCE 60D</div>
            <div class="sb-body"><div class="big-val re" id="ti-res">—</div><div class="big-sub">CEILING LEVEL</div></div>
          </div>
        </div>
        <!-- TechnicalAnalyst narrative -->
        <div id="tech-narrative" style="display:none">
          <div class="strat-block full" style="margin:0 0 8px 0">
            <div class="sb-hdr">TREND ASSESSMENT</div>
            <div class="sb-body" id="ti-trend" style="font-size:11px;color:var(--gray2);line-height:1.7"></div>
          </div>
          <div class="strat-block full" style="margin:0 0 8px 0">
            <div class="sb-hdr cy">MOMENTUM</div>
            <div class="sb-body" id="ti-momentum" style="font-size:11px;color:var(--gray2);line-height:1.7"></div>
          </div>
          <div class="strat-block full" style="margin:0 0 8px 0">
            <div class="sb-hdr gr">KEY LEVELS</div>
            <div class="sb-body" id="ti-levels" style="font-size:11px;color:var(--gray2);line-height:1.7"></div>
          </div>
          <div class="strat-block" style="margin:0">
            <div class="sb-hdr">ENTRY QUALITY</div>
            <div class="sb-body"><div class="big-val" id="ti-eq">—</div><div class="big-sub">TECHNICAL ENTRY SIGNAL</div></div>
          </div>
        </div>
      </div>
    </div>
```

- [ ] **Step 4: Add BuyTiming technical_signals block in the STRATEGY panel**

Find the `tim-rat-block` closing div inside `tc-strategy` (after the DCA plan block around line 583). Insert after it:

```html
        <div class="strat-block full" id="tech-confirm-block" style="display:none">
          <div class="sb-hdr cy">TECHNICAL CONFIRMATION <span style="color:var(--gray)">BUYTIMING</span></div>
          <div class="sb-body" id="s-techconf" style="font-size:10px;color:var(--gray2);line-height:1.9;font-family:inherit"></div>
        </div>
```

- [ ] **Step 5: Add JavaScript functions `G.renderTechnicalsData` and `G.renderTechnicalsAnalysis`**

Find the existing `G.renderTiming` function (around line 767). Insert these two functions before it:

```javascript
G.renderTechnicalsData=function(d){
  var ph=G.$('tech-ph'),bd=G.$('tech-body');
  if(ph)ph.style.display='none';
  if(bd)bd.style.display='';

  // RSI
  var rsi=d.rsi_14!=null?d.rsi_14.toFixed(1):'—';
  var rsiStatus=(d.rsi_status||'neutral').replace(/_/g,' ').toUpperCase();
  var rsiCol=d.rsi_14<=30?'var(--green)':d.rsi_14>=70?'var(--red)':'var(--orange)';
  if(G.$('ti-rsi')){G.$('ti-rsi').textContent=rsi;G.$('ti-rsi').style.color=rsiCol;}
  if(G.$('ti-rsi-status')){G.$('ti-rsi-status').textContent=rsiStatus;G.$('ti-rsi-status').style.color=rsiCol;}

  // MACD
  var macdSig=(d.macd_signal||'').replace(/_/g,' ').toUpperCase();
  var macdCol=macdSig.indexOf('BULL')>=0?'var(--green)':macdSig.indexOf('BEAR')>=0?'var(--red)':'var(--gray2)';
  if(G.$('ti-macd')){G.$('ti-macd').textContent=macdSig||'—';G.$('ti-macd').style.color=macdCol;}
  if(G.$('ti-macd-hist')){
    var h=d.macd_histogram!=null?'HIST '+d.macd_histogram.toFixed(3):'—';
    G.$('ti-macd-hist').textContent=h;
  }

  // Bollinger
  var bbPos=(d.bb_position||'mid_range').replace(/_/g,' ').toUpperCase();
  var bbCol=bbPos.indexOf('LOWER')>=0?'var(--green)':bbPos.indexOf('UPPER')>=0?'var(--red)':'var(--cyan)';
  if(G.$('ti-bb')){G.$('ti-bb').textContent=bbPos;G.$('ti-bb').style.color=bbCol;}

  // MA / cross signal
  var cross=(d.cross_signal||'none').replace(/_/g,' ').toUpperCase();
  var crossCol=cross.indexOf('GOLDEN')>=0?'var(--green)':cross.indexOf('DEATH')>=0?'var(--red)':'var(--gray2)';
  if(G.$('ti-cross')){G.$('ti-cross').textContent=cross==='NONE'?'NO CROSS':cross;G.$('ti-cross').style.color=crossCol;}
  if(G.$('ti-ma20'))G.$('ti-ma20').textContent=d.price_vs_ma20?'VS MA20: '+d.price_vs_ma20:'—';

  // Volume
  var volT=(d.volume_trend||'neutral').toUpperCase();
  var volCol=volT==='EXPANDING'?'var(--green)':volT==='CONTRACTING'?'var(--red)':'var(--gray2)';
  if(G.$('ti-vol')){G.$('ti-vol').textContent=volT;G.$('ti-vol').style.color=volCol;}
  if(G.$('ti-vol-ratio'))G.$('ti-vol-ratio').textContent=d.volume_ratio!=null?'RATIO '+d.volume_ratio.toFixed(2)+'x':'—';

  // Support / Resistance
  if(G.$('ti-sup'))G.$('ti-sup').textContent=d.support_60d!=null?d.support_60d.toLocaleString('id-ID'):'—';
  if(G.$('ti-res'))G.$('ti-res').textContent=d.resistance_60d!=null?d.resistance_60d.toLocaleString('id-ID'):'—';

  G.$('d-technicals').classList.add('v');
};
G.renderTechnicalsAnalysis=function(a){
  var nar=G.$('tech-narrative');
  if(nar)nar.style.display='';
  if(G.$('ti-trend'))G.$('ti-trend').textContent=a.trend_assessment||'—';
  if(G.$('ti-momentum'))G.$('ti-momentum').textContent=a.momentum_reading||'—';
  if(G.$('ti-levels'))G.$('ti-levels').textContent=a.key_levels||'—';
  var eq=(a.entry_quality||'neutral').toUpperCase();
  var eqCol=eq==='GOOD'?'var(--green)':eq==='POOR'?'var(--red)':'var(--yellow)';
  if(G.$('ti-eq')){G.$('ti-eq').textContent=eq;G.$('ti-eq').style.color=eqCol;}
};
```

- [ ] **Step 6: Update `G.renderTiming` to also populate `tech-confirm-block`**

Find `G.renderTiming` (around line 767). After the line `G.$('d-strategy').classList.add('v');` at the end of the function, add:

```javascript
  // Show BuyTiming technical_signals in Strategy tab
  var ts=d.technical_signals||{};
  var lines=[];
  if(ts.rsi)lines.push('RSI    '+ts.rsi);
  if(ts.macd)lines.push('MACD   '+ts.macd);
  if(ts.bollinger)lines.push('BB     '+ts.bollinger);
  if(ts.trend)lines.push('TREND  '+ts.trend);
  if(ts.volume)lines.push('VOL    '+ts.volume);
  var tcb=G.$('tech-confirm-block'),tcc=G.$('s-techconf');
  if(tcb&&lines.length){tcb.style.display='';if(tcc)tcc.textContent=lines.join('\n');}
```

- [ ] **Step 7: Wire the two new SSE event cases in the message handler**

Find the SSE switch statement (around line 985):
```javascript
        case 'timing':G.renderTiming(msg.data||{});break;
```

Insert before it:
```javascript
        case 'technicals':G.renderTechnicalsData(msg.data||{});break;
        case 'technicals_analysis':G.renderTechnicalsAnalysis(msg.data||{});break;
```

- [ ] **Step 8: Update the reset function to hide new elements**

Find `G.reset` (around line 741 where it hides `tim-sig-block` etc). Add the new elements to the reset:

```javascript
  ['tim-sig-block','tim-win-block','tim-rat-block','tech-confirm-block'].forEach(function(id){var el=G.$(id);if(el)el.style.display='none'});
  var tph=G.$('tech-ph'),tbd=G.$('tech-body'),tnar=G.$('tech-narrative');
  if(tph)tph.style.display='';
  if(tbd)tbd.style.display='none';
  if(tnar)tnar.style.display='none';
```

- [ ] **Step 9: Verify the terminal loads without JS errors**

```powershell
$env:PYTHONUTF8=1; python server.py
```
Open `http://localhost:8000/stock` in browser. Open DevTools console — no errors on load.

- [ ] **Step 10: Run a full end-to-end analysis**

In the terminal, type `BBCA.JK` and press ANALYZE. Verify:
- 6 agent rows appear: DeepResearch, NewsIntelligence, TechnicalAnalyst, Strategy, FinalVerdict, BuyTiming
- TechnicalAnalyst row turns yellow → green during Phase 2
- TECHNICALS tab dot lights up after Phase 1.5 (indicator cards populated)
- Narrative sections appear after Phase 2 (TechnicalAnalyst done)
- STRATEGY tab entry_zone references a price near the support level shown in TECHNICALS tab
- BuyTiming "TECHNICAL CONFIRMATION" block appears in STRATEGY tab with RSI/MACD/BB lines

- [ ] **Step 11: Commit**

```powershell
git add "static/CassanovaL Terminal v2.html"
git commit -m "feat(stock): TECHNICALS tab, TechnicalAnalyst agent row, BuyTiming signals display"
```

---

## Final Verification

```powershell
# 1. All tests pass
pytest tests/test_stock_tools.py tests/test_stock_agents.py -v
# Expected: 0 failures

# 2. Full pipeline smoke test with real ticker
$env:PYTHONUTF8=1; python server.py
# Open http://localhost:8000/stock → type BBCA.JK → ANALYZE
# Pipeline completes in ~120s with 6 agents

# 3. Resilience test — invalid ticker
# Type INVALID123 → pipeline completes gracefully, technical_data = {}, no crash
# TECHNICALS tab shows dashes (—) for all values

# 4. Check entry zone in STRATEGY uses real support level
# TECHNICALS tab support_60d value should appear in entry_zone of STRATEGY tab
```

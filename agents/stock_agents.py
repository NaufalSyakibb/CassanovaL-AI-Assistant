import json
import re
import time
from agents.base import build_agent
from tools.stock_tools import get_market_data, get_news_sentiment, get_technical_indicators


def _invoke_with_retry(agent, messages: dict, max_retries: int = 5) -> dict:
    """Invoke a LangGraph agent with exponential backoff on 429 rate-limit errors."""
    delay = 20
    last_exc = None
    for attempt in range(max_retries):
        try:
            return agent.invoke(messages)
        except Exception as e:
            last_exc = e
            if "429" in str(e) or "rate" in str(e).lower():
                time.sleep(delay)
                delay = min(delay * 2, 120)
            else:
                raise
    raise last_exc


def _parse_json_output(agent_result: dict) -> dict:
    """Extract last AI message content and parse the first JSON object found."""
    messages = agent_result.get("messages", [])
    for msg in reversed(messages):
        content = getattr(msg, "content", "")
        if not content:
            continue
        match = re.search(r"\{.*\}", content, re.DOTALL)
        if match:
            try:
                return json.loads(match.group())
            except json.JSONDecodeError:
                continue
    raw = str(messages[-1]) if messages else "no messages"
    return {"error": "Could not parse agent output", "raw": raw[:500]}


_DEEP_RESEARCH_PROMPT = """Kamu adalah DeepResearch Agent — analis fundamental mendalam yang menggabungkan analisis kuantitatif dan konteks makroekonomi.
Tugasmu: Gunakan tool get_market_data untuk mengambil data lengkap saham target, termasuk laporan keuangan 3 tahun, target analis, dan korelasi makro. Hasilkan analisis komprehensif dalam Bahasa Indonesia profesional.

Kembalikan HANYA JSON dengan format berikut (tanpa teks lain):
{
  "summary": "ringkasan 3-4 kalimat kondisi fundamental, valuasi, dan konteks makro",
  "valuation": "analisis P/E, P/B, atau EV/EBITDA vs peers — mahal/murah/wajar",
  "growth_trend": "CAGR revenue 3 tahun terakhir dan tren margin (naik/stabil/turun)",
  "financial_health": "kondisi hutang, free cash flow, dan neraca keuangan",
  "analyst_consensus": "rata-rata target price analis dan distribusi rekomendasi",
  "macro_context": "dampak kondisi makro saat ini terhadap saham ini",
  "current_price": 0.0,
  "ohlcv": {},
  "macro_correlation": {}
}
"""

_NEWS_INTELLIGENCE_PROMPT = """Kamu adalah NewsIntelligence Agent — analis berita finansial yang cerdas dengan kemampuan deteksi sinyal tersembunyi.
Tugasmu: Gunakan tool get_news_sentiment untuk mengambil 15 berita terbaru tentang ticker yang diberikan. Analisis sentimen, klasifikasi event, dan deteksi anomali dalam Bahasa Indonesia profesional.

Data dari tool berisi field: articles (list dengan event_type per artikel) dan volume_anomaly (boolean).

Kembalikan HANYA JSON dengan format berikut (tanpa teks lain):
{
  "summary": "ringkasan sentimen pasar 3-4 kalimat",
  "sentiment_score": 0.0,
  "event_type": "jenis event dominan: earnings/M&A/management/regulatory/macro/other",
  "key_events": ["event penting 1", "event penting 2"],
  "risk_signals": ["sinyal negatif atau risiko"],
  "catalyst_signals": ["katalis positif atau peluang"],
  "anomaly_detected": false
}

sentiment_score: -1.0 (sangat negatif) hingga +1.0 (sangat positif).
anomaly_detected: true jika volume_anomaly dari tool adalah true atau ada event major.
"""

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

_STRATEGY_PROMPT = """Kamu adalah Strategy Agent — ahli strategi trading yang terinspirasi dari metodologi ValueCell.
Kamu menerima output dari DeepResearch dan NewsIntelligence sebagai konteks dalam pesan.
Tugasmu: Berdasarkan analisis fundamental, teknikal, dan sentimen, susun strategi trading yang konkret dan actionable dalam Bahasa Indonesia profesional.

Kembalikan HANYA JSON dengan format berikut (tanpa teks lain):
{
  "entry_zone": "zona harga entry yang disarankan (mis. 9500-9800)",
  "exit_target": "target harga keluar berdasarkan resistance dan target analis",
  "stop_loss": "level stop loss yang disarankan",
  "stop_loss_pct": 0.0,
  "time_horizon": "short|medium|long",
  "time_horizon_detail": "estimasi durasi investasi (mis. 3-6 bulan)",
  "position_size": "rekomendasi % portofolio (mis. 5%)",
  "risk_reward_ratio": "rasio risk/reward (mis. 1:3.5)",
  "rationale": "1-2 kalimat alasan strategi ini berdasarkan data"
}

time_horizon: gunakan short (< 1 bulan), medium (1-6 bulan), atau long (> 6 bulan).
stop_loss_pct: persentase penurunan dari entry price sebagai stop loss (angka positif).
"""

_BUY_TIMING_PROMPT = """Kamu adalah BuyTiming Agent — spesialis market timing yang menggabungkan analisis teknikal mendalam dengan psikologi pasar.
Tugasmu: Gunakan tool get_technical_indicators untuk mengambil data teknikal terkini dari ticker yang diberikan. Lalu tentukan timing masuk yang optimal berdasarkan indikator teknikal, strategi yang telah disusun, dan verdict investasi. Analisis dalam Bahasa Indonesia profesional.

Kembalikan HANYA JSON dengan format berikut (tanpa teks lain):
{
  "timing_signal": "BUY_NOW",
  "confidence": 7,
  "entry_condition": "kondisi teknikal yang harus terpenuhi untuk entry",
  "ideal_entry_price": 0.0,
  "ideal_entry_window": "estimasi jendela waktu masuk terbaik (mis. 1-2 minggu ke depan)",
  "dca_plan": "rencana DCA jika memilih cicil masuk",
  "technical_signals": {
    "rsi": "kondisi RSI saat ini dan implikasinya",
    "macd": "kondisi MACD dan status crossover",
    "bollinger": "posisi harga relatif terhadap Bollinger Bands",
    "trend": "tren MA jangka pendek/menengah/panjang dan golden/death cross",
    "volume": "konfirmasi volume (expanding/neutral/contracting)"
  },
  "timing_rationale": "2-3 kalimat alasan timing ini berdasarkan data teknikal dan konteks fundamental"
}

timing_signal hanya boleh: BUY_NOW (beli sekarang), WAIT (tunggu koreksi/konfirmasi), DCA (cicil masuk bertahap), atau AVOID (hindari dulu).
confidence: integer 1 (sangat tidak yakin) hingga 10 (sangat yakin).
ideal_entry_price: harga entry ideal dalam angka desimal berdasarkan support/resistance dan zona entry strategi.
"""

_FINAL_VERDICT_PROMPT = """Kamu adalah FinalVerdict Agent — investment committee chairman yang bertindak sebagai devil's advocate.
Kamu menerima output dari DeepResearch, NewsIntelligence, dan Strategy sebagai konteks dalam pesan.
Tugasmu: Gabungkan semua insight, tantang setiap asumsi yang lemah, lalu susun laporan investasi final profesional dalam Bahasa Indonesia.

Kembalikan HANYA JSON dengan format berikut (tanpa teks lain):
{
  "executive_summary": "2-3 kalimat kondisi saham menyeluruh yang objektif",
  "fundamental_analysis": "paragraph analisis fundamental dan teknikal yang tajam",
  "sentiment_macro": "paragraph gabungan sentimen berita dan konteks makro",
  "risk_assessment": ["risiko utama 1", "risiko utama 2", "risiko utama 3"],
  "counter_arguments": "devil's advocate — 1-2 argumen mengapa tesis ini bisa salah",
  "bull_case": ["skenario positif 1", "skenario positif 2", "skenario positif 3"],
  "bear_case": ["skenario negatif 1", "skenario negatif 2", "skenario negatif 3"],
  "verdict": "BUY",
  "conviction_score": 7,
  "risk_reward": "1:3.5",
  "investment_memo": "memo investasi profesional 3-4 kalimat yang berisi tesis lengkap"
}

verdict hanya boleh: BUY, HOLD, atau SELL.
conviction_score: integer 1 (sangat tidak yakin) hingga 10 (sangat yakin).
"""


def run_deep_research(ticker: str) -> dict:
    agent = build_agent(_DEEP_RESEARCH_PROMPT, [get_market_data])
    result = _invoke_with_retry(agent, {
        "messages": [{"role": "user", "content": f"Lakukan analisis mendalam saham: {ticker}"}]
    })
    return _parse_json_output(result)


def run_news_intelligence(ticker: str) -> dict:
    agent = build_agent(_NEWS_INTELLIGENCE_PROMPT, [get_news_sentiment])
    result = _invoke_with_retry(agent, {
        "messages": [{"role": "user", "content": f"Analisis berita dan sentimen untuk saham: {ticker}"}]
    })
    return _parse_json_output(result)


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


def run_strategy(deep_research: dict, news_intelligence: dict) -> dict:
    agent = build_agent(_STRATEGY_PROMPT, [])
    context = json.dumps({
        "deep_research":    {k: v for k, v in deep_research.items() if k != "ohlcv"},
        "news_intelligence": news_intelligence,
    }, ensure_ascii=False)
    result = _invoke_with_retry(agent, {
        "messages": [{"role": "user", "content": f"Susun strategi trading berdasarkan data ini: {context}"}]
    })
    return _parse_json_output(result)


def run_final_verdict(ticker: str, deep_research: dict, news_intelligence: dict, strategy: dict) -> dict:
    agent = build_agent(_FINAL_VERDICT_PROMPT, [])
    combined = json.dumps({
        "ticker":            ticker,
        "deep_research":     {k: v for k, v in deep_research.items() if k != "ohlcv"},
        "news_intelligence": news_intelligence,
        "strategy":          strategy,
    }, ensure_ascii=False)
    result = _invoke_with_retry(agent, {
        "messages": [{"role": "user", "content": f"Buat laporan investasi final: {combined}"}]
    })
    return _parse_json_output(result)


def run_buy_timing(ticker: str, strategy: dict, verdict: dict) -> dict:
    agent = build_agent(_BUY_TIMING_PROMPT, [get_technical_indicators])
    context = json.dumps({
        "ticker":           ticker,
        "entry_zone":       strategy.get("entry_zone", ""),
        "stop_loss":        strategy.get("stop_loss", ""),
        "verdict_signal":   verdict.get("verdict", "HOLD"),
        "conviction_score": verdict.get("conviction_score", 5),
        "risk_reward":      verdict.get("risk_reward", ""),
    }, ensure_ascii=False)
    result = _invoke_with_retry(agent, {
        "messages": [{"role": "user", "content": f"Tentukan timing beli optimal untuk {ticker} berdasarkan konteks ini: {context}"}]
    })
    return _parse_json_output(result)

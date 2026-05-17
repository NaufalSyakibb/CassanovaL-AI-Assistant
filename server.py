import asyncio
import json
import sys
import io
import os
import re
import base64
import threading
import uuid
from pathlib import Path
from datetime import datetime
from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from pydantic import BaseModel
from typing import Optional, List
from dotenv import load_dotenv
import uvicorn

load_dotenv()

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

app = FastAPI(title="OmniSync API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

_supervisor = None


def get_supervisor():
    global _supervisor
    if _supervisor is None:
        from router import SupervisorRouter
        _supervisor = SupervisorRouter()
    return _supervisor


class ChatRequest(BaseModel):
    message: str
    agent: Optional[str] = None  # if provided, skip auto-classification


# ─── Receipt Scanner ─────────────────────────────────────────────────────────

RECEIPT_PROMPT = """Kamu adalah sistem pembaca struk/bukti transaksi keuangan.
Analisis gambar ini dan ekstrak informasi transaksi.

Kembalikan HANYA JSON dengan format berikut (tanpa penjelasan apapun):
{"type":"expense","amount":50000,"category":"food","description":"Makan siang di warung","date":"2025-01-15"}

Aturan:
- type: "expense" untuk pengeluaran, "income" untuk pemasukan (hampir semua struk = expense)
- amount: angka saja tanpa titik/koma/simbol mata uang
- category expense: food, transport, shopping, entertainment, bills, health, education, other
- category income: salary, freelance, business, investment, gift, other
- description: nama toko / deskripsi singkat apa yang dibeli
- date: format YYYY-MM-DD jika terlihat di struk, atau null jika tidak ada
"""

@app.post("/api/budget/scan-receipt")
async def scan_receipt(file: UploadFile = File(...)):
    api_key = os.getenv("MISTRAL_API_KEY")
    if not api_key:
        raise HTTPException(status_code=500, detail="MISTRAL_API_KEY not found")

    image_data = await file.read()
    b64 = base64.b64encode(image_data).decode("utf-8")
    mime = file.content_type or "image/jpeg"

    try:
        from mistralai import Mistral
        client = Mistral(api_key=api_key)
        response = client.chat.complete(
            model="pixtral-12b-2409",
            messages=[{
                "role": "user",
                "content": [
                    {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{b64}"}},
                    {"type": "text", "text": RECEIPT_PROMPT},
                ],
            }],
        )
        raw = response.choices[0].message.content.strip()
        match = re.search(r"\{.*?\}", raw, re.DOTALL)
        if not match:
            raise HTTPException(status_code=422, detail="Tidak bisa membaca struk. Coba foto yang lebih jelas.")
        result = json.loads(match.group())
        # Ensure required fields
        result.setdefault("type", "expense")
        result.setdefault("category", "other")
        result.setdefault("description", "")
        result.setdefault("date", datetime.now().strftime("%Y-%m-%d"))
        if not result.get("date"):
            result["date"] = datetime.now().strftime("%Y-%m-%d")
        result["amount"] = float(result.get("amount", 0))
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Gagal memproses struk: {str(e)}")


# ─── Chat History Logger ─────────────────────────────────────────────────────

_AGENT_FILENAMES = {
    "task":     "alfred",
    "notes":    "cicero",
    "news":     "najwa",
    "coding":   "linus",
    "schedule": "miyamoto",
    "budget":   "mansa",
    "fitness":  "lavoisier",
    "journal":  "dostoyevsky",
    "davinci":  "davinci",
}


def _my_ai_dir() -> Path:
    vault = os.getenv("OBSIDIAN_VAULT_PATH", "").strip()
    base = (Path(vault) / "My AI") if vault \
           else (Path(__file__).parent / "AI Data" / "My AI")
    base.mkdir(parents=True, exist_ok=True)
    return base


def _save_chat_history(agent_key: str, agent_display: str, user_msg: str, ai_response: str) -> None:
    """Append one conversation turn to AI Data/My AI/<agent>.md"""
    try:
        filename = _AGENT_FILENAMES.get(agent_key, agent_key.lower())
        filepath = _my_ai_dir() / f"{filename}.md"

        # Write header if file is new
        if not filepath.exists():
            filepath.write_text(
                f"# Conversation History — {agent_display}\n\n",
                encoding="utf-8",
            )

        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        entry = (
            f"## {ts}\n\n"
            f"**You:** {user_msg}\n\n"
            f"**{agent_display}:** {ai_response}\n\n"
            f"---\n\n"
        )
        with filepath.open("a", encoding="utf-8") as f:
            f.write(entry)
    except Exception:
        pass  # Never let logging break the chat response


# ─── Chat ────────────────────────────────────────────────────────────────────

@app.post("/api/chat")
async def chat(req: ChatRequest):
    try:
        supervisor = get_supervisor()
        if req.agent:
            agent_name, response = supervisor.chat_direct(req.agent, req.message)
        else:
            agent_name, response = supervisor.chat(req.message)

        # Save to AI Data/My AI/<agent>.md
        agent_key = req.agent or agent_name.lower()
        _save_chat_history(agent_key, agent_name, req.message, response)

        return {"agent": agent_name, "response": response}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ─── DataAnalyst File Endpoints ──────────────────────────────────────────────

def _dataanalyst_dir() -> Path:
    """Resolve the DataAnalyst Agent data folder (mirrors data_tools._data_dir logic)."""
    from dotenv import load_dotenv
    load_dotenv()
    vault = os.getenv("OBSIDIAN_VAULT_PATH", "").strip()
    # OBSIDIAN_VAULT_PATH already points to the "AI Data" folder — only append the subfolder
    base = (Path(vault) / "DataAnalyst Agent") if vault \
           else (Path(__file__).parent / "AI Data" / "DataAnalyst Agent")
    base.mkdir(parents=True, exist_ok=True)
    return base


_ALLOWED_EXTS = {".csv", ".xlsx", ".xls", ".json"}


@app.post("/api/dataanalyst/upload")
async def upload_data_file(file: UploadFile = File(...)):
    """Upload a CSV/Excel/JSON file to the DataAnalyst Agent folder."""
    ext = Path(file.filename).suffix.lower()
    if ext not in _ALLOWED_EXTS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type '{ext}'. Allowed: CSV, XLSX, XLS, JSON",
        )
    folder = _dataanalyst_dir()
    dest = folder / file.filename
    content = await file.read()
    dest.write_bytes(content)
    size_kb = len(content) / 1024
    return {
        "filename": file.filename,
        "path": str(dest),
        "size_kb": round(size_kb, 1),
        "message": f"Uploaded '{file.filename}' ({size_kb:.1f} KB). Tell the agent: load_dataset('{file.filename}')",
    }


@app.get("/api/dataanalyst/files")
async def list_dataanalyst_files():
    """List all data files available in the DataAnalyst Agent folder."""
    folder = _dataanalyst_dir()
    files = []
    for f in sorted(folder.iterdir(), key=lambda x: x.stat().st_mtime, reverse=True):
        if f.suffix.lower() in _ALLOWED_EXTS:
            files.append({
                "name": f.name,
                "size_kb": round(f.stat().st_size / 1024, 1),
                "modified": datetime.fromtimestamp(f.stat().st_mtime).strftime("%Y-%m-%d %H:%M"),
            })
    return {"files": files, "folder": str(folder)}


@app.get("/api/dataanalyst/download/{filename}")
async def download_dataanalyst_file(filename: str):
    """Download a processed file from the DataAnalyst Agent folder."""
    folder = _dataanalyst_dir()
    file_path = folder / filename
    if not file_path.exists() or not file_path.is_file():
        raise HTTPException(status_code=404, detail=f"File '{filename}' not found.")
    # Security: ensure path stays within folder
    if not str(file_path.resolve()).startswith(str(folder.resolve())):
        raise HTTPException(status_code=403, detail="Access denied.")
    return FileResponse(str(file_path), filename=filename)


# ─── Data Endpoints ───────────────────────────────────────────────────────────

@app.get("/api/tasks")
async def get_tasks():
    try:
        data = json.loads(Path("data/tasks.json").read_text(encoding="utf-8"))
        pending = [t for t in data if t["status"] == "pending"]
        completed = [t for t in data if t["status"] == "completed"]
        high = [t for t in pending if t.get("priority") == "high"]
        return {
            "tasks": data,
            "stats": {
                "total": len(data),
                "pending": len(pending),
                "completed": len(completed),
                "high_priority": len(high),
            },
        }
    except Exception:
        return {"tasks": [], "stats": {"total": 0, "pending": 0, "completed": 0, "high_priority": 0}}


@app.get("/api/notes")
async def get_notes():
    try:
        data = json.loads(Path("data/notes.json").read_text(encoding="utf-8"))
        sorted_notes = sorted(data, key=lambda x: x.get("updated_at", ""), reverse=True)
        return {"notes": sorted_notes[:8], "total": len(data)}
    except Exception:
        return {"notes": [], "total": 0}


@app.get("/api/journal/dashboard")
async def get_journal_dashboard():
    from datetime import timedelta
    MONTH_NAMES = ["Januari","Februari","Maret","April","Mei","Juni","Juli","Agustus","September","Oktober","November","Desember"]
    DAY_NAMES   = ["Senin","Selasa","Rabu","Kamis","Jumat","Sabtu","Minggu"]
    POSITIVE    = {"happy","senang","grateful","content","great","baik","gembira","bersyukur","excited","semangat","joy","joyful","calm","tenang","satisfied","puas","lega","antusias"}
    NEGATIVE    = {"sad","sedih","anxious","cemas","stressed","stress","kecewa","lelah","tired","bad","buruk","down","frustrated","marah","angry","worried","khawatir","berat","burnout"}

    vault = os.getenv("OBSIDIAN_VAULT_PATH","").strip()
    journal_dir = Path(vault) / "Dostoyevsky Agent" if vault else Path("AI Data") / "Dostoyevsky Agent"

    if not journal_dir.exists():
        return {"entries":[],"today":None,"streak":0,"total_entries":0,"mood_history":[],"tags":[],"this_month_count":0,"current_month_label":""}

    def mood_cat(mood: str) -> str:
        m = mood.lower()
        if any(w in m for w in POSITIVE): return "positive"
        if any(w in m for w in NEGATIVE): return "negative"
        if m in ("unspecified","—",""): return "none"
        return "neutral"

    files = sorted(journal_dir.glob("Journal_*.md"), reverse=True)[:90]
    entries, mood_history, all_tags = [], [], set()

    for f in files:
        try: content = f.read_text(encoding="utf-8")
        except: continue
        date_str = f.stem.replace("Journal_","")
        mood_m = re.search(r"^mood:\s*(.+)$", content, re.MULTILINE)
        mood   = mood_m.group(1).strip() if mood_m else "unspecified"
        tags_m = re.search(r"^tags:\s*\[([^\]]*)\]", content, re.MULTILINE)
        tags   = [t.strip() for t in tags_m.group(1).split(",") if t.strip()] if tags_m else []
        all_tags.update(tags)
        body   = re.sub(r"^---.*?---\s*", "", content, flags=re.DOTALL).strip()
        body   = re.sub(r"^# .*\n", "", body).strip()
        wc     = len(body.split())
        clean  = re.sub(r"[#*`>_\-]+", "", body).replace("\n"," ").strip()
        preview= clean[:160] + ("…" if len(clean)>160 else "")
        try:
            dt = datetime.strptime(date_str, "%Y-%m-%d")
            date_label = f"{dt.day} {MONTH_NAMES[dt.month-1]} {dt.year}"
            day_name   = DAY_NAMES[dt.weekday()]
        except:
            date_label, day_name = date_str, ""
        cat = mood_cat(mood)
        entries.append({"date":date_str,"date_label":date_label,"day_name":day_name,"mood":mood,"mood_cat":cat,"word_count":wc,"preview":preview,"content":body})
        mood_history.append({"date":date_str,"mood":mood,"mood_cat":cat})

    today_str  = datetime.now().strftime("%Y-%m-%d")
    dates_set  = {e["date"] for e in entries}
    streak, start_i = 0, (0 if today_str in dates_set else 1)
    for i in range(start_i, 60):
        d = (datetime.now() - timedelta(days=i)).strftime("%Y-%m-%d")
        if d in dates_set: streak += 1
        else: break

    now = datetime.now()
    cur_month = now.strftime("%Y-%m")
    return {
        "entries": entries,
        "today": next((e for e in entries if e["date"]==today_str), None),
        "streak": streak,
        "total_entries": len(entries),
        "mood_history": mood_history,
        "tags": sorted(all_tags),
        "this_month_count": sum(1 for e in entries if e["date"].startswith(cur_month)),
        "current_month_label": f"{MONTH_NAMES[now.month-1]} {now.year}",
    }


@app.get("/api/budget/summary")
async def get_budget_summary():
    try:
        raw = json.loads(Path("data/budget.json").read_text(encoding="utf-8"))
        data = raw if isinstance(raw, list) else raw.get("transactions", [])
        total_income = sum(t["amount"] for t in data if t["type"] == "income")
        total_expense = sum(t["amount"] for t in data if t["type"] == "expense")
        current_month = datetime.now().strftime("%Y-%m")
        monthly = [t for t in data if t.get("date", "").startswith(current_month)]
        monthly_income = sum(t["amount"] for t in monthly if t["type"] == "income")
        monthly_expense = sum(t["amount"] for t in monthly if t["type"] == "expense")
        recent = sorted(data, key=lambda x: x.get("date", ""), reverse=True)[:5]
        return {
            "balance": total_income - total_expense,
            "total_income": total_income,
            "total_expense": total_expense,
            "monthly_income": monthly_income,
            "monthly_expense": monthly_expense,
            "recent_transactions": recent,
        }
    except Exception:
        return {
            "balance": 0, "total_income": 0, "total_expense": 0,
            "monthly_income": 0, "monthly_expense": 0, "recent_transactions": [],
        }


@app.get("/api/finance/dashboard")
async def get_finance_dashboard():
    from dateutil.relativedelta import relativedelta
    try:
        raw = json.loads(Path("data/budget.json").read_text(encoding="utf-8"))
    except Exception:
        raw = {}
    if isinstance(raw, list):
        raw = {"accounts": [], "transactions": raw, "budget_goals": [], "investments": [], "net_worth_history": [], "recurring": []}

    accounts     = raw.get("accounts", [])
    transactions = raw.get("transactions", [])
    goals        = raw.get("budget_goals", [])
    investments  = raw.get("investments", [])
    recurring    = raw.get("recurring", [])

    LIABILITY_TYPES = {"credit_card", "loan"}

    # ── Net worth ──
    total_assets      = sum(a["balance"] for a in accounts if a.get("account_type") not in LIABILITY_TYPES)
    total_liabilities = sum(a["balance"] for a in accounts if a.get("account_type") in LIABILITY_TYPES)
    inv_value         = sum(i["quantity"] * i.get("current_price", i["buy_price"]) for i in investments)
    net_worth         = total_assets + inv_value - total_liabilities

    # ── Monthly income/expense ──
    now           = datetime.now()
    current_month = now.strftime("%Y-%m")
    month_names   = ["Januari","Februari","Maret","April","Mei","Juni","Juli","Agustus","September","Oktober","November","Desember"]
    current_month_label = f"{month_names[now.month-1]} {now.year}"

    monthly_txs     = [t for t in transactions if t.get("date","").startswith(current_month)]
    monthly_income  = sum(t["amount"] for t in monthly_txs if t["type"] == "income")
    monthly_expense = sum(t["amount"] for t in monthly_txs if t["type"] == "expense")

    # ── Expense by category (current month) ──
    cat_expense: dict = {}
    for t in monthly_txs:
        if t["type"] == "expense":
            cat = t.get("category", "other")
            cat_expense[cat] = cat_expense.get(cat, 0) + t["amount"]

    # ── Investments with computed fields ──
    inv_out = []
    for i in investments:
        cp    = i.get("current_price", i["buy_price"])
        mv    = i["quantity"] * cp
        pnl   = mv - i["quantity"] * i["buy_price"]
        cost  = i["quantity"] * i["buy_price"]
        pct   = round(pnl / cost * 100, 2) if cost else 0
        inv_out.append({**i, "current_price": cp, "market_value": mv, "pnl": pnl, "pnl_pct": pct})

    # ── Budget goals with spent & pct ──
    goals_out = []
    for g in goals:
        if g.get("month") != current_month:
            continue
        cat   = g.get("category","")
        spent = sum(t["amount"] for t in monthly_txs if t["type"]=="expense" and t.get("category")==cat)
        limit = g.get("monthly_limit", 0)
        pct   = round(spent / limit * 100, 1) if limit else 0
        goals_out.append({**g, "spent": spent, "pct": pct})

    # ── Recurring with days_until ──
    rec_out = []
    today   = now.date()
    for r in recurring:
        nd  = r.get("next_date")
        try:
            days = (datetime.strptime(nd, "%Y-%m-%d").date() - today).days
        except Exception:
            days = None
        rec_out.append({**r, "days_until": days})
    rec_out.sort(key=lambda x: x.get("next_date") or "9999")

    # ── Cash flow last 6 months ──
    cash_flow = []
    for i in range(5, -1, -1):
        m     = (now - relativedelta(months=i))
        mkey  = m.strftime("%Y-%m")
        label = f"{month_names[m.month-1][:3]} {m.year}"
        inc   = sum(t["amount"] for t in transactions if t.get("date","").startswith(mkey) and t["type"]=="income")
        exp   = sum(t["amount"] for t in transactions if t.get("date","").startswith(mkey) and t["type"]=="expense")
        cash_flow.append({"month": label, "income": inc, "expense": exp})

    return {
        "net_worth":        net_worth,
        "total_assets":     total_assets,
        "investment_value": inv_value,
        "total_liabilities":total_liabilities,
        "monthly_income":   monthly_income,
        "monthly_expense":  monthly_expense,
        "current_month":    current_month_label,
        "accounts":         accounts,
        "investments":      inv_out,
        "budget_goals":     goals_out,
        "recent_transactions": sorted(transactions, key=lambda x: x.get("date",""), reverse=True)[:50],
        "recurring":        rec_out,
        "cash_flow":        cash_flow,
        "cat_expense":      cat_expense,
    }


# ─── Stock Terminal ───────────────────────────────────────────────────────────

def _sse(data: dict) -> str:
    return f"data: {json.dumps(data, ensure_ascii=False, default=float)}\n\n"


async def _run_agent(loop, fn, *args):
    """Run a synchronous agent function in the default executor and return its result."""
    return await loop.run_in_executor(None, fn, *args)


def _normalize_ticker(raw: str) -> str:
    """Auto-append .JK for IDX tickers (≤4 chars, no exchange suffix already)."""
    t = raw.upper().strip()
    if "." not in t and len(t) <= 4:
        return t + ".JK"
    return t


@app.get("/api/stock/analyze")
async def stock_analyze(ticker: str):
    if not ticker or len(ticker) > 20:
        raise HTTPException(status_code=400, detail="Invalid ticker symbol")
    ticker = _normalize_ticker(ticker)

    async def generate():
        # Yield immediately so the client marks gotData=true before imports run
        yield _sse({"event": "log", "text": f"Initializing pipeline for {ticker}..."})
        try:
            from agents.stock_agents import (
                run_deep_research, run_news_intelligence,
                run_strategy, run_final_verdict, run_buy_timing,
            )
            from tools.stock_tools import build_candlestick_json, build_heatmap_json, build_python_code
            loop = asyncio.get_running_loop()

            # ── Phase 1: DeepResearch ─────────────────────────────────────
            yield _sse({"event": "step", "agent": "DeepResearch", "status": "running"})
            deep_research_data = await _run_agent(loop, run_deep_research, ticker)
            price  = deep_research_data.get("current_price", "N/A")
            growth = deep_research_data.get("growth_trend", "N/A")
            yield _sse({"event": "log", "text": f"Harga: {price} | Growth: {growth}"})
            yield _sse({"event": "step", "agent": "DeepResearch", "status": "done"})

            # ── Market stats event (populates key-stats bar in terminal) ──────
            pe_raw  = deep_research_data.get("pe_ratio")
            roe_raw = deep_research_data.get("roe")
            chg_1y  = deep_research_data.get("price_change_1y_pct") or 0
            closes  = deep_research_data.get("ohlcv", {}).get("close", [])
            rsi_val = None
            if len(closes) >= 15:
                delta  = [float(closes[i]) - float(closes[i-1]) for i in range(1, len(closes))]
                gains  = [max(d, 0) for d in delta]
                losses = [max(-d, 0) for d in delta]
                ag = sum(gains[-14:]) / 14
                al = sum(losses[-14:]) / 14
                rsi_val = round(100 - 100 / (1 + ag / (al or 1e-10)), 1)
            yield _sse({
                "event": "market",
                "price": float(price) if isinstance(price, (int, float)) else 0,
                "chg":   round(float(chg_1y), 2),
                "pe":    f"{float(pe_raw):.1f}x" if pe_raw else "N/A",
                "roe":   f"{float(roe_raw) * 100:.1f}%" if roe_raw else "N/A",
                "rsi":   rsi_val,
            })

            await asyncio.sleep(5)

            # ── Phase 2: NewsIntelligence ─────────────────────────────────
            yield _sse({"event": "step", "agent": "NewsIntelligence", "status": "running"})
            news_data = await _run_agent(loop, run_news_intelligence, ticker)
            sentiment  = news_data.get("sentiment_score", "N/A")
            event_type = news_data.get("event_type", "N/A")
            yield _sse({"event": "log", "text": f"Sentimen: {sentiment} | Event: {event_type}"})
            yield _sse({"event": "step", "agent": "NewsIntelligence", "status": "done"})

            await asyncio.sleep(5)

            # ── Phase 3: Strategy ─────────────────────────────────────────
            yield _sse({"event": "step", "agent": "Strategy", "status": "running"})
            strategy_data = await _run_agent(loop, run_strategy, deep_research_data, news_data)
            entry = strategy_data.get("entry_zone", "N/A")
            rr    = strategy_data.get("risk_reward_ratio", "N/A")
            yield _sse({"event": "strategy", "data": strategy_data})
            yield _sse({"event": "log", "text": f"Entry: {entry} | R/R: {rr}"})
            yield _sse({"event": "step", "agent": "Strategy", "status": "done"})

            await asyncio.sleep(5)

            # ── Phase 4: FinalVerdict ─────────────────────────────────────
            yield _sse({"event": "step", "agent": "FinalVerdict", "status": "running"})
            verdict_data = await _run_agent(
                loop, run_final_verdict, ticker, deep_research_data, news_data, strategy_data
            )
            yield _sse({"event": "verdict", "data": verdict_data})
            yield _sse({"event": "step", "agent": "FinalVerdict", "status": "done"})

            await asyncio.sleep(5)

            # ── Phase 5: BuyTiming ────────────────────────────────────────
            yield _sse({"event": "step", "agent": "BuyTiming", "status": "running"})
            timing_data = await _run_agent(loop, run_buy_timing, ticker, strategy_data, verdict_data)
            signal     = timing_data.get("timing_signal", "WAIT")
            confidence = timing_data.get("confidence", 5)
            yield _sse({"event": "timing", "data": timing_data})
            yield _sse({"event": "log", "text": f"Timing: {signal} | Confidence: {confidence}/10"})
            yield _sse({"event": "step", "agent": "BuyTiming", "status": "done"})

            # ── Charts + code ─────────────────────────────────────────────
            ohlcv = deep_research_data.get("ohlcv", {})
            corr  = deep_research_data.get("macro_correlation", {})
            yield _sse({"event": "chart",
                        "candlestick": build_candlestick_json(ticker, ohlcv),
                        "heatmap":     build_heatmap_json(ticker, corr)})
            yield _sse({"event": "code", "python": build_python_code(ticker, ohlcv, corr)})

            # ── Final report ──────────────────────────────────────────────
            risk_list = verdict_data.get("risk_assessment", [])
            risk_text = "\n".join(risk_list) if isinstance(risk_list, list) else str(risk_list)
            report = {
                "executive_summary": verdict_data.get("executive_summary", ""),
                "fundamental":       deep_research_data.get("summary", "") + "\n\n" + verdict_data.get("fundamental_analysis", ""),
                "sentiment":         news_data.get("summary", "") + "\n\n" + verdict_data.get("sentiment_macro", ""),
                "risk":              risk_text + "\n\n" + verdict_data.get("counter_arguments", ""),
                "verdict":           verdict_data.get("verdict", "HOLD"),
                "conviction_score":  verdict_data.get("conviction_score", 5),
                "risk_reward":       verdict_data.get("risk_reward", ""),
                "bull_case":         verdict_data.get("bull_case", []),
                "bear_case":         verdict_data.get("bear_case", []),
                "investment_memo":   verdict_data.get("investment_memo", ""),
            }
            yield _sse({"event": "done", "report": report})

        except Exception as e:
            yield _sse({"event": "error", "message": str(e)})

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


# ─── CrewAI Multi-Agent Endpoints ────────────────────────────────────────────

_crew_jobs: dict = {}  # job_id → job state dict


class CrewKickoffRequest(BaseModel):
    topic: str
    crew_type: str = "research"            # "research" | "dataanalyst" | "career" | "scraper"
    filename: Optional[str] = None         # required when crew_type == "dataanalyst"
    cv_text: Optional[str] = None          # optional CV text for career ops
    agents: Optional[List[dict]] = None    # future: custom agent configs
    # scraper-specific
    platforms: Optional[List[str]] = None  # None = all enabled platforms
    translate: Optional[bool] = False
    target_lang: Optional[str] = "en"


def _run_crew_background(job_id: str, topic: str,
                          crew_type: str = "research",
                          filename: Optional[str] = None,
                          cv_text: Optional[str] = None,
                          platforms: Optional[List[str]] = None,
                          translate: bool = False,
                          target_lang: str = "en") -> None:
    """Run a CrewAI pipeline in a background thread and update _crew_jobs."""
    job = _crew_jobs[job_id]
    import traceback as _tb

    logs: list = []

    def _log(obj) -> None:
        """Thread-safe incremental log collector — never touches sys.stdout."""
        line = str(obj).strip()
        if line:
            logs.append(line)
            job["logs"] = logs[:]   # snapshot so polling sees incremental updates

    try:
        outputs = {}  # initialize here so all branches can write to it

        if crew_type == "scraper":
            import sys as _sys
            scraper_root = str(Path(__file__).parent / "social_scraper")
            if scraper_root not in _sys.path:
                _sys.path.insert(0, scraper_root)

            # topic → keyword list
            kw_raw = topic.strip() if topic and topic not in ("all platforms",) else ""
            keywords = [k.strip() for k in kw_raw.replace(",", " ").split() if k.strip()] or None

            active_platforms = platforms or ["youtube", "tiktok", "facebook", "instagram"]

            _log(f"[Scraper] Starting xcrawl harvest for: {', '.join(active_platforms)}")
            if keywords:
                _log(f"[Scraper] Keywords: {', '.join(keywords)}")

            from agents.xcrawl_harvester import XcrawlHarvester
            harvester = XcrawlHarvester()

            saved_files = {}
            for plat in active_platforms:
                _log(f"[{plat.upper()}] Scraping...")
                plat_saved = harvester.run(platforms=[plat], keywords=keywords)
                if plat_saved:
                    path = plat_saved[plat]
                    items = json.loads(path.read_text(encoding="utf-8"))
                    total_chars = sum(i.get("raw_length", 0) for i in items)
                    _log(f"[{plat.upper()}] Done — {len(items)} pages, {total_chars:,} chars")
                    saved_files[plat] = path
                else:
                    _log(f"[{plat.upper()}] No data collected")

            # Build summary report
            lines = [
                "# Social Scraper Report\n\n",
                f"**Platforms:** {', '.join(saved_files.keys()) or 'none'}\n",
                f"**Keywords:** {', '.join(keywords) if keywords else 'trending (default)'}\n\n",
                "## Per-Platform Results\n\n",
                "| Platform | Pages | Total Chars | File |\n",
                "|----------|-------|-------------|------|\n",
            ]
            for plat, path in saved_files.items():
                items = json.loads(path.read_text(encoding="utf-8"))
                total_chars = sum(i.get("raw_length", 0) for i in items)
                lines.append(f"| {plat} | {len(items)} | {total_chars:,} | {path.name} |\n")
            outputs["scraper_report.md"] = "".join(lines)

            # Attach per-platform content previews (first item, first 3000 chars)
            for plat, path in saved_files.items():
                try:
                    items = json.loads(path.read_text(encoding="utf-8"))
                    if items:
                        item = items[0]
                        preview = {
                            "platform": item["platform"],
                            "label": item["metadata"]["label"],
                            "url": item["url"],
                            "content_preview": item["content"][:3000],
                            "total_pages": len(items),
                        }
                        outputs[f"{plat}_data.json"] = json.dumps(preview, ensure_ascii=False, indent=2)
                except Exception:
                    pass

            # AI summaries per platform
            if saved_files:
                _log("[Summarizer] Generating AI insights per platform...")
                from agents.summarizer_agent import SummarizerAgent
                summaries = SummarizerAgent().run(saved_files)
                for plat, summary in summaries.items():
                    _log(f"[Summarizer] {plat} summary ready ({len(summary)} chars)")
                    outputs[f"{plat}_summary.md"] = summary

            result = {
                "platforms": list(saved_files.keys()),
                "total_pages": sum(len(json.loads(p.read_text(encoding="utf-8"))) for p in saved_files.values()),
            }

        elif crew_type == "dataanalyst":
            from crewai_agents import build_data_crew
            crew = build_data_crew(filename or topic, step_cb=_log, task_cb=_log)
            result = crew.kickoff()
        elif crew_type == "career":
            from crewai_agents import build_career_crew
            crew = build_career_crew(topic, cv_text or "", step_cb=_log, task_cb=_log)
            result = crew.kickoff()
        elif crew_type == "academic_swarm":
            from crewai_agents import build_academic_swarm
            pipeline = build_academic_swarm(topic, step_cb=_log, task_cb=_log)
            result = pipeline.kickoff()
        else:
            from crewai_agents import build_crew
            crew = build_crew(topic, step_cb=_log, task_cb=_log)
            result = crew.kickoff()
        job["logs"] = logs

        # ── Collect output files (scraper already populated outputs above) ────
        if crew_type == "scraper":
            pass  # outputs already built inside the scraper block
        elif crew_type == "dataanalyst":
            # task text summaries
            for fname in ("task1_data_clean.txt", "task2_stats_analysis.txt", "task3_visualization.txt"):
                p = Path(fname)
                if p.exists():
                    outputs[fname] = p.read_text(encoding="utf-8")
            # stats report + viz code from agent folder
            try:
                from tools.data_tools import _data_dir, _session
                da_dir = _data_dir()
                for rel in ("stats_report.md", "visualization.py"):
                    fp = da_dir / rel
                    if fp.exists():
                        outputs[rel] = fp.read_text(encoding="utf-8")
                # cleaned CSV — just show the path/summary, not full content
                if _session.get("autosave_path"):
                    cp = Path(_session["autosave_path"])
                    if cp.exists():
                        size_kb = cp.stat().st_size / 1024
                        outputs["cleaned_data.csv"] = (
                            f"✅ Cleaned dataset saved:\n{cp}\n\n"
                            f"Size: {size_kb:.1f} KB\n"
                            f"Reload with: load_dataset('{cp.name}')"
                        )
            except Exception:
                pass
        elif crew_type == "career":
            from crewai_agents import _career_dir
            career_out = _career_dir()
            for fname in (
                "career_archetype.txt", "career_scores.txt",
                "career_cv_advice.txt", "career_eval_report.md",
            ):
                p = career_out / fname
                if p.exists():
                    outputs[fname] = p.read_text(encoding="utf-8")
        elif crew_type == "academic_swarm":
            from crewai_agents import _research_dir
            research_out = _research_dir()
            ts = (result or {}).get("ts", "")
            if ts:
                for suffix in (
                    "0_meta.txt", "1_scout.txt", "2_analysis.txt",
                    "3_validation.txt", "4_citations.txt",
                    "5_synthesis.txt", "6_critique.txt", "final_report.md",
                ):
                    p = research_out / f"swarm_{ts}_{suffix}"
                    if p.exists():
                        outputs[f"swarm_{ts}_{suffix}"] = p.read_text(encoding="utf-8")
        else:
            from crewai_agents import _research_dir
            research_out = _research_dir()
            for fname in (
                "task1_scout.txt", "task2_filter.txt",
                "task3a_ideas.txt", "task3b_validation.txt",
                "task4_synthesis.txt", "task5_critique.txt",
                "task6_final_report.md",
            ):
                p = research_out / fname
                if p.exists():
                    outputs[fname] = p.read_text(encoding="utf-8")

        job["status"]  = "done"
        job["result"]  = str(result)
        job["outputs"] = outputs

    except Exception as exc:
        job["status"] = "error"
        job["error"]  = f"{type(exc).__name__}: {exc}\n{_tb.format_exc()}"


@app.post("/api/crew/kickoff")
async def crew_kickoff(req: CrewKickoffRequest):
    """Start a CrewAI pipeline (research or dataanalyst). Returns a job_id to poll."""
    topic = req.topic.strip()
    if not topic:
        raise HTTPException(status_code=400, detail="topic is required")
    if req.crew_type == "dataanalyst" and not req.filename:
        raise HTTPException(status_code=400, detail="filename is required for dataanalyst crew")

    job_id = str(uuid.uuid4())[:8]
    _crew_jobs[job_id] = {
        "status":     "running",
        "topic":      topic,
        "crew_type":  req.crew_type,
        "filename":   req.filename,
        "result":     None,
        "error":      None,
        "outputs":    {},
        "logs":       [],
        "started":    datetime.now().isoformat(),
    }

    t = threading.Thread(
        target=_run_crew_background,
        args=(job_id, topic, req.crew_type, req.filename, req.cv_text,
              req.platforms, req.translate or False, req.target_lang or "en"),
        daemon=True,
    )
    t.start()
    return {"job_id": job_id, "status": "running", "topic": topic, "crew_type": req.crew_type}


@app.get("/api/crew/status/{job_id}")
async def crew_status(job_id: str):
    """Poll the status of a running or completed crew job."""
    job = _crew_jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Job '{job_id}' not found")
    return job


@app.get("/api/crew/jobs")
async def crew_jobs():
    """List all crew jobs (newest first)."""
    return {"jobs": [
        {"job_id": jid, "status": j["status"], "topic": j["topic"], "started": j["started"]}
        for jid, j in sorted(_crew_jobs.items(), key=lambda x: x[1]["started"], reverse=True)
    ]}


# ─── Frontend ─────────────────────────────────────────────────────────────────

Path("static").mkdir(exist_ok=True)
Path("static/avatars").mkdir(exist_ok=True)
Path("static/stock").mkdir(exist_ok=True)


@app.get("/stock", include_in_schema=False)
@app.get("/stock/", include_in_schema=False)
async def serve_stock_terminal():
    # Primary: CassanovaL Terminal v2 in static root
    terminal_v2 = Path("static/CassanovaL Terminal v2.html")
    if terminal_v2.exists():
        return FileResponse(str(terminal_v2))
    # Fallback: stock/index.html
    stock_index = Path("static/stock/index.html")
    if stock_index.exists():
        return FileResponse(str(stock_index))
    return JSONResponse({"error": "Stock terminal not found"}, status_code=404)


# Mounts must come AFTER explicit routes so Starlette checks routes first
app.mount("/stock", StaticFiles(directory="static/stock", html=True), name="stock")
app.mount("/static", StaticFiles(directory="static"), name="static")


@app.get("/journal", include_in_schema=False)
@app.get("/journal/", include_in_schema=False)
async def serve_journal():
    p = Path("static/journal/index.html")
    if p.exists():
        return FileResponse(str(p), headers={"Cache-Control": "no-cache"})
    return JSONResponse({"error": "Journal page not found"}, status_code=404)


@app.get("/finance", include_in_schema=False)
@app.get("/finance/", include_in_schema=False)
async def serve_finance():
    p = Path("static/finance/index.html")
    if p.exists():
        return FileResponse(str(p), headers={"Cache-Control": "no-cache"})
    return JSONResponse({"error": "Finance page not found"}, status_code=404)


@app.get("/pixel", include_in_schema=False)
@app.get("/pixel/", include_in_schema=False)
async def serve_pixel():
    p = Path("static/pixel/index.html")
    if p.exists():
        return FileResponse(str(p), headers={"Cache-Control": "no-cache"})
    return JSONResponse({"error": "Pixel page not found"}, status_code=404)


@app.get("/{full_path:path}")
async def serve_frontend(full_path: str):
    index = Path("static/index.html")
    if index.exists():
        return FileResponse(
            str(index),
            headers={
                "Cache-Control": "no-cache, no-store, must-revalidate",
                "Pragma": "no-cache",
                "Expires": "0",
            },
        )
    return JSONResponse(
        {"error": "Frontend not found. Place index.html in static/ folder."},
        status_code=404,
    )


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("server:app", host="0.0.0.0", port=port, reload=True)

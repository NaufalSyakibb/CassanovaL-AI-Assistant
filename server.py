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


@app.get("/api/budget/summary")
async def get_budget_summary():
    try:
        data = json.loads(Path("data/budget.json").read_text(encoding="utf-8"))
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


# ─── Stock Terminal ───────────────────────────────────────────────────────────

def _sse(data: dict) -> str:
    return f"data: {json.dumps(data, ensure_ascii=False, default=float)}\n\n"


async def _run_agent(loop, fn, *args):
    """Run a synchronous agent function in the default executor and return its result."""
    return await loop.run_in_executor(None, fn, *args)


@app.get("/api/stock/analyze")
async def stock_analyze(ticker: str):
    if not ticker or len(ticker) > 20:
        raise HTTPException(status_code=400, detail="Invalid ticker symbol")

    async def generate():
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

            _log("[Scout] Initializing platform monitoring…")
            from agents.scout_agent import ScoutAgent
            scout = ScoutAgent()
            # topic → keyword list (split on comma or space)
            kw_raw = topic.strip() if topic and topic not in ("all platforms",) else ""
            keywords = [k.strip() for k in kw_raw.replace(",", " ").split() if k.strip()] or None
            # scout.run() returns a flat list[dict]
            scout_results = scout.run(platforms=platforms or None, keywords=keywords)
            platform_count = len({r["platform"] for r in scout_results if isinstance(r, dict)})
            _log(f"[Scout] Complete — {len(scout_results)} targets across {platform_count} platform(s)")

            _log("[Harvester] Starting content collection…")
            from agents.harvester_agent import HarvesterAgent
            harvester = HarvesterAgent()
            if platforms:
                harvester._platform_filter = platforms
            scout_file = getattr(scout, "_last_combined_path", None)
            harvester.run(scout_file=scout_file)
            _log("[Harvester] Complete")

            _log("[Cleaner] Normalizing, deduplicating, filtering spam…")
            from agents.cleaner_agent import CleanerAgent
            cleaner = CleanerAgent()
            stats = cleaner.run(
                platforms=platforms or None,
                translate=translate,
                target_lang=target_lang,
            )
            for plat, s in (stats or {}).items():
                _log(f"[Cleaner] {plat}: {s.get('cleaned', 0)} items, "
                     f"{s.get('spam', 0)} spam removed, {s.get('duplicates', 0)} dupes")

            lines = [
                "# Social Scraper Report\n\n",
                f"**Platforms:** {', '.join((stats or {}).keys()) or 'none'}\n",
                f"**Translate:** {'Yes → ' + target_lang if translate else 'No'}\n\n",
                "## Per-Platform Stats\n\n",
                "| Platform | Cleaned | Spam | Dupes |\n",
                "|----------|---------|------|-------|\n",
            ]
            for plat, s in (stats or {}).items():
                lines.append(f"| {plat} | {s.get('cleaned',0)} | {s.get('spam',0)} | {s.get('duplicates',0)} |\n")
            outputs["scraper_report.md"] = "".join(lines)

            cleaned_root = Path(__file__).parent / "social_scraper" / "data" / "cleaned"
            if cleaned_root.exists():
                for plat_dir in sorted(cleaned_root.iterdir()):
                    if not plat_dir.is_dir():
                        continue
                    if platforms and plat_dir.name not in platforms:
                        continue
                    latest = sorted(plat_dir.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
                    if latest:
                        try:
                            items = json.loads(latest[0].read_text(encoding="utf-8"))
                            preview = items[:5] if isinstance(items, list) else items
                            outputs[f"{plat_dir.name}_preview.json"] = json.dumps(preview, ensure_ascii=False, indent=2)
                        except Exception:
                            pass

            result = {"platforms": list((stats or {}).keys()), "total": sum(s.get("cleaned", 0) for s in (stats or {}).values())}

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
    stock_index = Path("static/stock/index.html")
    if stock_index.exists():
        return FileResponse(str(stock_index))
    return JSONResponse({"error": "Stock terminal not found"}, status_code=404)


@app.get("/stock/v2", include_in_schema=False)
@app.get("/stock/v2/", include_in_schema=False)
async def serve_stock_terminal_v2():
    stock_v2_index = Path("static/stock/index_v2.html")
    if stock_v2_index.exists():
        return FileResponse(str(stock_v2_index))
    return JSONResponse({"error": "Stock terminal v2 not found"}, status_code=404)


# Mounts must come AFTER explicit routes so Starlette checks routes first
app.mount("/stock", StaticFiles(directory="static/stock", html=True), name="stock")
app.mount("/static", StaticFiles(directory="static"), name="static")


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

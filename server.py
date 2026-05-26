import asyncio
import json
import sys
import io
import os
import re
import base64
import threading
import uuid
from contextlib import asynccontextmanager
from pathlib import Path
from datetime import datetime, date
from fastapi import FastAPI, HTTPException, UploadFile, File, BackgroundTasks
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from pydantic import BaseModel
from typing import Optional, List
from dotenv import load_dotenv
import uvicorn

load_dotenv()

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

# ─── Proactive Scheduler ─────────────────────────────────────────────────────

_NOTIF_FILE = Path("data/notifications.json")


def _load_json_s(path: Path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def _run_morning_brief():
    """Daily 07:00 — generate and save morning brief if not already done today."""
    today_str = date.today().isoformat()
    data = _load_json_s(_NOTIF_FILE, {"notifications": []})
    if any(n.get("date") == today_str for n in data.get("notifications", [])):
        return  # already generated today
    try:
        from tools.sentinel_tools import (
            _overdue_tasks, _budget_status, _fitness_gaps,
            _mood_trend, _save_notification,
        )
        day_str = datetime.now().strftime("%A, %d %B %Y")
        sections = [
            f"# Morning Brief — {day_str}\n",
            f"## Tasks\n{_overdue_tasks()}",
            f"## Budget\n{_budget_status()}",
            f"## Fitness\n{_fitness_gaps()}",
            f"## Mood\n{_mood_trend()}",
        ]
        try:
            from tools.contradiction_tools import get_all_contradictions
            conflicts = get_all_contradictions()
            if conflicts:
                sections.append("## Conflicts\n" + "\n".join(f"  {c}" for c in conflicts))
        except Exception:
            pass
        _save_notification("\n\n".join(sections))
        print(f"[Scheduler] Morning brief generated for {today_str}")
    except Exception as e:
        print(f"[Scheduler] Morning brief error: {e}")


def _run_weekly_patterns():
    """Sunday 08:00 — compute behavioral patterns and save as notification."""
    try:
        from tools.pattern_tools import compute_patterns
        from tools.sentinel_tools import _save_notification
        result = compute_patterns(30)
        insights = result.get("insights", [])
        coverage = result.get("data_coverage_days", 0)
        if insights and coverage >= 14:
            day_str = datetime.now().strftime("%A, %d %B %Y")
            brief = f"# Weekly Pattern Report — {day_str}\n\n" + "\n".join(f"  • {i}" for i in insights)
            _save_notification(brief)
            print(f"[Scheduler] Weekly patterns saved ({len(insights)} insights)")
    except Exception as e:
        print(f"[Scheduler] Weekly patterns error: {e}")


def _run_monthly_budget():
    """1st of month 09:00 — check budget goals and save alert if goals exceeded."""
    try:
        from tools.contradiction_tools import check_budget_conflicts, check_income_vs_obligations
        from tools.sentinel_tools import _save_notification
        conflicts = check_budget_conflicts() + check_income_vs_obligations()
        if conflicts:
            day_str = datetime.now().strftime("%B %Y")
            brief = f"# Monthly Budget Alert — {day_str}\n\n" + "\n".join(f"  ⚠ {c}" for c in conflicts)
            _save_notification(brief)
            print(f"[Scheduler] Monthly budget alert saved ({len(conflicts)} conflicts)")
    except Exception as e:
        print(f"[Scheduler] Monthly budget error: {e}")


def _run_intelligence_synthesis():
    """Sunday 08:30 — auto-refresh the agent intelligence synthesis."""
    try:
        from tools.intelligence_tools import generate_intelligence_synthesis
        generate_intelligence_synthesis(force=True)
        print("[Scheduler] Intelligence synthesis complete.")
    except Exception as e:
        print(f"[Scheduler] Intelligence synthesis error: {e}")


def _setup_scheduler(scheduler):
    brief_hour = int(os.getenv("MORNING_BRIEF_HOUR", "7"))
    scheduler.add_job(_run_morning_brief,   "cron", hour=brief_hour, minute=0,  id="morning_brief",   replace_existing=True)
    scheduler.add_job(_run_weekly_patterns, "cron", day_of_week="sun", hour=8, minute=0, id="weekly_patterns", replace_existing=True)
    scheduler.add_job(_run_monthly_budget,  "cron", day=1, hour=9, minute=0,    id="monthly_budget",  replace_existing=True)
    scheduler.add_job(_run_intelligence_synthesis, "cron",
                      day_of_week="sun", hour=8, minute=30,
                      id="intelligence_synthesis", replace_existing=True)
    print(f"[Scheduler] Morning brief → daily {brief_hour:02d}:00 WIB | Weekly patterns → Sun 08:00 | Monthly budget → 1st 09:00 | Intelligence → Sun 08:30")


@asynccontextmanager
async def _lifespan(app):
    from apscheduler.schedulers.background import BackgroundScheduler
    scheduler = BackgroundScheduler(timezone="Asia/Jakarta")
    _setup_scheduler(scheduler)
    scheduler.start()
    app.state.scheduler = scheduler

    # Pre-warm router + Alfred agent in background (eliminates first-open cold start)
    def _prewarm():
        try:
            sv = get_supervisor()
            sv._load_agent("task")
            print("[Startup] Alfred agent pre-warmed.")
        except Exception as e:
            print(f"[Startup] Alfred pre-warm failed: {e}")
    threading.Thread(target=_prewarm, daemon=True).start()

    yield
    scheduler.shutdown(wait=False)


app = FastAPI(title="OmniSync API", version="1.0.0", lifespan=_lifespan)

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


class FitnessRecommendRequest(BaseModel):
    ingredients: str = ""


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


_DATA_DIR = Path(__file__).resolve().parent / "data"
_DATA_DIR.mkdir(exist_ok=True)
_WRAP_LOG_PATH = _DATA_DIR / "chat_log.json"

def _log_chat_wrap(agent_key: str, user_msg: str):
    """Append one entry to data/chat_log.json for Monthly Wrap tracking."""
    try:
        if agent_key not in ("news", "coding", "schedule", "fitness", "journal", "budget", "task"):
            return
        log: list = []
        if _WRAP_LOG_PATH.exists():
            try:
                log = json.loads(_WRAP_LOG_PATH.read_text(encoding="utf-8"))
            except Exception:
                log = []
        log.append({
            "ts":     datetime.now().isoformat(timespec="seconds"),
            "month":  datetime.now().strftime("%Y-%m"),
            "agent":  agent_key,
            "preview": user_msg[:200],
        })
        _WRAP_LOG_PATH.write_text(json.dumps(log, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        pass


# ─── Chat ────────────────────────────────────────────────────────────────────

@app.post("/api/chat")
async def chat(req: ChatRequest):
    try:
        supervisor = get_supervisor()
        if req.agent:
            agent_name, response = supervisor.chat_direct(req.agent, req.message)
        else:
            agent_name, response = supervisor.chat(req.message)

        agent_key = req.agent or agent_name.lower()
        _save_chat_history(agent_key, agent_name, req.message, response)
        _log_chat_wrap(agent_key, req.message)

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


# ─── Alfred Sentinel Endpoints ────────────────────────────────────────────────

@app.get("/api/alfred/notifications")
async def get_alfred_notifications():
    """Return all saved morning briefs / notifications, newest first."""
    from tools.sentinel_tools import _load_json, _NOTIF_FILE
    data = _load_json(_NOTIF_FILE, {"notifications": []})
    if not isinstance(data, dict):
        data = {"notifications": []}
    return data


@app.get("/api/alfred/brief/today")
async def get_alfred_brief_today():
    """Return today's morning brief, generating and saving it if not yet created."""
    from tools.sentinel_tools import (
        _load_json, _NOTIF_FILE, _save_notification,
        _overdue_tasks, _budget_status, _fitness_gaps, _mood_trend,
    )
    today_str = datetime.now().strftime("%Y-%m-%d")
    data = _load_json(_NOTIF_FILE, {"notifications": []})
    existing = next((n for n in data.get("notifications", []) if n.get("date") == today_str), None)
    if existing:
        return {"brief": existing["brief"], "date": today_str, "fresh": False}

    day_str = datetime.now().strftime("%A, %d %B %Y")
    sections = [
        f"# Morning Brief — {day_str}\n",
        f"## Tasks\n{_overdue_tasks()}",
        f"## Budget\n{_budget_status()}",
        f"## Fitness\n{_fitness_gaps()}",
        f"## Mood\n{_mood_trend()}",
    ]
    brief = "\n\n".join(sections)
    _save_notification(brief)
    return {"brief": brief, "date": today_str, "fresh": True}


@app.post("/api/alfred/notifications/read")
async def mark_alfred_notifications_read():
    """Mark all notifications as read (clears the bell badge)."""
    from tools.sentinel_tools import _load_json, _NOTIF_FILE
    data = _load_json(_NOTIF_FILE, {"notifications": []})
    for n in data.get("notifications", []):
        n["read"] = True
    _NOTIF_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"ok": True}


@app.get("/api/alfred/schedule")
async def get_alfred_schedule():
    """Return all active scheduled jobs with their next run times."""
    try:
        scheduler = app.state.scheduler
        jobs = []
        for job in scheduler.get_jobs():
            next_run = job.next_run_time
            jobs.append({
                "id":       job.id,
                "next_run": next_run.strftime("%Y-%m-%d %H:%M %Z") if next_run else None,
                "trigger":  str(job.trigger),
            })
        return {"jobs": jobs}
    except Exception as e:
        return {"jobs": [], "error": str(e)}


@app.get("/api/alfred/contradictions")
async def get_alfred_contradictions():
    """Run all contradiction detectors and return detected life conflicts."""
    try:
        from tools.contradiction_tools import get_all_contradictions
        conflicts = get_all_contradictions()
        return {"conflicts": conflicts, "count": len(conflicts)}
    except Exception as e:
        return {"conflicts": [], "count": 0, "error": str(e)}


@app.get("/api/alfred/patterns")
async def get_alfred_patterns():
    """Return behavioral pattern analysis from the last 30 days of personal data."""
    try:
        from tools.pattern_tools import compute_patterns
        result = compute_patterns(30)
        return result
    except Exception as e:
        return {"insights": [], "error": str(e)}


@app.get("/api/alfred/intelligence")
async def get_intelligence():
    """Return cached intelligence synthesis + per-agent experiment stats."""
    try:
        from tools.intelligence_tools import generate_intelligence_synthesis
        return generate_intelligence_synthesis(force=False)
    except Exception as e:
        return {"synthesis": "", "generated_at": None, "agents": [], "error": str(e)}


@app.post("/api/alfred/intelligence/refresh", status_code=202)
async def refresh_intelligence(background_tasks: BackgroundTasks):
    """Trigger a fresh Mistral synthesis in the background. Returns 202 immediately."""
    try:
        from tools.intelligence_tools import generate_intelligence_synthesis
        background_tasks.add_task(generate_intelligence_synthesis, force=True)
        return {"status": "generating"}
    except Exception as e:
        return {"status": "error", "error": str(e)}


# ─── Data Endpoints ───────────────────────────────────────────────────────────

@app.get("/api/tasks")
async def get_tasks():
    try:
        data = json.loads((_DATA_DIR / "tasks.json").read_text(encoding="utf-8"))
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
        data = json.loads((_DATA_DIR / "notes.json").read_text(encoding="utf-8"))
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


@app.get("/api/productivity/dashboard")
async def get_productivity_dashboard():
    from datetime import timedelta as _td
    loop = asyncio.get_running_loop()
    today = datetime.now()
    today_str = today.strftime("%Y-%m-%d")

    # ── Tasks ──────────────────────────────────────────────────────────────────
    try:
        tasks_raw = json.loads((_DATA_DIR / "tasks.json").read_text(encoding="utf-8"))
        priority_order = {"high": 0, "medium": 1, "low": 2}
        pending = [t for t in tasks_raw if t.get("status", "pending") != "done"]
        pending.sort(key=lambda t: (priority_order.get(t.get("priority", "medium"), 1), t.get("due_date") or "9999"))
        tasks = pending[:15]
    except Exception:
        tasks = []

    # ── Google Calendar ────────────────────────────────────────────────────────
    def _fetch_events():
        from tools.schedule_tools import _get_calendar_service
        service = _get_calendar_service()
        day_start = datetime(today.year, today.month, today.day).isoformat() + "Z"
        end_utc   = (datetime(today.year, today.month, today.day) + _td(days=14)).isoformat() + "Z"
        result = service.events().list(
            calendarId="primary",
            timeMin=day_start,
            timeMax=end_utc,
            maxResults=60,
            singleEvents=True,
            orderBy="startTime",
        ).execute()
        return result.get("items", [])

    cal_connected, raw_events = False, []
    try:
        raw_events   = await loop.run_in_executor(None, _fetch_events)
        cal_connected = True
    except Exception:
        pass

    def _parse_event(e):
        start   = e["start"].get("dateTime", e["start"].get("date", ""))
        end_val = e["end"].get("dateTime",   e["end"].get("date",   ""))
        all_day = "T" not in start
        if all_day:
            day = start; st = "All day"; et = ""; hour = 0; minute = 0; dur = 1440
        else:
            day = start[:10]; st = start[11:16]; et = end_val[11:16] if end_val else ""
            try:
                hour, minute = int(start[11:13]), int(start[14:16])
                eh,   em     = int(end_val[11:13]), int(end_val[14:16])
                dur = max((eh * 60 + em) - (hour * 60 + minute), 15)
            except Exception:
                hour, minute, dur = 0, 0, 60
        return {
            "id":           e["id"][:12],
            "title":        e.get("summary", "Untitled"),
            "day":          day,
            "start_time":   st,
            "end_time":     et,
            "is_all_day":   all_day,
            "hour":         hour,
            "minute":       minute,
            "duration_min": dur,
            "description":  e.get("description") or "",
            "location":     e.get("location")    or "",
            "color_id":     e.get("colorId",      ""),
        }

    events      = [_parse_event(e) for e in raw_events]
    today_evs   = [ev for ev in events if ev["day"] == today_str]
    week_events: dict = {}
    for ev in events:
        week_events.setdefault(ev["day"], []).append(ev)
    upcoming    = [ev for ev in events if ev["day"] != today_str][:20]
    week_days   = [(today + _td(days=i)).strftime("%Y-%m-%d") for i in range(7)]

    return {
        "calendar_connected": cal_connected,
        "today":              today_str,
        "today_label":        today.strftime("%A, %d %B %Y"),
        "today_events":       today_evs,
        "week_days":          week_days,
        "week_events":        week_events,
        "upcoming":           upcoming,
        "tasks":              tasks,
    }


@app.get("/api/fitness/dashboard")
async def get_fitness_dashboard():
    from datetime import timedelta as _td
    today = datetime.now()
    today_str = today.strftime("%Y-%m-%d")

    try:
        raw: dict = json.loads((_DATA_DIR / "food_log.json").read_text(encoding="utf-8"))
    except Exception:
        raw = {}

    def _day_totals(entries: list) -> dict:
        return {
            "calories":  round(sum(e.get("calories", 0)  for e in entries), 1),
            "protein_g": round(sum(e.get("protein_g", 0) for e in entries), 1),
            "carbs_g":   round(sum(e.get("carbs_g", 0)   for e in entries), 1),
            "fiber_g":   round(sum(e.get("fiber_g", 0)   for e in entries), 1),
            "fat_g":     round(sum(e.get("fat_g", 0)     for e in entries), 1),
        }

    # ── Today ──────────────────────────────────────────────────────────────────
    today_entries = raw.get(today_str, [])
    today_totals  = _day_totals(today_entries)
    today_grouped: dict = {}
    for e in today_entries:
        meal = (e.get("meal_time") or "lainnya").capitalize()
        today_grouped.setdefault(meal, []).append(e)

    # ── 14-day weekly ──────────────────────────────────────────────────────────
    weekly = []
    for i in range(13, -1, -1):
        d       = (today - _td(days=i)).strftime("%Y-%m-%d")
        entries = raw.get(d, [])
        t       = _day_totals(entries) if entries else {"calories":0,"protein_g":0,"carbs_g":0,"fiber_g":0,"fat_g":0}
        t["date"]        = d
        t["has_data"]    = bool(entries)
        t["entry_count"] = len(entries)
        weekly.append(t)

    days_with_data = [w for w in weekly if w["has_data"]]
    if days_with_data:
        n = len(days_with_data)
        weekly_avg = {k: round(sum(d[k] for d in days_with_data) / n, 1)
                      for k in ["calories","protein_g","carbs_g","fiber_g","fat_g"]}
        weekly_avg["days_logged"] = n
    else:
        weekly_avg = {"calories":0,"protein_g":0,"carbs_g":0,"fiber_g":0,"fat_g":0,"days_logged":0}

    # ── Food frequency (all-time) ───────────────────────────────────────────────
    freq: dict = {}
    for d, entries in raw.items():
        for e in entries:
            name = e["food"]
            if name not in freq:
                freq[name] = {"food":name,"count":0,"last_eaten":"","total_cal":0}
            freq[name]["count"]     += 1
            freq[name]["total_cal"] += e.get("calories", 0)
            if d > freq[name]["last_eaten"]:
                freq[name]["last_eaten"] = d
    food_frequency = sorted(freq.values(), key=lambda x: x["count"], reverse=True)[:25]
    for f in food_frequency:
        f["avg_cal"] = round(f["total_cal"] / f["count"]) if f["count"] else 0

    return {
        "today":           today_str,
        "today_label":     today.strftime("%A, %d %B %Y"),
        "today_entries":   today_entries,
        "today_grouped":   today_grouped,
        "today_totals":    today_totals,
        "weekly":          weekly,
        "weekly_avg":      weekly_avg,
        "food_frequency":  food_frequency,
        "total_days":      len([d for d in raw if raw[d]]),
        "total_entries":   sum(len(v) for v in raw.values()),
    }


@app.post("/api/fitness/recommend")
async def fitness_recommend(body: FitnessRecommendRequest):
    ingredients = body.ingredients.strip()
    try:
        raw: dict = json.loads((_DATA_DIR / "food_log.json").read_text(encoding="utf-8"))
    except Exception:
        raw = {}

    freq: dict = {}
    cal_total, entry_count = 0.0, 0
    for entries in raw.values():
        for e in entries:
            n = e["food"]
            freq[n] = freq.get(n, 0) + 1
            cal_total   += e.get("calories", 0)
            entry_count += 1

    top_foods    = sorted(freq.items(), key=lambda x: x[1], reverse=True)[:12]
    top_food_str = ", ".join(f"{n} ({c}x)" for n, c in top_foods) or "belum ada data"
    avg_cal      = round(cal_total / max(len([d for d in raw if raw[d]]), 1))

    prompt = f"""Kamu adalah Lavoisier, AI nutrition coach personal.

DATA POLA MAKAN PENGGUNA:
- Makanan paling sering dikonsumsi: {top_food_str}
- Rata-rata kalori per hari: {avg_cal} kkal
- Bahan / makanan yang tersedia: {ingredients if ingredients else "bebas, gunakan bahan umum"}

TUGAS: Buat TEPAT 3 rekomendasi menu sehat yang praktis. Balas HANYA dengan JSON array valid (tanpa teks lain):
[
  {{
    "name": "Nama Menu",
    "description": "Deskripsi singkat menggugah selera",
    "meal_type": "sarapan",
    "ingredients": ["100g dada ayam", "2 butir telur", "1 sdt minyak zaitun"],
    "steps": ["Panaskan wajan…", "Masukkan ayam…", "Sajikan dengan…"],
    "macros": {{"calories": 420, "protein_g": 35, "carbs_g": 40, "fat_g": 10, "fiber_g": 4}},
    "why": "Alasan singkat kenapa menu ini cocok untuk pola makanmu"
  }}
]"""

    api_key = os.getenv("MISTRAL_API_KEY")
    if not api_key:
        raise HTTPException(status_code=500, detail="MISTRAL_API_KEY not set")
    try:
        from mistralai import Mistral
        client = Mistral(api_key=api_key)
        resp = client.chat.complete(
            model="mistral-large-latest",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7,
        )
        content = resp.choices[0].message.content.strip()
        match   = re.search(r"\[.*\]", content, re.DOTALL)
        if not match:
            raise ValueError("No JSON array in response")
        menus = json.loads(match.group())
        return {"menus": menus, "context": {"top_foods": top_food_str, "avg_cal": avg_cal}}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"AI error: {e}")


@app.get("/api/monthly-wrap")
async def get_monthly_wrap(month: str = None):
    """Spotify Wrapped-style monthly recap for all agents."""
    from datetime import timedelta as _td
    loop = asyncio.get_running_loop()

    today = datetime.now()
    if not month:
        month = today.strftime("%Y-%m")
    try:
        _yr, _mo = month.split("-")
        yr, mo = int(_yr), int(_mo)
    except Exception:
        yr, mo = today.year, today.month
        month = f"{yr:04d}-{mo:02d}"
    import calendar as _cal
    month_label = f"{_cal.month_name[mo]} {yr}"

    # ── 1. Lavoisier (food_log.json) ──────────────────────────────────────────
    def _food_stats():
        try:
            raw: dict = json.loads((_DATA_DIR / "food_log.json").read_text(encoding="utf-8"))
        except Exception:
            return {}
        entries, freq, cal_sum, pro_sum, car_sum, fat_sum = [], {}, 0, 0, 0, 0
        meal_dist: dict = {}
        for day, day_entries in raw.items():
            if not day.startswith(month):
                continue
            for e in day_entries:
                entries.append(e)
                n = e.get("food", "?")
                freq[n] = freq.get(n, 0) + 1
                cal_sum += e.get("calories", 0)
                pro_sum += e.get("protein_g", 0)
                car_sum += e.get("carbs_g", 0)
                fat_sum += e.get("fat_g", 0)
                m = (e.get("meal_time") or "other").lower()
                meal_dist[m] = meal_dist.get(m, 0) + 1
        days_logged = len({d for d in raw if d.startswith(month) and raw[d]})
        top_foods = sorted(freq.items(), key=lambda x: x[1], reverse=True)[:6]
        return {
            "total_entries": len(entries),
            "days_logged": days_logged,
            "unique_foods": len(freq),
            "total_calories": round(cal_sum),
            "avg_daily_cal": round(cal_sum / max(days_logged, 1)),
            "total_protein": round(pro_sum),
            "total_carbs":   round(car_sum),
            "total_fat":     round(fat_sum),
            "top_foods": [{"name": n, "count": c} for n, c in top_foods],
            "meal_distribution": meal_dist,
            "top_food": top_foods[0][0] if top_foods else "—",
        }

    # ── 2. Mansa (budget.json) ────────────────────────────────────────────────
    def _mansa_stats():
        try:
            raw = json.loads((_DATA_DIR / "budget.json").read_text(encoding="utf-8"))
            txns = raw.get("transactions", []) if isinstance(raw, dict) else raw
        except Exception:
            return {}
        month_txns = [t for t in txns if str(t.get("date", "")).startswith(month)]
        income  = sum(t["amount"] for t in month_txns if t.get("type") == "income")
        expense = sum(t["amount"] for t in month_txns if t.get("type") == "expense")
        cat_spend: dict = {}
        for t in month_txns:
            if t.get("type") == "expense":
                c = t.get("category", "other")
                cat_spend[c] = cat_spend.get(c, 0) + t["amount"]
        top_cats = sorted(cat_spend.items(), key=lambda x: x[1], reverse=True)[:5]
        biggest = max(month_txns, key=lambda t: t.get("amount", 0), default=None)
        return {
            "total_income":   round(income),
            "total_expense":  round(expense),
            "net":            round(income - expense),
            "transaction_count": len(month_txns),
            "top_categories": [{"name": c, "amount": round(a)} for c, a in top_cats],
            "top_category":   top_cats[0][0] if top_cats else "—",
            "biggest_expense": biggest.get("description", "—") if biggest else "—",
            "biggest_amount":  round(biggest.get("amount", 0)) if biggest else 0,
        }

    # ── 3. Dostoyevsky (journal markdown files) ───────────────────────────────
    def _dostoy_stats():
        from dotenv import load_dotenv; load_dotenv()
        vault = os.getenv("OBSIDIAN_VAULT_PATH", "").strip()
        if vault:
            base = Path(vault) / "Dostoyevsky Agent"
        else:
            base = Path("AI Data/My AI/Dostoyevsky Agent")
        if not base.exists():
            return {"entry_count": 0, "content_preview": ""}
        files = sorted(base.glob(f"Journal_{yr:04d}-{mo:02d}-*.md"))
        entry_count = len(files)
        content = ""
        for f in files[:5]:
            try:
                content += f.read_text(encoding="utf-8")[:1500] + "\n\n"
            except Exception:
                pass
        return {"entry_count": entry_count, "content_preview": content[:6000]}

    # ── 4. Miyamoto (Google Calendar) ────────────────────────────────────────
    def _miyamoto_stats():
        try:
            from tools.schedule_tools import _get_calendar_service
            service = _get_calendar_service()
            import calendar as _cal2
            last_day = _cal2.monthrange(yr, mo)[1]
            t_min = f"{yr:04d}-{mo:02d}-01T00:00:00Z"
            t_max = f"{yr:04d}-{mo:02d}-{last_day:02d}T23:59:59Z"
            items = service.events().list(
                calendarId="primary", timeMin=t_min, timeMax=t_max,
                maxResults=250, singleEvents=True, orderBy="startTime",
            ).execute().get("items", [])
        except Exception:
            return {"connected": False, "event_count": 0}
        day_freq: dict = {}
        total_min = 0
        for e in items:
            start = e["start"].get("dateTime", e["start"].get("date", ""))
            end_v = e["end"].get("dateTime", e["end"].get("date", ""))
            day   = start[:10]
            day_freq[day] = day_freq.get(day, 0) + 1
            if "T" in start and "T" in end_v:
                try:
                    sh, sm = int(start[11:13]), int(start[14:16])
                    eh, em = int(end_v[11:13]),  int(end_v[14:16])
                    total_min += max((eh*60+em) - (sh*60+sm), 0)
                except Exception:
                    pass
        busiest = max(day_freq, key=day_freq.get) if day_freq else "—"
        top_events = [e.get("summary", "Untitled") for e in items[:3]]
        return {
            "connected": True,
            "event_count": len(items),
            "total_hours": round(total_min / 60, 1),
            "busiest_day": busiest,
            "busiest_count": day_freq.get(busiest, 0),
            "sample_events": top_events,
        }

    # ── 5. Najwa + Linus (chat_log.json) ─────────────────────────────────────
    def _chat_stats(agent_key: str):
        try:
            log = json.loads(_WRAP_LOG_PATH.read_text(encoding="utf-8")) if _WRAP_LOG_PATH.exists() else []
        except Exception:
            log = []
        entries = [e for e in log if e.get("month") == month and e.get("agent") == agent_key]
        previews = [e.get("preview", "") for e in entries]
        return {"session_count": len(entries), "previews": previews[:20]}

    # ── Gather all in parallel ────────────────────────────────────────────────
    food_d, mansa_d, dostoy_d, miyamoto_d, najwa_d, linus_d = await asyncio.gather(
        loop.run_in_executor(None, _food_stats),
        loop.run_in_executor(None, _mansa_stats),
        loop.run_in_executor(None, _dostoy_stats),
        loop.run_in_executor(None, _miyamoto_stats),
        loop.run_in_executor(None, lambda: _chat_stats("news")),
        loop.run_in_executor(None, lambda: _chat_stats("coding")),
    )

    # ── AI Narratives (Mistral) ───────────────────────────────────────────────
    narratives: dict = {}
    try:
        from mistralai import Mistral
        _client = Mistral(api_key=os.getenv("MISTRAL_API_KEY", ""))

        def _narrative(system: str, user: str) -> str:
            r = _client.chat.complete(
                model="mistral-large-latest",
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user",   "content": user},
                ],
                max_tokens=180, temperature=0.85,
            )
            return r.choices[0].message.content.strip()

        sys_base = (
            "Kamu adalah narrator CassanovaL Monthly Wrap. "
            "Tulis 2 kalimat yang personal, hangat, sedikit puitis dalam Bahasa Indonesia. "
            "Gunakan data yang diberikan. Jangan bullet point, cukup prosa pendek."
        )

        # Run narratives concurrently
        def _lavoisier_narr():
            if not food_d.get("total_entries"):
                return "Belum ada log makanan bulan ini. Mulai catat makanmu!"
            return _narrative(sys_base,
                f"Lavoisier bulan {month_label}: {food_d['total_entries']} kali makan, "
                f"makanan terfavorit: {food_d.get('top_food','—')}, "
                f"total kalori: {food_d.get('total_calories',0)} kkal, "
                f"{food_d.get('days_logged',0)} hari tercatat.")

        def _mansa_narr():
            if not mansa_d.get("transaction_count"):
                return "Belum ada transaksi bulan ini. Mulai catat keuanganmu!"
            return _narrative(sys_base,
                f"Mansa bulan {month_label}: pengeluaran Rp{mansa_d.get('total_expense',0):,}, "
                f"pemasukan Rp{mansa_d.get('total_income',0):,}, "
                f"kategori terbesar: {mansa_d.get('top_category','—')}, "
                f"{mansa_d.get('transaction_count',0)} transaksi.")

        def _dostoy_narr():
            if not dostoy_d.get("entry_count"):
                return "Belum ada jurnal bulan ini. Tulis sesuatu untuk Dostoyevsky!"
            preview = dostoy_d.get("content_preview", "")[:3000]
            return _narrative(
                sys_base + " Analisis mood dan emosi dari potongan jurnal berikut.",
                f"Jurnal Dostoyevsky bulan {month_label} ({dostoy_d['entry_count']} entri):\n\n{preview}")

        def _miyamoto_narr():
            if not miyamoto_d.get("connected") or not miyamoto_d.get("event_count"):
                return "Kalender belum tersambung atau belum ada event bulan ini."
            return _narrative(sys_base,
                f"Miyamoto bulan {month_label}: {miyamoto_d['event_count']} event, "
                f"total {miyamoto_d.get('total_hours',0)} jam, "
                f"hari tersibuk: {miyamoto_d.get('busiest_day','—')} "
                f"dengan {miyamoto_d.get('busiest_count',0)} event.")

        def _najwa_narr():
            if not najwa_d.get("session_count"):
                return "Belum ada sesi berita tercatat. Mulai chat dengan Najwa!"
            return _narrative(sys_base,
                f"Najwa bulan {month_label}: {najwa_d['session_count']} sesi berita. "
                f"Topik yang dibahas: {'; '.join(najwa_d.get('previews',[])[:5])}")

        def _linus_narr():
            if not linus_d.get("session_count"):
                return "Belum ada sesi coding tercatat. Mulai belajar kode dengan Linus!"
            return _narrative(sys_base,
                f"Linus bulan {month_label}: {linus_d['session_count']} sesi coding. "
                f"Yang dipelajari: {'; '.join(linus_d.get('previews',[])[:5])}")

        narr_results = await asyncio.gather(
            loop.run_in_executor(None, _lavoisier_narr),
            loop.run_in_executor(None, _mansa_narr),
            loop.run_in_executor(None, _dostoy_narr),
            loop.run_in_executor(None, _miyamoto_narr),
            loop.run_in_executor(None, _najwa_narr),
            loop.run_in_executor(None, _linus_narr),
        )
        keys = ["lavoisier", "mansa", "dostoyevsky", "miyamoto", "najwa", "linus"]
        narratives = dict(zip(keys, narr_results))
    except Exception as _narr_err:
        pass  # narratives stay empty, frontend shows raw stats

    return {
        "month": month,
        "month_label": month_label,
        "lavoisier":   {**food_d,    "narrative": narratives.get("lavoisier", "")},
        "mansa":       {**mansa_d,   "narrative": narratives.get("mansa", "")},
        "dostoyevsky": {**dostoy_d,  "narrative": narratives.get("dostoyevsky", "")},
        "miyamoto":    {**miyamoto_d,"narrative": narratives.get("miyamoto", "")},
        "najwa":       {**najwa_d,   "narrative": narratives.get("najwa", "")},
        "linus":       {**linus_d,   "narrative": narratives.get("linus", "")},
    }


@app.get("/api/budget/summary")
async def get_budget_summary():
    try:
        raw = json.loads((_DATA_DIR / "budget.json").read_text(encoding="utf-8"))
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
        raw = json.loads((_DATA_DIR / "budget.json").read_text(encoding="utf-8"))
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
    """Normalize ticker: uppercase + strip. Tools handle .JK fallback internally."""
    return raw.upper().strip()


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
                run_deep_research, run_news_intelligence, run_technical_analyst,
                run_strategy, run_final_verdict, run_buy_timing,
            )
            from tools.stock_tools import (
                build_candlestick_json, build_heatmap_json, build_python_code,
                get_technical_indicators,
            )
            loop = asyncio.get_running_loop()

            # ── Phase 1: DeepResearch ─────────────────────────────────────
            yield _sse({"event": "step", "agent": "DeepResearch", "status": "running"})
            deep_research_data = await _run_agent(loop, run_deep_research, ticker)
            price  = deep_research_data.get("current_price", "N/A")
            growth = deep_research_data.get("growth_trend", "N/A")
            yield _sse({"event": "log", "text": f"Harga: {price} | Growth: {growth}"})
            yield _sse({"event": "step", "agent": "DeepResearch", "status": "done"})

            # ── Phase 1.5 — direct tool call, no LLM ─────────────────────────
            try:
                tech_raw = get_technical_indicators.invoke({"ticker": ticker})
                technical_data = json.loads(tech_raw) if isinstance(tech_raw, str) else tech_raw
            except Exception:
                technical_data = {}
            technical_analyst_data = {}
            yield _sse({"event": "technicals", "data": technical_data})

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
                "event":    "market",
                "price":    float(price) if isinstance(price, (int, float)) else 0,
                "chg":      round(float(chg_1y), 2),
                "pe":       f"{float(pe_raw):.1f}x" if pe_raw else "N/A",
                "roe":      f"{float(roe_raw) * 100:.1f}%" if roe_raw else "N/A",
                "rsi":      rsi_val,
                "currency": "IDR" if ticker.endswith(".JK") else "USD",
            })

            await asyncio.sleep(5)

            # ── Phase 2 — parallel: NewsIntelligence + TechnicalAnalyst ─────
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

            # ── Phase 3: Strategy ─────────────────────────────────────────
            yield _sse({"event": "step", "agent": "Strategy", "status": "running"})
            strategy_data = await _run_agent(
                loop, run_strategy, deep_research_data, news_data,
                technical_analyst_data, technical_data,
            )
            entry = strategy_data.get("entry_zone", "N/A")
            rr    = strategy_data.get("risk_reward_ratio", "N/A")
            yield _sse({"event": "strategy", "data": strategy_data})
            yield _sse({"event": "log", "text": f"Entry: {entry} | R/R: {rr}"})
            yield _sse({"event": "step", "agent": "Strategy", "status": "done"})

            await asyncio.sleep(5)

            # ── Phase 4: FinalVerdict ─────────────────────────────────────
            yield _sse({"event": "step", "agent": "FinalVerdict", "status": "running"})
            verdict_data = await _run_agent(
                loop, run_final_verdict, ticker, deep_research_data, news_data,
                strategy_data, technical_analyst_data, technical_data,
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


# ── Study Pipeline ─────────────────────────────────────────────────────────────

@app.get("/api/study/generate")
async def study_generate(topic: str):
    if not topic or not topic.strip():
        raise HTTPException(status_code=400, detail="Topic is required")
    if len(topic) > 200:
        raise HTTPException(status_code=400, detail="Topic too long (max 200 chars)")
    topic = topic.strip()

    async def generate():
        yield _sse({"event": "log", "text": f"Memulai pipeline untuk: {topic}..."})
        try:
            from agents.study_agents import run_materi_agent, run_konsep_agent, run_ringkasan_agent
            loop = asyncio.get_running_loop()

            # Phase 1: MateriAgent
            yield _sse({"event": "step", "agent": "MateriAgent", "status": "running"})
            materi_data = await _run_agent(loop, run_materi_agent, topic)
            yield _sse({"event": "materi", "data": materi_data})
            yield _sse({"event": "step", "agent": "MateriAgent", "status": "done"})

            sections = materi_data.get("sections", [])
            materi_text = "\n\n".join(
                f"{s.get('title', '')}\n{s.get('content', '')}" for s in sections
            )

            # Phase 2: KonsepAgent
            yield _sse({"event": "step", "agent": "KonsepAgent", "status": "running"})
            konsep_data = await _run_agent(loop, run_konsep_agent, topic, materi_text)
            yield _sse({"event": "konsep", "data": konsep_data})
            yield _sse({"event": "step", "agent": "KonsepAgent", "status": "done"})

            concepts = konsep_data.get("concepts", [])
            konsep_text = "\n".join(
                f"- {c.get('term', '')}: {c.get('definition', '')}" for c in concepts
            )

            # Phase 3: RingkasanAgent
            yield _sse({"event": "step", "agent": "RingkasanAgent", "status": "running"})
            ringkasan_data = await _run_agent(loop, run_ringkasan_agent, topic, materi_text, konsep_text)
            yield _sse({"event": "ringkasan", "data": ringkasan_data})
            yield _sse({"event": "step", "agent": "RingkasanAgent", "status": "done"})

            yield _sse({"event": "done"})

        except Exception as e:
            yield _sse({"event": "error", "message": str(e)})

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


class StudySaveRequest(BaseModel):
    topic: str
    materi: dict
    konsep: dict
    ringkasan: dict


@app.post("/api/study/save")
async def study_save(req: StudySaveRequest):
    notes_path = Path("data/notes.json")
    try:
        notes = json.loads(notes_path.read_text(encoding="utf-8")) if notes_path.exists() else []
    except Exception:
        notes = []

    sections = req.materi.get("sections", [])
    concepts = req.konsep.get("concepts", [])
    summary = req.ringkasan.get("summary", "")

    lines = [f"# {req.topic}\n\n## Materi Lengkap\n"]
    for s in sections:
        lines.append(f"### {s.get('title', '')}\n{s.get('content', '')}\n")
    lines.append("\n## Konsep Kunci\n")
    for c in concepts:
        lines.append(f"**{c.get('term', '')}:** {c.get('definition', '')}")
    lines.append(f"\n## Ringkasan\n{summary}")

    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    note = {
        "id": uuid.uuid4().hex[:8],
        "title": req.topic,
        "content": "\n".join(lines),
        "tags": ["study", "cicero"],
        "created_at": now,
        "updated_at": now,
    }
    notes.append(note)
    notes_path.write_text(json.dumps(notes, indent=2, ensure_ascii=False), encoding="utf-8")
    return {"id": note["id"], "title": note["title"]}


# ── Stock Picks Screener ───────────────────────────────────────────────────────

_VALID_PICK_REGIONS = {"us", "asia", "idx"}

@app.get("/api/stock/picks")
async def stock_picks(region: str = "us"):
    region = region.lower()
    if region not in _VALID_PICK_REGIONS:
        raise HTTPException(status_code=400, detail=f"Unknown region: {region}. Valid: us, asia, idx")

    async def generate():
        try:
            from agents.stock_screener import run_pick_screener, WATCHLISTS
            tickers = WATCHLISTS.get(region, [])
            if not tickers:
                yield _sse({"event": "error", "message": f"No watchlist for region: {region}"})
                return

            yield _sse({"event": "picks_start", "region": region, "total": len(tickers)})
            loop = asyncio.get_running_loop()
            count = 0

            for i in range(0, len(tickers), 3):
                batch = tickers[i:i + 3]
                tasks = [_run_agent(loop, run_pick_screener, t) for t in batch]
                results = await asyncio.gather(*tasks, return_exceptions=True)
                for ticker, result in zip(batch, results):
                    if isinstance(result, Exception):
                        yield _sse({"event": "pick_result", "ticker": ticker, "verdict": "ERROR",
                                    "conviction_score": 0, "rationale": str(result)[:120],
                                    "key_catalyst": "", "risk_factor": "", "pe_ratio": 0, "rsi": 0})
                    else:
                        yield _sse({"event": "pick_result", **result})
                    count += 1

            yield _sse({"event": "picks_done", "region": region, "count": count})
        except Exception as e:
            yield _sse({"event": "error", "message": str(e)})

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


# ── Da Vinci Creative Page ─────────────────────────────────────────────────────

@app.get("/api/davinci/generate")
async def davinci_generate(topic: str = ""):
    topic = topic.strip()
    if not topic:
        raise HTTPException(status_code=400, detail="Topic required")
    if len(topic) > 200:
        raise HTTPException(status_code=400, detail="Topic too long (max 200 chars)")

    async def generate():
        try:
            from agents.davinci_pipeline import run_idea_generator
            loop = asyncio.get_running_loop()
            result = await _run_agent(loop, run_idea_generator, topic)
            ideas = result.get("ideas", [])
            for idea in ideas:
                yield _sse({"event": "idea", **idea})
            yield _sse({"event": "ideas_done", "count": len(ideas)})
        except Exception as e:
            yield _sse({"event": "error", "message": str(e)})

    return StreamingResponse(generate(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@app.get("/api/davinci/expand")
async def davinci_expand(ideas: str = ""):
    try:
        ideas_list = json.loads(ideas)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid ideas param — must be JSON array")
    if not ideas_list:
        raise HTTPException(status_code=400, detail="No ideas provided")

    async def generate():
        try:
            from agents.davinci_pipeline import run_idea_expander
            loop = asyncio.get_running_loop()
            tasks = [_run_agent(loop, run_idea_expander, idea["title"], idea.get("tagline", ""))
                     for idea in ideas_list]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            count = 0
            for idea, result in zip(ideas_list, results):
                if isinstance(result, Exception):
                    yield _sse({"event": "expansion", "title": idea["title"],
                                "error": str(result)[:120]})
                else:
                    yield _sse({"event": "expansion", **result})
                count += 1
            yield _sse({"event": "expand_done", "count": count})
        except Exception as e:
            yield _sse({"event": "error", "message": str(e)})

    return StreamingResponse(generate(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


class DaVinciSaveRequest(BaseModel):
    topic: str
    expansions: list[dict]


@app.post("/api/davinci/save")
async def davinci_save(req: DaVinciSaveRequest):
    notes_path = Path("data/notes.json")
    try:
        notes = json.loads(notes_path.read_text(encoding="utf-8"))
    except Exception:
        notes = []
    for exp in req.expansions:
        content = f"## {exp.get('title', '')}\n\n"
        content += f"**Use Cases:** {exp.get('use_cases', '')}\n\n"
        content += f"**Steps:** {exp.get('steps', '')}\n\n"
        content += f"**Example:** {exp.get('example', '')}\n\n"
        content += f"**Impact:** {exp.get('impact', '')}"
        notes.append({
            "id": str(uuid.uuid4()),
            "title": exp.get("title", req.topic),
            "content": content,
            "tags": ["da-vinci", "brainstorming", req.topic[:30]],
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
        })
    notes_path.write_text(json.dumps(notes, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"saved": len(req.expansions)}


# ── Nostradamus Prophetic Page ────────────────────────────────────────────────

@app.get("/api/nostradamus/prophesy")
async def nostradamus_prophesy(event: str = ""):
    event = event.strip()
    if not event:
        raise HTTPException(status_code=400, detail="Event required")
    if len(event) > 200:
        raise HTTPException(status_code=400, detail="Event too long (max 200 chars)")

    async def generate():
        try:
            from agents.nostradamus_pipeline import run_news_gatherer, run_predictor, run_council, PREDICTORS
            loop = asyncio.get_running_loop()

            # Phase 1 — News gathering
            news_result = await _run_agent(loop, run_news_gatherer, event)
            news_items = news_result.get("news", [])
            news_summary = "\n".join(
                f"- {n.get('headline', '')} ({n.get('source', '')}, {n.get('date', '')}): {n.get('summary', '')}"
                for n in news_items
            )
            for item in news_items:
                yield _sse({"event": "news_item", **item})
            yield _sse({"event": "news_done", "count": len(news_items)})

            # Phase 2 — Parallel predictions, stream as each finishes
            async def safe_predict(predictor):
                try:
                    return await _run_agent(loop, run_predictor, predictor, event, news_summary)
                except Exception as exc:
                    return {"agent_id": predictor["id"], "agent_name": predictor["name"],
                            "error": str(exc)[:120]}

            tasks = [asyncio.create_task(safe_predict(p)) for p in PREDICTORS]
            predictions = []
            for coro in asyncio.as_completed(tasks):
                result = await coro
                if "error" not in result:
                    predictions.append(result)
                yield _sse({"event": "prediction", **result})
            yield _sse({"event": "predictions_done", "count": len(PREDICTORS)})

            # Phase 3 — Council verdict
            verdict = await _run_agent(loop, run_council, event, predictions)
            yield _sse({"event": "verdict", **verdict})
            yield _sse({"event": "prophesy_done"})

        except Exception as exc:
            yield _sse({"event": "error", "message": str(exc)})

    return StreamingResponse(generate(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


class NostradamusSaveRequest(BaseModel):
    event: str
    verdict: dict


@app.post("/api/nostradamus/save")
async def nostradamus_save(req: NostradamusSaveRequest):
    notes_path = Path("data/notes.json")
    try:
        notes = json.loads(notes_path.read_text(encoding="utf-8"))
    except Exception:
        notes = []
    v = req.verdict
    content = (
        f"## {v.get('verdict_title', req.event)}\n\n"
        f"{v.get('verdict_detail', '')}\n\n"
        f"**Kepercayaan:** {v.get('confidence', '?')}%  \n"
        f"**Didukung:** {v.get('endorsed_agent', '')}  \n"
        f"**Dissent:** {v.get('dissenting_view', '')}"
    )
    notes.append({
        "id": str(uuid.uuid4()),
        "title": v.get("verdict_title", req.event),
        "content": content,
        "tags": ["nostradamus", "prediction", req.event[:30]],
        "created_at": datetime.now().isoformat(),
        "updated_at": datetime.now().isoformat(),
    })
    notes_path.write_text(json.dumps(notes, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"saved": 1}


# ─── Najwa News Feed ──────────────────────────────────────────────────────────

_news_cache: dict = {"data": None, "ts": 0.0}

@app.get("/api/news/feed")
async def get_news_feed():
    """Return live news for all categories, cached for 3 minutes."""
    import time as _t
    now = _t.time()
    if _news_cache["data"] and now - _news_cache["ts"] < 180:
        return _news_cache["data"]

    from tools.news_tools import _search_news
    loop = asyncio.get_running_loop()

    categories = {
        "breaking":   "breaking news urgent today",
        "world":      "world news today international",
        "technology": "technology AI software news today",
        "business":   "business economy markets finance today",
        "indonesia":  "Indonesia news berita hari ini",
    }

    async def _fetch(cat: str, query: str):
        try:
            items = await loop.run_in_executor(None, _search_news, query, 8)
            return cat, items
        except Exception:
            return cat, []

    results = await asyncio.gather(*[_fetch(c, q) for c, q in categories.items()])
    data = {cat: articles for cat, articles in results}
    _news_cache["data"] = data
    _news_cache["ts"] = now
    return data


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

            _log(f"[Scraper] Firecrawl pipeline — platforms: {', '.join(active_platforms)}")
            if keywords:
                _log(f"[Scraper] Keywords: {', '.join(keywords)}")
            _log("[Scraper] Agents: Discover → Scrape → Extract (parallel across platforms)")

            from social_scraper.agents.firecrawl_harvester import FirecrawlHarvester
            harvester = FirecrawlHarvester()

            # Run all platforms in parallel (harvester handles ThreadPoolExecutor internally)
            saved_files = harvester.run(platforms=active_platforms, keywords=keywords)

            for plat, path in saved_files.items():
                items = json.loads(path.read_text(encoding="utf-8"))
                total_chars = sum(i.get("raw_length", 0) for i in items)
                n_topics = sum(len(i.get("topics", [])) for i in items)
                _log(f"[{plat.upper()}] {n_topics} topics, {total_chars:,} chars → {path.name}")

            for plat in active_platforms:
                if plat not in saved_files:
                    _log(f"[{plat.upper()}] No data collected")

            # Build summary report
            lines = [
                "# Social Scraper Report\n\n",
                f"**Engine:** Firecrawl-pattern (Discover → Scrape → Extract)\n",
                f"**Platforms:** {', '.join(saved_files.keys()) or 'none'}\n",
                f"**Keywords:** {', '.join(keywords) if keywords else 'trending (default)'}\n\n",
                "## Per-Platform Results\n\n",
                "| Platform | Topics | Sources | Chars | File |\n",
                "|----------|--------|---------|-------|------|\n",
            ]
            for plat, path in saved_files.items():
                items = json.loads(path.read_text(encoding="utf-8"))
                n_topics = sum(len(i.get("topics", [])) for i in items)
                n_sources = sum(len(i.get("sources", [])) for i in items)
                total_chars = sum(i.get("raw_length", 0) for i in items)
                lines.append(f"| {plat} | {n_topics} | {n_sources} | {total_chars:,} | {path.name} |\n")
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

            # AI summaries per platform (parallel, each with 90s timeout)
            if saved_files:
                _log("[Summarizer] Generating AI insights per platform (parallel)...")
                from social_scraper.agents.summarizer_agent import SummarizerAgent
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
Path("static/study").mkdir(exist_ok=True)
Path("static/davinci").mkdir(exist_ok=True)
Path("static/nostradamus").mkdir(exist_ok=True)


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


@app.get("/study", include_in_schema=False)
@app.get("/study/", include_in_schema=False)
async def serve_study():
    p = Path("static/study/index.html")
    if p.exists():
        return FileResponse(str(p), headers={"Cache-Control": "no-cache"})
    return JSONResponse({"error": "Study page not found"}, status_code=404)


@app.get("/davinci", include_in_schema=False)
@app.get("/davinci/", include_in_schema=False)
async def serve_davinci():
    p = Path("static/davinci/index.html")
    if p.exists():
        return FileResponse(str(p), headers={"Cache-Control": "no-cache"})
    return JSONResponse({"error": "Da Vinci page not found"}, status_code=404)


@app.get("/nostradamus", include_in_schema=False)
@app.get("/nostradamus/", include_in_schema=False)
async def serve_nostradamus():
    p = Path("static/nostradamus/index.html")
    if p.exists():
        return FileResponse(str(p), headers={"Cache-Control": "no-cache"})
    return JSONResponse({"error": "Nostradamus page not found"}, status_code=404)


@app.get("/fitness", include_in_schema=False)
@app.get("/fitness/", include_in_schema=False)
async def serve_fitness():
    p = Path("static/fitness/index.html")
    if p.exists():
        return FileResponse(str(p), headers={"Cache-Control": "no-cache"})
    return JSONResponse({"error": "Fitness page not found"}, status_code=404)


@app.get("/coding", include_in_schema=False)
@app.get("/coding/", include_in_schema=False)
async def serve_coding():
    p = Path("static/coding/index.html")
    if p.exists():
        return FileResponse(str(p), headers={"Cache-Control": "no-cache"})
    return JSONResponse({"error": "Coding page not found"}, status_code=404)


@app.get("/productivity", include_in_schema=False)
@app.get("/productivity/", include_in_schema=False)
async def serve_productivity():
    p = Path("static/productivity/index.html")
    if p.exists():
        return FileResponse(str(p), headers={"Cache-Control": "no-cache"})
    return JSONResponse({"error": "Productivity page not found"}, status_code=404)


@app.get("/news", include_in_schema=False)
@app.get("/news/", include_in_schema=False)
async def serve_news():
    p = Path("static/news/index.html")
    if p.exists():
        return FileResponse(str(p), headers={"Cache-Control": "no-cache"})
    return JSONResponse({"error": "News page not found"}, status_code=404)


@app.get("/journal", include_in_schema=False)
@app.get("/journal/", include_in_schema=False)
async def serve_journal():
    p = Path("static/journal/index.html")
    if p.exists():
        return FileResponse(str(p), headers={"Cache-Control": "no-cache"})
    return JSONResponse({"error": "Journal page not found"}, status_code=404)


@app.get("/wrap", include_in_schema=False)
@app.get("/wrap/", include_in_schema=False)
async def serve_wrap():
    p = Path("static/wrap/index.html")
    if p.exists():
        return FileResponse(str(p), headers={"Cache-Control": "no-cache"})
    return JSONResponse({"error": "Wrap page not found"}, status_code=404)


@app.get("/alfred", include_in_schema=False)
@app.get("/alfred/", include_in_schema=False)
async def serve_alfred():
    p = Path("static/alfred/index.html")
    if p.exists():
        return FileResponse(str(p), headers={"Cache-Control": "no-cache"})
    return JSONResponse({"error": "Alfred page not found"}, status_code=404)


@app.get("/api/alfred/dashboard")
async def get_alfred_dashboard():
    from datetime import timedelta as _td
    loop  = asyncio.get_running_loop()
    today = datetime.now()
    today_str = today.strftime("%Y-%m-%d")

    # ── Tasks ──────────────────────────────────────────────────────────────────
    try:
        tasks_raw = json.loads((_DATA_DIR / "tasks.json").read_text(encoding="utf-8"))
    except Exception:
        tasks_raw = []

    priority_order = {"high": 0, "medium": 1, "low": 2}
    all_tasks   = tasks_raw
    pending     = [t for t in all_tasks if t.get("status", "pending") != "done"]
    done        = [t for t in all_tasks if t.get("status") == "done"]
    overdue     = [t for t in pending if t.get("due_date") and t["due_date"] < today_str]
    due_soon    = [t for t in pending if t.get("due_date") and today_str <= t["due_date"] <= (today + _td(days=7)).strftime("%Y-%m-%d")]
    pending.sort(key=lambda t: (priority_order.get(t.get("priority","medium"),1), t.get("due_date") or "9999"))

    stats = {
        "total":   len(all_tasks),
        "pending": len(pending),
        "done":    len(done),
        "overdue": len(overdue),
        "due_soon": len(due_soon),
        "high":    sum(1 for t in pending if t.get("priority") == "high"),
        "medium":  sum(1 for t in pending if t.get("priority") == "medium"),
        "low":     sum(1 for t in pending if t.get("priority") == "low"),
    }

    # ── Google Calendar — future 90 days ───────────────────────────────────────
    def _fetch_future():
        from tools.schedule_tools import _get_calendar_service
        service = _get_calendar_service()
        t_min = datetime(today.year, today.month, today.day).isoformat() + "Z"
        t_max = (datetime(today.year, today.month, today.day) + _td(days=90)).isoformat() + "Z"
        return service.events().list(
            calendarId="primary", timeMin=t_min, timeMax=t_max,
            maxResults=200, singleEvents=True, orderBy="startTime",
        ).execute().get("items", [])

    def _fetch_past():
        from tools.schedule_tools import _get_calendar_service
        service = _get_calendar_service()
        t_min = (datetime(today.year, today.month, today.day) - _td(days=30)).isoformat() + "Z"
        t_max = datetime(today.year, today.month, today.day).isoformat() + "Z"
        return service.events().list(
            calendarId="primary", timeMin=t_min, timeMax=t_max,
            maxResults=200, singleEvents=True, orderBy="startTime",
        ).execute().get("items", [])

    cal_connected = False
    raw_future, raw_past = [], []
    try:
        raw_future, raw_past = await asyncio.gather(
            loop.run_in_executor(None, _fetch_future),
            loop.run_in_executor(None, _fetch_past),
        )
        cal_connected = True
    except Exception:
        pass

    def _parse(e):
        start   = e["start"].get("dateTime", e["start"].get("date", ""))
        end_val = e["end"].get("dateTime",   e["end"].get("date",   ""))
        all_day = "T" not in start
        if all_day:
            day = start; st = "All day"; et = ""; hour = 0; minute = 0; dur = 1440
        else:
            day = start[:10]; st = start[11:16]; et = end_val[11:16] if end_val else ""
            try:
                hour, minute = int(start[11:13]), int(start[14:16])
                eh, em = int(end_val[11:13]), int(end_val[14:16])
                dur = max((eh * 60 + em) - (hour * 60 + minute), 15)
            except Exception:
                hour, minute, dur = 0, 0, 60
        return {
            "id":           e["id"][:12],
            "title":        e.get("summary", "Untitled"),
            "day":          day,
            "start_time":   st,
            "end_time":     et,
            "is_all_day":   all_day,
            "hour":         hour,
            "minute":       minute,
            "duration_min": dur,
            "description":  e.get("description") or "",
            "location":     e.get("location")    or "",
            "color_id":     e.get("colorId",     ""),
        }

    future_events = [_parse(e) for e in raw_future]
    past_events   = list(reversed([_parse(e) for e in raw_past]))  # newest first

    # Group by day
    def _group_by_day(evs):
        grouped: dict = {}
        for ev in evs:
            grouped.setdefault(ev["day"], []).append(ev)
        return grouped

    today_events   = [ev for ev in future_events if ev["day"] == today_str]
    future_grouped = _group_by_day([ev for ev in future_events if ev["day"] != today_str])
    past_grouped   = _group_by_day(past_events)
    future_days    = sorted(future_grouped.keys())
    past_days      = sorted(past_grouped.keys(), reverse=True)

    return {
        "calendar_connected": cal_connected,
        "today":              today_str,
        "today_label":        today.strftime("%A, %d %B %Y"),
        "tasks":              all_tasks,
        "pending":            pending,
        "done_tasks":         done,
        "stats":              stats,
        "today_events":       today_events,
        "future_grouped":     future_grouped,
        "future_days":        future_days,
        "past_grouped":       past_grouped,
        "past_days":          past_days,
        "due_soon":           due_soon,
    }


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


@app.get("/hub", include_in_schema=False)
@app.get("/hub/", include_in_schema=False)
async def serve_hub():
    p = Path("static/hub.html")
    if p.exists():
        return FileResponse(str(p), headers={"Cache-Control": "no-cache"})
    return JSONResponse({"error": "Hub page not found"}, status_code=404)


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

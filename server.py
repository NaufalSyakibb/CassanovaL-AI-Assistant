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
from fastapi.responses import FileResponse, JSONResponse
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


# ─── Chat ────────────────────────────────────────────────────────────────────

@app.post("/api/chat")
async def chat(req: ChatRequest):
    try:
        supervisor = get_supervisor()
        if req.agent:
            agent_name, response = supervisor.chat_direct(req.agent, req.message)
        else:
            agent_name, response = supervisor.chat(req.message)
        return {"agent": agent_name, "response": response}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ─── DataAnalyst File Endpoints ──────────────────────────────────────────────

def _dataanalyst_dir() -> Path:
    """Resolve the DataAnalyst Agent data folder (mirrors data_tools._data_dir logic)."""
    from dotenv import load_dotenv
    load_dotenv()
    vault = os.getenv("OBSIDIAN_VAULT_PATH", "").strip()
    base = (Path(vault) / "AI Data" / "DataAnalyst Agent") if vault \
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


# ─── CrewAI Multi-Agent Endpoints ────────────────────────────────────────────

_crew_jobs: dict = {}  # job_id → job state dict


class CrewKickoffRequest(BaseModel):
    topic: str
    crew_type: str = "research"            # "research" | "dataanalyst"
    filename: Optional[str] = None         # required when crew_type == "dataanalyst"
    agents: Optional[List[dict]] = None    # future: custom agent configs


def _run_crew_background(job_id: str, topic: str,
                          crew_type: str = "research",
                          filename: Optional[str] = None) -> None:
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
        if crew_type == "dataanalyst":
            from crewai_agents import build_data_crew
            crew = build_data_crew(filename or topic, step_cb=_log, task_cb=_log)
        else:
            from crewai_agents import build_crew
            crew = build_crew(topic, step_cb=_log, task_cb=_log)

        result = crew.kickoff()
        job["logs"] = logs

        # ── Collect output files ──────────────────────────────────────────────
        outputs = {}
        if crew_type == "dataanalyst":
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
        else:
            from crewai_agents import _research_dir
            research_out = _research_dir()
            for fname in ("task1_research.txt", "task2_report.md"):
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
        args=(job_id, topic, req.crew_type, req.filename),
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
    uvicorn.run("server:app", host="0.0.0.0", port=8000, reload=True)

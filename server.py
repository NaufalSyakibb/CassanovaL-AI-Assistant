import json
import sys
import io
from pathlib import Path
from datetime import datetime
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel
from typing import Optional
import uvicorn

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


# ─── Frontend ─────────────────────────────────────────────────────────────────

Path("static").mkdir(exist_ok=True)
app.mount("/static", StaticFiles(directory="static"), name="static")


@app.get("/{full_path:path}")
async def serve_frontend(full_path: str):
    index = Path("static/index.html")
    if index.exists():
        return FileResponse(str(index))
    return JSONResponse(
        {"error": "Frontend not found. Place index.html in static/ folder."},
        status_code=404,
    )


if __name__ == "__main__":
    uvicorn.run("server:app", host="0.0.0.0", port=8000, reload=True)

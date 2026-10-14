import os

import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles

from pr_agent.dashboard.storage import (
    get_run_record,
    get_summary_stats,
    list_run_records,
)

app = FastAPI(title="PR-Agent Telemetry & Token Analytics Dashboard")

# Enable CORS for local development flexibility
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")
os.makedirs(STATIC_DIR, exist_ok=True)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/api/stats")
async def api_summary_stats():
    """Return aggregated token metrics and run statistics."""
    return get_summary_stats()


@app.get("/api/runs")
async def api_list_runs(limit: int = 100, offset: int = 0):
    """Return recent run records."""
    return list_run_records(limit=limit, offset=offset)


@app.get("/api/runs/{run_id}")
async def api_get_run(run_id: str):
    """Return detailed telemetry for a single run."""
    record = get_run_record(run_id)
    if not record:
        raise HTTPException(status_code=404, detail="Run record not found")
    return record


@app.get("/", response_class=HTMLResponse)
async def serve_index():
    """Serve the dashboard overview home page."""
    index_path = os.path.join(STATIC_DIR, "index.html")
    if os.path.isfile(index_path):
        return FileResponse(index_path)
    return HTMLResponse("<h1>PR-Agent Dashboard</h1><p>Frontend assets not found.</p>")


@app.get("/runs/{run_id}", response_class=HTMLResponse)
async def serve_run_detail(run_id: str):
    """Serve the run deep-dive inspection page."""
    run_html_path = os.path.join(STATIC_DIR, "run.html")
    if os.path.isfile(run_html_path):
        return FileResponse(run_html_path)
    return HTMLResponse(f"<h1>Run {run_id}</h1><p>Run detail asset not found.</p>")


def main():
    """CLI launcher for the dashboard web server."""
    port = int(os.environ.get("PR_AGENT_DASHBOARD_PORT", 8000))
    host = os.environ.get("PR_AGENT_DASHBOARD_HOST", "0.0.0.0")
    print(f"\n[PR-Agent] Telemetry & Token Analytics Dashboard running at http://localhost:{port}\n")
    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    main()

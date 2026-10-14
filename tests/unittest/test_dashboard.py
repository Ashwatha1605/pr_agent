import shutil
import tempfile

from fastapi.testclient import TestClient

from pr_agent.dashboard.app import app
from pr_agent.dashboard.storage import (
    get_run_record,
    get_summary_stats,
    list_run_records,
    save_run_record,
)


def test_dashboard_storage_lifecycle(monkeypatch):
    temp_dir = tempfile.mkdtemp()
    try:
        monkeypatch.setattr("pr_agent.dashboard.storage.get_runs_dir", lambda: temp_dir)

        # 1. Initially empty
        assert len(list_run_records()) == 0
        stats = get_summary_stats()
        assert stats["total_runs"] == 0

        # 2. Save a run record
        sample_record = {
            "pr_url": "https://github.com/org/repo/pull/42",
            "pr_title": "Fix combat collision",
            "repo": "org/repo",
            "command": "test_and_fix",
            "model_used": "ollama/qwen2.5:7b",
            "engine": "unreal",
            "status": "success",
            "prompt_tokens": 1200,
            "completion_tokens": 300,
            "total_tokens": 1500,
            "num_ai_calls": 2,
            "duration_seconds": 5.4,
            "total_tests": 5,
            "passed_tests": 5,
            "failed_tests": 0,
        }
        run_id = save_run_record(sample_record)
        assert run_id.startswith("run_")

        # 3. Retrieve run record
        retrieved = get_run_record(run_id)
        assert retrieved is not None
        assert retrieved["pr_title"] == "Fix combat collision"
        assert retrieved["total_tokens"] == 1500

        # 4. List and stats
        records = list_run_records()
        assert len(records) == 1
        assert records[0]["run_id"] == run_id

        stats = get_summary_stats()
        assert stats["total_runs"] == 1
        assert stats["total_tokens"] == 1500
        assert stats["passed_tests"] == 5
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def test_dashboard_api_endpoints():
    client = TestClient(app)

    # Stats endpoint
    res = client.get("/api/stats")
    assert res.status_code == 200
    data = res.json()
    assert "total_runs" in data
    assert "total_tokens" in data

    # Runs list endpoint
    res = client.get("/api/runs")
    assert res.status_code == 200
    assert isinstance(res.json(), list)

    # HTML routes
    res = client.get("/")
    assert res.status_code == 200
    assert "PR-Agent" in res.text

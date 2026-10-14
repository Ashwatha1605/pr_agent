import json
import os
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional


def get_runs_dir() -> str:
    """Return the absolute path to the runs directory."""
    runs_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "runs"))
    os.makedirs(runs_dir, exist_ok=True)
    return runs_dir


def generate_run_id(prefix: str = "run") -> str:
    """Generate a unique human-readable run identifier with timestamp."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    random_suffix = uuid.uuid4().hex[:6]
    return f"{prefix}_{timestamp}_{random_suffix}"


def save_run_record(run_data: Dict[str, Any]) -> str:
    """
    Persist a PR-Agent run's telemetry and results as a standalone JSON file.
    Returns the assigned run_id.
    """
    runs_dir = get_runs_dir()
    run_id = run_data.get("run_id") or generate_run_id()
    run_data["run_id"] = run_id
    if "created_at" not in run_data:
        run_data["created_at"] = datetime.now().isoformat()

    file_path = os.path.join(runs_dir, f"{run_id}.json")
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(run_data, f, indent=2, default=str)

    return run_id


def get_run_record(run_id: str) -> Optional[Dict[str, Any]]:
    """Retrieve a single run record by its run_id."""
    runs_dir = get_runs_dir()
    clean_id = run_id.replace(".json", "")
    file_path = os.path.join(runs_dir, f"{clean_id}.json")
    if not os.path.isfile(file_path):
        return None

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def list_run_records(limit: int = 100, offset: int = 0) -> List[Dict[str, Any]]:
    """List recent run summaries sorted from newest to oldest."""
    runs_dir = get_runs_dir()
    if not os.path.exists(runs_dir):
        return []

    records = []
    for file_name in os.listdir(runs_dir):
        if not file_name.endswith(".json"):
            continue
        file_path = os.path.join(runs_dir, file_name)
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                records.append({
                    "run_id": data.get("run_id", file_name.replace(".json", "")),
                    "created_at": data.get("created_at", ""),
                    "pr_url": data.get("pr_url", ""),
                    "pr_title": data.get("pr_title", ""),
                    "repo": data.get("repo", ""),
                    "command": data.get("command", ""),
                    "model_used": data.get("model_used", ""),
                    "engine": data.get("engine", "none"),
                    "status": data.get("status", "success"),
                    "total_tokens": data.get("total_tokens", 0),
                    "prompt_tokens": data.get("prompt_tokens", 0),
                    "completion_tokens": data.get("completion_tokens", 0),
                    "num_ai_calls": data.get("num_ai_calls", 0),
                    "duration_seconds": data.get("duration_seconds", 0.0),
                    "total_tests": data.get("total_tests", 0),
                    "passed_tests": data.get("passed_tests", 0),
                    "failed_tests": data.get("failed_tests", 0),
                    "regression_areas": data.get("regression_areas", []),
                    "has_fix": bool(data.get("fix_result")),
                })
        except Exception:
            continue

    # Sort newest first by created_at (fallback to empty)
    records.sort(key=lambda r: r.get("created_at", ""), reverse=True)
    return records[offset : offset + limit]


def get_summary_stats() -> Dict[str, Any]:
    """Calculate aggregated stats across all runs for the dashboard KPI cards and charts."""
    runs = list_run_records(limit=1000)
    total_runs = len(runs)
    total_tokens = sum(r.get("total_tokens", 0) for r in runs)
    prompt_tokens = sum(r.get("prompt_tokens", 0) for r in runs)
    completion_tokens = sum(r.get("completion_tokens", 0) for r in runs)
    total_ai_calls = sum(r.get("num_ai_calls", 0) for r in runs)
    total_tests = sum(r.get("total_tests", 0) for r in runs)
    passed_tests = sum(r.get("passed_tests", 0) for r in runs)
    failed_tests = sum(r.get("failed_tests", 0) for r in runs)

    models_freq: Dict[str, int] = {}
    engines_freq: Dict[str, int] = {}
    commands_freq: Dict[str, int] = {}
    components_freq: Dict[str, int] = {}

    total_duration = 0.0
    runs_with_failures = 0
    runs_with_fixes = 0

    for r in runs:
        m = r.get("model_used") or "unknown"
        models_freq[m] = models_freq.get(m, 0) + 1
        e = r.get("engine") or "none"
        if e != "none":
            engines_freq[e] = engines_freq.get(e, 0) + 1
        cmd = r.get("command") or "other"
        commands_freq[cmd] = commands_freq.get(cmd, 0) + 1

        dur = float(r.get("duration_seconds", 0.0))
        total_duration += dur

        if r.get("failed_tests", 0) > 0:
            runs_with_failures += 1
            if r.get("has_fix"):
                runs_with_fixes += 1

        for area in r.get("regression_areas", []):
            comp = area.get("component")
            if comp:
                components_freq[comp] = components_freq.get(comp, 0) + 1

    # Average tokens per second
    avg_speed = round(total_tokens / total_duration, 1) if total_duration > 0 else 0.0
    fix_rate = round((runs_with_fixes / runs_with_failures * 100), 1) if runs_with_failures > 0 else 100.0

    return {
        "total_runs": total_runs,
        "total_tokens": total_tokens,
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "total_ai_calls": total_ai_calls,
        "total_tests": total_tests,
        "passed_tests": passed_tests,
        "failed_tests": failed_tests,
        "test_pass_rate": round((passed_tests / total_tests * 100), 1) if total_tests > 0 else 100.0,
        "avg_speed_tokens_per_sec": avg_speed,
        "self_healing_rate": fix_rate,
        "models_breakdown": models_freq,
        "engines_breakdown": engines_freq,
        "commands_breakdown": commands_freq,
        "top_components_risk": dict(sorted(components_freq.items(), key=lambda item: item[1], reverse=True)[:8]),
    }

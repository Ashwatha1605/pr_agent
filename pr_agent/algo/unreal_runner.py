import glob
import json
import os
import re
import subprocess
import tempfile
from dataclasses import dataclass, field
from typing import List, Optional

from pr_agent.log import get_logger


@dataclass
class UnrealTestFailure:
    test_name: str
    message: str
    stack_trace: str
    failing_file: str = ""
    failing_line: int = -1


@dataclass
class UnrealTestRunResult:
    all_passed: bool
    total_count: int
    passed_count: int
    failed_count: int
    failures: List[UnrealTestFailure] = field(default_factory=list)
    log_output: str = ""
    is_simulated: bool = False


def find_unreal_executable(configured_path: str = "auto") -> Optional[str]:
    """Find the Unreal Editor command-line executable (UnrealEditor-Cmd.exe or UE4Editor-Cmd.exe)."""
    if configured_path and configured_path.lower() != "auto" and os.path.isfile(configured_path):
        return configured_path

    for env_var in ("UNREAL_ENGINE_PATH", "UE5_PATH", "UE4_PATH"):
        env_val = os.environ.get(env_var)
        if env_val and os.path.isfile(env_val):
            return env_val

    # Standard Windows Epic Games Launcher installation paths
    candidate_patterns = [
        r"C:\Program Files\Epic Games\UE_5.*\Engine\Binaries\Win64\UnrealEditor-Cmd.exe",
        r"D:\Program Files\Epic Games\UE_5.*\Engine\Binaries\Win64\UnrealEditor-Cmd.exe",
        r"C:\Epic Games\UE_5.*\Engine\Binaries\Win64\UnrealEditor-Cmd.exe",
        r"D:\Epic Games\UE_5.*\Engine\Binaries\Win64\UnrealEditor-Cmd.exe",
        r"C:\Program Files\Epic Games\UE_4.*\Engine\Binaries\Win64\UE4Editor-Cmd.exe",
        r"D:\Program Files\Epic Games\UE_4.*\Engine\Binaries\Win64\UE4Editor-Cmd.exe",
    ]

    for pattern in candidate_patterns:
        matches = glob.glob(pattern)
        if matches:
            matches.sort(reverse=True)
            return matches[0]

    return None


def parse_unreal_results_json(json_content: str) -> UnrealTestRunResult:
    """Parse Unreal Automation Test JSON report output."""
    try:
        data = json.loads(json_content)
    except Exception as e:
        get_logger().error(f"Failed to parse Unreal test JSON results: {e}")
        return UnrealTestRunResult(
            all_passed=False,
            total_count=0,
            passed_count=0,
            failed_count=1,
            failures=[UnrealTestFailure("ExecutionFailure", f"Invalid JSON output: {e}", "")],
        )

    tests = data.get("tests", [])
    total = len(tests)
    passed = 0
    failed = 0
    failures: List[UnrealTestFailure] = []
    file_line_re = re.compile(r"([A-Za-z0-9_/\\]+\.(?:cpp|h|hpp)):(\d+)", re.IGNORECASE)

    for t in tests:
        state = t.get("state", "").lower()
        test_name = t.get("testDisplayName", t.get("fullTestPath", "UnknownTest"))
        if state in ("success", "passed"):
            passed += 1
        else:
            failed += 1
            entries = t.get("entries", [])
            messages = []
            stack_trace = ""
            failing_file = ""
            failing_line = -1

            for entry in entries:
                event = entry.get("event", {})
                msg_type = event.get("type", "")
                msg_text = event.get("message", "")
                if msg_type.lower() in ("error", "fail") or "error" in msg_text.lower():
                    messages.append(msg_text)
                    match = file_line_re.search(msg_text)
                    if match and not failing_file:
                        failing_file = match.group(1).replace("\\", "/")
                        try:
                            failing_line = int(match.group(2))
                        except ValueError:
                            pass

            full_msg = "\n".join(messages) if messages else "Unreal Automation assertion failed."
            failures.append(
                UnrealTestFailure(
                    test_name=test_name,
                    message=full_msg,
                    stack_trace=stack_trace,
                    failing_file=failing_file,
                    failing_line=failing_line,
                )
            )

    return UnrealTestRunResult(
        all_passed=(failed == 0 and total > 0),
        total_count=total,
        passed_count=passed,
        failed_count=failed,
        failures=failures,
    )


def run_headless_unreal_tests(
    uproject_path: str,
    test_filter: str,
    unreal_executable: Optional[str] = None,
    timeout_seconds: int = 300,
) -> UnrealTestRunResult:
    """Execute Unreal Engine Automation Tests in headless batchmode."""
    exe = unreal_executable or find_unreal_executable()
    if not exe or not os.path.isfile(exe):
        return UnrealTestRunResult(
            all_passed=False,
            total_count=0,
            passed_count=0,
            failed_count=1,
            failures=[
                UnrealTestFailure(
                    "RunnerConfig",
                    "Unreal Editor executable (UnrealEditor-Cmd.exe) not found on system.",
                    "",
                )
            ],
            log_output="Unreal Editor not found. Run in simulated/static mode.",
            is_simulated=True,
        )

    with tempfile.TemporaryDirectory() as temp_dir:
        report_export_path = os.path.join(temp_dir, "Report")
        os.makedirs(report_export_path, exist_ok=True)

        cmd = [
            exe,
            uproject_path,
            f"-ExecCmds=Automation RunTests {test_filter}; Quit",
            "-nullrhi",
            "-nosound",
            "-unattended",
            f"-ReportExportPath={report_export_path}",
        ]

        get_logger().info(f"Running Unreal headless tests: {' '.join(cmd)}")
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout_seconds,
            )
            log_output = result.stdout + "\n" + result.stderr

            # Look for index.json in report export directory
            report_file = os.path.join(report_export_path, "index.json")
            if os.path.isfile(report_file):
                with open(report_file, "r", encoding="utf-8") as f:
                    run_result = parse_unreal_results_json(f.read())
                    run_result.log_output = log_output
                    return run_result

            # Check if logs indicate success or failures directly
            if "Automation Test Succeeded" in log_output:
                return UnrealTestRunResult(
                    all_passed=True,
                    total_count=1,
                    passed_count=1,
                    failed_count=0,
                    log_output=log_output,
                )
            else:
                return UnrealTestRunResult(
                    all_passed=False,
                    total_count=1,
                    passed_count=0,
                    failed_count=1,
                    failures=[
                        UnrealTestFailure(
                            "AutomationRun",
                            "Unreal automation execution finished with errors.",
                            log_output[-500:],
                        )
                    ],
                    log_output=log_output,
                )
        except subprocess.TimeoutExpired:
            return UnrealTestRunResult(
                all_passed=False,
                total_count=0,
                passed_count=0,
                failed_count=1,
                failures=[UnrealTestFailure("Timeout", f"Test timed out after {timeout_seconds}s.", "")],
            )
        except Exception as e:
            return UnrealTestRunResult(
                all_passed=False,
                total_count=0,
                passed_count=0,
                failed_count=1,
                failures=[UnrealTestFailure("ProcessError", f"Failed to execute Unreal runner: {e}", "")],
            )

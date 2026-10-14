import glob
import os
import re
import subprocess
import tempfile
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from typing import List, Optional

from pr_agent.log import get_logger


@dataclass
class UnityTestFailure:
    test_name: str
    message: str
    stack_trace: str
    failing_file: str = ""
    failing_line: int = -1


@dataclass
class UnityTestRunResult:
    all_passed: bool
    total_count: int
    passed_count: int
    failed_count: int
    failures: List[UnityTestFailure] = field(default_factory=list)
    log_output: str = ""
    is_simulated: bool = False


def find_unity_executable(configured_path: str = "auto") -> Optional[str]:
    """Find the Unity Editor executable on the system."""
    if configured_path and configured_path.lower() != "auto" and os.path.isfile(configured_path):
        return configured_path

    env_path = os.environ.get("UNITY_PATH")
    if env_path and os.path.isfile(env_path):
        return env_path

    # Standard Windows Unity Hub install directories
    candidate_patterns = [
        r"C:\Program Files\Unity\Hub\Editor\*\Editor\Unity.exe",
        r"C:\Program Files (x86)\Unity\Hub\Editor\*\Editor\Unity.exe",
        r"C:\Program Files\Unity\Editor\Unity.exe",
        r"D:\Program Files\Unity\Hub\Editor\*\Editor\Unity.exe",
    ]

    for pattern in candidate_patterns:
        matches = glob.glob(pattern)
        if matches:
            # Sort to prefer latest installed version
            matches.sort(reverse=True)
            return matches[0]

    return None


def parse_nunit_results_xml(xml_content: str) -> UnityTestRunResult:
    """Parse NUnit/Unity test-results XML output."""
    try:
        root = ET.fromstring(xml_content)
    except ET.ParseError as e:
        get_logger().error(f"Failed to parse Unity test XML results: {e}")
        return UnityTestRunResult(
            all_passed=False,
            total_count=0,
            passed_count=0,
            failed_count=1,
            failures=[UnityTestFailure("ExecutionFailure", f"Invalid XML output: {e}", "")],
        )

    total = int(root.attrib.get("total", "0"))
    passed = int(root.attrib.get("passed", "0"))
    failed = int(root.attrib.get("failed", "0"))

    failures: List[UnityTestFailure] = []
    stack_trace_re = re.compile(r"in (.*):line (\d+)", re.IGNORECASE)

    for test_case in root.iter("test-case"):
        result = test_case.attrib.get("result", "")
        if result.lower() in ("failed", "failure"):
            name = test_case.attrib.get("name", "UnknownTest")
            failure_el = test_case.find("failure")
            message = ""
            stack_trace = ""
            if failure_el is not None:
                msg_el = failure_el.find("message")
                st_el = failure_el.find("stack-trace")
                message = msg_el.text.strip() if msg_el is not None and msg_el.text else ""
                stack_trace = st_el.text.strip() if st_el is not None and st_el.text else ""

            failing_file = ""
            failing_line = -1
            match = stack_trace_re.search(stack_trace)
            if match:
                failing_file = match.group(1).strip()
                try:
                    failing_line = int(match.group(2))
                except ValueError:
                    pass

            failures.append(
                UnityTestFailure(
                    test_name=name,
                    message=message,
                    stack_trace=stack_trace,
                    failing_file=failing_file,
                    failing_line=failing_line,
                )
            )

    all_passed = failed == 0 and total > 0
    return UnityTestRunResult(
        all_passed=all_passed,
        total_count=total,
        passed_count=passed,
        failed_count=failed,
        failures=failures,
    )


def run_headless_unity_tests(
    unity_path: str,
    project_path: str,
    platform: str = "EditMode",
    timeout: int = 180,
) -> UnityTestRunResult:
    """Run Unity Test Runner headlessly and return parsed results."""
    with tempfile.TemporaryDirectory() as temp_dir:
        results_xml_path = os.path.join(temp_dir, "test-results.xml")
        log_file_path = os.path.join(temp_dir, "unity-editor.log")

        cmd = [
            unity_path,
            "-batchmode",
            "-nographics",
            "-projectPath",
            project_path,
            "-runTests",
            "-testPlatform",
            platform,
            "-testResults",
            results_xml_path,
            "-logFile",
            log_file_path,
        ]

        get_logger().info(f"Executing Unity Headless Test Runner: {' '.join(cmd)}")
        try:
            process = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
            log_output = ""
            if os.path.exists(log_file_path):
                try:
                    with open(log_file_path, "r", encoding="utf-8", errors="replace") as f:
                        log_output = f.read()
                except Exception:
                    pass

            if not os.path.exists(results_xml_path):
                get_logger().warning("Unity finished without writing test-results.xml")
                return UnityTestRunResult(
                    all_passed=False,
                    total_count=0,
                    passed_count=0,
                    failed_count=1,
                    failures=[
                        UnityTestFailure(
                            "UnityBatchModeError",
                            f"Unity exited with code {process.returncode} but produced no test-results.xml.",
                            log_output[-2000:] if log_output else process.stderr,
                        )
                    ],
                    log_output=log_output,
                )

            with open(results_xml_path, "r", encoding="utf-8", errors="replace") as f:
                xml_content = f.read()

            result = parse_nunit_results_xml(xml_content)
            result.log_output = log_output
            return result

        except subprocess.TimeoutExpired:
            get_logger().error(f"Unity test execution timed out after {timeout} seconds.")
            return UnityTestRunResult(
                all_passed=False,
                total_count=0,
                passed_count=0,
                failed_count=1,
                failures=[
                    UnityTestFailure(
                        "TimeoutExpired",
                        f"Unity test run timed out after {timeout} seconds.",
                        "",
                    )
                ],
            )
        except Exception as e:
            get_logger().exception("Failed to execute Unity process.")
            return UnityTestRunResult(
                all_passed=False,
                total_count=0,
                passed_count=0,
                failed_count=1,
                failures=[
                    UnityTestFailure(
                        "ProcessExecutionError",
                        str(e),
                        "",
                    )
                ],
            )

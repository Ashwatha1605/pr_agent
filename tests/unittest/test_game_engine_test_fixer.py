import json
from unittest.mock import MagicMock

from pr_agent.algo.unreal_runner import UnrealTestFailure, parse_unreal_results_json
from pr_agent.tools.pr_game_test_fixer import PRGameTestFixer


def test_parse_unreal_results_json_success():
    sample_json = json.dumps({
        "tests": [
            {
                "testDisplayName": "PlayerCombat.HealthCheck",
                "state": "Success",
                "entries": []
            }
        ]
    })
    res = parse_unreal_results_json(sample_json)
    assert res.all_passed is True
    assert res.total_count == 1
    assert res.passed_count == 1
    assert res.failed_count == 0
    assert len(res.failures) == 0


def test_parse_unreal_results_json_failure():
    sample_json = json.dumps({
        "tests": [
            {
                "testDisplayName": "PlayerCombat.DamageCheck",
                "state": "Failed",
                "entries": [
                    {
                        "event": {
                            "type": "Error",
                            "message": "Expected: 50.0, Actual: 0.0 in Source/Player/Character.cpp:42"
                        }
                    }
                ]
            }
        ]
    })
    res = parse_unreal_results_json(sample_json)
    assert res.all_passed is False
    assert res.total_count == 1
    assert res.passed_count == 0
    assert res.failed_count == 1
    assert len(res.failures) == 1
    failure = res.failures[0]
    assert failure.test_name == "PlayerCombat.DamageCheck"
    assert "Expected: 50.0" in failure.message
    assert failure.failing_file == "Source/Player/Character.cpp"
    assert failure.failing_line == 42


def test_detect_engine_unreal():
    mock_file = MagicMock()
    mock_file.filename = "Source/MyGame/MyCharacter.cpp"
    mock_provider = MagicMock()
    mock_provider.get_files.return_value = [mock_file]
    mock_provider.get_languages.return_value = {"C++": 1000}

    fixer = PRGameTestFixer.__new__(PRGameTestFixer)
    fixer.args = []
    fixer.forced_engine = None
    fixer.git_provider = mock_provider
    fixer.main_pr_language = "C++"

    assert fixer._detect_engine() == "unreal"


def test_detect_engine_unity():
    mock_file = MagicMock()
    mock_file.filename = "Assets/Scripts/Game/Player.cs"
    mock_provider = MagicMock()
    mock_provider.get_files.return_value = [mock_file]
    mock_provider.get_languages.return_value = {"C#": 1000}

    fixer = PRGameTestFixer.__new__(PRGameTestFixer)
    fixer.args = []
    fixer.forced_engine = None
    fixer.git_provider = mock_provider
    fixer.main_pr_language = "C#"

    assert fixer._detect_engine() == "unity"


def test_build_report_markdown_includes_github_suggestion():
    fixer = PRGameTestFixer.__new__(PRGameTestFixer)
    fixer.engine = "unreal"

    run_result = MagicMock()
    run_result.all_passed = False
    run_result.is_simulated = True
    run_result.total_count = 1
    run_result.passed_count = 0
    run_result.failed_count = 1
    failure = UnrealTestFailure(
        test_name="FHealthTest",
        message="Assertion failed",
        stack_trace="at Character.cpp:10",
        failing_file="Source/Character.cpp",
        failing_line=10,
    )
    run_result.failures = [failure]

    fix_result = {
        "target_class": "AMyCharacter",
        "target_method": "TakeDamage",
        "root_cause_explanation": "Health underflow was not clamped.",
        "fixed_method_code": "Health = FMath::Max(0.0f, Health - Damage);",
    }

    report = fixer._build_report_markdown(
        regression_areas=[{"component": "Combat", "risk": "Health underflow"}],
        test_class_name="FHealthTest",
        test_code="// Test code",
        run_result=run_result,
        fix_result=fix_result,
    )

    assert "## 🎮 Unreal Engine (C++) Regression & Self-Healing Test Report" in report
    assert "```suggestion" in report
    assert "Health = FMath::Max(0.0f, Health - Damage);" in report
    assert "Commit suggestion" in report


def test_is_redundant_or_invalid_fix():
    fixer = PRGameTestFixer.__new__(PRGameTestFixer)

    # 1. Redundant fix: code is already in source code
    source_code = "public override bool IsValid() => playerMovement != null;"
    diff = "+ public override bool IsValid() => playerMovement != null;"
    candidate = {
        "fixed_method_code": "public override bool IsValid() => playerMovement != null;",
        "root_cause_explanation": "Added null check.",
    }
    assert fixer._is_redundant_or_invalid_fix(candidate, source_code, diff) is True

    # 2. Redundant fix: explanation states already implemented / no bug
    candidate_no_bug = {
        "fixed_method_code": "public override bool IsValid() => true;",
        "root_cause_explanation": "The method is already implemented correctly in the PR diff.",
    }
    assert fixer._is_redundant_or_invalid_fix(candidate_no_bug, "some code", "some diff") is True

    # 3. Genuine fix: code is novel and fixes a real bug
    candidate_valid = {
        "fixed_method_code": "public int CalculateScore() => BaseScore * 100;",
        "root_cause_explanation": "Multiply score instead of adding.",
    }
    assert (
        fixer._is_redundant_or_invalid_fix(candidate_valid, "public int CalculateScore() => 0;", "some diff") is False
    )


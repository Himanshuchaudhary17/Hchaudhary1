"""Pytest wrapper for the Weather Advisor application smoke test."""

from pathlib import Path
import subprocess
import sys

import pytest


pytestmark = pytest.mark.integration


def test_application_smoke():
    """Run the nine-check application smoke test through pytest."""

    project_root = Path(__file__).resolve().parents[2]
    testing_dir = project_root / "testing"

    result = subprocess.run(
        [sys.executable, "app_smoke_test.py"],
        cwd=testing_dir,
        capture_output=True,
        text=True,
        check=False,
    )

    print(result.stdout)

    if result.stderr:
        print(result.stderr)

    assert result.returncode == 0, (
        "Weather Advisor smoke test failed:\n"
        f"{result.stdout}\n{result.stderr}"
    )

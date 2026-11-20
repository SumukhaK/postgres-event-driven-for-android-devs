"""The reset commands must check the resolved database before destructive SQL."""
from contextlib import nullcontext
from pathlib import Path
import runpy
from unittest.mock import Mock

import pytest

from tools import run_sql


@pytest.mark.parametrize("code, output", [(0, "production\n"), (1, "connection failed")])
def test_course_runner_refuses_reset(monkeypatch, code, output):
    execute = Mock(return_value=(code, output))
    monkeypatch.setattr(run_sql, "psql", execute)
    assert run_sql.main() == 2
    execute.assert_called_once_with("SELECT current_database();")


def test_demo_fixture_checks_resolved_database(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://localhost/course_test?dbname=production")
    fixture = runpy.run_path(str(Path(__file__).parents[2] / "project/tests/conftest.py"))
    conn = Mock()
    conn.execute.return_value.fetchone.return_value = ("production",)
    monkeypatch.setattr(fixture["psycopg"], "connect", lambda *args, **kwargs: nullcontext(conn))
    with pytest.raises(RuntimeError, match="refusing to wipe"):
        fixture["schema"].__wrapped__()
    conn.execute.assert_called_once_with("SELECT current_database()")

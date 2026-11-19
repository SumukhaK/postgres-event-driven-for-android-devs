"""Run every ```sql block of every chapter, in order, against a fresh database.

  ```sql         must succeed
  ```sql-error   must fail (we show it on purpose)
  ```sql-skip    shown only, never run (fragments, pseudo-code, two-session demos)

Usage: python tools/run_sql.py   (needs a Postgres reachable with the env vars below)
Resets public schema; the connected database name must end in _test.
"""
import os, re, subprocess, sys, glob

DSN = os.environ.get("COURSE_DSN", "postgresql://course:course@localhost:5432/course_test")
SRC = os.path.join(os.path.dirname(__file__), "..", "src")
FENCE = re.compile(r"^```(sql|sql-error|sql-skip)\n(.*?)^```", re.S | re.M)


def psql(sql: str) -> tuple[int, str]:
    p = subprocess.run(["psql", DSN, "-v", "ON_ERROR_STOP=1", "-q", "-X", "-t", "-A", "-f", "-"],
                       input=sql, text=True, capture_output=True)
    return p.returncode, (p.stdout + p.stderr)


def main() -> int:
    ok, bad = 0, 0
    code, out = psql("SELECT current_database();")
    if code:
        print(out); return 2
    if not out.strip().endswith("_test"):
        print("refusing to wipe a database whose name does not end in _test")
        return 2
    code, out = psql("DROP SCHEMA public CASCADE; CREATE SCHEMA public;")
    if code:
        print(out); return 2
    for path in sorted(glob.glob(os.path.join(SRC, "*.md"))):
        text = open(path, encoding="utf-8").read()
        for n, m in enumerate(FENCE.finditer(text), 1):
            kind, sql = m.group(1), m.group(2)
            if kind == "sql-skip":
                continue
            code, out = psql(sql)
            expected_fail = kind == "sql-error"
            if (code != 0) == expected_fail:
                ok += 1
            else:
                bad += 1
                print(f"FAIL {os.path.basename(path)} block {n} ({kind})\n{sql}\n--> {out}\n")
    print(f"sql blocks: {ok} ok, {bad} failed")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())

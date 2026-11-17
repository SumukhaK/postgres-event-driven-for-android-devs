"""Controlled local tuning trial; saves public exercise answers for manual review.

Run from the repository root: python tools/evaluate_t26.py --model qwen2.5:7b-instruct
Requires Windows and an already running Ollama. Never downloads models;
run exclusively, with no other clients loading models during the trial.
"""
import argparse
import ctypes
import hashlib
import json
import sys
import threading
import time
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from learning_app.assistant import ACTION_PROMPTS, INSTRUCTIONS, CoachRequest, lesson_context

CASES = [
    ("03-select", "nudge", ""),
    ("05-joins", "hint", ""),
    ("04-changing-data", "solution", ""),
    ("07-indexes-explain", "explanation", ""),
    ("10-event-driven-thinking", "ask", "When is the outbox event saved, and what does the worker retry if publishing fails?"),
]


def free_ram():
    class Memory(ctypes.Structure):
        _fields_ = [("length", ctypes.c_ulong), ("load", ctypes.c_ulong)] + [
            (name, ctypes.c_ulonglong) for name in
            ("total", "available", "page_total", "page_available", "virtual_total", "virtual_available", "extended")]
    memory = Memory()
    memory.length = ctypes.sizeof(memory)
    if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(memory)):
        raise OSError("Cannot measure available RAM")
    return memory.available


def run(model, destination):
    records = []
    with httpx.Client(base_url="http://127.0.0.1:11434", trust_env=False,
                      timeout=httpx.Timeout(180, connect=10)) as client:
        def get(path):
            response = client.get(path)
            response.raise_for_status()
            return response.json()

        installed = {item["name"]: item for item in get("/api/tags")["models"]}
        if model not in installed:
            raise RuntimeError("Model must already be installed")
        if get("/api/ps")["models"]:
            raise RuntimeError("Run only when no other Ollama model is resident")
        # These gates assume this trial's 4 GiB GPU; 14B needs substantially more CPU RAM.
        required_gib = 4 if model == "qwen2.5:7b-instruct" else 8
        if free_ram() < required_gib * 1024**3:
            raise RuntimeError(f"Less than {required_gib} GiB free RAM before loading; retry with more headroom")
        sources = ["learning_app/assistant.py", "learning_app/static/seed.sql", "learning_app/static/exercises.json",
                   *[f"src/{lesson}.md" for lesson, _, _ in CASES]]
        metadata = {"model": installed[model], "server": get("/api/version"),
                    "source_sha256": {path: hashlib.sha256((ROOT / path).read_bytes()).hexdigest() for path in sources},
                    "sampling": {"seed": 42, "temperature": 0, "num_ctx": 4096},
                    "note": "Native Ollama requests with app-built context; first text is client receipt, not browser paint."}

        def save():
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_text(json.dumps({"metadata": metadata, "records": records}, indent=2), encoding="utf-8")

        def unload():
            response = client.post("/api/chat", json={"model": model, "messages": [], "keep_alive": 0, "stream": False})
            response.raise_for_status()
            deadline = time.perf_counter() + 15
            while any(item["name"] == model for item in get("/api/ps")["models"]):
                if time.perf_counter() > deadline:
                    raise RuntimeError("Model did not unload")
                time.sleep(0.5)

        def sample(phase, repeat, variant, case):
            if free_ram() < 1024**3:
                raise RuntimeError("Less than 1 GiB free RAM; stopping this trial")
            lesson, action, question = case
            payload = CoachRequest(provider="local", model=model, lesson_slug=lesson,
                                   exercise_slug=lesson, action=action, message=question)
            prompt = question if action == "ask" else ACTION_PROMPTS[action]
            limit = 160 if variant == "short_help" and action in {"hint", "nudge"} else 500
            body = {"model": model, "think": False, "stream": True, "keep_alive": "5m",
                    "options": {**metadata["sampling"], "num_predict": limit}, "messages": [
                        {"role": "system", "content": INSTRUCTIONS + "\n" + lesson_context(payload)},
                        {"role": "user", "content": prompt}]}
            row = {"phase": phase, "repeat": repeat, "variant": variant, "lesson": lesson,
                   "action": action, "prompt": prompt, "limit": limit, "ram_before": free_ram()}
            memory = [row["ram_before"]]
            stop = threading.Event()
            # shortcut: sampled RAM is not an allocation cap; use OS limits for unattended trials.
            def monitor():
                while not stop.wait(0.5):
                    memory.append(free_ram())
            monitor_thread = threading.Thread(target=monitor, daemon=True)
            monitor_thread.start()
            started = time.perf_counter()
            first = None
            answer = ""
            final = {}
            try:
                with client.stream("POST", "/api/chat", json=body) as response:
                    response.raise_for_status()
                    for line in response.iter_lines():
                        if min(memory) < 1024**3:
                            raise RuntimeError("Memory headroom fell below 1 GiB")
                        if not line:
                            continue
                        event = json.loads(line)
                        if event.get("error"):
                            raise RuntimeError("Ollama stream returned an error")
                        delta = event.get("message", {}).get("content", "")
                        if delta and first is None:
                            first = time.perf_counter() - started
                        answer += delta
                        if event.get("done"):
                            final = {key: event.get(key) for key in ("done_reason", "total_duration", "load_duration",
                                     "prompt_eval_duration", "eval_duration", "prompt_eval_count", "eval_count")}
                if not final or not answer:
                    raise RuntimeError("Incomplete or empty answer")
                row.update(outcome="completed", metrics=final)
            except Exception as error:
                row.update(outcome="failed", error_type=type(error).__name__)
            finally:
                stop.set()
                monitor_thread.join()
                row.update(seconds=round(time.perf_counter() - started, 3), first_text_seconds=first,
                           answer=answer, ram_min=min(memory), ram_after=free_ram())
                records.append(row)
                save()
                row["resident"] = get("/api/ps")["models"]
                save()
                print(json.dumps({key: row.get(key) for key in
                      ("phase", "repeat", "variant", "action", "outcome", "seconds", "metrics")}), flush=True)
            if row["outcome"] != "completed":
                raise RuntimeError("Trial stopped on inference failure; see saved record")

        try:
            # Residency pairs also warm up the model before the output-budget trial.
            for repeat in range(2):
                unload()
                sample("residency", repeat, "cold", CASES[3])
                sample("residency", repeat, "warm", CASES[3])
            for repeat, variants in enumerate((("control", "short_help"), ("short_help", "control"))):
                for case in CASES:
                    for variant in variants:
                        sample("budget", repeat, variant, case)
        finally:
            unload()
            metadata["ram_after_unload"] = free_ram()
            metadata["resident_after_unload"] = get("/api/ps")["models"]
            save()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", required=True, choices=["qwen2.5:7b-instruct", "qwen3:14b"])
    args = parser.parse_args()
    output = ROOT / "tasks" / "evaluations" / ("t26-" + args.model.replace(":", "-") + ".json")
    if output.exists():
        parser.error("Result file already exists; preserve it before running another trial")
    run(args.model, output)

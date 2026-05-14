#!/usr/bin/env python3
"""
MLE-bench logger daemon.

Watches a parent directory for problem folders (any subdir containing
solution.ipynb), executes notebooks, extracts metrics via Claude, and
serves a local UI.

Usage:
    python logger_daemon.py --watch /path/to/gym-environment/
    python logger_daemon.py --watch . --port 8765
"""

from __future__ import annotations

import argparse
import json
import logging
import queue
import re
import subprocess
import sys
import threading
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import nbformat
import uvicorn
from anthropic import Anthropic
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    stream=sys.stdout,
)
log = logging.getLogger("logger_daemon")

MODEL = "claude-sonnet-4-6"


# ---------------------------------------------------------------------------
# RunStore
# ---------------------------------------------------------------------------

class RunStore:
    def __init__(self, runs_dir: Path):
        self.runs_dir = runs_dir
        self.runs_dir.mkdir(parents=True, exist_ok=True)

    def _path(self, run_id: str) -> Path:
        return self.runs_dir / f"{run_id}.json"

    def save(self, run: dict) -> None:
        path = self._path(run["run_id"])
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(run, indent=2, ensure_ascii=False), encoding="utf-8")
        tmp.replace(path)

    def load(self, run_id: str) -> dict | None:
        path = self._path(run_id)
        if not path.exists():
            return None
        return json.loads(path.read_text(encoding="utf-8"))

    def list_runs(self) -> list[dict]:
        runs = []
        for p in self.runs_dir.glob("*.json"):
            try:
                runs.append(json.loads(p.read_text(encoding="utf-8")))
            except Exception:
                pass
        return sorted(runs, key=lambda r: r.get("timestamp", ""), reverse=True)

    def runs_for_problem(self, problem: str) -> list[dict]:
        return sorted(
            [r for r in self.list_runs() if r.get("problem") == problem],
            key=lambda r: r.get("timestamp", ""),
        )

    def latest_completed(self, problem: str) -> dict | None:
        done = [r for r in self.runs_for_problem(problem) if r.get("status") == "complete"]
        return done[-1] if done else None


# ---------------------------------------------------------------------------
# NotebookRunner
# ---------------------------------------------------------------------------

class NotebookRunner:
    def __init__(self, timeout: int = 600):
        self.timeout = timeout

    def needs_execution(self, nb_path: Path) -> bool:
        nb = nbformat.read(str(nb_path), as_version=4)
        for cell in nb.cells:
            if cell.cell_type == "code" and cell.get("outputs"):
                return False
        return True

    def execute(self, nb_path: Path) -> tuple[bool, str]:
        result = subprocess.run(
            [sys.executable, "-m", "jupyter", "nbconvert",
             "--to", "notebook", "--execute", "--inplace",
             f"--ExecutePreprocessor.timeout={self.timeout}", str(nb_path)],
            capture_output=True, text=True, timeout=self.timeout + 30,
        )
        if result.returncode != 0:
            return False, (result.stderr or result.stdout)[:4000]
        return True, ""

    def parse_cells(self, nb_path: Path) -> list[dict]:
        nb = nbformat.read(str(nb_path), as_version=4)
        cells = []
        for i, cell in enumerate(nb.cells):
            outputs: list[str] = []
            for out in cell.get("outputs", []):
                otype = out.get("output_type", "")
                if otype == "stream":
                    outputs.append("".join(out.get("text", [])))
                elif otype in ("execute_result", "display_data"):
                    data = out.get("data", {})
                    text = data.get("text/plain", "")
                    outputs.append("".join(text) if isinstance(text, list) else text)
                elif otype == "error":
                    outputs.append(f"{out.get('ename')}: {out.get('evalue')}")
            cells.append({
                "cell_index": i,
                "cell_type": cell.cell_type,
                "source": cell.source,
                "outputs": outputs,
                "changed_from_prev": None,
                "ai_summary": None,
            })
        return cells


# ---------------------------------------------------------------------------
# Diff
# ---------------------------------------------------------------------------

def diff_cells(current: list[dict], previous: list[dict] | None) -> list[dict]:
    if previous is None:
        return current
    prev_map = {c["cell_index"]: c for c in previous}
    for cell in current:
        prev = prev_map.get(cell["cell_index"])
        if prev is None:
            cell["changed_from_prev"] = True
        else:
            cell["changed_from_prev"] = (
                cell["source"] != prev.get("source")
                or cell["outputs"] != prev.get("outputs")
            )
    return current


# ---------------------------------------------------------------------------
# AIExtractor
# ---------------------------------------------------------------------------

class AIExtractor:
    def __init__(self):
        self.client = Anthropic()

    def extract_metrics(self, cells: list[dict]) -> dict:
        outputs = "\n".join(
            f"[Cell {c['cell_index']}]\n" + "\n".join(c["outputs"])
            for c in cells if c.get("outputs")
        )
        if not outputs.strip():
            return {"accuracy": None, "loss": None, "hyperparams": None}
        try:
            resp = self.client.messages.create(
                model=MODEL, max_tokens=512,
                messages=[{"role": "user", "content": (
                    "Extract ML metrics from this notebook output. "
                    "Return ONLY a valid JSON object with keys: "
                    "accuracy (float or null), loss (float or null), hyperparams (object or null). "
                    "No markdown, no explanation.\n\n" + outputs[:8000]
                )}],
            )
            raw = resp.content[0].text.strip().lstrip("```json").lstrip("```").rstrip("```").strip()
            return json.loads(raw)
        except Exception as e:
            log.warning("Metrics extraction failed: %s", e)
            return {"accuracy": None, "loss": None, "hyperparams": None}

    def summarize_cells(self, cells: list[dict]) -> list[dict]:
        """Return cells with ai_summary filled in for code cells."""
        code_cells = [c for c in cells if c["cell_type"] == "code" and c["source"].strip()]
        if not code_cells:
            return cells
        snippets = "\n\n".join(
            f"Cell {c['cell_index']}:\n{c['source'][:400]}"
            for c in code_cells[:15]
        )
        try:
            resp = self.client.messages.create(
                model=MODEL, max_tokens=1024,
                messages=[{"role": "user", "content": (
                    "For each cell below, write ONE short sentence (max 12 words) describing what it does. "
                    "Format strictly as: Cell N: <sentence>\n\n" + snippets
                )}],
            )
            summaries: dict[int, str] = {}
            for line in resp.content[0].text.splitlines():
                m = re.match(r"Cell\s+(\d+):\s*(.+)", line.strip())
                if m:
                    summaries[int(m.group(1))] = m.group(2).strip()
            for cell in cells:
                if cell["cell_type"] == "code":
                    cell["ai_summary"] = summaries.get(cell["cell_index"])
        except Exception as e:
            log.warning("Cell summaries failed: %s", e)
        return cells

    def summarize_approach(self, cells: list[dict]) -> str:
        source = "\n\n".join(
            f"# Cell {c['cell_index']}\n{c['source']}"
            for c in cells if c["cell_type"] == "code" and c["source"].strip()
        )
        if not source.strip():
            return ""
        try:
            resp = self.client.messages.create(
                model=MODEL, max_tokens=400,
                messages=[{"role": "user", "content": (
                    "Describe the ML approach in this notebook in one paragraph (3-4 sentences). "
                    "Cover model, preprocessing, evaluation. Be specific.\n\n" + source[:6000]
                )}],
            )
            return resp.content[0].text.strip()
        except Exception as e:
            log.warning("Approach summary failed: %s", e)
            return ""

    def summarize_trajectory(self, runs: list[dict]) -> str | None:
        if len(runs) < 2:
            return None
        lines = []
        for r in runs:
            acc = (r.get("metrics") or {}).get("accuracy")
            approach = (r.get("approach_summary") or "")[:150]
            lines.append(f"Run {r['run_id']} | accuracy={acc} | {approach}")
        try:
            resp = self.client.messages.create(
                model=MODEL, max_tokens=400,
                messages=[{"role": "user", "content": (
                    "Explain the accuracy trend across these ML runs in one paragraph. "
                    "What changed between runs, what helped, what didn't.\n\n" + "\n".join(lines)
                )}],
            )
            return resp.content[0].text.strip()
        except Exception as e:
            log.warning("Trajectory failed: %s", e)
            return None


# ---------------------------------------------------------------------------
# RunWorker
# ---------------------------------------------------------------------------

class RunWorker(threading.Thread):
    def __init__(self, work_queue: queue.Queue, store: RunStore,
                 ai: AIExtractor, runner: NotebookRunner, watch_root: Path):
        super().__init__(daemon=True, name="RunWorker")
        self.queue = work_queue
        self.store = store
        self.ai = ai
        self.runner = runner
        self.watch_root = watch_root
        self._in_flight: set[str] = set()  # problems currently being processed
        self._lock = threading.Lock()

    def run(self):
        while True:
            item = self.queue.get()
            try:
                self._process(item)
            except Exception as e:
                log.error("Run error: %s", e, exc_info=True)
            finally:
                self.queue.task_done()

    def _process(self, item: dict):
        problem = item["problem"]

        # Skip if this problem already has a run in flight
        with self._lock:
            if problem in self._in_flight:
                log.info("Skip %s — run already in flight", problem)
                return
            self._in_flight.add(problem)

        try:
            self._do_process(item)
        finally:
            with self._lock:
                self._in_flight.discard(problem)

    def _do_process(self, item: dict):
        problem = item["problem"]
        problem_path = Path(item["problem_path"])
        nb_path = Path(item["nb_path"])

        if not nb_path.exists():
            return

        ts = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
        run_id = f"{problem}-{ts}-{uuid.uuid4().hex[:6]}"
        t0 = time.time()

        run: dict[str, Any] = {
            "run_id": run_id,
            "problem": problem,
            "problem_path": str(problem_path),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "status": "running",
            "prompt": None,
            "notebook_executed": False,
            "notebook_error": None,
            "cells": [],
            "metrics": {"accuracy": None, "loss": None, "hyperparams": None},
            "approach_summary": None,
            "trajectory_summary": None,
            "duration_seconds": None,
        }

        prompt_file = problem_path / "prompt.txt"
        if prompt_file.exists():
            run["prompt"] = prompt_file.read_text(encoding="utf-8").strip() or None

        self.store.save(run)

        # 1. Execute if needed
        if self.runner.needs_execution(nb_path):
            log.info("[%s] Executing notebook...", run_id)
            ok, err = self.runner.execute(nb_path)
            run["notebook_executed"] = True
            if not ok:
                run["notebook_error"] = err
                run["status"] = "failed"
                run["duration_seconds"] = round(time.time() - t0, 1)
                self.store.save(run)
                log.error("[%s] Execution failed", run_id)
                return
            log.info("[%s] Execution done.", run_id)
        else:
            log.info("[%s] Notebook already has outputs.", run_id)

        # 2. Parse + diff cells
        cells = self.runner.parse_cells(nb_path)
        prev = self.store.latest_completed(problem)
        cells = diff_cells(cells, prev.get("cells") if prev else None)
        run["cells"] = cells
        self.store.save(run)

        # 3. AI: per-cell summaries (batched)
        log.info("[%s] Generating cell summaries...", run_id)
        run["cells"] = self.ai.summarize_cells(cells)
        self.store.save(run)

        # 4. AI: metrics
        log.info("[%s] Extracting metrics...", run_id)
        run["metrics"] = self.ai.extract_metrics(cells)
        self.store.save(run)

        # 5. AI: approach
        log.info("[%s] Approach summary...", run_id)
        run["approach_summary"] = self.ai.summarize_approach(cells)
        self.store.save(run)

        # 6. AI: trajectory
        prior = self.store.runs_for_problem(problem)
        if prior:
            log.info("[%s] Trajectory summary...", run_id)
            run["trajectory_summary"] = self.ai.summarize_trajectory(prior + [run])

        run["status"] = "complete"
        run["duration_seconds"] = round(time.time() - t0, 1)
        self.store.save(run)
        log.info("[%s] Done. accuracy=%s duration=%.1fs",
                 run_id, (run["metrics"] or {}).get("accuracy"), run["duration_seconds"])

        # 7. Auto-log to aicodinggym experiment log
        self._auto_log(run, problem_path)

    def _auto_log(self, run: dict, problem_path: Path):
        accuracy = (run.get("metrics") or {}).get("accuracy")
        if accuracy is None:
            return
        problem = run["problem"]
        approach = (run.get("approach_summary") or "")[:120].replace('"', "'")
        try:
            subprocess.run(
                ["aicodinggym", "mle", "log", "add", problem,
                 "--no-input",
                 "-s", approach or f"run {run['run_id'][-6:]}",
                 "--author", "ai",
                 "--val-metric", "accuracy",
                 "--val-score", str(accuracy)],
                capture_output=True, text=True, timeout=30,
                cwd=str(problem_path.parent),
            )
            log.info("[%s] Logged to mle experiment log (accuracy=%.4f)", run["run_id"], accuracy)
        except Exception as e:
            log.warning("mle log add failed: %s", e)


# ---------------------------------------------------------------------------
# Watcher
# ---------------------------------------------------------------------------

class NotebookEventHandler(FileSystemEventHandler):
    DEBOUNCE_SECS = 10  # longer debounce — notebooks trigger multiple FS events during execution

    def __init__(self, watch_root: Path, work_queue: queue.Queue):
        self.watch_root = watch_root
        self.queue = work_queue
        self._last: dict[str, float] = {}
        self._lck = threading.Lock()

    def _enqueue(self, src: str):
        nb_path = Path(src)
        if nb_path.name != "solution.ipynb":
            return
        problem_path = nb_path.parent
        try:
            rel = problem_path.relative_to(self.watch_root)
        except ValueError:
            return
        if len(rel.parts) != 1:
            return

        with self._lck:
            now = time.time()
            if now - self._last.get(src, 0) < self.DEBOUNCE_SECS:
                return
            self._last[src] = now

        log.info("Queuing: %s", problem_path.name)
        self.queue.put({
            "problem": problem_path.name,
            "problem_path": str(problem_path),
            "nb_path": src,
        })

    def on_created(self, event):
        if not event.is_directory:
            self._enqueue(event.src_path)

    def on_modified(self, event):
        if not event.is_directory:
            self._enqueue(event.src_path)


# ---------------------------------------------------------------------------
# FastAPI
# ---------------------------------------------------------------------------

def make_app(store: RunStore, ui_path: Path) -> FastAPI:
    app = FastAPI(title="MLE Logger", docs_url=None, redoc_url=None)

    @app.get("/")
    def index():
        return FileResponse(str(ui_path), media_type="text/html")

    @app.get("/runs")
    def list_runs():
        return [
            {
                "run_id": r["run_id"],
                "problem": r["problem"],
                "timestamp": r["timestamp"],
                "status": r["status"],
                "accuracy": (r.get("metrics") or {}).get("accuracy"),
            }
            for r in store.list_runs()
        ]

    @app.get("/runs/{run_id}")
    def get_run(run_id: str):
        run = store.load(run_id)
        if run is None:
            raise HTTPException(404, "Run not found")
        return run

    @app.get("/problems/{name}/runs")
    def problem_runs(name: str):
        return store.runs_for_problem(name)

    @app.get("/health")
    def health():
        return {"status": "ok", "runs": len(store.list_runs())}

    return app


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="MLE-bench logger daemon")
    parser.add_argument("--watch", required=True, metavar="DIR")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--runs-dir", default=None, metavar="DIR")
    args = parser.parse_args()

    watch_root = Path(args.watch).resolve()
    runs_dir = Path(args.runs_dir).resolve() if args.runs_dir else watch_root / ".logger_runs"
    ui_path = Path(__file__).with_name("logger_ui.html")

    if not watch_root.is_dir():
        sys.exit(f"Error: --watch path does not exist: {watch_root}")
    if not ui_path.exists():
        sys.exit("Error: logger_ui.html not found next to logger_daemon.py")

    store = RunStore(runs_dir)
    ai = AIExtractor()
    runner = NotebookRunner()
    work_queue: queue.Queue = queue.Queue()

    worker = RunWorker(work_queue, store, ai, runner, watch_root)
    worker.start()

    handler = NotebookEventHandler(watch_root, work_queue)
    observer = Observer()
    observer.schedule(handler, str(watch_root), recursive=True)
    observer.start()
    log.info("Watching : %s", watch_root)
    log.info("Runs dir : %s", runs_dir)
    log.info("UI       : http://localhost:%d", args.port)

    try:
        app = make_app(store, ui_path)
        uvicorn.run(app, host="0.0.0.0", port=args.port, log_level="warning")
    finally:
        observer.stop()
        observer.join()


if __name__ == "__main__":
    main()

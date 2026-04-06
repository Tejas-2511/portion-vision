"""
Pipeline Run Context — single-run diagnostic state.

Creates a timestamped output directory, provides helpers to save images,
NumPy arrays, JSON, and log entries, and generates an HTML report at the end.
"""

from __future__ import annotations

import os
import json
import time
import uuid
import logging
import cv2
import numpy as np
from datetime import datetime


# ── Subdirectory names (created inside each run folder) ──────────────────
_SUBDIRS = [
    "input",
    "preprocessing",
    "compartments",
    "depth",
    "segmentation",
    "features",
    "volume",
    "logs",
]


class RunContext:
    """
    Encapsulates a single pipeline run's output directory and logging.

    Usage:
        ctx = RunContext(debug=True)
        ctx.save_image("preprocessing", "01_resized.png", img)
        ctx.log("Preprocessing", "Resize applied", {"target": 1024})
        ...
        ctx.generate_report()
    """

    def __init__(self, debug: bool = True, outputs_root: str = None):
        self.debug = debug
        self._step_counter: dict[str, int] = {}
        self._saved_files: list[dict] = []
        self._log_entries: list[dict] = []

        # Build root path
        if outputs_root is None:
            outputs_root = os.path.join(
                os.path.dirname(os.path.dirname(__file__)), "outputs"
            )

        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        uid = uuid.uuid4().hex[:8]
        self.run_id = f"{ts}_{uid}"
        self.run_dir = os.path.join(outputs_root, self.run_id)

        # Create subdirectories
        for sub in _SUBDIRS:
            os.makedirs(os.path.join(self.run_dir, sub), exist_ok=True)

        # Set up per-run file logger
        self._logger = logging.getLogger(f"pipeline.{self.run_id}")
        self._logger.setLevel(logging.DEBUG)
        log_path = os.path.join(self.run_dir, "logs", "pipeline.log")
        fh = logging.FileHandler(log_path, encoding="utf-8")
        fh.setFormatter(logging.Formatter(
            "%(asctime)s │ %(levelname)s │ %(message)s"
        ))
        self._logger.addHandler(fh)
        self._logger.info(f"Run started — debug={debug}, id={self.run_id}")

    # ── Public helpers ───────────────────────────────────────────────────

    def next_index(self, stage: str) -> int:
        """Return the next sequential index (1-based) for a given stage."""
        idx = self._step_counter.get(stage, 0) + 1
        self._step_counter[stage] = idx
        return idx

    def save_image(self, stage: str, filename: str, image: np.ndarray) -> str:
        """
        Save an image to <run_dir>/<stage>/<filename>.
        Returns the absolute path written to.
        """
        path = os.path.join(self.run_dir, stage, filename)
        cv2.imwrite(path, image)
        self._record_file(stage, filename, path)
        self._logger.info(f"[{stage}] Saved image → {filename}")
        return path

    def save_npy(self, stage: str, filename: str, array: np.ndarray) -> str:
        """Save a NumPy array as .npy."""
        path = os.path.join(self.run_dir, stage, filename)
        np.save(path, array)
        self._record_file(stage, filename, path)
        self._logger.info(f"[{stage}] Saved npy → {filename}")
        return path

    def save_json(self, stage: str, filename: str, data: dict | list) -> str:
        """Save a dict/list as JSON."""
        path = os.path.join(self.run_dir, stage, filename)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        self._record_file(stage, filename, path)
        self._logger.info(f"[{stage}] Saved JSON → {filename}")
        return path

    def log(
        self,
        step_name: str,
        message: str,
        params: dict = None,
        elapsed: float = None,
        input_file: str = None,
        output_file: str = None,
    ):
        """Append a structured log entry (also written to pipeline.log)."""
        entry = {
            "step": step_name,
            "message": message,
            "params": params or {},
            "elapsed_s": round(elapsed, 4) if elapsed else None,
            "input_file": input_file,
            "output_file": output_file,
            "timestamp": datetime.now().isoformat(),
        }
        self._log_entries.append(entry)

        parts = [f"[{step_name}] {message}"]
        if params:
            parts.append(f"params={params}")
        if elapsed is not None:
            parts.append(f"time={elapsed:.4f}s")
        if output_file:
            parts.append(f"output={output_file}")
        self._logger.info(" │ ".join(parts))

    # ── Report generation ────────────────────────────────────────────────

    def generate_report(self) -> str:
        """
        Build a self-contained HTML report that displays every saved image
        in processing order and includes the full structured log.
        Returns the path to report.html.
        """
        # Also dump the log as JSON
        self.save_json("logs", "run_log.json", self._log_entries)

        html_parts = [
            "<!DOCTYPE html>",
            "<html lang='en'><head><meta charset='utf-8'>",
            f"<title>Pipeline Report — {self.run_id}</title>",
            "<style>",
            "  * { margin:0; padding:0; box-sizing:border-box; }",
            "  body { font-family: 'Segoe UI', system-ui, sans-serif;",
            "         background:#0f0f0f; color:#e0e0e0; padding:2rem; }",
            "  h1 { color:#80cbc4; margin-bottom:0.3rem; }",
            "  h2 { color:#4dd0e1; margin:2rem 0 0.8rem; border-bottom:1px solid #333; padding-bottom:0.4rem; }",
            "  .meta { color:#888; margin-bottom:2rem; }",
            "  .card { background:#1a1a1a; border-radius:8px; padding:1rem;",
            "          margin-bottom:1rem; border:1px solid #2a2a2a; }",
            "  .card img { max-width:100%; border-radius:4px; margin-top:0.5rem; }",
            "  .card .fname { color:#aed581; font-family:monospace; font-size:0.9rem; }",
            "  table { border-collapse:collapse; width:100%; margin-top:0.5rem; }",
            "  th, td { padding:6px 10px; text-align:left; border-bottom:1px solid #2a2a2a;",
            "           font-size:0.85rem; }",
            "  th { color:#4dd0e1; }",
            "  .log-table td { font-family:monospace; font-size:0.8rem; }",
            "</style></head><body>",
            f"<h1>🔬 Pipeline Run Report</h1>",
            f"<p class='meta'>Run ID: <code>{self.run_id}</code> &nbsp;│&nbsp; "
            f"Debug: <code>{self.debug}</code> &nbsp;│&nbsp; "
            f"Files saved: <code>{len(self._saved_files)}</code></p>",
        ]

        # Group images by stage
        stages_order = _SUBDIRS
        files_by_stage: dict[str, list[dict]] = {}
        for f in self._saved_files:
            files_by_stage.setdefault(f["stage"], []).append(f)

        for stage in stages_order:
            items = files_by_stage.get(stage, [])
            if not items:
                continue

            html_parts.append(f"<h2>📁 {stage}</h2>")
            for item in items:
                fname = item["filename"]
                rel = os.path.relpath(item["path"], self.run_dir).replace("\\", "/")

                if fname.lower().endswith((".png", ".jpg", ".jpeg")):
                    html_parts.append(
                        f"<div class='card'><span class='fname'>{fname}</span>"
                        f"<br><img src='{rel}' alt='{fname}'></div>"
                    )
                elif fname.lower().endswith(".json"):
                    try:
                        with open(item["path"], "r") as jf:
                            content = jf.read()[:2000]
                    except Exception:
                        content = "(could not read)"
                    html_parts.append(
                        f"<div class='card'><span class='fname'>{fname}</span>"
                        f"<pre style='color:#ccc;margin-top:0.5rem;'>{content}</pre></div>"
                    )
                else:
                    html_parts.append(
                        f"<div class='card'><span class='fname'>{fname}</span></div>"
                    )

        # Log table
        html_parts.append("<h2>📋 Execution Log</h2>")
        html_parts.append("<table class='log-table'><tr>"
                          "<th>Step</th><th>Message</th>"
                          "<th>Params</th><th>Time</th></tr>")
        for entry in self._log_entries:
            elapsed = f"{entry['elapsed_s']:.4f}s" if entry["elapsed_s"] else "—"
            params = json.dumps(entry["params"]) if entry["params"] else "—"
            html_parts.append(
                f"<tr><td>{entry['step']}</td><td>{entry['message']}</td>"
                f"<td>{params}</td><td>{elapsed}</td></tr>"
            )
        html_parts.append("</table></body></html>")

        report_path = os.path.join(self.run_dir, "report.html")
        with open(report_path, "w", encoding="utf-8") as f:
            f.write("\n".join(html_parts))

        self._logger.info(f"HTML report generated → report.html")
        return report_path

    # ── Internal ─────────────────────────────────────────────────────────

    def _record_file(self, stage: str, filename: str, path: str):
        self._saved_files.append({
            "stage": stage,
            "filename": filename,
            "path": path,
        })

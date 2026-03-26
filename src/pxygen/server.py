"""FastAPI server for the pxygen WebUI."""
from __future__ import annotations

import queue
import threading
import time
import uuid
import webbrowser
from pathlib import Path
from typing import Any

import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, StreamingResponse
from pydantic import BaseModel

from .modes import list_footage_folders, process_directory_mode
from .paths import clean_path_input
from .resolve import ProxyGeneratorError

app = FastAPI(title="pxygen")

_STATIC_DIR = Path(__file__).parent / "static"
_CONFIRM_SENTINEL = "__CONFIRM__"

JOBS: dict[str, dict[str, Any]] = {}


class DiscoverRequest(BaseModel):
    input_path: str
    in_depth: int


class RunRequest(BaseModel):
    footage_path: str
    proxy_path: str
    in_depth: int
    out_depth: int
    codec: str = "auto"
    clean_image: bool = False
    selected_folders: list[str] | None = None  # full paths; None means process all


class ConfirmRequest(BaseModel):
    proceed: bool


@app.get("/", response_class=HTMLResponse)
def index() -> str:
    return (_STATIC_DIR / "index.html").read_text(encoding="utf-8")


@app.post("/api/discover")
def discover(req: DiscoverRequest) -> dict[str, list[str]]:
    try:
        folders = list_footage_folders(clean_path_input(req.input_path), req.in_depth)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"folders": folders}


@app.post("/api/run")
def run_job(req: RunRequest) -> dict[str, str]:
    job_id = str(uuid.uuid4())[:8]
    out_q: queue.Queue[str | None] = queue.Queue()
    confirm_event = threading.Event()
    job: dict[str, Any] = {
        "status": "running",
        "output_queue": out_q,
        "confirm_event": confirm_event,
        "confirm_result": None,
    }
    JOBS[job_id] = job

    def output_fn(msg: str) -> None:
        out_q.put(msg)

    def confirm_render() -> bool:
        out_q.put(_CONFIRM_SENTINEL)
        job["status"] = "awaiting_confirm"
        confirm_event.wait()
        return bool(job["confirm_result"])

    filter_mode: str | None = None
    filter_list: str | None = None
    if req.selected_folders is not None:
        filter_mode = "filter"
        filter_list = ",".join(Path(p).name for p in req.selected_folders)

    def run() -> None:
        try:
            process_directory_mode(
                clean_path_input(req.footage_path),
                clean_path_input(req.proxy_path),
                req.in_depth,
                req.out_depth,
                clean_image=req.clean_image,
                filter_mode=filter_mode,
                filter_list=filter_list,
                codec=req.codec,
                output=output_fn,
                confirm_render=confirm_render,
            )
            job["status"] = "done"
        except (ProxyGeneratorError, ValueError, AttributeError) as exc:
            out_q.put(f"ERROR: {exc}")
            job["status"] = "error"
        except Exception as exc:
            out_q.put(f"ERROR: Unexpected error: {exc}")
            job["status"] = "error"
        finally:
            out_q.put(None)

    t = threading.Thread(target=run, daemon=True)
    job["thread"] = t
    t.start()
    return {"job_id": job_id}


@app.get("/api/jobs/{job_id}/stream")
def stream_job(job_id: str) -> StreamingResponse:
    if job_id not in JOBS:
        raise HTTPException(status_code=404, detail="Job not found")
    out_q: queue.Queue[str | None] = JOBS[job_id]["output_queue"]

    def generate():
        while True:
            try:
                item = out_q.get(timeout=15)
            except queue.Empty:
                yield ": keepalive\n\n"
                continue
            if item is None:
                yield "event: done\ndata: \n\n"
                break
            elif item == _CONFIRM_SENTINEL:
                yield "event: awaiting_confirm\ndata: \n\n"
            else:
                for line in item.splitlines() or [item]:
                    yield f"data: {line}\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream")


@app.post("/api/jobs/{job_id}/confirm")
def confirm_job(job_id: str, req: ConfirmRequest) -> dict[str, bool]:
    if job_id not in JOBS:
        raise HTTPException(status_code=404, detail="Job not found")
    job = JOBS[job_id]
    job["confirm_result"] = req.proceed
    job["status"] = "running"
    job["confirm_event"].set()
    return {"ok": True}


@app.get("/api/jobs/{job_id}/status")
def job_status(job_id: str) -> dict[str, str]:
    if job_id not in JOBS:
        raise HTTPException(status_code=404, detail="Job not found")
    return {"status": JOBS[job_id]["status"]}


def launch_server(port: int = 8321) -> None:
    """Start the uvicorn server (blocking). Opens browser after startup."""

    def _open_browser() -> None:
        time.sleep(0.8)
        webbrowser.open(f"http://localhost:{port}")

    threading.Thread(target=_open_browser, daemon=True).start()
    uvicorn.run(app, host="127.0.0.1", port=port, log_level="warning")

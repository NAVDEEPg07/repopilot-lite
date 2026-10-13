from metrics import analyze_metrics
from pathlib import Path, PurePosixPath
from zipfile import ZipFile, BadZipFile
import io

from fastapi.responses import JSONResponse, HTMLResponse
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from analyzer import analyze_sources, impact_for

BASE_DIR = Path(__file__).resolve().parent
MAX_UPLOAD = 10 * 1024 * 1024
MAX_FILES = 2000
MAX_UNCOMPRESSED = 30 * 1024 * 1024
MAX_FILE_SIZE = 2 * 1024 * 1024

app = FastAPI(title="RepoPilot Lite", description="Static Python import and change-impact analysis")
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")
SESSIONS: dict[str, dict] = {}


class ImpactRequest(BaseModel):
    session_id: str
    selected_file: str


@app.get("/")
def index():
    return FileResponse(BASE_DIR / "templates" / "index.html")

@app.get("/privacy")
def privacy():
    return FileResponse(BASE_DIR / "templates" / "privacy.html")

@app.get("/terms")
def terms():
    return FileResponse(BASE_DIR / "templates" / "terms.html")

@app.get("/favicon.ico")
def favicon():
    return FileResponse(BASE_DIR / "static" / "favicon.svg", media_type="image/svg+xml")


def read_zip(upload: bytes) -> dict[str, str]:
    try:
        archive = ZipFile(io.BytesIO(upload))
    except (BadZipFile, OSError):
        raise HTTPException(400, "That file is not a valid ZIP archive.")
    sources = {}
    total = 0
    try:
        infos = archive.infolist()
        if len(infos) > MAX_FILES:
            raise HTTPException(413, f"ZIP contains too many entries (limit: {MAX_FILES}).")
        for info in infos:
            if info.is_dir():
                continue
            raw_name = info.filename.replace("\\", "/")
            posix = PurePosixPath(raw_name)
            if posix.is_absolute() or ".." in posix.parts or not posix.parts or (posix.parts and ":" in posix.parts[0]):
                raise HTTPException(400, "ZIP contains an unsafe file path.")
            if info.flag_bits & 0x1:
                raise HTTPException(400, "Password-protected ZIP files are not supported.")
            total += info.file_size
            if total > MAX_UNCOMPRESSED:
                raise HTTPException(413, "Extracted ZIP contents exceed the 30 MB limit.")
            if info.file_size > MAX_FILE_SIZE:
                raise HTTPException(413, f"File exceeds the 2 MB per-file limit: {posix.as_posix()}")
            # Ignore common metadata and binary assets; keep the real project structure for source/config/text files.
            path = posix.as_posix()
            if path.startswith("__MACOSX/") or posix.name == ".DS_Store":
                continue
            if posix.suffix.lower() in {".pyc", ".png", ".jpg", ".jpeg", ".gif", ".pdf", ".exe", ".dll", ".so", ".zip", ".db"}:
                continue
            try:
                data = archive.read(info)
            except (BadZipFile, RuntimeError):
                raise HTTPException(400, f"Could not read ZIP entry: {path}")
            if b"\x00" in data[:8192]:
                continue
            try:
                sources[path] = data.decode("utf-8-sig")
            except UnicodeDecodeError:
                # Preserve source-tree visibility, but don't attempt AST parsing on non-text bytes.
                sources[path] = ""
        return sources
    finally:
        archive.close()


@app.post("/api/analyze")
async def analyze_project(file: UploadFile = File(...)):
    if not file.filename or not file.filename.lower().endswith(".zip"):
        raise HTTPException(400, "Upload a .zip archive containing your project.")
    data = await file.read(MAX_UPLOAD + 1)
    if len(data) > MAX_UPLOAD:
        raise HTTPException(413, "ZIP upload exceeds the 10 MB limit.")
    if not data:
        raise HTTPException(400, "The uploaded ZIP is empty.")
    sources = read_zip(data)
    if not sources:
        raise HTTPException(400, "No readable project files were found in the ZIP.")
    analysis = analyze_sources(sources)
    analysis["metrics"] = analyze_metrics(sources)
    import uuid
    session_id = uuid.uuid4().hex
    SESSIONS[session_id] = analysis
    # Keep memory bounded for this lightweight local demo.
    if len(SESSIONS) > 20:
        SESSIONS.pop(next(iter(SESSIONS)))
    return {"session_id": session_id, **analysis}


@app.post("/api/impact")
def get_impact(request: ImpactRequest):
    analysis = SESSIONS.get(request.session_id)
    if not analysis:
        raise HTTPException(404, "Analysis session expired. Upload the ZIP again.")
    try:
        return impact_for(analysis, request.selected_file)
    except ValueError as exc:
        raise HTTPException(400, str(exc))

@app.get("/api/health")
def health():
    return {"status": "ok"}

@app.exception_handler(404)
async def custom_404(request, exc):
    if request.url.path.startswith("/api/"):
        return JSONResponse(status_code=404, content={"detail": getattr(exc, "detail", "Not found")})
    return FileResponse(BASE_DIR / "templates" / "404.html", status_code=404)


@app.get("/api/report/{session_id}/json")
def download_json_report(session_id: str):
    from fastapi.responses import JSONResponse
    from fastapi.encoders import jsonable_encoder

    analysis = SESSIONS.get(session_id)
    if analysis is None:
        return JSONResponse({"error": "Analysis session not found. Upload the ZIP again."}, status_code=404)

    return JSONResponse(
        content=jsonable_encoder(analysis),
        headers={"Content-Disposition": 'attachment; filename="repopilot-report.json"'}
    )


@app.get("/api/report/{session_id}/html")
def download_html_report(session_id: str):
    from fastapi.responses import HTMLResponse
    from html import escape
    import json

    analysis = SESSIONS.get(session_id)
    if analysis is None:
        return HTMLResponse("Analysis session not found. Upload the ZIP again.", status_code=404)

    metrics = analysis.get("metrics", [])
    rows = ""
    for m in metrics:
        rows += (
            "<tr>"
            f"<td>{escape(str(m.get('file', '')))}</td>"
            f"<td>{m.get('lines', 0)}</td>"
            f"<td>{m.get('loc', 0)}</td>"
            f"<td>{m.get('functions', 0)}</td>"
            f"<td>{m.get('classes', 0)}</td>"
            f"<td>{m.get('complexity', '?')}</td>"
            "</tr>"
        )

    report_json = escape(json.dumps(analysis, indent=2, default=str))
    html = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>RepoPilot Analysis Report</title>
<style>
body{{font-family:Arial,sans-serif;max-width:1100px;margin:40px auto;padding:0 20px;background:#f3f4f6;color:#111827}}
h1,h2{{color:#111827}}.card{{background:white;padding:20px;border-radius:12px;margin:18px 0;overflow-x:auto}}
table{{width:100%;border-collapse:collapse}}th,td{{padding:10px;text-align:left;border-bottom:1px solid #ddd;overflow-wrap:anywhere}}
pre{{white-space:pre-wrap;overflow-wrap:anywhere}}button{{padding:10px 16px;cursor:pointer}}
</style></head><body>
<h1>RepoPilot Analysis Report</h1>
<p>Generated by RepoPilot Lite</p>
<div class="card"><h2>Code Metrics</h2>
<table><thead><tr><th>File</th><th>Lines</th><th>LOC</th><th>Functions</th><th>Classes</th><th>Complexity</th></tr></thead>
<tbody>{rows or '<tr><td colspan="6">No Python metrics available</td></tr>'}</tbody></table></div>
<div class="card"><h2>Complete Analysis Data</h2><pre>{report_json}</pre></div>
<button onclick="window.print()">Print / Save as PDF</button>
</body></html>"""

    return HTMLResponse(
        content=html,
        headers={"Content-Disposition": 'attachment; filename="repopilot-report.html"'}
    )

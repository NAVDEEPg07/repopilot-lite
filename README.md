# RepoPilot Lite

A small educational web app that inspects a Python project ZIP, parses Python imports with the built-in `ast` module, and reports which files may be affected by changing a selected file. Uploaded source is never executed.

## Features

- Upload a ZIP of source files (10 MB compressed, 30 MB expanded, 2,000 entries, 2 MB per file).
- View the actual file tree and detected internal Python import edges.
- Select a Python file to see direct and indirect dependents with dependency paths.
- Warnings for syntax errors and imports that could not be resolved.
- Basic privacy/terms pages, custom 404, favicon, responsive layout, and pytest tests.

## Requirements

Python 3.10+ recommended. Windows PowerShell instructions follow.

## Run on Windows

Open PowerShell in the `repopilot-lite` project folder:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
python -m uvicorn app:app --reload
```

Open **http://127.0.0.1:8000**. API health check: **http://127.0.0.1:8000/api/health**. FastAPI's interactive API docs are at **http://127.0.0.1:8000/docs**.

If PowerShell blocks virtual-environment activation, you can avoid activation and run `\.venv\Scripts\python.exe -m pip install -r requirements.txt`, then `\.venv\Scripts\python.exe -m uvicorn app:app --reload`.

## Test

With the virtual environment active:

```powershell
python -m pytest -q
```

Tests cover known direct/indirect imports, cycles, unresolved imports, syntax errors, empty archives, invalid ZIPs, traversal attempts, and the upload-to-impact API flow.

## Try the included example

Create a ZIP with the three files in `examples/sample_project/` at the archive root:

```powershell
Compress-Archive -Path .\examples\sample_project\*.py -DestinationPath .\sample-project.zip -Force
```

Upload `sample-project.zip`. Select `user_service.py`. The expected result is `auth.py` as a direct dependent and `login.py` as an indirect dependent.

## How it works

1. The browser posts the selected ZIP to `POST /api/analyze`.
2. The backend checks ZIP paths and resource limits, reads text files into memory, and parses `.py` files using `ast.parse`.
3. Imports that match files/modules discovered inside the ZIP become graph edges directed from importer to imported module.
4. `POST /api/impact` traverses the reverse graph from the selected file to find dependent files and dependency paths.
5. The browser renders the JSON returned by the backend; it does not calculate dependencies itself.

### Limits to understand

- This is static analysis, not a full Python runtime/import resolver. Dynamic imports, environment-specific import paths, namespace packages, installed dependencies, and some relative-import edge cases may not resolve.
- Unresolved imports are reported rather than guessed. Some third-party imports can appear in the unresolved list because the analyzer intentionally does not inspect the Python environment.
- The report identifies potential impact, not guaranteed failures.
- Session data is stored in process memory, not a database. Restarting the server clears it. This is intended for local demos, not multi-user production hosting.
- A deployment behind a different origin can set `window.REPOPILOT_API_BASE` before `app.js` loads, but the current bundled page assumes frontend and API are served by the same FastAPI origin. Configure CORS and deployment policy deliberately if splitting them across origins.

## GitHub upload

Create an empty repository on GitHub, then from this folder:

```powershell
git init
git add .
git commit -m "Build RepoPilot Lite Python impact analyzer"
git branch -M main
git remote add origin https://github.com/YOUR-USERNAME/YOUR-REPOSITORY.git
git push -u origin main
```

Replace the remote URL with your repository's actual URL. Do not commit `.venv`, secrets, or uploaded project ZIPs.

## Before public deployment

- Use a production ASGI server configuration and set request/time/memory limits at the hosting layer.
- Add rate limiting and stronger concurrency/session management if exposed publicly.
- Configure HTTPS, domain, allowed origins, and trusted proxy settings as applicable.
- Review the privacy policy and terms; add the real operator identity and contact information and get appropriate legal review.
- Test uploads and resource limits on the target host; do not treat the demo as production-secure.
- Add monitoring/logging carefully without logging uploaded source code.
- Decide whether uploads and analysis sessions should be isolated per user before any multi-user deployment.

## Project layout

```text
repopilot-lite/
  app.py
  analyzer.py
  requirements.txt
  README.md
  static/        # CSS, JavaScript, favicon
  templates/     # main, legal, and 404 pages
  tests/         # analyzer and API tests
  examples/      # tiny known-dependency project
```

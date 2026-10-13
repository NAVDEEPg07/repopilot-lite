import io
from zipfile import ZipFile

import pytest
from fastapi.testclient import TestClient

from analyzer import analyze_sources, impact_for
from app import app


def sample_sources():
    return {
        "user_service.py": "def find_user(name):\n    return name\n",
        "auth.py": "from user_service import find_user\ndef auth(name): return find_user(name)\n",
        "login.py": "from auth import auth\ndef login(name): return auth(name)\n",
    }


def make_zip(files):
    buf = io.BytesIO()
    with ZipFile(buf, "w") as z:
        for name, content in files.items():
            z.writestr(name, content)
    return buf.getvalue()


def test_direct_and_indirect_impact_paths():
    result = analyze_sources(sample_sources())
    impact = impact_for(result, "user_service.py")
    assert [x["file"] for x in impact["direct_dependents"]] == ["auth.py"]
    assert [x["file"] for x in impact["indirect_dependents"]] == ["login.py"]
    assert impact["indirect_dependents"][0]["path"] == ["user_service.py", "auth.py", "login.py"]


def test_cycle_does_not_loop_forever():
    result = analyze_sources({"a.py": "import b\n", "b.py": "import a\n"})
    impact = impact_for(result, "a.py")
    assert [x["file"] for x in impact["direct_dependents"]] == ["b.py"]
    assert len(impact["dependency_paths"]) == 1


def test_unresolved_import_is_reported():
    result = analyze_sources({"main.py": "import package_that_is_not_here\n"})
    assert any(x["import"] == "package_that_is_not_here" for x in result["unresolved_imports"])


def test_malformed_python_produces_warning():
    result = analyze_sources({"broken.py": "def this is not python"})
    assert result["warnings"] and result["warnings"][0]["file"] == "broken.py"


def test_empty_sources_are_handled():
    result = analyze_sources({})
    assert result["files"] == []
    assert result["python_files"] == []


def test_invalid_zip_rejected():
    client = TestClient(app)
    response = client.post("/api/analyze", files={"file": ("project.zip", b"not a zip", "application/zip")})
    assert response.status_code == 400


def test_empty_zip_rejected_with_useful_message():
    client = TestClient(app)
    response = client.post("/api/analyze", files={"file": ("empty.zip", make_zip({}), "application/zip")})
    assert response.status_code == 400
    assert "No readable project files" in response.json()["detail"]


def test_api_end_to_end_zip_and_impact():
    client = TestClient(app)
    response = client.post("/api/analyze", files={"file": ("sample.zip", make_zip(sample_sources()), "application/zip")})
    assert response.status_code == 200
    payload = response.json()
    assert "login.py" in [x["path"] for x in payload["files"]]
    impact = client.post("/api/impact", json={"session_id": payload["session_id"], "selected_file": "user_service.py"})
    assert impact.status_code == 200
    assert [x["file"] for x in impact.json()["direct_dependents"]] == ["auth.py"]
    assert [x["file"] for x in impact.json()["indirect_dependents"]] == ["login.py"]


def test_zip_path_traversal_rejected():
    client = TestClient(app)
    response = client.post("/api/analyze", files={"file": ("bad.zip", make_zip({"../evil.py": "x=1"}), "application/zip")})
    assert response.status_code == 400
    assert "unsafe file path" in response.json()["detail"]


def test_non_python_file_cannot_be_selected():
    result = analyze_sources({"readme.md": "hello", "main.py": "x = 1"})
    with pytest.raises(ValueError):
        impact_for(result, "readme.md")

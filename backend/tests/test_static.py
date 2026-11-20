from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.static import mount_frontend


def make_client(tmp_path):
    (tmp_path / "assets").mkdir()
    (tmp_path / "index.html").write_text("<html>app</html>")
    (tmp_path / "assets" / "a.js").write_text("console.log(1)")
    (tmp_path / "robots.txt").write_text("ok")
    app = FastAPI()
    app.get("/api/health")(lambda: {"status": "ok"})
    mount_frontend(app, tmp_path)
    return TestClient(app)


def test_serves_index_assets_and_client_side_routes(tmp_path):
    c = make_client(tmp_path)
    assert c.get("/").text == "<html>app</html>"
    assert c.get("/roster/5?view=brand").text == "<html>app</html>"      # client-side route falls back to the app
    assert c.get("/assets/a.js").text == "console.log(1)"
    assert c.get("/robots.txt").text == "ok"


def test_api_routes_are_not_shadowed_and_unknown_api_is_404(tmp_path):
    c = make_client(tmp_path)
    assert c.get("/api/health").json() == {"status": "ok"}
    assert c.get("/api/nope").status_code == 404


def test_cannot_read_files_outside_the_dist_folder(tmp_path):
    dist = tmp_path / "dist"
    dist.mkdir()
    (dist / "index.html").write_text("<html>app</html>")
    (tmp_path / "secret.txt").write_text("secret")
    app = FastAPI()
    mount_frontend(app, dist)
    r = TestClient(app).get("/..%2Fsecret.txt")
    assert "secret" not in r.text

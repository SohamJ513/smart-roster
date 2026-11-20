def test_reset_open_when_no_token_configured(client):
    assert client.post("/api/demo/reset").status_code == 200


def test_reset_requires_token_when_configured(client, monkeypatch):
    monkeypatch.setenv("DEMO_RESET_TOKEN", "s3cret")
    assert client.post("/api/demo/reset").status_code == 403
    assert client.post("/api/demo/reset", headers={"X-Demo-Token": "s3cret"}).status_code == 200

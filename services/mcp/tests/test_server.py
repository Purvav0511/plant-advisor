from advisor_mcp.server import server


def test_server_builds_http_app():
    app = server.streamable_http_app()
    assert any(getattr(route, "path", None) == "/mcp" for route in app.routes)

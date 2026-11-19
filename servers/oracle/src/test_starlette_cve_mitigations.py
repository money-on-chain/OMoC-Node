"""Exercise the Oracle HTTP guards without starting blockchain services."""

import ast
import asyncio
import logging
from pathlib import Path
from types import SimpleNamespace

from fastapi import FastAPI, Form, Request
from starlette.responses import JSONResponse, Response


APP_SOURCE = Path(__file__).with_name("app.py")


def load_http_guards():
    """Load the real guards without importing app.py's startup dependencies."""
    tree = ast.parse(APP_SOURCE.read_text())
    names = {
        "OPEN_ENDPOINTS",
        "SIGN_ENDPOINTS",
        "MAX_SIGN_BODY_SIZE",
        "LimitSignBodyMiddleware",
        "filter_ips_by_selected_oracles",
    }
    nodes = [
        node
        for node in tree.body
        if (isinstance(node, ast.Assign) and any(
            isinstance(target, ast.Name) and target.id in names
            for target in node.targets
        ))
        or (isinstance(node, (ast.ClassDef, ast.AsyncFunctionDef)) and node.name in names)
    ]
    namespace = {
        "Response": Response,
        "Request": Request,
        "JSONResponse": JSONResponse,
        "logger": logging.getLogger(__name__),
        "oracle_settings": SimpleNamespace(ORACLE_RUN_IP_FILTER=True),
        "settings": SimpleNamespace(DEBUG=False),
        "main_executor": SimpleNamespace(is_valid_ip=lambda ip: False),
        "not_authorized_msg": "Not authorized",
        "get_error_msg": str,
        "app": FastAPI(),
    }
    exec(compile(ast.Module(body=nodes, type_ignores=[]), str(APP_SOURCE), "exec"), namespace)
    return namespace


async def request_asgi(app, path, host, body=b"", chunks=None, headers=()):
    events = []
    parts = chunks if chunks is not None else [body]
    incoming = [
        {"type": "http.request", "body": part, "more_body": index < len(parts) - 1}
        for index, part in enumerate(parts)
    ]

    async def receive():
        if incoming:
            return incoming.pop(0)
        return {"type": "http.disconnect"}

    async def send(event):
        events.append(event)

    scope = {
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": "POST",
        "scheme": "http",
        "path": path,
        "raw_path": path.encode(),
        "query_string": b"",
        "root_path": "",
        "headers": [(b"host", host.encode()), *headers],
        "client": ("203.0.113.10", 12345),
        "server": ("127.0.0.1", 80),
    }
    await app(scope, receive, send)
    return next(event["status"] for event in events if event["type"] == "http.response.start")


def test_malformed_host_cannot_bypass_ip_filter():
    guards = load_http_guards()
    app = guards["app"]
    app.middleware("http")(guards["filter_ips_by_selected_oracles"])

    @app.post("/sign/")
    async def sign():
        return {"signed": True}

    # CVE-2026-48710: the reconstructed URL looks like /info, while the
    # router still sees /sign/. An unauthorized IP must be rejected.
    assert asyncio.run(request_asgi(app, "/sign/", "example.com/info?x=")) == 417
    assert asyncio.run(request_asgi(app, "/sign/", "example.com")) == 417


def test_sign_body_limit_rejects_chunked_oversize_before_form_parsing():
    guards = load_http_guards()
    guards["main_executor"].is_valid_ip = lambda ip: True
    reached = []
    app = guards["app"]
    app.add_middleware(guards["LimitSignBodyMiddleware"])

    @app.post("/sign/")
    async def sign(value: str = Form(...)):
        reached.append(True)
        return {"signed": True}

    limit = guards["MAX_SIGN_BODY_SIZE"]
    headers = [(b"content-type", b"application/x-www-form-urlencoded")]
    valid_body = b"value=" + b"a" * (limit - len(b"value="))
    assert asyncio.run(request_asgi(app, "/sign/", "example.com", body=valid_body, headers=headers)) == 200
    assert reached == [True]
    reached.clear()
    assert asyncio.run(request_asgi(app, "/sign/", "example.com", chunks=[valid_body, b"b"], headers=headers)) == 413
    assert reached == []

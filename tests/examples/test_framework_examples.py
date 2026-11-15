from __future__ import annotations

import importlib.util
import py_compile
import sys
import time
from pathlib import Path
from types import ModuleType

import pytest

import rstream

ROOT = Path(__file__).resolve().parents[2]
PAYLOAD = (
    b'{"id":"evt_example","type":"tunnel.created",'
    b'"created_at":"2026-06-01T12:00:00Z",'
    b'"project_id":"proj_example","object":{"id":"tun_example"}}'
)
SECRET = "whsec_test"
SIGNATURE = rstream.sign_payload(PAYLOAD, SECRET, timestamp=int(time.time()))


def test_example_entrypoints_compile() -> None:
    for path in sorted((ROOT / "examples").glob("*/main.py")):
        py_compile.compile(str(path), doraise=True)


def test_fastapi_tunnel_application_shape() -> None:
    from fastapi.testclient import TestClient

    module = load_example_module("fastapi_tunnel")
    client = TestClient(module.app)

    response = client.get("/")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_flask_tunnel_application_shape() -> None:
    module = load_example_module("flask_tunnel")
    client = module.app.test_client()

    response = client.get("/")

    assert response.status_code == 200
    assert response.json == {"framework": "flask", "ok": True}


def test_fastapi_webhook_receiver_accepts_signed_payload(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from fastapi.testclient import TestClient

    monkeypatch.setenv("RSTREAM_WEBHOOK_SECRET", SECRET)
    module = load_example_module("fastapi_webhook_receiver")
    client = TestClient(module.app)

    response = client.post(
        "/webhooks/rstream",
        content=PAYLOAD,
        headers={"rstream-signature": SIGNATURE},
    )

    assert response.status_code == 200
    assert response.json() == {"received": True}

    rejected = client.post(
        "/webhooks/rstream",
        content=PAYLOAD,
        headers={"rstream-signature": "t=1780000000,v1=bad"},
    )
    assert rejected.status_code == 400


def test_flask_webhook_receiver_accepts_signed_payload(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("RSTREAM_WEBHOOK_SECRET", SECRET)
    module = load_example_module("flask_webhook_receiver")
    client = module.app.test_client()

    response = client.post(
        "/webhooks/rstream",
        data=PAYLOAD,
        headers={"rstream-signature": SIGNATURE},
        content_type="application/json",
    )

    assert response.status_code == 200
    assert response.json == {
        "event_id": "evt_example",
        "event_type": "tunnel.created",
        "received": True,
    }

    rejected = client.post(
        "/webhooks/rstream",
        data=PAYLOAD,
        headers={"rstream-signature": "t=1780000000,v1=bad"},
        content_type="application/json",
    )
    assert rejected.status_code == 400


def test_django_webhook_receiver_accepts_signed_payload(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from django.test import Client as DjangoClient

    monkeypatch.setenv("RSTREAM_WEBHOOK_SECRET", SECRET)
    load_example_module("django_webhook_receiver")
    client = DjangoClient()

    response = client.post(
        "/webhooks/rstream",
        data=PAYLOAD,
        content_type="application/json",
        headers={"rstream-signature": SIGNATURE},
    )

    assert response.status_code == 200
    assert response.json() == {
        "event_id": "evt_example",
        "event_type": "tunnel.created",
        "received": True,
    }

    rejected = client.post(
        "/webhooks/rstream",
        data=PAYLOAD,
        content_type="application/json",
        headers={"rstream-signature": "t=1780000000,v1=bad"},
    )
    assert rejected.status_code == 400


def load_example_module(example: str) -> ModuleType:
    directories = {"fastapi_webhook_receiver": "webhook-receiver"}
    path = (
        ROOT
        / "examples"
        / directories.get(example, example.replace("_", "-"))
        / "main.py"
    )
    module_name = f"rstream_python_example_{example}"
    spec = importlib.util.spec_from_file_location(module_name, path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


@pytest.mark.asyncio
@pytest.mark.parametrize("failure", ["none", "connect", "serve", "cancel"])
async def test_fastapi_entrypoint_owns_lifespan_on_success_and_failure(
    monkeypatch: pytest.MonkeyPatch, failure: str
) -> None:
    import asyncio
    from collections.abc import AsyncIterator
    from contextlib import asynccontextmanager
    from unittest.mock import AsyncMock, MagicMock

    from fastapi import FastAPI

    module = load_example_module("fastapi_tunnel")
    events: list[str] = []

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        app.state.ready = True
        events.append("startup")
        try:
            yield
        finally:
            app.state.ready = False
            events.append("shutdown")

    application = FastAPI(lifespan=lifespan)
    monkeypatch.setattr(module, "app", application)
    tunnel = MagicMock(forwarding_address="https://example.test")
    control = MagicMock()
    control.__aenter__ = AsyncMock(return_value=control)
    control.__aexit__ = AsyncMock(return_value=False)
    control.create_tunnel = AsyncMock(return_value=tunnel)
    client = MagicMock()
    client.__aenter__ = AsyncMock(return_value=client)
    client.__aexit__ = AsyncMock(return_value=False)

    async def connect() -> object:
        assert application.state.ready
        events.append("connect")
        if failure == "connect":
            raise RuntimeError("connect failed")
        return control

    async def serve(app: FastAPI, accepted: object) -> None:
        assert app is application
        assert accepted is tunnel
        assert app.state.ready
        events.append("serve")
        if failure == "serve":
            raise RuntimeError("serve failed")
        if failure == "cancel":
            raise asyncio.CancelledError

    client.connect = connect
    monkeypatch.setattr(rstream.Client, "from_env", lambda: client)
    monkeypatch.setattr(rstream.asgi, "serve", serve)
    expected = asyncio.CancelledError if failure == "cancel" else RuntimeError
    if failure == "none":
        await module.main()
    else:
        with pytest.raises(expected):
            await module.main()
    assert events == (
        ["startup", "connect", "shutdown"]
        if failure == "connect"
        else ["startup", "connect", "serve", "shutdown"]
    )
    assert not application.state.ready
    client.__aexit__.assert_awaited_once()

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

from __future__ import annotations

import asyncio
from contextlib import suppress

import django
from django.apps import apps
from django.conf import settings
from django.core.wsgi import get_wsgi_application
from django.http import JsonResponse
from django.urls import path

import rstream


def root(_request: object) -> JsonResponse:
    return JsonResponse({"framework": "django", "ok": True})


urlpatterns = [path("", root)]


def configure_django() -> None:
    if not settings.configured:
        settings.configure(
            ALLOWED_HOSTS=["*"],
            DEBUG=True,
            DEFAULT_AUTO_FIELD="django.db.models.BigAutoField",
            INSTALLED_APPS=[],
            MIDDLEWARE=[],
            ROOT_URLCONF=__name__,
            SECRET_KEY="rstream-python-django-tunnel",
        )
    if not apps.ready:
        django.setup()


async def main() -> None:
    configure_django()
    application = get_wsgi_application()
    async with (
        rstream.Client.from_env() as client,
        await client.connect() as control,
    ):
        # Client.from_env reads the same config file and environment variables
        # used by the rstream CLI and the other SDKs.
        tunnel = await control.create_tunnel(
            protocol="http",
            http_version="http/1.1",
            publish=True,
        )
        print("Forwarding address:", tunnel.forwarding_address)
        # The WSGI helper dispatches accepted rstream streams directly to Django.
        await rstream.wsgi.serve(application, tunnel)


def run() -> None:
    with suppress(KeyboardInterrupt):
        asyncio.run(main())


if __name__ == "__main__":
    run()

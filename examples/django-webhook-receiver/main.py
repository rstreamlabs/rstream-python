from __future__ import annotations

import os
import sys

import django
from django.apps import apps
from django.conf import settings
from django.core.management import execute_from_command_line
from django.http import HttpRequest, JsonResponse
from django.urls import path
from django.views.decorators.csrf import csrf_exempt

import rstream


@csrf_exempt
def rstream_webhook(request: HttpRequest) -> JsonResponse:
    if request.method != "POST":
        return JsonResponse({"error": "Method not allowed."}, status=405)
    secret = os.environ.get("RSTREAM_WEBHOOK_SECRET")
    if secret is None:
        return JsonResponse({"error": "Webhook secret missing."}, status=500)
    signature = request.headers.get("rstream-signature", "")
    try:
        # Django exposes request.body as the raw bytes required for signature
        # verification. Do not verify a parsed JSON object.
        event = rstream.verify_event(request.body, signature, secret)
    except rstream.RstreamError as error:
        return JsonResponse({"error": str(error)}, status=400)
    return JsonResponse(
        {
            "event_id": event.id,
            "event_type": event.type,
            "received": True,
        }
    )


urlpatterns = [path("webhooks/rstream", rstream_webhook)]


def configure_django() -> None:
    if not settings.configured:
        settings.configure(
            ALLOWED_HOSTS=["*"],
            DEBUG=True,
            DEFAULT_AUTO_FIELD="django.db.models.BigAutoField",
            INSTALLED_APPS=[],
            MIDDLEWARE=[],
            ROOT_URLCONF=__name__,
            SECRET_KEY="rstream-python-django-webhook-receiver",
        )
    if not apps.ready:
        django.setup()


def main() -> None:
    configure_django()
    execute_from_command_line(
        [
            sys.argv[0],
            "runserver",
            os.environ.get("DJANGO_ADDR", "127.0.0.1:8000"),
        ]
    )


configure_django()


if __name__ == "__main__":
    main()

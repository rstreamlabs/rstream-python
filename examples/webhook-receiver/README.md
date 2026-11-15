# Webhook receiver

FastAPI receiver that verifies rstream webhook signatures.

```bash
python -m pip install -e "../../[asgi,examples]" uvicorn
export RSTREAM_WEBHOOK_SECRET="whsec_..."
python -m uvicorn main:app --host 127.0.0.1 --port 8000
```

Run these commands from this example directory in an activated virtual environment. The receiver listens at `http://127.0.0.1:8000/webhooks/rstream`. Use the [local signed delivery walkthrough](../../docs/003-webhooks.md#try-a-local-delivery) to see a valid delivery return 200 and an invalid signature return 400.

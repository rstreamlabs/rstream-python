# Webhook receiver

FastAPI receiver that verifies rstream webhook signatures.

```bash
pip install -e "../../[asgi,examples]"
export RSTREAM_WEBHOOK_SECRET="whsec_..."
uvicorn main:app --reload
```

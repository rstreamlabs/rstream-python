# Flask webhook receiver

Minimal Flask receiver that verifies rstream webhook signatures from the raw
request body.

```bash
pip install -e "../../[examples]"
export RSTREAM_WEBHOOK_SECRET="whsec_..."
python main.py
```

Point a webhook endpoint at `http://127.0.0.1:8000/webhooks/rstream` while
developing locally.

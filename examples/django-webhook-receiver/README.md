# Django webhook receiver

Single-file Django receiver that verifies rstream webhook signatures from
`request.body`.

```bash
pip install -e "../../[examples]"
export RSTREAM_WEBHOOK_SECRET="whsec_..."
python main.py
```

The development server listens on `127.0.0.1:8000` by default. Override it with
`DJANGO_ADDR`, for example `DJANGO_ADDR=127.0.0.1:8080 python main.py`.

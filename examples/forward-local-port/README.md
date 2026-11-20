# Forward local port

Publish an existing local TCP service through an HTTP tunnel.

```bash
python -m pip install -e "../..[api]"
python main.py 127.0.0.1 8000
```

Use this mode for services that already bind a local port. New Python framework
integrations should prefer the ASGI or WSGI helpers when available.

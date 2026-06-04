# FastAPI tunnel

Publish a FastAPI ASGI application through a public rstream HTTP tunnel without
binding the app to a local port.

```bash
pip install -e "../../[asgi,examples]"
python main.py
```

The example opens a published HTTP tunnel, then passes each accepted stream to
FastAPI through the SDK ASGI adapter.

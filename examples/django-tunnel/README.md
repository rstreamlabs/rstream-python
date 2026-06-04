# Django tunnel

Publish a Django WSGI application through a public rstream HTTP tunnel without
binding the app to a local port.

```bash
pip install -e "../../[wsgi,examples]"
RSTREAM_CONTEXT=tests python main.py
```

The example opens a published HTTP tunnel, then passes each accepted stream to
Django through the SDK WSGI adapter.

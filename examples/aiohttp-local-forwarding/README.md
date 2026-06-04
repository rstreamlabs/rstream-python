# aiohttp local forwarding

Publish an aiohttp web application through managed local forwarding. aiohttp
is not served by the direct ASGI or WSGI helpers here: it owns a loopback HTTP
socket, while the SDK owns the rstream tunnel lifecycle and forwards accepted
streams to that socket.

```bash
pip install -e "../../[examples]"
python main.py
```

Use the FastAPI, Flask, or Django examples when the framework can be served
directly from rstream streams without a loopback port.

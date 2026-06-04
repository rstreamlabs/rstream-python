# Test matrix

This matrix tracks the behavior that must stay covered before publishing the
Python SDK.

| Area | Coverage |
| --- | --- |
| Config | CLI-compatible YAML, selected context, env overrides, unsupported transport rejection, invalid timeouts, invalid YAML. |
| Client lifecycle | `from_env`, option overrides, client close closes open control channels, closed-client errors. |
| Control channel | TLS handshake, open response validation, tunnel creation, tunnel close, control close, unexpected transport close. |
| Timeouts | Engine connection timeout, control open timeout, tunnel open timeout, tunnel close timeout, stream handshake timeout, proxy handshake timeout. |
| Private streams | Dial by name, dial by ID, zero-RTT on, zero-RTT off, concurrent dials. |
| Published tunnels | HTTP/1.1 bytestream creation, local TCP forwarding, direct ASGI serving, and published HTTP fetch in real-engine e2e. |
| Framework adapters | Direct ASGI dispatch, streaming and chunked ASGI request bodies, direct WSGI dispatch, chunked WSGI request bodies, oversized payloads, framework errors, WSGI write callable, and real-engine ASGI/WSGI paths. |
| Proxy delivery | Engine-initiated proxy connection, app-side `accept()`, response propagation, proxy error reporting. |
| Webhooks | Signing, header building, signature verification, tolerance window, malformed payloads, parsed event object. |
| Framework examples | FastAPI, Flask, Django webhook receivers; direct FastAPI, Flask, and Django tunnel examples; aiohttp local-forwarding fallback. |

Unsupported datagram tunnels, QUIC runtime transport, HTTP/3 tunnel creation,
custom transport proxies, and external credential stores must continue to fail
explicitly until they are implemented.

# Dial a private HTTP service

Send an HTTP request over a private rstream byte stream. First start the
[local origin and private tunnel owner](../../docs/tunnels/001-private-and-tcp.md#dial-a-private-http-service).
From the repository root with the checkout environment active:

```sh
python examples/private-dial/main.py python-private-http
```

Use the existing private tunnel name or ID. The SDK writes the HTTP
request and prints the response through EOF. Expect HTTP 200 and the local
server's body. The program closes its stream and exits, and enforces a
15-second deadline for the exchange.

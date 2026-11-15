# Configuration

The Python SDK resolves configuration in the same order as the other rstream
SDKs. The PyPI distribution is `rstreamlabs-rstream`, and Python code imports
the package as `rstream`.

1. Explicit `Client(...)` options.
2. Environment variables.
3. The selected context in `~/.rstream/config.yaml`.
4. SDK defaults.

The default config path is:

```text
~/.rstream/config.yaml
```

Set `RSTREAM_CONFIG` to use another file.

## Environment variables

| Variable | Purpose |
| --- | --- |
| `RSTREAM_CONFIG` | Config file path. |
| `RSTREAM_CONTEXT` | Context name to load from the config file. |
| `RSTREAM_ENGINE` | Engine host and optional port. |
| `RSTREAM_AUTHENTICATION_TOKEN` | Data-plane authentication token. |
| `RSTREAM_MTLS_CERT_FILE` | mTLS client certificate path. |
| `RSTREAM_MTLS_KEY_FILE` | mTLS client key path. |
| `RSTREAM_API_URL` | Control plane API URL for managed project discovery. |
| `RSTREAM_REGION` | Authorized region to select for a managed project. |
| `RSTREAM_CONTROL_PLANE_HEADERS` | Additional Control plane request headers encoded as a JSON object. |
| `RSTREAM_TUNNEL_TRANSPORT` | `auto`, `tls`, or `quic`. Python maps `auto` to TLS and rejects explicit `quic`. |
| `RSTREAM_QUIC_TRANSPORT` | Legacy selector. Prefer `RSTREAM_TUNNEL_TRANSPORT`. |

The SDK also accepts `RSTREAM_ENGINE_ADDRESS` for compatibility with older
local C++ SDK workflows. Prefer `RSTREAM_ENGINE` in new code.

Region selection requires a managed project endpoint and cannot be combined
with an explicit engine override. Control plane headers may satisfy a separate
deployment access layer. Authentication, forwarding, and hop-by-hop headers are
reserved; malformed values and case-insensitive duplicates are rejected before
network I/O.

## Trust the engine

The TLS connection verifies the engine’s certificate and hostname. For a private CA, set `SSL_CERT_FILE` to its PEM bundle before starting Python, or configure the SDK’s `TLSOptions`. The engine address must match the certificate unless an explicit verification name is configured.

## Config file

```yaml
version: 1
defaults:
  context:
    name: production
contexts:
  - name: production
    apiUrl: https://rstream.io
    projectEndpoint: my-project
    auth:
      token:
        storage:
          value: eyJ...
```

If an explicit engine override is provided, stored tokens or stored mTLS
credentials from another context are refused. Pass an explicit token, explicit
mTLS files, or `no_token=True` for local unauthenticated engines.

The shared transport selector is available through `ClientOptions.tunnel_transport`
and YAML:

```yaml
transport:
  mode: auto
```

The Python runtime currently implements TLS only. The default `auto` mode uses
TLS, while an explicit `quic` request fails during resolution instead of being
silently downgraded. Legacy `transport.useQuic` remains readable.

## Unsupported config

The Python SDK supports bytestream tunnels. It rejects unsupported
transport or credential storage settings instead of ignoring them:

- QUIC transport.
- Datagram tunnels.
- SOCKS or custom proxy transport.
- Custom DNS transport settings.
- Keychain, PKCS#11, external mTLS signers (`auth.mtls.storage.kind: exec`),
  or other external credential stores.

The `exec` backend is supported by the Go SDK and CLI. Selecting a context or
environment that uses it raises `ERR_RSTREAM_UNSUPPORTED_MTLS_STORAGE` before
connecting; this SDK never executes the configured helper. Other contexts in the
same configuration file remain usable.

## Engine HTTP access with certificates

The existing `list_clients`, `list_tunnels` and `watch` methods support enrolled
file-based mTLS identities. Keep one `Client` in an `async with` block. It discovers
the dedicated project API through anonymous, verified HTTPS and caches the address
in memory, normally for one hour. Concurrent callers share discovery; cancellation
of one waiter does not cancel others, and closing the client cancels pending
lookup work. No YAML field, persistent cache or new login is required.

Discovery never sends the certificate, a token, cookies or Control plane headers,
refuses redirects and verifies the server even when runtime TLS is marked insecure.
The ordinary Engine hostname never requests a certificate. Runtime requests use
the discovered authority with the existing identity and project permissions.
Both SSE and WebSocket certificate watches use TLS/TCP. Python does not implement
HTTP/3 or a TURN generation helper; use Go/JavaScript or the documented Engine API
for TURN issuance. Control plane administration and region selectors still require
a token; provision an explicit Engine address for a certificate-only device.

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

The SDK also accepts `RSTREAM_ENGINE_ADDRESS` for compatibility with older
local C++ SDK workflows. Prefer `RSTREAM_ENGINE` in new code.

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

## Unsupported config

The Python SDK v0.1 supports bytestream tunnels. It rejects unsupported
transport or credential storage settings instead of ignoring them:

- QUIC transport.
- Datagram tunnels.
- SOCKS or custom proxy transport.
- Custom DNS transport settings.
- Keychain, PKCS#11, or other external credential stores.

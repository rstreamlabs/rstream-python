# Configure the Python SDK

The SDK resolves explicit `Client(...)` options first, then environment
variables, the selected context and SDK defaults. The CLI and SDK
share `~/.rstream/config.yaml`. Set `RSTREAM_CONFIG` to use a different
file.

| Deployment | What to supply |
| --- | --- |
| Hosted project | Select a CLI context, or provide a project endpoint and an authorized credential. Install the `api` extra when the SDK needs to resolve a project endpoint or choose a region. |
| Direct Engine | Set its hostname and port, agent credential and any private CA trust. |
| Unattended service | Provision that service's identity with the permissions and resource scope it needs. |

## Environment variables

| Variable | Purpose |
| --- | --- |
| `RSTREAM_CONFIG` | Shared YAML configuration file. |
| `RSTREAM_CONTEXT` | Name of the selected context. |
| `RSTREAM_ENGINE` | Direct Engine hostname and optional port. |
| `RSTREAM_AUTHENTICATION_TOKEN` | Agent token for the selected Engine or project. |
| `RSTREAM_MTLS_CERT_FILE` | Client certificate in a PEM file. |
| `RSTREAM_MTLS_KEY_FILE` | Corresponding private key in a PEM file. |
| `RSTREAM_API_URL` | Control plane URL for managed project discovery. |
| `RSTREAM_REGION` | Region for a managed project. |
| `RSTREAM_CONTROL_PLANE_HEADERS` | Additional authorized Control plane request headers as a JSON object. |
| `RSTREAM_TUNNEL_TRANSPORT` | `auto` or `tls` use TLS. An explicit `quic` request is rejected. |
| `RSTREAM_QUIC_TRANSPORT` | Legacy transport selector. Prefer `RSTREAM_TUNNEL_TRANSPORT`. |
| `SSL_CERT_FILE` | PEM trust bundle used by Python TLS. |

`RSTREAM_ENGINE_ADDRESS` remains a compatibility alias. Use
`RSTREAM_ENGINE` in new integrations. Region selection needs managed
project metadata. An explicit Engine override also needs explicit
credentials. The SDK rejects malformed, duplicate, or reserved
Control plane headers before making requests.

## Trust the Engine

The TLS connection verifies the Engine certificate and hostname.
For a private CA, set `SSL_CERT_FILE` before starting Python or provide
`TLSOptions(ca_file=...)`. The file is the bundle of authorities you
want the connection to trust. Python uses these settings for the Engine
connection. A shared CLI context's `transport.tls` section does not
supply Python's CA or name override.

For a direct Engine with an enrolled client certificate:

```python
import rstream

client = rstream.Client(
    engine="edge.example.com:443",
    tls=rstream.TLSOptions(
        ca_file="/etc/rstream/ca.pem",
        cert_file="/etc/rstream/agent-cert.pem",
        key_file="/etc/rstream/agent-key.pem",
    ),
)
```

Use the client in an async context. Set `server_name` when you need to
verify an explicit certificate identity. Use one form of agent
authentication for the selected Engine. File-based mTLS also accepts
the environment variables above or the file values in the selected
CLI context.

## Config file

This hosted context lets the SDK discover the Engine. Install the
`api` extra for this path. With the CLI, prefer a context provisioned by
`rstream project use`. A context with a resolved Engine address can
connect directly.

```yaml
version: 1
defaults:
  context:
    name: my-project
contexts:
  - name: my-project
    apiUrl: https://rstream.io
    projectEndpoint: my-project-endpoint
    auth:
      token:
        storage:
          kind: inline
          value: YOUR_PROJECT_TOKEN
    transport:
      mode: auto
```

Protect the real token if you provision the context in a file. Replace
the project endpoint and token independently. For a direct Engine,
select its context with the correct identity and trust.

## Unsupported config

| Area | Settings rejected by Python |
| --- | --- |
| Runtime transport | QUIC, datagram tunnels, proxy configuration and custom DNS. |
| Shared context | `transport.bind`, `transport.ipFamily` and `transport.mptcp`. Remove these fields from a context selected by Python, including `mptcp: false`. |
| Credential storage | Keychain, PKCS#11, inline client keys and external mTLS signers (`auth.mtls.storage.kind: exec`). |

Use the CLI or Go SDK for an external signer. Python rejects that
credential storage before connecting.

## Engine HTTP access with certificates

Use an enrolled certificate and private key from files to list and
watch through the Engine API. Install the `api` extra for discovery,
inventory and SSE. Install `realtime` for WebSocket watches. Keep one
client open while using the API. The SDK discovers the dedicated
endpoint over verified HTTPS, then uses the certificate with the
returned API endpoint and applicable project permissions.

Use a direct Engine address for a certificate-only device. Region
selection and Control plane administration have separate credentials.
The [inventory walkthrough](tunnels/003-inventory.md) shows a watch's
lifetime.

## Client and TLS options

`Client(...)` and `Client.from_env(...)` accept the same options. The
async client context owns its open control channels and ongoing HTTP
discovery work.

| Option | Purpose |
| --- | --- |
| `config_path`, `context`, `read_config_file` | Select or disable shared YAML loading. Explicit and environment options still apply. |
| `engine`, `project_endpoint`, `api_url`, `region` | Select a direct Engine or a managed project. |
| `token`, `no_token`, `require_token` | Set a credential, suppress token lookup, or require an authenticated identity. |
| `tls` | Configure CA trust, certificate identity and optional client certificate files through `TLSOptions`. |
| `connect_timeout`, `operation_timeout` | Bounds for connection and protocol operations. Defaults to 15 and 30 seconds. |
| `heartbeat`, `heartbeat_interval` | Controls admission liveness. Heartbeats default to a five-second interval. When enabled, the interval accepts 1 to 300 seconds with millisecond precision. |
| `zero_rtt` | Optimizes the rstream stream handshake. Defaults to `True`. This setting is independent of TLS early data. |
| `control_plane_headers` | Add validated headers for a deployment access layer. |

Use the [tunnel guide](002-tunnels.md) for stream lifetimes and
creation options.

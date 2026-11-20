# Add datagram tunnels

The Python SDK currently supports bytestream tunnels over TLS and rejects datagrams. Define the supported datagram delivery modes, then implement their runtime paths with cancellation and bounded resource use. Match the Go reference semantics, including stream-framed delivery where supported and QUIC for native datagrams, and verify real client/engine interoperability.

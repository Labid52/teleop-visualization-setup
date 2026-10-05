# Visualization telemetry relay

The relay accepts WebSocket clients on TCP 8767. The first client message must
be an authentication object:

```json
{"type":"auth","role":"publisher","token":"..."}
```

or:

```json
{"type":"auth","role":"subscriber","token":"..."}
```

Publisher and subscriber tokens are distinct, contain at least 32 characters,
and are loaded from a root-owned environment file. Only one publisher may be
connected. Multiple subscribers are supported.

Published messages must be JSON objects with `schema_version` equal to `1` and
`message_type` equal to `vehicle_visualization`. The relay does not interpret
control messages. Each subscriber has a queue of size one; a newer state
replaces an unsent older state so a slow subscriber cannot block the publisher.
No GPS or telemetry history is persisted.

The initial bench deployment uses `ws://` with token authentication because no
trusted domain/certificate is available. Set both `TELEMETRY_TLS_CERT` and
`TELEMETRY_TLS_KEY` later to enable `wss://` without changing the protocol.

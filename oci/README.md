# Teleoperation visualization cloud

This repository contains the cloud-side infrastructure for the visualization
plane. It is intentionally independent of the G29/ESP32 control plane.

The deployment provides:

- MediaMTX 1.21.0 with an SRT-only listener on UDP 8890 for `front`, `left`,
  `right`, and `cabin` video paths.
- A token-authenticated visualization telemetry relay on TCP 8767.

No service in this repository opens UDP 4210 or imports, sends, or interprets
vehicle control messages.

See [docs/OCI_VISUALIZATION_DEPLOYMENT.md](docs/OCI_VISUALIZATION_DEPLOYMENT.md)
for deployment, operations, validation, and rollback instructions.

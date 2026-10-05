# Visualization Setup Package

This repository contains the source and setup notes for the visualization
system. It is separate from the G29/ESP32 vehicle-control project.

## What runs where

- **Orin (`orin/`)** publishes camera video and GNSS visualization data.
- **OCI/server (`oci/`)** relays video with MediaMTX/SRT and telemetry with a
  WebSocket service.
- **Operator computer (`operator/`)** receives the streams and displays them
  in the PySide6 console.

The visualization path does not use the vehicle-control UDP port. **UDP 4210
is control-only and must not be used by this project.** The GUI is not part of
the vehicle-control loop.

## Repository contents

```text
docs/       Beginner setup guide
orin/       Orin camera and GNSS publisher source, scripts, and tests
oci/        MediaMTX and telemetry relay source, service templates, and tests
operator/   Operator GUI, WAN readers, mock mode, and environment definition
```

These are the source directories to use directly; no nested ZIP extraction is
needed after cloning this repository.

## Start here

Read [`docs/VISUALIZATION_BEGINNER_GUIDE.md`](docs/VISUALIZATION_BEGINNER_GUIDE.md)
before installing or launching anything. It describes prerequisites, setup
order, credentials, commands, shutdown, and troubleshooting.

Each machine needs its matching directory and platform-specific dependencies:

- The **Orin** needs compatible Jetson hardware/software, cameras, and the
  configured GNSS source.
- The **server** needs an existing or provisioned Linux host, administrator
  access for service installation, and the required cloud and host firewall
  ingress.
- The **operator computer** needs the Python environment and an SRT-capable
  FFmpeg installation described in the guide.

The source repository does not include cloud credentials or runtime secrets.
An administrator must provision the server and create separate publisher and
reader credentials. Install each role's credentials only on the machine that
needs them, using the protected file locations documented in the guide. Never
commit secret files or paste secret values into source code, terminal logs, or
documentation.

## Two-camera operator demo

After completing the prerequisites and configuring the role-specific secret
files, the operator launch command is:

```bash
DBUS_SYSTEM_BUS_ADDRESS=unix:path=/run/dbus/system_bus_socket \
  python -m visualization.gui.main --two-camera-wan --maximized
```

Run it from the `operator/` directory with the documented Python environment
active. To preview the interface without the Orin or server, see the mock/demo
instructions in the beginner guide.

On the Orin, the two-camera publisher is started with:

```bash
./scripts/run_two_camera_visualization.sh
```

Start the GNSS driver first as described in the guide. Server setup is a
separate administrator task; the source files here do not automatically
provision an OCI VM or open cloud firewall rules.

## Security and scope

- Do not add Wi-Fi passwords, publisher/reader tokens, SRT passphrases, SSH
  keys, cloud credentials, or machine-local secret files to this repository.
- SRT video and WebSocket telemetry are visualization transports only.
- Do not send `CMD`, `MANEUVER`, or `BUTTON` control messages from this project.
- Camera, GNSS, map, and GUI failures must not be used as vehicle-control
  feedback.

See the platform-specific READMEs and documents under `orin/`, `oci/`, and
`operator/` for implementation details and tests.

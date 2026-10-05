# Visualization Project: Beginner Run Guide

This guide covers the camera and GNSS display only. It does not run or explain
G29/ESP32 vehicle control.

## What the three computers do

```text
USB cameras + GNSS driver
          │
          ▼
   Orin publisher ── SRT video + WebSocket GNSS ──► OCI visualization server
                                                           │
                                                           ▼
                                                  Operator laptop GUI
```

- **Orin:** reads the FRONT and CABIN cameras and GNSS. It encodes and sends
  video and sends GNSS updates. It does not send vehicle-control commands.
- **OCI server:** passes video streams through MediaMTX and passes GNSS updates
  through a separate WebSocket service. The services are already installed to
  start automatically. Video uses UDP 8890; visualization data uses TCP 8767.
- **Operator laptop:** receives the two streams, decodes them, and displays the
  cameras, position, speed, and map. The map uses the laptop's Internet
  connection.

The visualization path is independent of the control path. **UDP 4210 is for
control and is not used by this guide.**

## Files to upload for a fresh installation

The project has three code packages because each computer runs a different
part:

| Package | Upload/extract on | Contains |
|---|---|---|
| `teleop_visualization_jetson.zip` | Orin | Camera publishers, GNSS telemetry publisher, run scripts, camera/video configuration, and Orin setup notes. |
| `teleop_visualization_cloud.zip` | OCI server | MediaMTX configuration template, telemetry relay, service templates, and server deployment notes. |
| `teleop_visualization_operator.zip` | Operator laptop | GUI, WAN video/telemetry readers, mock modes, and Python environment definition. |
| `VISUALIZATION_BEGINNER_GUIDE.md` | Keep with all three | This overview and run guide. |

For one upload, use `VISUALIZATION_SETUP_PACKAGE.zip` beside the main project
folder. It contains clean copies of the Orin, OCI, and operator source bundles,
this guide, a file list, and SHA-256 checksums. Upload the same package to the
three computers, then extract only the matching project ZIP on each one.

First unpack the outer package on the target computer:

```bash
unzip VISUALIZATION_SETUP_PACKAGE.zip -d ~/visualization_setup_package
```

Then use the matching inner ZIP path shown in the Orin, OCI, or operator
instructions below.

The Orin and operator bundles are source code, not complete computer images.
Each machine still needs its operating system and required software installed.
OCI also needs a server instance, firewall/VCN ingress, and administrator
setup. The project files do not create a cloud account or server. The current
OCI services are already deployed; a new server administrator should follow
`docs/OCI_VISUALIZATION_DEPLOYMENT.md` in the cloud package.

The Orin bundle is written for Jetson hardware and its NVIDIA camera encoder.
Another computer can act as the publisher only if its software sends the same
authenticated SRT video streams and version-1 visualization WebSocket data;
the Jetson ZIP itself is not a generic PC camera application.

The original Orin ZIP also contains Git metadata and a Python virtual
environment. The clean Orin ZIP inside `VISUALIZATION_SETUP_PACKAGE.zip`
omits those machine-specific files. Do not copy a virtual environment between
computers. The older `operator_side/visualization.zip` snapshot is not the
recommended upload; use the current operator package in the setup bundle.

## Server setup and ports

The cloud package runs two independent visualization services:

- **MediaMTX:** SRT video relay on UDP 8890. Stream names are `front`,
  `left`, `right`, and `cabin`.
- **Telemetry relay:** authenticated WebSocket on TCP 8767. It forwards the
  latest GNSS/visualization message to subscribers.

For a new server, an administrator must install the pinned MediaMTX release,
install the telemetry Python environment, install/enable the two systemd
units, and configure both the server firewall and cloud-network ingress for
UDP 8890 and TCP 8767. The existing UDP 4210 control service is separate and
must not be changed for visualization. The cloud deployment document contains
the installed paths, service names, validation commands, and rollback notes.

To unpack the cloud source archive on an Ubuntu OCI VM, copy
`VISUALIZATION_SETUP_PACKAGE.zip` to the VM, unpack it, then run:

```bash
unzip VISUALIZATION_SETUP_PACKAGE.zip -d ~/visualization_setup_package
unzip ~/visualization_setup_package/oci/teleop_visualization_cloud.zip -d ~
cd ~/teleop_visualization_cloud
less docs/OCI_VISUALIZATION_DEPLOYMENT.md
```

The archive provides the service source and templates; it does not install the
VM, create cloud ingress rules, or place secrets. Those steps require the OCI
administrator account and the protected values listed below.

The currently deployed server address is `147.224.145.24`. A different server
needs its own public IP or DNS name, and that address must be entered in both
client configuration files below.

## Credentials: values are intentionally not in the uploads

**No real token, password, SRT passphrase, cloud credential, or SSH key is
included in these source packages or this guide.** A new deployment must
create its own values. Do not send them in chat, add them to Git, or include
them in the upload bundle.

The OCI administrator creates one protected server file:

```text
/etc/teleop-visualization/secrets/visualization.env
owner: root
permissions: 0600
```

It needs these secret names:

- `MEDIA_PUBLISHER_USERNAME` and `MEDIA_PUBLISHER_PASSWORD`
- `MEDIA_READER_USERNAME` and `MEDIA_READER_PASSWORD`
- `FRONT_SRT_PUBLISH_PASSPHRASE` and `FRONT_SRT_READ_PASSPHRASE`
- `LEFT_SRT_PUBLISH_PASSPHRASE` and `LEFT_SRT_READ_PASSPHRASE`
- `RIGHT_SRT_PUBLISH_PASSPHRASE` and `RIGHT_SRT_READ_PASSPHRASE`
- `CABIN_SRT_PUBLISH_PASSPHRASE` and `CABIN_SRT_READ_PASSPHRASE`
- `TELEMETRY_PUBLISHER_TOKEN` and `TELEMETRY_SUBSCRIBER_TOKEN`

The server file also needs non-secret listener settings:
`TELEMETRY_HOST=0.0.0.0` and `TELEMETRY_PORT=8767`. The server template
documents its exact required variables. Use different strong values for
publisher and reader passwords, each camera's publish/read passphrases, and
publisher/subscriber tokens. Telemetry tokens must be at least 32 characters;
SRT passphrases must be 10–79 characters. Long random alphanumeric values are
easiest to enter consistently. The deployment uses SRT encryption with
`pbkeylen=32`.

The server file uses `NAME=value` lines. This is a template showing names only;
replace every `<...>` item with a newly generated secret before starting the
services:

```text
TELEMETRY_HOST=0.0.0.0
TELEMETRY_PORT=8767
MEDIA_PUBLISHER_USERNAME=<publisher-account-name>
MEDIA_PUBLISHER_PASSWORD=<new-random-password>
MEDIA_READER_USERNAME=<reader-account-name>
MEDIA_READER_PASSWORD=<different-random-password>
FRONT_SRT_PUBLISH_PASSPHRASE=<front-publish-passphrase>
FRONT_SRT_READ_PASSPHRASE=<front-read-passphrase>
LEFT_SRT_PUBLISH_PASSPHRASE=<left-publish-passphrase>
LEFT_SRT_READ_PASSPHRASE=<left-read-passphrase>
RIGHT_SRT_PUBLISH_PASSPHRASE=<right-publish-passphrase>
RIGHT_SRT_READ_PASSPHRASE=<right-read-passphrase>
CABIN_SRT_PUBLISH_PASSPHRASE=<cabin-publish-passphrase>
CABIN_SRT_READ_PASSPHRASE=<cabin-read-passphrase>
TELEMETRY_PUBLISHER_TOKEN=<new-publisher-token-at-least-32-characters>
TELEMETRY_SUBSCRIBER_TOKEN=<different-subscriber-token-at-least-32-characters>
```

These are placeholders, not working values. Optional TLS certificate settings
are not needed for the currently deployed `ws://` bench service.

The Orin receives only the publisher subset in:

```text
/home/mila/.config/teleop_visualization/oci_visualization.env
permissions: 0600
```

It needs `OCI_VISUALIZATION_HOST`, `SRT_PORT`, `TELEMETRY_PORT`,
`MEDIA_PUBLISHER_USERNAME`, `MEDIA_PUBLISHER_PASSWORD`, the four
`*_SRT_PUBLISH_PASSPHRASE` values, and `TELEMETRY_PUBLISHER_TOKEN`.

The operator laptop receives only the reader/subscriber subset in:

```text
~/.config/teleop_visualization/oci_visualization.env
owner: current user
permissions: 0600
```

It needs `OCI_VISUALIZATION_HOST`, `SRT_PORT`, `TELEMETRY_PORT`,
`MEDIA_READER_USERNAME`, `MEDIA_READER_PASSWORD`, the four
`*_SRT_READ_PASSPHRASE` values, and `TELEMETRY_SUBSCRIBER_TOKEN`. The GUI
checks this file before connecting. The Orin must never receive reader
credentials; the operator must never receive publisher credentials.

For the current server, the non-secret port values are `SRT_PORT=8890` and
`TELEMETRY_PORT=8767`. Create each client file locally using a private editor
or a secure configuration process, then set mode 0600. Never paste secret
values into terminal commands, screenshots, logs, or this guide. If an
administrator does not have the account values, create new values on the
server and update both client files securely; do not guess or reuse old ones.

The current telemetry endpoint is token-authenticated `ws://` because no
trusted TLS certificate is configured. A new public deployment should add
trusted TLS/WSS and restrict ingress when its network setup supports it.

## Before starting the two-camera run

You need:

- The Orin project extracted to `/home/mila/teleop_visualization_jetson`.
  The provided archive is `teleop_visualization_jetson.zip`.
- ROS 2 Jazzy and the installed Septentrio sensor workspace on the Orin.
- The Orin publisher credentials already installed in its private local
  configuration. See “Credentials” above if setting up a new deployment.
- The operator source extracted to a folder such as
  `~/teleop_visualization_operator` (or the existing project checkout).
- The operator's `teleop_viz` Conda environment and private reader credentials
  installed at `~/.config/teleop_visualization/oci_visualization.env`.
- Both computers connected to the Internet. They can be on different Wi-Fi
  networks.

If using the package, extract the Orin source archive with:

```bash
unzip ~/visualization_setup_package/orin/teleop_visualization_jetson.zip -d /home/mila
```

This creates `/home/mila/teleop_visualization_jetson`. A Python environment
inside an older archive may contain paths from the machine where it was
created; use the Orin setup notes in `docs/DEVELOPMENT_ENVIRONMENT.md` if its
Python environment does not start.

## Start the two-camera display

Start the GNSS driver first. Keep it running while the visualization is in use.
On the Orin, open a terminal and run:

```bash
source /opt/ros/jazzy/setup.bash
source /home/mila/sensors_ws/install/setup.bash
ros2 launch mila_septentrio_launch septentrio.launch.py
```

Open a second Orin terminal and start FRONT, CABIN, and GNSS publishing:

```bash
cd /home/mila/teleop_visualization_jetson
./scripts/run_two_camera_visualization.sh
```

This mode sends two 640×480 video feeds at 10 frames per second and GNSS
telemetry at about 5 updates per second. It is the recommended starting mode
for a limited or variable Internet connection. The launcher checks for
conflicting publishers and refuses to start duplicates.

On the operator laptop, open a terminal, go to the project root, and activate
the visualization environment:

```bash
cd /home/labid/mila/teleoperations_students/2_Teleoperation_Lili_UDP/Teleoperation_Lili_UDP_v2
conda activate teleop_viz
```

For a separately extracted operator package, use its folder instead:

```bash
mkdir -p ~/teleop_visualization_operator
unzip ~/visualization_setup_package/operator/teleop_visualization_operator.zip \
  -d ~/teleop_visualization_operator
cd ~/teleop_visualization_operator
conda activate teleop_viz
```

Start the GUI with the optional button guide:

```bash
DBUS_SYSTEM_BUS_ADDRESS=unix:path=/run/dbus/system_bus_socket \
python -m visualization.gui.main --two-camera-wan --maximized --button
```

To run without the button guide, use:

```bash
DBUS_SYSTEM_BUS_ADDRESS=unix:path=/run/dbus/system_bus_socket \
python -m visualization.gui.main --two-camera-wan --maximized
```

Choose one command. `--button` displays a local picture beside the speedometer;
it does not read a controller or send commands.

## Stop the display

Stop each foreground program with **Ctrl+C** in its own terminal:

1. Stop the GUI on the operator laptop.
2. Stop `run_two_camera_visualization.sh` on the Orin. Its cleanup handler
   stops the two video publishers and the telemetry publisher.
3. Stop the GNSS launch on the Orin.

Do not start another Orin visualization mode while these publishers are still
running. The telemetry relay allows one active publisher.

## First-time environment setup

If `teleop_viz` is not already installed on the operator laptop, create it
from the project root:

```bash
conda env create -f visualization/environment.yml
conda activate teleop_viz
```

The operator needs an FFmpeg build with SRT support. The GUI checks this when
it starts. If it reports that no SRT-capable FFmpeg is available, try the
system FFmpeg explicitly:

```bash
DBUS_SYSTEM_BUS_ADDRESS=unix:path=/run/dbus/system_bus_socket \
python -m visualization.gui.main --two-camera-wan --maximized --button \
  --ffmpeg /usr/bin/ffmpeg
```

On the Orin, the supplied project scripts activate `.venv` and source ROS 2
Jazzy automatically. They depend on the Orin's NVIDIA GStreamer encoder and
camera drivers, which are installed on the Orin, not the operator laptop.

## Offline GUI demonstration

To see the two-camera layout without the Orin or OCI streams, run this on the
operator laptop from the project root:

```bash
conda activate teleop_viz
python -m visualization.gui.main --two-camera-demo --maximized
```

Add `--button` to this command to show the local button guide. The demo uses
synthetic cameras and GNSS; its displayed location and speed are not real.

## Common problems

| What you see | What to check |
|---|---|
| FRONT or CABIN says CONNECTING / WAITING FOR STREAM | Confirm the Orin two-camera script is running and connected to the Internet. Check its terminal for camera or publisher errors. The GUI retries streams automatically. |
| One camera works, the other does not | Check that both expected cameras are connected and that `config/cameras_two_camera.yaml` still matches their USB paths. USB device numbers can change after unplugging or rebooting. |
| Video works but position says NO DATA | Confirm the Septentrio launch is running and was started after sourcing both ROS setup files. Allow the receiver time to get a GNSS fix. Video and GNSS are separate streams, so one can work while the other is unavailable. |
| Neither video nor GNSS arrives | Check Internet connectivity on both computers and confirm the OCI visualization services are available. Visualization uses UDP 8890 for video and TCP 8767 for telemetry. |
| The GUI says no SRT-capable FFmpeg | Start it with `--ffmpeg /usr/bin/ffmpeg` as shown above. Some Conda FFmpeg builds do not include SRT support. |
| Map is blank but coordinates update | Map tiles come directly from the operator laptop's Internet connection. Video and numeric GNSS can continue when the map provider is unavailable. |
| Orin launcher refuses to start | Another camera or telemetry publisher may already be running. Stop the previous mode with Ctrl+C in its terminal before starting this one. Do not launch a second telemetry publisher. |
| Telemetry stops after Wi-Fi changes | The publisher has TCP keepalive and reconnect handling for this case. If it does not recover, stop and restart the Orin two-camera launcher after the network is stable. |
| MediaMTX reports “too many reordered frames” | The validated H.264 encoder setting `poc-type=2` addresses the observed frame-order issue. Keep the supplied video configuration; do not change encoder or SRT settings as a first troubleshooting step. |

If OCI services need an administrator check, the service names are
`mediamtx` and `teleop-telemetry`. Their status can be checked on OCI with:

```bash
sudo systemctl status mediamtx teleop-telemetry --no-pager
```

Do not paste credentials, tokens, or complete authenticated SRT addresses into
terminal screenshots, messages, or logs. The current telemetry connection
uses token-authenticated `ws://`; it is a visualization bench service and is
not a control channel.

## Optional modes

- **One camera:** Orin `./scripts/run_minimal_visualization.sh`; operator
  `python -m visualization.gui.main --minimal-wan --maximized`.
- **Four cameras:** the Orin has separate per-camera publisher scripts and a
  full telemetry mode. The operator GUI uses
  `python -m visualization.gui.main --wan --maximized`. Confirm all four
  camera USB mappings before choosing this mode.

For architecture and implementation detail, see the Orin archive's
`docs/WAN_PUBLISHER.md`, the operator's `visualization/README.md`, and the
cloud project's `docs/OCI_VISUALIZATION_DEPLOYMENT.md`.

# Isolated visualization foundation

This subsystem acquires and publishes display-only camera, GPS, and onboard-computer health data. It is an independent process and has no dependency on the teleoperation control plane. Stopping this process, disconnecting a receiver, or losing a provider cannot stop or alter control command transmission.

## Environment

Create the dedicated environment without changing `g29_mqtt`:

```bash
conda env create -f visualization/environment.yml
conda activate teleop_viz
```

## Local diagnostic run

From the repository root, start the mock onboard agent:

```bash
python -m visualization.onboard.main \
  --config visualization/config/visualization.example.yaml
```

In another terminal, start the engineering receiver:

```bash
conda activate teleop_viz
python -m visualization.receiver.diagnostic_receiver
```

Add `--preview` to decode and show frames in an OpenCV window. The default receiver is headless and prints rates, sequences, dropped-frame count, freshness, and health once per second. `Ctrl+C` closes providers, tasks, and sockets.

The reproducible sustained demonstration is:

```bash
python -m visualization.run_mock_demo --duration 120
```

## Local transport

Both diagnostic services bind only to `127.0.0.1` by default.

- Telemetry uses newline-delimited, versioned JSON over TCP on port 8765.
- Video uses TCP port 8766. Each record contains a four-byte big-endian metadata length, UTF-8 JSON frame metadata, a four-byte big-endian JPEG length, and JPEG bytes.

Pixels are never embedded in telemetry JSON. This frame socket is only a Level 3A localhost diagnostic mechanism. It is not the selected WAN video transport.

## Providers and failure behavior

`CameraProvider`, `GPSProvider`, and `HealthProvider` are independent contracts. The mock camera produces an annotated moving pattern. The mock GPS follows a deterministic path from a configurable synthetic origin. `UsbCameraProvider` is the optional OpenCV adapter for an index or device path. No physical GPS protocol is assumed yet.

Video and telemetry run on separate acquisition threads and separate transport threads. Each path has a bounded queue. The video queue discards its oldest frame when full so the most recent image wins. Provider and receiver failures stay within the affected visualization path.

## Tests

```bash
python -m pytest -q visualization/tests
```

The isolation tests reject control-module imports, datagram sockets, and the control port in visualization runtime code.

## Four-camera operator console

The Level 3B1 console runs completely from mock sources when vehicle-side visualization hardware is unavailable:

```bash
cd /home/labid/mila/teleoperations_students/2_Teleoperation_Lili_UDP/Teleoperation_Lili_UDP_v2
conda activate teleop_viz
python -m visualization.gui.main --demo
```

The normal view prioritizes FRONT, with LEFT, RIGHT, and CABIN views beneath it. Double-click a camera or use its `MAX` button to focus it. Keyboard shortcuts are `1` FRONT, `2` LEFT, `3` RIGHT, `4` CABIN, and `Esc` to restore the grid. Press `F12` or the header capture button to save a screenshot under the ignored `visualization/output/screenshots/` directory.

The GUI consumes `VideoSource`, `TelemetrySource`, and `OperatorStateSource` interfaces. It does not depend on the Level 3A localhost ports or any prospective WAN technology. Acquisition runs on worker threads; Qt's GUI thread receives one latest-value slot per camera and never performs acquisition or decoding.

## Real WAN operator console

```bash
cd /home/labid/mila/teleoperations_students/2_Teleoperation_Lili_UDP/Teleoperation_Lili_UDP_v2
conda activate teleop_viz
python -m visualization.gui.main --wan
```

WAN mode reads the existing private `~/.config/teleop_visualization/oci_visualization.env` (current-user owned, mode 0600). Use `--secrets-file /path/to/private/reader.env` to select another handoff file. It needs reader/subscriber variables only; no publisher credentials are required. Never commit or display that file. The dependency definition adds `websockets=15.0.1` only to `teleop_viz`. An installed `ffmpeg` with SRT, H.264 decoding, and BMP/image2pipe support must be on PATH; the tested executable is `/usr/bin/ffmpeg` 4.4.2.

The GUI checks installed decoder protocol support rather than assuming the first `ffmpeg` on PATH supports SRT. On this laptop, activating Conda selects its FFmpeg 9.0.1, which lacks SRT; WAN mode now skips it and finds `/usr/bin/ffmpeg` 4.4.2. No package replacement is required. To select an installed decoder explicitly, use `python -m visualization.gui.main --wan --ffmpeg /usr/bin/ffmpeg`. An explicitly selected decoder without SRT is rejected at startup.

Each camera has an independent decoder and retry loop for its logical OCI path: `front`, `left`, `right`, `cabin`. Missing streams show CONNECTING or WAITING FOR STREAM and attach automatically when available. Stale images are cleared rather than presented as live. The same maximize/restore shortcuts and screenshot button work in both modes.

Real mode displays GNSS position/speed/fix, optional heading, remote camera health, and onboard health received from the authenticated telemetry subscriber. Missing measurements show `--`. A new subscriber waits for telemetry progress before declaring cached data live. The operator gauges/buttons are hidden in WAN mode because no real read-only operator-state mirror is connected; control-link indicators remain `--`. Mock mode retains the complete animated demonstration.

Network acquisition and decoding run outside the Qt GUI thread. Each camera and telemetry channel has a single latest-value delivery slot. Frame age in a WAN camera tile means **time since local decoding**, not capture-to-display latency. Camera sequence numbers count local decoded frames; GUI drops are local replacements, not measured WAN packet loss. No RTT or one-way latency is inferred.

Validation/performance output can be collected without video captures:

```bash
python -m visualization.gui.main --wan --duration 180 --metrics-output /tmp/gui-wan-metrics.json
```

FFmpeg input credentials are never printed or retained in stderr logs. Its authenticated input URI is necessarily present in the child process arguments and can be inspected by another process with appropriate OS permissions. The existing telemetry service uses token-authenticated plain WebSocket; trusted TLS remains a later infrastructure hardening task. WAN operation does not modify cloud services or the independent control plane.

## Cabin and GNSS premium console

The FRONT + CABIN view adds equal-priority side-by-side cameras above the same
GNSS speedometer, preserving the approved map and GNSS panels:

```bash
conda activate teleop_viz
python -m visualization.gui.main --two-camera-wan --maximized
# Add the replaceable G29 button-region guide beside the speedometer:
python -m visualization.gui.main --two-camera-wan --maximized --button
# Independent mock cameras and synthetic GNSS, without remote hardware:
python -m visualization.gui.main --two-camera-demo --maximized
```

This view instantiates only the `front` and `cabin` readers. Both reuse the
existing independent reconnect and latest-frame behavior. MAX/double-click
focuses either camera; Esc restores both. The minimum two-camera window is
1360×860 to retain readable labels and approved badge sizes. The existing
one-camera and full four-camera modes remain available.

The optional `--button` flag divides only the ground-speed content row: the
speedometer remains on the left and the aspect-fitted `button_region.png` from
the repository root appears on the right. Replacing that file changes the
guide on the next launch. A missing or unreadable image shows an unavailable
placeholder instead of preventing the console from opening. Camera, GNSS, and
map composition are unchanged, and omitting `--button` preserves the previous
ground-speed layout.

The focused console preserves the full `--wan` application. It requests only
CABIN and GNSS, with no operator-control or system-health panels:

```bash
conda activate teleop_viz
python -m visualization.gui.main --minimal-wan
```

For an entirely offline demonstration with clearly identified synthetic data:

```bash
python -m visualization.gui.main --minimal-demo
```

Use `--maximized` for a maximized initial window. `F11` toggles fullscreen;
`MAX` or double-clicking CABIN focuses the camera; `Esc` restores the console.
`F12` saves a screenshot to the ignored screenshots directory.

The video viewport follows its 4:3 source aspect ratio. Coordinates, a GNSS
speedometer, compass/course, satellites, accuracy, fix, and age fill the two
columns. Invalid or stale measurements are identified; missing speed is not
represented as zero. The compass uses GNSS course or sufficient position
displacement, with no IMU dependency.

Navigation uses bundled MapLibre GL JS and Qt WebEngine. Real mode loads the
OpenFreeMap dark basemap directly from the operator computer, with a triangular
vehicle marker, smooth follow, recenter, zoom, and perspective toggle. Provider
attribution remains visible. No credentials or telemetry payloads enter the
web page: only coordinates, course, and stale state. Demo mode uses fictional
local geometry and requires no map Internet access. A map failure leaves
numeric GNSS and video operational.

The environment definition includes PySide6 and Qt WebEngine 6.11.2. For an
existing environment missing WebEngine, install it in `teleop_viz` only:

```bash
conda install -n teleop_viz -c conda-forge --freeze-installed qt6-webengine=6.11.2
```

See [the C4 implementation and validation record](../docs/LEVEL3C1C4_PREMIUM_CONSOLE.md)
for geometry, test results, limitations, and control-isolation evidence.

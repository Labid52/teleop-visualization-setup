# OCI visualization deployment

## Scope and separation

This deployment is a public rendezvous point for visualization data only. The
existing G29/ESP32 control relay remains an independent systemd service on UDP
4210. The visualization services do not import control code, share a config,
or open the control port.

## Components and ports

| Component | Service | Listener | Purpose |
|---|---|---|---|
| MediaMTX 1.21.0 | `mediamtx.service` | UDP 8890 | SRT media relay |
| Telemetry relay | `teleop-telemetry.service` | TCP 8767 | Visualization WebSocket relay |
| Existing control relay | `teleoperation-relay.service` | UDP 4210 | Protected control plane |

MediaMTX is installed at `/opt/teleop-visualization/mediamtx/mediamtx` and its
rendered configuration is `/etc/teleop-visualization/mediamtx.yml`. The
telemetry service and virtual environment are under
`/opt/teleop-visualization/telemetry/`.

The root-owned, mode-0600 secret source is
`/etc/teleop-visualization/secrets/visualization.env`. It is excluded from this
repository. A future Jetson/operator handoff copy is stored outside Git on the
administrator workstation with mode 0600.

## Video architecture

The SRT paths are:

- `front`
- `left`
- `right`
- `cabin`

Publisher and reader use separate internal MediaMTX accounts. Account
permissions restrict publishing and reading to exactly these paths. Each path
also has separate publish and read SRT encryption passphrases using a 256-bit
SRT key length (`pbkeylen=32`). RTSP, RTMP, HLS, WebRTC, MoQ, API, metrics,
pprof, and playback listeners are disabled.

## Telemetry architecture

Clients connect with WebSocket and send a first-message authentication object
with either the `publisher` or `subscriber` role and the corresponding token.
Only one publisher is allowed. Subscribers receive schema-version-1
`vehicle_visualization` JSON messages. A queue of one latest state per
subscriber prevents a slow subscriber from blocking the publisher. History is
not persisted.

The initial bench endpoint is plain `ws://147.224.145.24:8767`, protected by
strong role-specific tokens. No trusted domain or TLS certificate is currently
available. TLS can be enabled later by supplying both certificate environment
variables; production hardening should deploy a trusted certificate and WSS.
This channel must never carry vehicle control.

## Firewall

The OCI host firewall has independent narrow accept rules for UDP 8890 and TCP
8767, persisted with `netfilter-persistent`. The existing UDP 4210 rule is not
changed. The OCI VCN/security list also needs these two bench ingress rules:

- UDP destination port 8890 from `0.0.0.0/0`
- TCP destination port 8767 from `0.0.0.0/0`

The broad source is temporary for different networks with dynamic NAT and is
acceptable only with application authentication. Restrict ingress when stable
egress addresses or a VPN are available.

## Operations

```bash
sudo systemctl status mediamtx teleop-telemetry
sudo systemctl start mediamtx teleop-telemetry
sudo systemctl stop mediamtx teleop-telemetry
sudo journalctl -u mediamtx -f
sudo journalctl -u teleop-telemetry -f
sudo ss -lunp | grep ':8890'
sudo ss -ltnp | grep ':8767'
```

Do not paste complete SRT URLs or authentication messages into tickets or
logs; they contain credentials.

## Rollback

Rollback affects only visualization:

```bash
sudo systemctl disable --now mediamtx teleop-telemetry
sudo rm -f /etc/systemd/system/mediamtx.service
sudo rm -f /etc/systemd/system/teleop-telemetry.service
sudo systemctl daemon-reload
```

Then remove only the UDP 8890 and TCP 8767 host-firewall rules and save with
`netfilter-persistent`. Remove the corresponding two OCI ingress rules. Leave
`teleoperation-relay.service`, its files, and UDP 4210 untouched.

## Remaining hardening

Before production visualization use, add a trusted TLS certificate/domain for
WSS, restrict firewall sources or use a VPN, define credential rotation,
monitor resource use, and establish media bandwidth limits. The current phase
does not deploy Jetson publishing code or operator GUI integration.

## Deployment validation record

Validation was completed on 2026-09-15 against OCI public IPv4
`147.224.145.24`.

- VM: Ubuntu 22.04.5 LTS, Linux AMD64 (`x86_64`), Python 3.10.12.
- MediaMTX: official standalone release 1.21.0. The downloaded Linux AMD64
  archive matched its official SHA-256 value
  `e02e34c3337a35f20ac9e5aa31524566108964e6e37dbc46cf8292169f6c792b`.
- MediaMTX native configuration validation: passed.
- Cloud-project automated tests: 10 passed, 0 failed.
- Local OCI SRT test: anonymous publishing rejected; encrypted authenticated
  publisher-to-reader delivery passed.
- Local OCI telemetry test: unauthenticated client and second publisher
  rejected; authenticated publisher-to-subscriber delivery passed.
- External sender-laptop SRT test: encrypted authenticated publish/read passed
  through public UDP 8890 before and after reboot.
- External sender-laptop telemetry test: authenticated publish/subscribe passed
  and an invalid token was rejected through public TCP 8767 before and after
  reboot.
- OCI CLI was not configured locally or on the VM. The exact security-list
  objects could not be inspected, but effective public ingress for both ports
  was proven with the application-level tests. No console action remained.
- Host firewall accepts for UDP 8890 and TCP 8767 were inserted separately and
  persisted with `netfilter-persistent`; the existing UDP 4210 rule remained.
- Reboot persistence: `teleoperation-relay`, `mediamtx`, and
  `teleop-telemetry` returned enabled and active, and all three listeners
  returned after reboot.
- Protected control relay SHA-256 remained
  `5558aae64740725dc312c433529349d7a91b23601f58a7da5a58e4990b019d05`.

During installation, Ubuntu's package-maintenance tooling automatically
restarted services it considered affected, including the existing control
relay. The relay returned active immediately, and its unit, source hash,
listener, and firewall rule were unchanged. The later planned persistence
reboot also restarted all enabled services normally.

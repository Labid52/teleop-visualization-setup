# Media relay

MediaMTX is pinned to version 1.21.0 and installed as its official standalone
Linux AMD64 binary. The deployed configuration enables only SRT on UDP 8890.
RTSP, RTMP, HLS, WebRTC, MoQ, API, metrics, pprof, and playback listeners are
disabled.

The four configured paths are `front`, `left`, `right`, and `cabin`.
Publisher and reader accounts have separate credentials and are restricted to
their respective action on those paths. Every path also has independent SRT
publish and read passphrases.

The example YAML contains placeholders only. Render the deployed configuration
from a root-owned environment file:

```bash
python3 scripts/render_mediamtx_config.py \
  --template mediamtx/mediamtx.example.yml \
  --env-file /etc/teleop-visualization/secrets/visualization.env \
  --output /etc/teleop-visualization/mediamtx.yml \
  --group teleop-visualization
```

MediaMTX SRT clients authenticate through the SRT stream ID and use the SRT
passphrase as a separate URL parameter. Keep complete client URLs out of logs
because they contain credentials.

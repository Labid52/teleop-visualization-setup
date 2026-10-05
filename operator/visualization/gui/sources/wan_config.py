"""Reader-only credentials loaded from the existing out-of-repository handoff."""

from dataclasses import dataclass, field
import os
from pathlib import Path
import re
import shlex
import stat
from urllib.parse import quote

from visualization.gui.models.ui_state import CameraId

READER_VARIABLES = (
    "OCI_VISUALIZATION_HOST", "SRT_PORT", "TELEMETRY_PORT",
    "MEDIA_READER_USERNAME", "MEDIA_READER_PASSWORD",
    "FRONT_SRT_READ_PASSPHRASE", "LEFT_SRT_READ_PASSPHRASE",
    "RIGHT_SRT_READ_PASSPHRASE", "CABIN_SRT_READ_PASSPHRASE",
    "TELEMETRY_SUBSCRIBER_TOKEN",
)


@dataclass(frozen=True)
class WanCredentials:
    host: str
    srt_port: int = 8890
    telemetry_port: int = 8767
    username: str = field(default="", repr=False)
    password: str = field(default="", repr=False)
    passphrases: dict[CameraId, str] = field(default_factory=dict, repr=False)
    subscriber_token: str = field(default="", repr=False)

    def reader_uri(self, camera_id: CameraId) -> str:
        role = CameraId(camera_id)
        return (
            f"srt://{self.host}:{self.srt_port}?streamid=read:{role.value}:"
            f"{quote(self.username, safe='')}:{quote(self.password, safe='')}"
            f"&passphrase={quote(self.passphrases[role], safe='')}&pbkeylen=32"
        )

    @property
    def telemetry_uri(self) -> str:
        return f"ws://{self.host}:{self.telemetry_port}/"


def load_wan_credentials(path: str | Path) -> WanCredentials:
    path = Path(path).expanduser()
    info = path.stat()
    if not stat.S_ISREG(info.st_mode) or info.st_mode & 0o077 or info.st_uid != os.getuid():
        raise ValueError("WAN secret file must be owned by the current user and private (mode 0600)")
    values = {}
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[7:]
        key, sep, value = line.partition("=")
        if not sep or key not in READER_VARIABLES:
            continue
        try:
            parsed = shlex.split(value, comments=True)
        except ValueError:
            raise ValueError(f"invalid value syntax for WAN variable {key}") from None
        if len(parsed) != 1:
            raise ValueError(f"missing or invalid WAN variable {key}")
        values[key] = parsed[0]
    missing = [key for key in READER_VARIABLES if not values.get(key)]
    if missing:
        raise ValueError("missing reader variable names: " + ", ".join(missing))
    if not re.fullmatch(r"[A-Za-z0-9.-]+", values["OCI_VISUALIZATION_HOST"]):
        raise ValueError("WAN host must be an IPv4 address or DNS hostname")
    if values["SRT_PORT"] != "8890" or values["TELEMETRY_PORT"] != "8767":
        raise ValueError("WAN ports must match the accepted visualization handoff")
    return WanCredentials(
        host=values["OCI_VISUALIZATION_HOST"],
        username=values["MEDIA_READER_USERNAME"], password=values["MEDIA_READER_PASSWORD"],
        passphrases={role: values[f"{role.value.upper()}_SRT_READ_PASSPHRASE"] for role in CameraId},
        subscriber_token=values["TELEMETRY_SUBSCRIBER_TOKEN"],
    )

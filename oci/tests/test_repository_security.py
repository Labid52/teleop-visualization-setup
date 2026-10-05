from pathlib import Path
import unittest

from scripts.render_mediamtx_config import PLACEHOLDER, load_env, render


ROOT = Path(__file__).resolve().parents[1]


class RepositorySecurityTests(unittest.TestCase):
    def test_mediamtx_enables_only_srt(self):
        config = (ROOT / "mediamtx" / "mediamtx.example.yml").read_text()
        self.assertIn("srt: true", config)
        self.assertIn("srtAddress: :8890", config)
        for protocol in ("rtsp", "rtmp", "hls", "webrtc", "moq"):
            self.assertIn(f"{protocol}: false", config)
        for service in ("api", "metrics", "pprof", "playback"):
            self.assertIn(f"{service}: false", config)

    def test_exact_paths_and_separate_roles(self):
        config = (ROOT / "mediamtx" / "mediamtx.example.yml").read_text()
        for path in ("front", "left", "right", "cabin"):
            self.assertIn(f"  {path}:\n", config)
        self.assertIn("action: publish", config)
        self.assertIn("action: read", config)
        self.assertNotIn("all_others:", config)

    def test_renderer_requires_every_secret(self):
        template = "x={{ONE}} y={{TWO}}"
        with self.assertRaises(ValueError):
            render(template, {"ONE": "a"})
        self.assertEqual(render(template, {"ONE": "a", "TWO": "b"}), "x=a y=b")

    def test_runtime_files_do_not_reference_control_plane(self):
        runtime_paths = [
            ROOT / "telemetry" / "telemetry_relay.py",
            ROOT / "mediamtx" / "mediamtx.example.yml",
            ROOT / "systemd" / "mediamtx.service",
            ROOT / "systemd" / "teleop-telemetry.service",
        ]
        combined = "\n".join(path.read_text(encoding="utf-8") for path in runtime_paths)
        for forbidden in (
            "4210",
            "CMD;",
            "MANEUVER;",
            "BUTTON;",
            "relay_server.py",
            "teleoperation-relay.service",
        ):
            self.assertNotIn(forbidden, combined)

    def test_no_private_keys_or_secret_files_tracked(self):
        for path in ROOT.rglob("*"):
            if (
                not path.is_file()
                or ".git" in path.parts
                or "__pycache__" in path.parts
                or path.suffix not in {".py", ".md", ".yml", ".service", ".txt"}
            ):
                continue
            text = path.read_text(encoding="utf-8", errors="ignore")
            self.assertNotIn("BEGIN " + "RSA PRIVATE KEY", text, path)
            self.assertNotIn("BEGIN " + "OPENSSH PRIVATE KEY", text, path)


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

import ast
from pathlib import Path


ROOT = Path("visualization")
PROTECTED_MODULES = {"g29_to_server_v2", "relay_server", "maneuver_protocol", "vehicle_receiver_level2"}


def test_visualization_has_no_control_module_imports() -> None:
    violations: list[str] = []
    for path in ROOT.rglob("*.py"):
        if "tests" in path.parts:
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            names: list[str] = []
            if isinstance(node, ast.Import):
                names = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module:
                names = [node.module]
            for name in names:
                if name.split(".")[0] in PROTECTED_MODULES:
                    violations.append(f"{path}: {name}")
    assert violations == []


def test_visualization_runtime_has_no_datagram_socket_or_control_port() -> None:
    runtime = "\n".join(path.read_text(encoding="utf-8") for path in ROOT.rglob("*.py") if "tests" not in path.parts)
    forbidden_socket_token = "SOCK" + "_DGRAM"
    forbidden_control_port = "42" + "10"
    assert forbidden_socket_token not in runtime
    assert forbidden_control_port not in runtime


def test_visualization_runtime_generates_no_control_packet_families() -> None:
    runtime = "\n".join(path.read_text(encoding="utf-8") for path in ROOT.rglob("*.py") if "tests" not in path.parts)
    forbidden_packets = ("C" + "MD;", "MANEU" + "VER;", "BUT" + "TON;")
    assert all(packet not in runtime for packet in forbidden_packets)


def test_protected_control_files_are_outside_visualization_tree() -> None:
    names = {path.name for path in ROOT.rglob("*") if path.is_file()}
    assert "esp32_car.ino" not in names
    assert "g29_to_server_v2.py" not in names
    assert "relay_server.py" not in names
    assert "maneuver_protocol.py" not in names

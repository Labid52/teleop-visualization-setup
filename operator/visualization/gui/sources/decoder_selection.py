"""Choose an installed SRT reader rather than assuming every FFmpeg supports SRT."""

import os
import shutil
import subprocess


def select_srt_decoder(executable: str = "ffmpeg") -> str:
    candidates = []
    if executable == "ffmpeg":
        for directory in os.get_exec_path():
            candidate = shutil.which(executable, path=directory)
            if candidate:
                candidates.append(candidate)
        if os.path.isfile("/usr/bin/ffmpeg"):
            candidates.append("/usr/bin/ffmpeg")
    else:
        candidate = shutil.which(executable)
        if candidate:
            candidates.append(candidate)
    checked = set()
    for candidate in candidates:
        candidate = os.path.realpath(candidate)
        if candidate in checked:
            continue
        checked.add(candidate)
        try:
            result = subprocess.run([candidate, "-hide_banner", "-protocols"],
                stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                text=True, errors="replace", timeout=3)
            if result.returncode == 0 and "srt" in result.stdout.split():
                return candidate
        except (OSError, subprocess.SubprocessError):
            continue
    raise ValueError("No installed FFmpeg supports SRT; select an SRT-capable decoder")

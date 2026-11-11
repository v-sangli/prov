"""Facts about the machine a run executes on."""

import platform
import shutil
import subprocess

from prov.runs.schema import Env


def env() -> Env:
    gpus = []
    if shutil.which("nvidia-smi"):
        p = subprocess.run(["nvidia-smi", "--query-gpu=name", "--format=csv,noheader"],
                           capture_output=True, text=True)
        gpus = [g.strip() for g in p.stdout.splitlines() if g.strip()] if p.returncode == 0 else []
    return Env(python=platform.python_version(), platform=platform.platform(), gpu=gpus)

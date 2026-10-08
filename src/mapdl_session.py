"""Launch isolated MAPDL runs; use PYMAPDL_MAPDL_EXEC or PyMAPDL discovery."""
import hashlib
import os
import re
import tempfile
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
os.environ.setdefault("MPLCONFIGDIR", str(Path(tempfile.gettempdir()) / "lathe_cutter_mpl"))


def session_options(label):
    if not isinstance(label, str) or not re.fullmatch(r"[A-Za-z][A-Za-z0-9_-]{0,119}", label):
        raise ValueError("Case label must start with a letter; use up to 120 ASCII letters, digits, _ or -")
    nproc = int(os.environ.get("PYMAPDL_NPROC", "2"))
    if nproc < 1:
        raise ValueError("PYMAPDL_NPROC must be a positive integer")
    jobname = label if len(label) <= 32 else label[:23] + "_" + hashlib.sha256(label.encode()).hexdigest()[:8]
    options = dict(jobname=jobname, nproc=nproc, additional_switches="-smp", timeout=120,
                   cleanup_on_exit=True, remove_temp_dir_on_exit=False)
    executable = os.environ.get("PYMAPDL_MAPDL_EXEC", "").strip()
    if executable:
        path = Path(executable).expanduser()
        if not path.is_file():
            raise FileNotFoundError(f"MAPDL executable does not exist: {path}")
        options["exec_file"] = str(path.resolve())
    return options


def launch_session(label):
    options = session_options(label)
    from ansys.mapdl.core import launch_mapdl
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    run_dir = ROOT / "results" / "runs" / f"{label}_{stamp}"
    run_dir.mkdir(parents=True)
    print(f"Run directory: {run_dir}", flush=True)
    mapdl = launch_mapdl(
        **options, run_location=str(run_dir),
        log_apdl=str(run_dir / "commands.apdl"),
        mapdl_output=str(run_dir / "mapdl_stdout.txt"),
    )
    return mapdl, run_dir

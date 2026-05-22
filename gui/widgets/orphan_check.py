"""Detect and offer to kill orphaned FreeSurfer / AFNI processes left over
from a previous GUI session that didn't shut down cleanly.

Trigger this at app startup *and* just before each Start click.  Killing
orphans before launching a new run prevents the worst-case bug we hit
where two ``recon-all`` processes ended up fighting over the same subject
for 8+ hours.
"""
import os
import subprocess
import signal
import time as _time
from typing import List, Dict
from PyQt6.QtWidgets import QMessageBox

# Substring → display label.  Order matters — most-specific first so the
# *Type* column is informative.
_PATTERNS = [
    ("recon-all",          "recon-all (parent)"),
    ("mri_ca_register",    "mri_ca_register"),
    ("mri_em_register",    "mri_em_register"),
    ("mri_synthstrip",     "mri_synthstrip"),
    ("mri_normalize",      "mri_normalize"),
    ("@afni_refacer_run",  "@afni_refacer_run"),
    ("afni_proc.py",       "afni_proc.py"),
    ("3dDeconvolve",       "3dDeconvolve"),
]


def find_pipeline_processes(current_user_only: bool = True) -> List[Dict]:
    """Scan ``ps`` for processes that look like pipeline children.

    Returns a list of dicts with keys: pid, etime, type, subject, cmd.
    Returns empty list if ``ps`` isn't usable.
    """
    try:
        ps_args = ["ps", "axo", "pid=,user=,etime=,command="]
        out = subprocess.run(ps_args, capture_output=True, text=True, timeout=5).stdout
    except (subprocess.SubprocessError, FileNotFoundError):
        return []

    me = os.environ.get("USER", "")
    found = []
    for line in out.splitlines():
        line = line.strip()
        if not line:
            continue
        parts = line.split(None, 3)
        if len(parts) < 4:
            continue
        pid_s, user, etime, cmd = parts
        if current_user_only and me and user != me:
            continue
        try:
            pid = int(pid_s)
        except ValueError:
            continue
        if pid == os.getpid():
            continue  # don't match ourselves

        # Match a known pattern (needle → label, in declared order)
        ptype = None
        for needle, label in _PATTERNS:
            if needle in cmd:
                ptype = label
                break
        if ptype is None:
            continue

        # Try to extract subject id from `-s <subj>` or `-subj_id <subj>`
        subj = ""
        toks = cmd.split()
        for i, t in enumerate(toks):
            if t in ("-s", "-subj_id") and i + 1 < len(toks):
                subj = toks[i + 1]
                break

        found.append({
            "pid": pid,
            "etime": etime,
            "type": ptype,
            "subject": subj,
            "cmd": cmd[:140],   # trim long command lines for display
        })
    return found


def kill_processes(pids: List[int]) -> int:
    """Best-effort: kill each PID's process group (TERM, then KILL).

    Returns the count successfully signaled.
    """
    killed = 0
    for pid in pids:
        try:
            if os.name == "posix":
                try:
                    pgid = os.getpgid(pid)
                    os.killpg(pgid, signal.SIGTERM)
                except (ProcessLookupError, PermissionError, OSError):
                    os.kill(pid, signal.SIGTERM)
            else:
                os.kill(pid, signal.SIGTERM)
            killed += 1
        except (ProcessLookupError, PermissionError, OSError):
            continue

    # Brief grace period, then SIGKILL anyone still alive
    _time.sleep(1.5)
    for pid in pids:
        try:
            os.kill(pid, 0)            # still alive?
            try:
                pgid = os.getpgid(pid)
                os.killpg(pgid, signal.SIGKILL)
            except (ProcessLookupError, PermissionError, OSError):
                os.kill(pid, signal.SIGKILL)
        except (ProcessLookupError, PermissionError, OSError):
            continue
    return killed


def prompt_kill_orphans(parent, *, silent_when_none: bool = True) -> int:
    """Scan, and if orphans are found, show a dialog with Kill-All / Ignore.

    Returns the number of processes that were killed (0 if none / declined).
    """
    procs = find_pipeline_processes()
    if not procs:
        if not silent_when_none:
            QMessageBox.information(parent, "Orphan check",
                                    "✓ No orphaned FreeSurfer / AFNI processes found.")
        return 0

    # Build a tidy display
    lines = [f"{len(procs)} pipeline process(es) are already running on this machine:",
             ""]
    for p in procs:
        subj = f"[{p['subject']}]" if p['subject'] else ""
        lines.append(f"  PID {p['pid']:>6}  {p['etime']:>9}  {p['type']:<18} {subj}")
    lines.append("")
    lines.append("These may be left over from a previous run.  If you start a new run "
                 "for one of the same subjects, the two recon-all processes will fight "
                 "and slow each other down for hours.")

    dlg = QMessageBox(parent)
    dlg.setWindowTitle("Orphaned pipeline processes detected")
    dlg.setIcon(QMessageBox.Icon.Warning)
    dlg.setText("\n".join(lines))
    btn_kill = dlg.addButton("🛑 Kill all and continue", QMessageBox.ButtonRole.DestructiveRole)
    btn_ignore = dlg.addButton("Ignore", QMessageBox.ButtonRole.RejectRole)
    dlg.setDefaultButton(btn_kill)
    dlg.exec()

    if dlg.clickedButton() is btn_kill:
        n = kill_processes([p["pid"] for p in procs])
        QMessageBox.information(parent, "Orphan check",
                                f"✓ Sent terminate to {n} process(es). "
                                "Wait a moment then re-Start your pipeline.")
        return n
    return 0

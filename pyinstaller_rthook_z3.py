import builtins
import os
import sys


def _candidate_dirs():
    base = getattr(sys, "_MEIPASS", None)
    if not base:
        return []
    return [
        os.path.join(base, "z3", "lib"),
        os.path.join(base, "z3"),
        base,
    ]


dirs = [path for path in _candidate_dirs() if os.path.isdir(path)]
if dirs:
    builtins.Z3_LIB_DIRS = dirs
    current = os.environ.get("Z3_LIBRARY_PATH", "")
    merged = os.pathsep.join(dirs + ([current] if current else []))
    os.environ["Z3_LIBRARY_PATH"] = merged

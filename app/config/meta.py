"""
Overview:
    Meta information for app package.
"""

import os
import sys
from pathlib import Path

#: Title of this project (should be `app`).
__TITLE__ = "pyqt5-demo"

#: Version of this project.
__VERSION__ = "0.0.3"

#: Short description of the project, will be included in ``setup.py``.
__DESCRIPTION__ = 'Demo Application of PyQt5.'

#: Author of this project.
__AUTHOR__ = "HansBug"

#: Email of the authors'.
__AUTHOR_EMAIL__ = "hansbug@buaa.edu.cn"


def resource_path(relative_path: str) -> str:
    """Return an absolute path that works in source and PyInstaller builds."""
    if hasattr(sys, "_MEIPASS"):
        base_path = Path(sys._MEIPASS)
    else:
        base_path = Path(__file__).resolve().parents[2]
    return str(base_path / relative_path)


PLANTUML_JAR_PATH = os.environ.get("PLANTUML_JAR_PATH") or resource_path("docs/plantuml.jar")

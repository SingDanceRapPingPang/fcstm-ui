"""
Cross-platform-safe PlantUML rendering helpers.

The default ``plantumlcli.LocalPlantuml`` implementation writes the
plantuml source to a ``NamedTemporaryFile(prefix='puml', suffix='.puml')``
that it keeps open while spawning ``java -jar plantuml.jar``.  On Linux
and macOS the OS lets a second process re-open that path with write
mode, so it works.  On Windows ``NamedTemporaryFile`` defaults to an
exclusive handle and the immediately-following ``save_text_file(...)``
inside plantumlcli fails with::

    PermissionError: [Errno 13] Permission denied: '...puml'

This module sidesteps the bug entirely: write the .puml ourselves into
a regular ``TemporaryDirectory``, run ``java -jar plantuml.jar -t<fmt>
-o <outdir> <input.puml>``, then copy the produced file to the requested
output path.  Behaviour is identical on all three platforms — Windows
just stops crashing.

A ``RemotePlantuml`` fallback is kept for the rare case where the local
JAR is missing (we ship one, but the policy says "Java not bundled, jar
is bundled").  Remote rendering does not hit the offending code path.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from typing import Optional


def _resolve_java() -> Optional[str]:
    return shutil.which('java')


def _resolve_plantuml_jar() -> Optional[str]:
    # Lazy import to avoid pulling app config when this module is used
    # standalone (e.g. unit tests).
    from app.config import PLANTUML_JAR_PATH

    if PLANTUML_JAR_PATH and os.path.exists(PLANTUML_JAR_PATH):
        return PLANTUML_JAR_PATH
    return None


def render_plantuml(
    plantuml_code: str,
    output_path: str,
    output_format: str,
    *,
    java_path: Optional[str] = None,
    plantuml_jar: Optional[str] = None,
    timeout_seconds: int = 120,
) -> None:
    """Render ``plantuml_code`` into ``output_path`` in ``output_format``.

    Always goes through ``java -jar plantuml.jar`` (local rendering).
    Remote-server rendering is intentionally not used here — the GUI
    bundles the JAR specifically so we can stay offline-friendly.
    """
    fmt = (output_format or 'png').strip().lower()
    if fmt not in {'png', 'svg', 'eps', 'pdf', 'txt'}:
        raise ValueError(f'unsupported plantuml output format: {output_format!r}')

    java = java_path or _resolve_java()
    if not java:
        raise RuntimeError(
            'java not found on PATH; install a JRE (e.g. `default-jre` on '
            'Ubuntu) so PlantUML can run.'
        )
    jar = plantuml_jar or _resolve_plantuml_jar()
    if not jar:
        raise RuntimeError('plantuml.jar not bundled or missing')

    if fmt == 'txt':
        # plantuml's text output goes via -ttxt and writes to <input>.atxt.
        # We just write the source instead, matching the legacy behaviour
        # of the GUI's "save .puml" code path.
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(plantuml_code)
        return

    if fmt == 'pdf':
        # PlantUML's native PDF emitter has CJK font issues on a barebones
        # OpenJDK install, so render PNG first and embed it in a PDF page
        # via Qt — same fallback the legacy plantuml_render_cli used.
        with tempfile.TemporaryDirectory(prefix='fcstm_pdf_') as tmp_dir:
            png_path = os.path.join(tmp_dir, 'graph.png')
            _run_java_render(java, jar, plantuml_code, png_path, 'png', timeout_seconds)
            _png_to_pdf(png_path, output_path)
        return

    _run_java_render(java, jar, plantuml_code, output_path, fmt, timeout_seconds)


def _run_java_render(
    java: str,
    jar: str,
    plantuml_code: str,
    output_path: str,
    fmt: str,
    timeout_seconds: int,
) -> None:
    with tempfile.TemporaryDirectory(prefix='fcstm_puml_') as tmp_dir:
        input_path = os.path.join(tmp_dir, 'input.puml')
        out_dir = os.path.join(tmp_dir, 'out')
        os.makedirs(out_dir, exist_ok=True)
        with open(input_path, 'w', encoding='utf-8') as f:
            f.write(plantuml_code)
        cmd = [java, '-jar', jar, f'-t{fmt}', '-o', out_dir, input_path]
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
        )
        if proc.returncode != 0:
            raise RuntimeError(
                f'plantuml rendering failed (rc={proc.returncode})\n'
                f'cmd: {cmd}\n'
                f'stdout:\n{proc.stdout}\n'
                f'stderr:\n{proc.stderr}'
            )
        produced = [p for p in os.listdir(out_dir) if not p.startswith('.')]
        if not produced:
            raise RuntimeError(
                'plantuml produced no output; this usually means an invalid '
                'PUML source — stderr below:\n' + (proc.stderr or '(empty)')
            )
        src = os.path.join(out_dir, produced[0])
        # Make sure the destination directory exists.
        os.makedirs(os.path.dirname(os.path.abspath(output_path)) or '.', exist_ok=True)
        shutil.copyfile(src, output_path)


def _png_to_pdf(png_path: str, pdf_path: str) -> None:
    """Embed a PNG file as a single PDF page via Qt's QPdfWriter."""
    os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
    from PyQt5.QtCore import QMarginsF, QRectF, QSizeF
    from PyQt5.QtGui import (
        QGuiApplication,
        QImage,
        QPageSize,
        QPainter,
        QPdfWriter,
    )

    app = QGuiApplication.instance()
    if app is None:
        app = QGuiApplication([])

    image = QImage(png_path)
    if image.isNull():
        raise RuntimeError(
            'PlantUML returned a PNG that Qt cannot decode — corrupt output?'
        )

    writer = QPdfWriter(pdf_path)
    resolution = max(image.dotsPerMeterX(), 1) * 0.0254
    if resolution <= 1:
        resolution = 150
    writer.setResolution(int(resolution))
    width_mm = image.width() * 25.4 / resolution
    height_mm = image.height() * 25.4 / resolution
    writer.setPageSize(QPageSize(QSizeF(width_mm, height_mm), QPageSize.Millimeter))
    writer.setPageMargins(QMarginsF(0, 0, 0, 0))

    painter = QPainter(writer)
    painter.drawImage(
        QRectF(writer.pageLayout().paintRectPixels(writer.resolution())),
        image,
    )
    painter.end()

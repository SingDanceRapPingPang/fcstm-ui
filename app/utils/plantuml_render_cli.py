import argparse
import os
import sys
import tempfile

from plantumlcli import LocalPlantuml, RemotePlantuml
from plantumlcli.models.base import PlantumlResourceType

from app.config import PLANTUML_JAR_PATH


FORMAT_TYPES = {
    "png": PlantumlResourceType.PNG,
    "svg": PlantumlResourceType.SVG,
    "pdf": PlantumlResourceType.PDF,
}


def _backend():
    if PLANTUML_JAR_PATH and os.path.exists(PLANTUML_JAR_PATH):
        return LocalPlantuml.autoload(plantuml=PLANTUML_JAR_PATH)
    return RemotePlantuml.autoload(
        host=os.environ.get("PLANTUML_HOST", "http://www.plantuml.com/plantuml")
    )


def _validate_output(path: str, output_format: str):
    with open(path, "rb") as f:
        head = f.read(256)

    if output_format == "pdf" and not head.startswith(b"%PDF"):
        raise RuntimeError("PlantUML backend did not return a valid PDF document.")
    if output_format == "png" and not head.startswith(b"\x89PNG"):
        raise RuntimeError("PlantUML backend did not return a valid PNG image.")
    if output_format == "svg" and b"<svg" not in head and b"<?xml" not in head:
        raise RuntimeError("PlantUML backend did not return a valid SVG document.")


def _png_to_pdf(png_path: str, pdf_path: str):
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PyQt5.QtCore import QMarginsF, QRectF
    from PyQt5.QtGui import QGuiApplication, QImage, QPageSize, QPainter, QPdfWriter
    from PyQt5.QtCore import QSizeF

    app = QGuiApplication.instance()
    if app is None:
        app = QGuiApplication([])

    image = QImage(png_path)
    if image.isNull():
        raise RuntimeError("PlantUML backend returned an invalid PNG document for PDF export.")

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
    painter.drawImage(QRectF(writer.pageLayout().paintRectPixels(writer.resolution())), image)
    painter.end()


def _dump_with_pdf_fallback(output_path: str, output_format: str, plantuml_code: str):
    backend = _backend()
    if output_format != "pdf":
        backend.dump(output_path, FORMAT_TYPES[output_format], plantuml_code)
        return

    # The remote PlantUML backend does not consistently support PDF directly,
    # and Qt's SVG-to-PDF path can render CJK glyphs as black blocks. Embed the
    # already-correct PNG rendering into a PDF page instead.
    with tempfile.TemporaryDirectory(prefix="fcstm_pdf_") as tmp_dir:
        png_path = os.path.join(tmp_dir, "graph.png")
        backend.dump(png_path, FORMAT_TYPES["png"], plantuml_code)
        _validate_output(png_path, "png")
        _png_to_pdf(png_path, output_path)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--format", required=True, choices=sorted(FORMAT_TYPES))
    args = parser.parse_args(argv)

    with open(args.input, "r", encoding="utf-8") as f:
        plantuml_code = f.read()

    output_format = args.format.lower()
    _dump_with_pdf_fallback(args.output, output_format, plantuml_code)
    _validate_output(args.output, output_format)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as err:
        print(str(err), file=sys.stderr)
        raise SystemExit(1)

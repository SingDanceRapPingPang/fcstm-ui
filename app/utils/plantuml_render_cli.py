"""
CLI subcommand that renders a .puml file into PNG / SVG / PDF.

Used by both source mode (``python -m app.utils.plantuml_render_cli``)
and frozen mode (``fcstm-ui --plantuml-render-cli``, see ``main.py``).

Rendering goes through ``app.utils.plantuml_safe_dump`` which calls
``java -jar plantuml.jar`` directly — this sidesteps the
``plantumlcli.LocalPlantuml`` ``NamedTemporaryFile`` bug that breaks
on Windows and keeps Linux / macOS behaviour identical.
"""

from __future__ import annotations

import argparse
import os
import sys

from app.utils.plantuml_safe_dump import render_plantuml


VALID_FORMATS = ('png', 'svg', 'pdf')


def _validate_output(path: str, output_format: str) -> None:
    with open(path, 'rb') as f:
        head = f.read(256)

    if output_format == 'pdf' and not head.startswith(b'%PDF'):
        raise RuntimeError('PlantUML backend did not return a valid PDF document.')
    if output_format == 'png' and not head.startswith(b'\x89PNG'):
        raise RuntimeError('PlantUML backend did not return a valid PNG image.')
    if output_format == 'svg' and b'<svg' not in head and b'<?xml' not in head:
        raise RuntimeError('PlantUML backend did not return a valid SVG document.')


def main(argv=None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--input', required=True)
    parser.add_argument('--output', required=True)
    parser.add_argument('--format', required=True, choices=sorted(VALID_FORMATS))
    args = parser.parse_args(argv)

    with open(args.input, 'r', encoding='utf-8') as f:
        plantuml_code = f.read()

    output_format = args.format.lower()
    render_plantuml(plantuml_code, args.output, output_format)
    _validate_output(args.output, output_format)
    return 0


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except Exception as err:
        print(str(err), file=sys.stderr)
        raise SystemExit(1)

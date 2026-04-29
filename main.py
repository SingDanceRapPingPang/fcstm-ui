"""
Entry point for the fcstm-ui application.

The frozen PyInstaller binary doubles as a CLI dispatcher: any subprocess
the GUI fires off (currently only the PlantUML renderer) re-invokes the
same executable with a leading flag identifying the sub-command.  This
avoids the classic frozen-app trap where ``sys.executable -m foo.bar``
silently re-launches the whole GUI because the bootloader does not
implement ``-m``.

Smoke-test mode is dispatched as early as possible — before any app
package import — so the smoke routine still runs when ``app/__init__.py``
or its eager imports raise.  The smoke test is the last line of defence;
it must always launch.
"""

from __future__ import annotations

import os
import sys


def _is_smoke_test_mode() -> bool:
    if os.environ.get('FCSTM_UI_SMOKE_TEST') == '1':
        return True
    return any(arg == '--smoke-test' for arg in sys.argv[1:])


def _is_plantuml_render_cli_mode() -> bool:
    return len(sys.argv) > 1 and sys.argv[1] == '--plantuml-render-cli'


def _run_smoke_test() -> int:
    import traceback
    try:
        from app.smoke import run_smoke_test
    except Exception:
        print('fcstm-ui smoke test: failed to import app.smoke', flush=True)
        traceback.print_exc()
        return 2
    try:
        return run_smoke_test()
    except BaseException as exc:  # pragma: no cover - last-ditch guard
        print(f'fcstm-ui smoke test: top-level crash: {exc!r}', flush=True)
        traceback.print_exc()
        return 3


def _run_plantuml_render_cli() -> int:
    import traceback
    try:
        from app.utils.plantuml_render_cli import main as cli_main
    except Exception:
        traceback.print_exc()
        print('fcstm-ui: failed to import plantuml_render_cli', file=sys.stderr, flush=True)
        return 2
    try:
        return cli_main(sys.argv[2:]) or 0
    except SystemExit as exc:
        return int(exc.code or 0)
    except Exception as exc:  # pragma: no cover - error reporting branch
        print(str(exc), file=sys.stderr, flush=True)
        traceback.print_exc()
        return 1


if __name__ == '__main__':
    if _is_smoke_test_mode():
        sys.exit(_run_smoke_test())
    if _is_plantuml_render_cli_mode():
        sys.exit(_run_plantuml_render_cli())
    from app import run_app
    run_app()

"""
Entry point for the fcstm-ui application.

Smoke-test mode is dispatched as early as possible — before any app
package import — so that the smoke routine still runs even if
``app/__init__.py`` or any of its eager imports raise.  That way the
smoke test is the last line of defence: the user always gets a
per-check diagnostic instead of an opaque traceback at startup.
"""

from __future__ import annotations

import os
import sys


def _is_smoke_test_mode() -> bool:
    if os.environ.get('FCSTM_UI_SMOKE_TEST') == '1':
        return True
    return any(arg == '--smoke-test' for arg in sys.argv[1:])


def _run_smoke_test() -> int:
    # We deliberately import ``app.smoke`` lazily and *after* the
    # mode check, and we only depend on the stdlib up to this point.
    # If even ``app.smoke`` itself fails to import we still want to
    # print a useful diagnostic instead of bubbling up an exception.
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


if __name__ == '__main__':
    if _is_smoke_test_mode():
        sys.exit(_run_smoke_test())
    from app import run_app
    run_app()

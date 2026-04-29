"""
Smoke-test routine for the packaged fcstm-ui binary.

This is invoked when the application is started with ``--smoke-test``
or when ``FCSTM_UI_SMOKE_TEST=1`` is set in the environment.  It is
deliberately split into a long list of small, independent checks so
that a failure on a clean target machine (the canonical case being
"Ubuntu 22.04.5 LTS with only ``default-jre`` installed") points to
exactly which resource is missing instead of bubbling up an opaque
QApplication abort.

Java is treated as an *optional environment dependency*: if ``java`` is
not on ``PATH`` we report a warning and skip the java-dependent checks
without failing the run, so that the same smoke routine still proves
"all bundled resources are present" even on a Java-less host.
"""

from __future__ import annotations

import importlib
import os
import shutil
import subprocess
import sys
import tempfile
import traceback
from typing import Callable, List, Tuple


CheckFn = Callable[[], None]

#: Used by java-dependent checks to short-circuit cleanly.
class JavaUnavailable(RuntimeError):
    pass


_FAILURES: List[str] = []
_WARNINGS: List[str] = []


def _print(msg: str) -> None:
    print(msg, flush=True)


def _step(idx: int, total: int, name: str, fn: CheckFn) -> None:
    label = f'[{idx:>2}/{total}] {name}'
    try:
        fn()
    except JavaUnavailable as exc:
        _WARNINGS.append(name)
        _print(f'{label}: WARN ({exc})')
    except Exception as exc:  # pragma: no cover - smoke-test branch
        _FAILURES.append(name)
        _print(f'{label}: FAIL ({exc.__class__.__name__}: {exc})')
        traceback.print_exc()
    else:
        _print(f'{label}: OK')


# ---------------------------------------------------------------------
# Module import checks (1 module per check, so failure pinpoints which
# package is missing or broken in the bundle).
# ---------------------------------------------------------------------

PRIMARY_MODULES: List[str] = [
    # Qt / GUI stack
    'PyQt5.QtCore',
    'PyQt5.QtGui',
    'PyQt5.QtWidgets',
    'qtpy',
    'qtawesome',
    'qtmodern',
    'qtmodern.styles',

    # Core 3rd-party
    'hbutils',
    'hbutils.model',
    'plantumlcli',
    'plantumlcli.models.base',
    'openpyxl',
    'docx',
    'jinja2',
    'lxml',
    'pyquery',
    'antlr4',
    'rich',
    'prompt_toolkit',
    'click',
    'z3',

    # pyfcstm subpackages we exercise
    'pyfcstm',
    'pyfcstm.dsl',
    'pyfcstm.model',
    'pyfcstm.simulate',
    'pyfcstm.verify',
    'pyfcstm.verify.search',
    'pyfcstm.solver',
    'pyfcstm.convert.sysdesim',
    'pyfcstm.entry.simulate.commands',

    # Application packages
    'app',
    'app.app',
    'app.config',
    'app.config.meta',
    'app.model',
    'app.model.model',
    'app.utils.dsl_to_ui',
    'app.utils.ui_to_dsl',
    'app.utils.show_state_graph',
    'app.utils.export_to_excel',
    'app.utils.export_to_word',
    'app.utils.find_forced_transitions_and_remove',
    'app.utils.verification',
    'app.utils.xml_converter',
    'app.utils.text_overflow',
    'app.utils.create_formLayout_dialog',
    'app.utils.plantuml_render_cli',
    'app.widget',
    'app.widget.main_window',
    'app.widget.dialog_edit_state',
    'app.widget.dialog_show_graph',
    'app.widget.dialog_show_error',
    'app.widget.dialog_reachability_val',
    'app.widget.dialog_add_lifecycle',
    'app.widget.dialog_add_transition',
    'app.widget.dialog_simulate',
    'app.widget.dialog_exclusive_val',
    'app.widget.dialog_sysdesim_validate',
    'app.widget.draggable_tree_widget',
    'app.ui',
    'app.ui.main_window_ui',
]


def _make_module_check(modname: str) -> CheckFn:
    def _check() -> None:
        importlib.import_module(modname)
    _check.__name__ = f'_check_module_{modname.replace(".", "_")}'
    return _check


# ---------------------------------------------------------------------
# Resource / runtime checks
# ---------------------------------------------------------------------

def _check_python_runtime() -> None:
    assert sys.version_info >= (3, 7), f'unexpected python: {sys.version}'
    frozen = getattr(sys, 'frozen', False)
    meipass = getattr(sys, '_MEIPASS', None)
    _print(f'    python={sys.version.split()[0]} frozen={frozen} _MEIPASS={meipass}')


def _check_pyqt_versions() -> None:
    from PyQt5 import QtCore
    _print(f'    Qt={QtCore.QT_VERSION_STR} sip={QtCore.PYQT_VERSION_STR}')


def _check_qtawesome_assets() -> None:
    import qtawesome
    pkg_dir = os.path.dirname(os.path.abspath(qtawesome.__file__))
    fonts_dir = os.path.join(pkg_dir, 'fonts')
    assert os.path.isdir(fonts_dir), f'qtawesome fonts dir missing: {fonts_dir}'
    files = sorted(os.listdir(fonts_dir))
    assert files, 'qtawesome fonts dir is empty'
    _print(f'    {len(files)} font asset(s) in {fonts_dir}')


def _check_main_window_constructible() -> None:
    from PyQt5.QtWidgets import QApplication
    from app.widget import AppMainWindow

    app = QApplication.instance() or QApplication(sys.argv)
    window = AppMainWindow()
    window.show()
    globals()['_smoke_app'] = app
    globals()['_smoke_window'] = window


def _check_plantuml_jar_present() -> None:
    from app.config import PLANTUML_JAR_PATH

    assert os.path.exists(PLANTUML_JAR_PATH), (
        f'PlantUML jar missing at {PLANTUML_JAR_PATH}'
    )
    size = os.path.getsize(PLANTUML_JAR_PATH)
    assert size > 1_000_000, (
        f'PlantUML jar at {PLANTUML_JAR_PATH} is suspiciously small ({size} bytes)'
    )
    _print(f'    plantuml.jar at {PLANTUML_JAR_PATH} ({size // 1024} KiB)')


def _java_path() -> str:
    java = shutil.which('java')
    if not java:
        raise JavaUnavailable(
            'java not found on PATH; only the jar is bundled — install '
            'a JRE (e.g. default-jre on Ubuntu) to enable PlantUML.'
        )
    return java


def _check_java_on_path() -> None:
    java = _java_path()
    proc = subprocess.run(
        [java, '-version'], capture_output=True, text=True, timeout=30,
    )
    msg = (proc.stderr or proc.stdout).strip().splitlines()[:1]
    assert proc.returncode == 0, f'java -version failed: rc={proc.returncode}'
    _print(f'    java={java} {msg!r}')


def _check_plantuml_jar_runs_basic() -> None:
    """`java -jar plantuml.jar -version` — proves the bundled jar is
    not corrupted and the local Java can execute it."""
    java = _java_path()
    from app.config import PLANTUML_JAR_PATH

    proc = subprocess.run(
        [java, '-jar', PLANTUML_JAR_PATH, '-version'],
        capture_output=True, text=True, timeout=60,
    )
    assert proc.returncode == 0, (
        f'java -jar plantuml.jar -version failed: rc={proc.returncode}\n'
        f'stdout:\n{proc.stdout}\nstderr:\n{proc.stderr}'
    )
    head = (proc.stdout or proc.stderr).strip().splitlines()[:1]
    _print(f'    plantuml -version -> {head!r}')


def _resolve_sample_fcstm() -> str:
    from app.config.meta import resource_path

    candidates = [
        resource_path('docs/StateMachine.fcstm'),
        os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'docs', 'StateMachine.fcstm'),
    ]
    for p in candidates:
        if os.path.exists(p):
            return os.path.abspath(p)
    raise FileNotFoundError(f'no sample DSL file found, tried: {candidates}')


def _check_sample_dsl_present() -> None:
    sample = _resolve_sample_fcstm()
    size = os.path.getsize(sample)
    assert size > 100, f'sample DSL too small: {size}'
    _print(f'    sample DSL at {sample} ({size} bytes)')


def _check_dsl_parse_and_roundtrip() -> None:
    from app.utils.dsl_to_ui import dsl_to_state_manager
    from app.utils.ui_to_dsl import state_manager_to_dsl

    sample = _resolve_sample_fcstm()
    sm = dsl_to_state_manager(sample)
    out = state_manager_to_dsl(sm)
    assert out and len(out) > 50, f'roundtrip DSL output too small: {len(out)}'
    _print(f'    roundtrip DSL len={len(out)}')


def _check_plantuml_code_generation() -> None:
    from app.utils.dsl_to_ui import dsl_to_state_manager
    from app.utils.show_state_graph import ShowStateGraph

    sample = _resolve_sample_fcstm()
    sm = dsl_to_state_manager(sample)
    puml = ShowStateGraph.build_plantuml_code(sm)
    assert puml and '@startuml' in puml, 'plantuml code missing @startuml header'
    _print(f'    plantuml code len={len(puml)}')


def _check_plantuml_render_png() -> None:
    """End-to-end: state machine -> PUML -> java + plantuml.jar -> PNG."""
    _java_path()  # raises JavaUnavailable to skip without failing.

    from app.utils.dsl_to_ui import dsl_to_state_manager
    from app.utils.show_state_graph import ShowStateGraph

    sample = _resolve_sample_fcstm()
    sm = dsl_to_state_manager(sample)
    with tempfile.TemporaryDirectory() as tmp:
        out_path = os.path.join(tmp, 'state_graph.png')
        ShowStateGraph.dump_state_graph(sm, out_path, output_format='png')
        assert os.path.exists(out_path), f'plantuml did not produce {out_path}'
        size = os.path.getsize(out_path)
        assert size > 1024, f'plantuml PNG suspiciously small: {size} bytes'
        _print(f'    rendered PNG: {size} bytes')


def _check_z3_solve() -> None:
    import z3

    x = z3.Int('x')
    s = z3.Solver()
    s.add(x > 5, x < 10)
    assert s.check() == z3.sat, 'z3 failed to solve a trivial constraint'
    val = s.model()[x].as_long()
    assert 5 < val < 10, f'z3 model produced invalid value: {val}'
    _print(f'    z3 sat solved: x={val}')


def _check_pyfcstm_simulate_runtime() -> None:
    from pyfcstm.dsl import parse_with_grammar_entry
    from pyfcstm.model import parse_dsl_node_to_state_machine
    from pyfcstm.simulate import SimulationRuntime

    sample = _resolve_sample_fcstm()
    text = open(sample, 'r', encoding='utf-8').read()
    node = parse_with_grammar_entry(text, entry_name='state_machine_dsl')
    sm = parse_dsl_node_to_state_machine(node)
    rt = SimulationRuntime(sm)
    assert rt is not None, 'SimulationRuntime() returned None'
    _print(f'    SimulationRuntime created for {type(sm).__name__}')


def _check_event_loop_pumps() -> None:
    """Drive the QApplication event loop briefly to confirm the GUI
    layer actually runs (paints, processes events) and exits cleanly."""
    from PyQt5.QtCore import QTimer

    app = globals().get('_smoke_app')
    assert app is not None, 'main window check did not create a QApplication'
    QTimer.singleShot(500, app.quit)
    rc = app.exec_()
    assert rc == 0, f'app.exec_() returned {rc}'


# ---------------------------------------------------------------------
# Build the global checks list
# ---------------------------------------------------------------------

def _build_checks() -> List[Tuple[str, CheckFn]]:
    checks: List[Tuple[str, CheckFn]] = [
        ('python runtime',                _check_python_runtime),
        ('PyQt5 versions',                _check_pyqt_versions),
        ('qtawesome font assets',         _check_qtawesome_assets),
    ]
    for modname in PRIMARY_MODULES:
        checks.append((f'import {modname}', _make_module_check(modname)))
    checks.extend([
        ('AppMainWindow construct + show', _check_main_window_constructible),
        ('plantuml.jar bundled',           _check_plantuml_jar_present),
        ('java on PATH',                   _check_java_on_path),
        ('plantuml.jar runs under java',   _check_plantuml_jar_runs_basic),
        ('sample DSL bundled',             _check_sample_dsl_present),
        ('DSL parse + roundtrip',          _check_dsl_parse_and_roundtrip),
        ('plantuml code generation',       _check_plantuml_code_generation),
        ('PUML -> PNG render (e2e)',       _check_plantuml_render_png),
        ('z3 import + sat solve',          _check_z3_solve),
        ('pyfcstm simulate runtime',       _check_pyfcstm_simulate_runtime),
        ('Qt event loop pumps',            _check_event_loop_pumps),
    ])
    return checks


def run_smoke_test() -> int:
    """Run the full smoke-test sequence.

    The sequence is intentionally fault-tolerant: every check is wrapped
    in its own try/except, so even if every single check raises, the
    routine still walks through the entire list and prints one
    diagnostic line per failure.  This is the contract we expose to CI.
    """
    os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

    try:
        checks = _build_checks()
    except Exception as exc:
        traceback.print_exc()
        _print(f'fcstm-ui smoke test: FAILED to build check list ({exc!r})')
        return 2

    total = len(checks)
    _print(f'fcstm-ui smoke test: running {total} checks')
    _print(f'  cwd={os.getcwd()}')
    _print(f'  argv={sys.argv}')

    for idx, (name, fn) in enumerate(checks, start=1):
        # _step itself catches inside; this outer guard is paranoid
        # protection against bugs in _step's own bookkeeping so a single
        # crash never aborts the rest of the run.
        try:
            _step(idx, total, name, fn)
        except BaseException as exc:  # pragma: no cover
            _FAILURES.append(name)
            _print(f'[{idx:>2}/{total}] {name}: HARD-FAIL ({exc!r})')
            traceback.print_exc()

    ok = total - len(_FAILURES) - len(_WARNINGS)
    _print(f'fcstm-ui smoke test: {ok} OK / {len(_WARNINGS)} WARN / {len(_FAILURES)} FAIL')

    if _WARNINGS:
        _print('  warnings:')
        for name in _WARNINGS:
            _print(f'    - {name}')

    if _FAILURES:
        _print('  failures:')
        for name in _FAILURES:
            _print(f'    - {name}')
        _print('fcstm-ui smoke test: FAILED')
        return 1

    _print('fcstm-ui smoke test: PASSED')
    return 0


if __name__ == '__main__':
    sys.exit(run_smoke_test())

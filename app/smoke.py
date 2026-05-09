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
import struct
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
    'py_mini_racer',

    # pyfcstm subpackages we exercise
    'pyfcstm',
    'pyfcstm.dsl',
    'pyfcstm.model',
    'pyfcstm.simulate',
    'pyfcstm.verify',
    'pyfcstm.verify.search',
    'pyfcstm.solver',
    'pyfcstm.convert.sysdesim',
    'pyfcstm.convert.sysdesim.render',
    'pyfcstm.convert.sysdesim.static_check',
    'pyfcstm.diagnostics',
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


def _check_frozen_self_dispatch_render() -> None:
    """When frozen, the GUI runs PlantUML rendering by re-invoking the
    same executable with ``--plantuml-render-cli``.  Verify the dispatch
    works end-to-end and does NOT relaunch the GUI."""
    if not getattr(sys, 'frozen', False):
        # Not applicable in source mode — there's no self-dispatch path
        # there (sys.executable -m app.utils.plantuml_render_cli works
        # directly).  Treat as a documented no-op.
        _print('    skipped (not a frozen build)')
        return

    _java_path()  # warning if java is missing.

    sample = _resolve_sample_fcstm()
    from app.utils.dsl_to_ui import dsl_to_state_manager
    from app.utils.show_state_graph import ShowStateGraph

    sm = dsl_to_state_manager(sample)
    puml = ShowStateGraph.build_plantuml_code(sm)

    with tempfile.TemporaryDirectory() as tmp:
        puml_path = os.path.join(tmp, 'in.puml')
        out_path = os.path.join(tmp, 'out.png')
        with open(puml_path, 'w', encoding='utf-8') as f:
            f.write(puml)

        cmd = [
            sys.executable,
            '--plantuml-render-cli',
            '--input', puml_path,
            '--output', out_path,
            '--format', 'png',
        ]
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        assert proc.returncode == 0, (
            f'self-dispatch render exited {proc.returncode}\n'
            f'stdout:\n{proc.stdout}\nstderr:\n{proc.stderr}'
        )
        assert os.path.exists(out_path), 'self-dispatch did not produce PNG'
        size = os.path.getsize(out_path)
        assert size > 1024, f'self-dispatch PNG suspiciously small: {size} bytes'
        _print(f'    self-dispatch render OK: {size} bytes')


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


_SMOKE_SYSDESIM_XMI = """<?xml version="1.0" encoding="UTF-8"?>
<xmi:XMI xmi:version="20131001"
         xmlns:xmi="http://www.omg.org/spec/XMI/20131001"
         xmlns:uml="http://www.eclipse.org/uml2/5.0.0/UML">
  <uml:Model xmi:id="m1" name="m1">
    <packagedElement xmi:type="uml:Class" xmi:id="cls1" name="SmokeMachine" classifierBehavior="machine_1">
      <ownedBehavior xmi:type="uml:StateMachine" xmi:id="machine_1" name="SmokeMachine">
        <region xmi:type="uml:Region" xmi:id="region_root" name="">
          <transition xmi:type="uml:Transition" xmi:id="tx_init" source="init_root" target="state_idle"/>
          <transition xmi:type="uml:Transition" xmi:id="tx_idle_done" source="state_idle" target="state_done">
            <trigger xmi:type="uml:Trigger" xmi:id="trigger_go" event="signal_evt_go"/>
          </transition>
          <subvertex xmi:type="uml:Pseudostate" xmi:id="init_root"/>
          <subvertex xmi:type="uml:State" xmi:id="state_idle" name="Idle"/>
          <subvertex xmi:type="uml:State" xmi:id="state_done" name="Done"/>
        </region>
      </ownedBehavior>
      <ownedBehavior xmi:type="uml:Interaction" xmi:id="interaction_1" name="SmokeScenario">
        <ownedAttribute xmi:type="uml:Property" xmi:id="prop_send" name="sender"/>
        <ownedAttribute xmi:type="uml:Property" xmi:id="prop_recv" name="receiver"/>
        <lifeline xmi:type="uml:Lifeline" xmi:id="ll_send" name="sender" represents="prop_send"/>
        <lifeline xmi:type="uml:Lifeline" xmi:id="ll_recv" name="receiver" represents="prop_recv"/>
        <fragment xmi:type="uml:MessageOccurrenceSpecification" xmi:id="go_send" covered="ll_send" message="msg_go"/>
        <fragment xmi:type="uml:MessageOccurrenceSpecification" xmi:id="go_recv" covered="ll_recv" message="msg_go"/>
        <message xmi:type="uml:Message" xmi:id="msg_go" sendEvent="go_send" receiveEvent="go_recv" signature="signal_go"/>
      </ownedBehavior>
    </packagedElement>
    <packagedElement xmi:type="uml:Signal" xmi:id="signal_go" name="Go"/>
    <packagedElement xmi:type="uml:SignalEvent" xmi:id="signal_evt_go" signal="signal_go"/>
  </uml:Model>
</xmi:XMI>
"""


def _write_smoke_sysdesim_xml() -> str:
    handle = tempfile.NamedTemporaryFile('w', suffix='.xml', delete=False, encoding='utf-8')
    try:
        handle.write(_SMOKE_SYSDESIM_XMI)
        return handle.name
    finally:
        handle.close()


def _check_mini_racer_v8() -> None:
    from py_mini_racer import MiniRacer

    ctx = MiniRacer()
    assert ctx.eval('40 + 2') == 42, 'MiniRacer basic eval failed'
    js = """
    const wasmBytes = new Uint8Array([
      0x00, 0x61, 0x73, 0x6d, 0x01, 0x00, 0x00, 0x00,
      0x01, 0x07, 0x01, 0x60, 0x02, 0x7f, 0x7f, 0x01, 0x7f,
      0x03, 0x02, 0x01, 0x00,
      0x07, 0x07, 0x01, 0x03, 0x61, 0x64, 0x64, 0x00, 0x00,
      0x0a, 0x09, 0x01, 0x07, 0x00, 0x20, 0x00, 0x20, 0x01, 0x6a, 0x0b
    ]);
    const m = new WebAssembly.Module(wasmBytes);
    const i = new WebAssembly.Instance(m, {});
    i.exports.add(7, 35);
    """
    assert ctx.eval(js) == 42, 'MiniRacer WebAssembly support failed'
    _print('    MiniRacer V8 eval + WebAssembly OK')


def _check_pyfcstm_render_bundle() -> None:
    import pyfcstm.convert.sysdesim as sysdesim_pkg
    from pyfcstm.convert.sysdesim import render as render_module

    pkg_dir = os.path.dirname(os.path.abspath(sysdesim_pkg.__file__))
    bundle_path = os.path.join(pkg_dir, '_render_assets', 'pyfcstm-sysdesim-render.js')
    assert os.path.exists(bundle_path), f'SysDeSim render bundle missing: {bundle_path}'
    size = os.path.getsize(bundle_path)
    assert size > 1_000_000, f'SysDeSim render bundle too small: {size}'
    render_module._runtime_cached = None
    _ctx, version = render_module._get_runtime()
    assert version, 'PyfcstmSysdesim.version() returned empty value'
    _print(f'    render bundle OK: {size} bytes, version={version}')


def _check_sysdesim_static_and_render() -> None:
    from pyfcstm.convert.sysdesim import (
        build_overlay_from_diagnostics,
        build_sysdesim_phase10_report,
        build_sysdesim_timeline_import_report,
        render_sysdesim_timeline_png,
        render_sysdesim_timeline_svg,
        run_sysdesim_static_pre_checks,
    )

    path = _write_smoke_sysdesim_xml()
    try:
        phase10 = build_sysdesim_phase10_report(path)
        diagnostics = run_sysdesim_static_pre_checks(phase10_report=phase10)
        report = build_sysdesim_timeline_import_report(path)
        assert report and 'phase10' in report, 'timeline import report missing phase10'
        overlay = build_overlay_from_diagnostics(
            phase10_report=phase10,
            diagnostics=diagnostics,
            include_state_cells=True,
        )
        svg = render_sysdesim_timeline_svg(phase10_report=phase10, overlay=overlay)
        assert isinstance(svg, str) and '<svg' in svg and '</svg>' in svg, 'bad SVG render output'
        png = render_sysdesim_timeline_png(phase10_report=phase10, overlay=overlay)
        assert png[:8] == b'\x89PNG\r\n\x1a\n', 'bad PNG magic from SysDeSim renderer'
        width, height = struct.unpack('>II', png[16:24])
        assert width > 0 and height > 0, f'bad PNG dimensions: {width}x{height}'
        _print(f'    SysDeSim static/render OK: diagnostics={len(diagnostics)} svg={len(svg)} png={len(png)} {width}x{height}')
    finally:
        try:
            os.unlink(path)
        except OSError:
            pass


def _check_sysdesim_validate_dialog_views() -> None:
    from PyQt5.QtWidgets import QApplication
    from app.widget.dialog_sysdesim_validate import DialogSysdesimValidate
    from pyfcstm.convert.sysdesim import (
        build_overlay_from_diagnostics,
        build_sysdesim_phase10_report,
        build_sysdesim_timeline_import_report,
        render_sysdesim_timeline_svg,
        run_sysdesim_static_pre_checks,
    )

    path = _write_smoke_sysdesim_xml()
    app = QApplication.instance() or QApplication(sys.argv)
    dialog = None
    try:
        phase10 = build_sysdesim_phase10_report(path)
        diagnostics = run_sysdesim_static_pre_checks(phase10_report=phase10)
        report = build_sysdesim_timeline_import_report(
            path,
            left_machine_alias='SmokeMachine',
            left_state_ref='SmokeMachine.Idle',
            right_machine_alias='SmokeMachine',
            right_state_ref='SmokeMachine.Idle',
            observation_scope='both',
        )
        dialog = DialogSysdesimValidate(None, [])
        dialog.resize(900, 650)
        dialog.show()
        app.processEvents()

        dialog._populate_witness_table(report)
        assert dialog.table_witness.rowCount() >= 2, 'SAT witness table did not populate rows'
        assert dialog.table_witness.columnCount() >= 4, 'SAT witness table did not populate columns'
        co_values = [
            dialog.table_witness.item(row, dialog.table_witness.columnCount() - 1).text()
            for row in range(dialog.table_witness.rowCount())
        ]
        assert 'start' in co_values, f'SAT witness table missing start marker: {co_values}'

        overlay = build_overlay_from_diagnostics(
            phase10_report=phase10,
            diagnostics=diagnostics,
            coexistence_timeline=(report.get('phase11') or {}).get('timeline_report'),
            include_state_cells=True,
        )
        dialog._last_svg_text = render_sysdesim_timeline_svg(phase10_report=phase10, overlay=overlay)
        dialog._load_svg_preview()
        app.processEvents()
        base = dialog._diagram_base_size
        shown = dialog.svg_diagram.size()
        assert base.isValid() and shown.isValid(), 'sequence diagram preview size is invalid'
        assert shown.width() > 0 and shown.height() > 0, 'sequence diagram preview collapsed'
        base_ratio = float(base.width()) / float(base.height())
        shown_ratio = float(shown.width()) / float(shown.height())
        assert abs(base_ratio - shown_ratio) < 0.02, (
            f'sequence diagram aspect ratio changed: base={base_ratio:.4f} shown={shown_ratio:.4f}'
        )
        _print(
            '    SysDeSim validate dialog OK: witness_rows={} diagram={}x{} -> {}x{}'.format(
                dialog.table_witness.rowCount(),
                base.width(),
                base.height(),
                shown.width(),
                shown.height(),
            )
        )
    finally:
        if dialog is not None:
            dialog.close()
        try:
            os.unlink(path)
        except OSError:
            pass


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
        ('frozen self-dispatch render',    _check_frozen_self_dispatch_render),
        ('z3 import + sat solve',          _check_z3_solve),
        ('pyfcstm simulate runtime',       _check_pyfcstm_simulate_runtime),
        ('MiniRacer V8 + WebAssembly',     _check_mini_racer_v8),
        ('pyfcstm render bundle loadable', _check_pyfcstm_render_bundle),
        ('SysDeSim static + SVG/PNG render', _check_sysdesim_static_and_render),
        ('SysDeSim validate dialog views', _check_sysdesim_validate_dialog_views),
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

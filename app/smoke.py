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
import signal
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

#: Set of top-level module names whose isolated import failed.  In-process
#: checks that depend on a broken native binding consult this set via
#: ``_require_imports(...)`` and skip themselves cleanly instead of
#: re-triggering the same SIGSEGV/SIGABRT in the parent process.
_FAILED_IMPORTS = set()


def _require_imports(*modnames: str) -> None:
    failed = [m for m in modnames if m in _FAILED_IMPORTS]
    if failed:
        raise RuntimeError(
            'skipping: prerequisite import(s) already failed: ' + ', '.join(failed)
        )


def _supports_color() -> bool:
    if os.environ.get('NO_COLOR'):
        return False
    if os.environ.get('FORCE_COLOR'):
        return True
    try:
        return bool(sys.stdout.isatty())
    except Exception:
        return False


_USE_COLOR = _supports_color()


def _ansi(code: str, text: str) -> str:
    if not _USE_COLOR:
        return text
    return f'\033[{code}m{text}\033[0m'


def _green(text: str) -> str:  return _ansi('32', text)
def _red(text: str) -> str:    return _ansi('31', text)
def _yellow(text: str) -> str: return _ansi('33', text)
def _cyan(text: str) -> str:   return _ansi('36', text)
def _bold(text: str) -> str:   return _ansi('1', text)
def _dim(text: str) -> str:    return _ansi('2', text)


def _print(msg: str) -> None:
    print(msg, flush=True)


def _step(idx: int, total: int, name: str, fn: CheckFn) -> None:
    label = f'[{idx:>2}/{total}] {name}'
    try:
        fn()
    except JavaUnavailable as exc:
        _WARNINGS.append(name)
        _print(f'{label}: {_bold(_yellow("WARN"))} ({exc})')
    except Exception as exc:  # pragma: no cover - smoke-test branch
        _FAILURES.append(name)
        _print(f'{label}: {_bold(_red("FAIL"))} ({_red(exc.__class__.__name__)}: {exc})')
        traceback.print_exc()
    else:
        _print(f'{label}: {_bold(_green("OK"))}')


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
    'pyfcstm.utils',
    'pyfcstm.topology',
    'pyfcstm.topology.reachability',
    'pyfcstm.topology.finiteness',
    'pyfcstm.topology.inevitability',
    'pyfcstm.topology.graph',
    'pyfcstm.topology.render',
    'pyfcstm.topology.types',
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
    'app.widget.dialog_topology_verify',
    'app.widget.dialog_add_lifecycle',
    'app.widget.dialog_add_transition',
    'app.widget.dialog_simulate',
    'app.widget.dialog_exclusive_val',
    'app.widget.dialog_sysdesim_validate',
    'app.widget.draggable_tree_widget',
    'app.ui',
    'app.ui.main_window_ui',
]


def _import_module_isolated(modname: str) -> None:
    """Import *modname* in a forked subprocess so a native crash
    (SIGSEGV / SIGABRT from a broken ``z3-solver`` / ``py_mini_racer``
    / ``PyQt5`` binding, mismatched glibc, …) turns into an
    ``ImportError`` instead of taking the whole smoke run down.

    Falls back to an in-process import on platforms without ``os.fork``
    (Windows). The CI verify stage uses Linux + macOS + Windows; Linux
    and macOS get the hardened path, Windows keeps the old behaviour.
    """
    if not hasattr(os, 'fork') or sys.platform == 'darwin':
        # * Windows has no ``os.fork``.
        # * macOS Cocoa-linked processes cannot safely fork() once a
        #   Qt / AppKit symbol has been loaded — the child inherits a
        #   half-initialised Objective-C runtime and any subsequent
        #   message dispatch (e.g. importing another widget module
        #   that touches a Qt class) segfaults the child even though
        #   the parent is fine.  We fall back to in-process import on
        #   both, accepting that a broken native binding there takes
        #   the runner down — that path was never resilient on macOS
        #   anyway.  Linux keeps the fork-isolated path below.
        importlib.import_module(modname)
        return

    r_fd, w_fd = os.pipe()
    pid = os.fork()
    if pid == 0:
        # Child: do the import, write the result (or the exception
        # message) to the pipe, then leave via os._exit so that no
        # Python / PyInstaller / Qt cleanup runs in the child.
        os.close(r_fd)
        try:
            importlib.import_module(modname)
            try:
                os.write(w_fd, b'ok\n')
            finally:
                os.close(w_fd)
            os._exit(0)
        except BaseException as exc:
            try:
                payload = f'{exc.__class__.__name__}: {exc}'.encode('utf-8', errors='replace')
                os.write(w_fd, b'fail\n' + payload)
            except Exception:
                pass
            finally:
                try:
                    os.close(w_fd)
                except Exception:
                    pass
            os._exit(1)

    # Parent: drain the pipe (bounded) and reap the child.
    os.close(w_fd)
    try:
        buf = bytearray()
        while True:
            chunk = os.read(r_fd, 65536)
            if not chunk:
                break
            buf.extend(chunk)
            if len(buf) >= 65536:
                break
    finally:
        try:
            os.close(r_fd)
        except Exception:
            pass

    _, status = os.waitpid(pid, 0)
    if os.WIFEXITED(status):
        exit_code = os.WEXITSTATUS(status)
        if exit_code == 0:
            # Child said the import is fine. Mirror it in the parent so
            # that future fork-isolated imports inherit the loaded module
            # via copy-on-write rather than reloading from scratch every
            # time.  If the parent-side import surprises us (very rare,
            # would indicate a non-deterministic native binding), let the
            # exception bubble through as a normal FAIL.
            importlib.import_module(modname)
            return
        if buf.startswith(b'fail\n'):
            raise ImportError(buf[5:].decode('utf-8', errors='replace'))
        raise ImportError(f'subprocess exited {exit_code} with no diagnostic')
    if os.WIFSIGNALED(status):
        sig = os.WTERMSIG(status)
        try:
            sig_name = signal.Signals(sig).name  # type: ignore[attr-defined]
        except Exception:
            sig_name = f'signal {sig}'
        raise ImportError(
            f'native crash on `import {modname}` ({sig_name}); '
            f'usually a broken extension binding (incompatible glibc / '
            f'missing system library / wheel built for a different cpu) — '
            f'reinstall the offending package'
        )
    raise ImportError(f'subprocess exited with unrecognised status 0x{status:x}')


def _make_module_check(modname: str) -> CheckFn:
    def _check() -> None:
        try:
            _import_module_isolated(modname)
        except BaseException:
            # Remember the broken top-level package so that downstream
            # in-process checks can ``_require_imports(...)`` and skip
            # themselves instead of re-triggering the same crash.
            _FAILED_IMPORTS.add(modname)
            _FAILED_IMPORTS.add(modname.split('.', 1)[0])
            raise
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
    _import_module_isolated('PyQt5.QtCore')
    from PyQt5 import QtCore
    _print(f'    Qt={QtCore.QT_VERSION_STR} sip={QtCore.PYQT_VERSION_STR}')


def _check_qtawesome_assets() -> None:
    _import_module_isolated('qtawesome')
    import qtawesome
    pkg_dir = os.path.dirname(os.path.abspath(qtawesome.__file__))
    fonts_dir = os.path.join(pkg_dir, 'fonts')
    assert os.path.isdir(fonts_dir), f'qtawesome fonts dir missing: {fonts_dir}'
    files = sorted(os.listdir(fonts_dir))
    assert files, 'qtawesome fonts dir is empty'
    _print(f'    {len(files)} font asset(s) in {fonts_dir}')


def _check_main_window_constructible() -> None:
    _require_imports('app.widget.main_window')
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


def _resolve_topology_sample_fcstm() -> str:
    from app.config.meta import resource_path

    candidates = [
        resource_path('docs/topology_controller_all_in_one.fcstm'),
        os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'docs', 'topology_controller_all_in_one.fcstm'),
    ]
    for p in candidates:
        if os.path.exists(p):
            return os.path.abspath(p)
    raise FileNotFoundError(f'no topology sample DSL file found, tried: {candidates}')


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
    _require_imports('z3')
    import z3

    x = z3.Int('x')
    s = z3.Solver()
    s.add(x > 5, x < 10)
    assert s.check() == z3.sat, 'z3 failed to solve a trivial constraint'
    val = s.model()[x].as_long()
    assert 5 < val < 10, f'z3 model produced invalid value: {val}'
    _print(f'    z3 sat solved: x={val}')


def _check_pyfcstm_simulate_runtime() -> None:
    _require_imports('z3', 'pyfcstm.simulate', 'pyfcstm.dsl', 'pyfcstm.model')
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


def _check_pyfcstm_utils_identifier_runtime() -> None:
    from pyfcstm.utils import normalize, to_c_identifier, to_java_identifier, to_python_identifier

    assert normalize('Hello World!') == 'Hello_World'
    assert normalize('123 Test') == '123_Test'
    assert normalize('class', keyword_safe_for=['python']) == 'class_'
    assert to_python_identifier('123 Test') == '_123_Test'
    assert to_python_identifier('class') == 'class_'
    assert to_java_identifier('class') == 'class_'
    assert to_c_identifier('int') == 'int_'
    assert to_c_identifier('控制 器') == 'Kong_Zhi_Qi'
    _print('    pyfcstm utils identifier helpers OK')


_SMOKE_TOPOLOGY_DSL = """
state Controller named "控制器" {
    state Startup named "启动阶段" {
        state PowerOn named "上电";
        state SelfCheck named "自检";
        state Fault named "异常";
        [*] -> PowerOn;
        PowerOn -> SelfCheck;
        SelfCheck -> [*];
        SelfCheck -> Fault;
        Fault -> PowerOn;
        Fault -> [*];
    }
    state Running named "运行阶段" {
        state Idle named "等待";
        state Process named "处理";
        state Emit named "输出";
        [*] -> Idle;
        Idle -> Process;
        Process -> Emit;
        Process -> Idle;
        Emit -> Idle;
        Emit -> [*];
    }
    state Shutdown named "关闭阶段" {
        state Save named "保存数据";
        state PowerOff named "断电";
        [*] -> Save;
        Save -> PowerOff;
        PowerOff -> [*];
    }
    state Error named "故障";
    state Halt named "紧急停机";
    [*] -> Startup;
    Startup -> Running;
    Running -> Shutdown;
    Running -> Error;
    Error -> Halt;
    Halt -> [*];
    Shutdown -> [*];
}
"""


def _build_smoke_topology_model():
    from pyfcstm.dsl import parse_with_grammar_entry
    from pyfcstm.model import parse_dsl_node_to_state_machine

    try:
        with open(_resolve_topology_sample_fcstm(), 'r', encoding='utf-8') as f:
            dsl_code = f.read()
    except FileNotFoundError:
        dsl_code = _SMOKE_TOPOLOGY_DSL
    ast_node = parse_with_grammar_entry(dsl_code, 'state_machine_dsl')
    return parse_dsl_node_to_state_machine(ast_node)


def _check_pyfcstm_topology_runtime() -> None:
    _require_imports('py_mini_racer', 'pyfcstm.topology')
    from pyfcstm.topology import (
        build_topology_graph,
        check_finiteness,
        check_inevitability,
        check_reachability,
        render_topology_png,
        render_topology_svg,
    )

    sample = _resolve_topology_sample_fcstm()
    size = os.path.getsize(sample)
    assert size > 500, f'topology sample DSL too small: {size}'
    sm = _build_smoke_topology_model()
    graph = build_topology_graph(sm)
    reach_ok = check_reachability(sm, target='Controller.Shutdown.PowerOff', graph=graph)
    reach_fail = check_reachability(
        sm,
        target='Controller.Startup.PowerOn',
        source='Controller.Shutdown.PowerOff',
        graph=graph,
    )
    finite_ok = check_finiteness(sm, source='Controller.Shutdown.Save', graph=graph)
    finite_fail = check_finiteness(sm, graph=graph)
    inevitability_ok = check_inevitability(
        sm,
        target='Controller.Shutdown.PowerOff',
        source='Controller.Shutdown.Save',
        graph=graph,
    )
    inevitability_fail = check_inevitability(sm, target='Controller.Shutdown.Save', graph=graph)
    assert reach_ok.reachable is True, 'topology reachability expected Controller.Shutdown.PowerOff reachable'
    assert reach_fail.reachable is False, 'topology reachability expected Controller.Startup.PowerOn unreachable from PowerOff'
    assert finite_ok.finite is True, 'topology finiteness expected finite from Controller.Shutdown.Save'
    assert finite_fail.finite is False, 'topology finiteness expected default-source trap cycle'
    assert getattr(finite_fail.counterexample, 'kind', None) == 'trap_cycle', 'topology finiteness expected trap_cycle'
    assert inevitability_ok.inevitable is True, 'topology inevitability expected PowerOff inevitable from Save'
    assert inevitability_fail.inevitable is False, 'topology inevitability expected Save avoidable from default source'
    assert getattr(inevitability_fail.counterexample, 'kind', None) == 'alt_end', 'topology inevitability expected alt_end'
    svg = render_topology_svg(sm, inevitability_fail, graph=graph)
    assert isinstance(svg, str) and '<svg' in svg and '</svg>' in svg, 'bad topology SVG output'
    png = render_topology_png(sm, finite_fail, graph=graph)
    assert png[:8] == b'\x89PNG\r\n\x1a\n', 'bad topology PNG magic'
    width, height = struct.unpack('>II', png[16:24])
    assert width > 0 and height > 0, f'bad topology PNG dimensions: {width}x{height}'
    _print(
        '    topology checks/render OK: sample={} 6 scenarios leaves={} edges={} svg={} png={} {}x{}'.format(
            os.path.basename(sample), len(graph.leaves), len(graph.edges), len(svg), len(png), width, height,
        )
    )


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
    _require_imports('py_mini_racer')
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
    _require_imports('py_mini_racer', 'pyfcstm.convert.sysdesim')
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
    _require_imports('py_mini_racer', 'pyfcstm.convert.sysdesim')
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
    _require_imports('py_mini_racer', 'pyfcstm.convert.sysdesim', 'app.widget.dialog_sysdesim_validate')
    from PyQt5.QtCore import Qt
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
        assert '右键' in dialog.label_diagram_hint.text(), 'sequence diagram missing visible save hint'
        assert '滚动' in dialog.diagram_scroll.toolTip(), 'sequence diagram missing scroll tooltip'
        assert dialog.svg_diagram.contextMenuPolicy() == Qt.CustomContextMenu, 'sequence diagram missing SVG context menu'
        assert dialog.diagram_scroll.viewport().contextMenuPolicy() == Qt.CustomContextMenu, (
            'sequence diagram missing viewport context menu'
        )
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


def _check_state_graph_dialog_affordances() -> None:
    _require_imports('app.widget.dialog_show_graph')
    from PyQt5.QtCore import Qt
    from PyQt5.QtWidgets import QApplication
    from app.widget.dialog_show_graph import DialogShowGraph

    app = QApplication.instance() or QApplication(sys.argv)
    dialog = DialogShowGraph(None, [])
    try:
        dialog.resize(900, 650)
        dialog.show()
        app.processEvents()

        assert '右键' in dialog.label_graph_hint.text(), 'state graph missing visible save hint'
        assert '滚轮' in dialog.graphics_view_show_graph.toolTip(), 'state graph missing zoom tooltip'
        assert dialog.graphics_view_show_graph.viewport().contextMenuPolicy() == Qt.CustomContextMenu, (
            'state graph missing viewport context menu'
        )
    finally:
        dialog.close()


def _check_topology_verify_dialog_views() -> None:
    _require_imports('py_mini_racer', 'pyfcstm.topology', 'app.widget.dialog_topology_verify')
    from PyQt5.QtCore import Qt
    from PyQt5.QtWidgets import QApplication
    from app.widget.dialog_topology_verify import DialogTopologyVerify
    from app.utils.dsl_to_ui import convert_state_machine_to_state_manager
    from pyfcstm.dsl import parse_with_grammar_entry

    with open(_resolve_topology_sample_fcstm(), 'r', encoding='utf-8') as f:
        dsl_code = f.read()
    ast_node = parse_with_grammar_entry(dsl_code, 'state_machine_dsl')
    manager = convert_state_machine_to_state_manager(ast_node)
    app = QApplication.instance() or QApplication(sys.argv)
    dialog = DialogTopologyVerify(None, [manager], manager)
    try:
        dialog.resize(900, 650)
        dialog.show()
        app.processEvents()

        dialog._select_combo_path(dialog.combo_target_state, 'Controller.Shutdown.Save')
        dialog.combo_check.setCurrentIndex(dialog.combo_check.findData('inevitability'))
        dialog._run_check()
        app.processEvents()

        assert dialog._last_result is not None, 'topology dialog did not produce a result'
        assert getattr(dialog._last_result, 'inevitable', None) is False, 'dialog inevitability expected avoidable'
        assert getattr(dialog._last_result.counterexample, 'kind', None) == 'alt_end', 'dialog inevitability expected alt_end'
        assert dialog.table_result.rowCount() >= 2, 'topology result table did not populate rows'
        assert dialog._last_svg_text and '<svg' in dialog._last_svg_text, 'topology dialog missing SVG'
        base = dialog._diagram_base_size
        shown = dialog.svg_diagram.size()
        assert base.isValid() and shown.isValid(), 'topology diagram preview size is invalid'
        assert shown.width() > 0 and shown.height() > 0, 'topology diagram preview collapsed'
        assert '右键' in dialog.label_diagram_hint.text(), 'topology diagram missing visible save hint'
        assert '滚动条' in dialog.diagram_scroll.toolTip(), 'topology diagram missing pan/scroll tooltip'
        assert dialog.svg_diagram.contextMenuPolicy() == Qt.CustomContextMenu, 'topology diagram missing SVG context menu'
        assert dialog.diagram_scroll.viewport().contextMenuPolicy() == Qt.CustomContextMenu, (
            'topology diagram missing viewport context menu'
        )
        _print(
            '    topology dialog OK: rows={} diagram={}x{} -> {}x{}'.format(
                dialog.table_result.rowCount(),
                base.width(),
                base.height(),
                shown.width(),
                shown.height(),
            )
        )
    finally:
        dialog.close()


def _check_event_loop_pumps() -> None:
    """Drive the QApplication event loop briefly to confirm the GUI
    layer actually runs (paints, processes events) and exits cleanly."""
    _require_imports('PyQt5.QtCore', 'app.widget.main_window')
    from PyQt5.QtCore import QTimer

    app = globals().get('_smoke_app')
    if app is None:
        raise RuntimeError(
            'skipping: main window check did not create a QApplication '
            '(probably because an earlier prerequisite import failed)'
        )
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
        ('pyfcstm utils identifier runtime', _check_pyfcstm_utils_identifier_runtime),
        ('pyfcstm topology runtime',       _check_pyfcstm_topology_runtime),
        ('MiniRacer V8 + WebAssembly',     _check_mini_racer_v8),
        ('pyfcstm render bundle loadable', _check_pyfcstm_render_bundle),
        ('SysDeSim static + SVG/PNG render', _check_sysdesim_static_and_render),
        ('SysDeSim validate dialog views', _check_sysdesim_validate_dialog_views),
        ('state graph dialog affordances',  _check_state_graph_dialog_affordances),
        ('topology validate dialog views',  _check_topology_verify_dialog_views),
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
        _print(f'{_cyan("fcstm-ui smoke test:")} {_bold(_red("FAILED"))} to build check list ({exc!r})')
        return 2

    total = len(checks)
    _print(_cyan(f'fcstm-ui smoke test: running {total} checks'))
    _print(_dim(f'  cwd={os.getcwd()}'))
    _print(_dim(f'  argv={sys.argv}'))

    for idx, (name, fn) in enumerate(checks, start=1):
        # _step itself catches inside; this outer guard is paranoid
        # protection against bugs in _step's own bookkeeping so a single
        # crash never aborts the rest of the run.
        try:
            _step(idx, total, name, fn)
        except BaseException as exc:  # pragma: no cover
            _FAILURES.append(name)
            _print(f'[{idx:>2}/{total}] {name}: {_bold(_red("HARD-FAIL"))} ({exc!r})')
            traceback.print_exc()

    ok = total - len(_FAILURES) - len(_WARNINGS)
    _print(
        '{header} {ok_part} / {warn_part} / {fail_part}'.format(
            header=_cyan('fcstm-ui smoke test:'),
            ok_part=_green(f'{ok} OK'),
            warn_part=_yellow(f'{len(_WARNINGS)} WARN'),
            fail_part=_red(f'{len(_FAILURES)} FAIL'),
        )
    )

    if _WARNINGS:
        _print(_yellow('  warnings:'))
        for name in _WARNINGS:
            _print(_yellow(f'    - {name}'))

    if _FAILURES:
        _print(_red('  failures:'))
        for name in _FAILURES:
            _print(_red(f'    - {name}'))
        _print(f'{_cyan("fcstm-ui smoke test:")} {_bold(_red("FAILED"))}')
        return 1

    _print(f'{_cyan("fcstm-ui smoke test:")} {_bold(_green("PASSED"))}')
    return 0


if __name__ == '__main__':
    sys.exit(run_smoke_test())

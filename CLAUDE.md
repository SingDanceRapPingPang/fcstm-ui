# CLAUDE.md

`AGENTS.md` is a symbolic link to this file (`CLAUDE.md`). Edit `CLAUDE.md` only — do not modify both files separately.

This document is the entry-point guide for Claude Code (claude.ai/code) and other LLM-assisted agents working in this repository.

## Project Overview

`fcstm-ui` is the desktop UI front-end for [`pyfcstm`](https://github.com/HansBug/pyfcstm), the Python Finite Control State Machine framework. It is a PyQt5 application that:

- imports / edits `.fcstm` DSL files (the FCSTM hierarchical state-machine DSL parsed by `pyfcstm`)
- visualises state machines via PlantUML
- runs reachability / exclusivity / lifecycle / forced-transition validation against the `pyfcstm` solver and verifier
- runs interactive simulation against `pyfcstm.simulate`
- imports / converts SysDeSim XML models through `pyfcstm.convert.sysdesim`
- exports views to Excel / Word

The application logic lives entirely in this repo; the DSL parser, model, solver, simulator and converter come from `pyfcstm` (currently consumed from the `dev/damnx` branch).

## Repository Layout

```
.
├── main.py                # Thin entry point: from app import run_app
├── main.spec              # PyInstaller spec (current canonical one)
├── fcstm-ui.spec          # Older spec, kept for reference
├── pyinstaller_rthook_z3.py  # Runtime hook that exposes the bundled libz3 to z3-solver
├── requirements.txt       # Runtime deps (PyQt5, qtmodern/qtawesome, openpyxl, python-docx, pyfcstm@dev/damnx, …)
├── requirements-build.txt # PyInstaller toolchain
├── requirements-test.txt  # pytest / pytest-qt / pytest-xvfb
├── docs/
│   ├── plantuml.jar       # Bundled PlantUML jar — required at runtime, see "Java" below
│   └── *.fcstm            # Example DSL files used as fixtures
├── app/
│   ├── __init__.py        # `run_app()` re-exported here
│   ├── app.py             # QApplication bootstrap + theme handling
│   ├── config/            # Constants, including PLANTUML_JAR_PATH (frozen-aware)
│   ├── model/             # In-memory UI-side state-machine model (StateManager, State, …)
│   ├── ui/                # .ui XML + Makefile that compiles to *_ui.py via pyuic5
│   ├── widget/            # QMainWindow / QDialog subclasses (the UI behaviour)
│   └── utils/             # DSL ↔ UI bridge, exporters, plantuml render helper, validators
└── .github/workflows/
    └── build.yml          # 2-stage CI: build PyInstaller artifacts, then verify them in clean OS images
```

## Java Dependency Policy

The application **uses** Java at runtime (PlantUML is invoked through `java -jar plantuml.jar`), but the JRE itself is **not bundled**.

- The bundled `docs/plantuml.jar` is treated as an application resource and **is** packed into PyInstaller artifacts (`datas` entry).
- Target machines must have a working `java` on `PATH` — `default-jre` / `openjdk-17-jre-headless` on Linux, the system JRE on macOS, or any modern OpenJDK / Oracle JRE on Windows.
- Do **not** add Java runtime binaries to `binaries=` / `datas=` in the spec file.

## Setting Up a Local Dev Environment

A `venv37` directory can be created at the repo root for Python 3.7 development. Recreate it like this if needed:

```bash
python3.7 -m venv venv37
source venv37/bin/activate
python -m pip install "pip<23.1" "setuptools<69" "wheel<0.43"
python -m pip install -U -r requirements-build.txt -r requirements-test.txt -r requirements.txt
make -C app/ui build         # generate *_ui.py from .ui XML
```

Then run:

```bash
# normal run (needs a real display)
python main.py

# headless smoke run (Linux CI / docker / sshed-in machines)
QT_QPA_PLATFORM=offscreen python main.py
```

Linux additionally needs the Qt platform libraries (`libxkbcommon-x11-0`, `libxcb-*`, `libegl1`, `libfontconfig1`, …) — see the GitHub workflow for the full apt list.

## Common Commands

```bash
make build       # ui + pyinstaller, onedir (set STANDALONE=1 for onefile)
make run         # rebuild ui, then run main.py
make ui          # only regenerate *_ui.py
make clean       # wipe build/ dist/ ui generated files
make unittest    # pytest (currently a placeholder — most coverage runs through manual smoke tests)
```

`fcstm-ui.spec` is kept around for historical reference; `main.spec` is what `make build` uses today.

## Packaging Strategy (PyInstaller)

- **Spec entry**: `main.py` → `EXE(name='fcstm-ui', ...)`
- **Z3**: collected via `collect_dynamic_libs('z3', destdir='z3/lib')`, exposed back to the `z3-solver` Python wrapper through `pyinstaller_rthook_z3.py`. Without this hook the bundled binary cannot find `libz3.so` / `libz3.dylib` / `z3.dll` and `import z3` fails at runtime.
- **PlantUML jar**: pulled in via `datas` only when `docs/plantuml.jar` exists at build time.
- **Onefile (`-F`)**: produces a single executable; suitable for "drop one file on the target and run" use cases. Slower cold start due to bootloader extraction.
- **Onedir (`-D`)**: produces a directory; we ship it as a zip ("免安装 / portable").
- **Linux glibc**: the GitHub workflow builds inside the `ubuntu-22.04` runner (glibc 2.35) so the artifact runs on Ubuntu 22.04.5 LTS and any newer distro. Newer-glibc binaries cannot run on older glibc systems — do not bump the build runner past 22.04 unless the deployment baseline is also bumped.

## CI / Release Pipeline

`.github/workflows/build.yml` runs in two stages on a `windows-2022` / `ubuntu-22.04` / `macos-13` matrix (all x86_64 — arm64 is intentionally out of scope):

1. **build** — set up Python, install requirements, regenerate UI files, run PyInstaller in both onefile and onedir mode, zip the onedir output, upload as artifacts.
2. **verify** — download the artifacts on a *fresh* runner of the same OS without installing the project's Python deps. Smoke-test both the onefile binary and the unzipped onedir tree by running them with `QT_QPA_PLATFORM=offscreen` and asserting the process starts a `QMainWindow` and exits cleanly.

The verify stage intentionally does **not** install Python dependencies or the source repo — it proves the artifact is self-contained (modulo the documented Java + Linux Qt system-library requirements).

## Useful References

- Upstream `pyfcstm` repo: <https://github.com/HansBug/pyfcstm>
- Active branch in pyfcstm: `dev/damnx` (PR #74 at the time of writing)
- This repo on GitHub: <https://github.com/SingDanceRapPingPang/fcstm-ui>

## Pitfalls Already Hit (Don't Re-debug)

- `dsl_to_state_manager(...)` takes a **file path**, not a parsed AST node. If you need to convert from an AST in-memory, call `convert_state_machine_to_state_manager(ast_node, variable_definitions)` directly.
- `ShowStateGraph` is a class with classmethods (`build_plantuml_code`, `dump_state_graph`, `show_state_graph`). It does **not** take a `StateManager` in its constructor — pass the state manager into the classmethods.
- `app/config/meta.py:resource_path` is the PyInstaller-aware resource resolver. Always go through it (or constants like `PLANTUML_JAR_PATH`) rather than reading paths relative to `__file__`, otherwise resources break inside frozen builds.

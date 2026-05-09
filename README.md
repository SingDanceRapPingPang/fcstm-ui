# fcstm-ui

`fcstm-ui` 是 [`pyfcstm`](https://github.com/HansBug/pyfcstm) 状态机框架的桌面 GUI 前端，基于 **PyQt5** 开发。它把 `pyfcstm` 的 DSL 解析、模型、求解器、模拟器、SysDeSim 转换器都串在一个图形界面里，目标用户是状态机建模、可达性 / 排他性 / 生命周期校验、PlantUML 可视化、Excel/Word 文档导出这些场景。

> AGENTS.md 是 CLAUDE.md 的符号链接，二者内容保持一致，请只修改 `CLAUDE.md`。

---

## 目录

- [快速概览](#快速概览)
- [功能矩阵](#功能矩阵)
- [运行环境要求](#运行环境要求)
- [使用打包好的 portable 版本](#使用打包好的-portable-版本)
- [从源码运行](#从源码运行)
- [本地打包（PyInstaller）](#本地打包pyinstaller)
- [GitHub Actions CI 流程](#github-actions-ci-流程)
- [Smoke Test：最后一道防线](#smoke-test最后一道防线)
- [项目结构](#项目结构)
- [踩过的坑 / 常见问题](#踩过的坑--常见问题)
- [致谢与许可](#致谢与许可)

---

## 快速概览

| 项目 | 值 |
|------|----|
| 入口 | `python main.py` |
| Python 版本 | **3.7**（CI 与本地兼容环境使用 3.7.17） |
| GUI 框架 | PyQt5 5.15.9 |
| 状态机后端 | `pyfcstm`（当前依赖分支：`dev/damnx`） |
| PlantUML | 仓库内 `docs/plantuml.jar`，**Java 运行时不打包，目标机自带** |
| 求解器 | `z3-solver`，二进制 libz3 通过 PyInstaller runtime hook 暴露 |
| 打包工具 | PyInstaller 5.x，spec 文件 `main.spec` 同时支持 onefile / onedir |
| CI 平台 | GitHub Actions ， 矩阵覆盖 `ubuntu-22.04` / `windows-2022` / `macos-15-intel`（全部 x86_64，全部免费 runner） |
| 目标运行环境 | Linux: Ubuntu 22.04.5 LTS x86_64 + `default-jre`（OpenJDK 11）；Win/Mac: 系统自带 Java |

---

## 功能矩阵

| 模块 | 文件 | 说明 |
|------|------|------|
| 主窗口 | `app/widget/main_window.py` | 状态树管理、文件 IO、菜单调度 |
| DSL ↔ UI 双向转换 | `app/utils/{dsl_to_ui,ui_to_dsl}.py` | 解析 `.fcstm` → UI 模型，反向再生 DSL |
| PlantUML 可视化 | `app/utils/show_state_graph.py` | 经 `plantumlcli` 调 `java -jar plantuml.jar` 出图 |
| 可达性 / 排他性校验 | `app/widget/dialog_reachability_val.py`、`dialog_exclusive_val.py` | 调 `pyfcstm.verify` 与 `pyfcstm.solver` |
| 生命周期 / 强制迁移管理 | `dialog_add_lifecycle.py`、`find_forced_transitions_and_remove.py` | UI 编辑 + DSL 后处理 |
| 模拟运行 | `app/widget/dialog_simulate.py` | `pyfcstm.simulate.SimulationRuntime` 驱动交互 |
| SysDeSim XML 导入 | `app/widget/dialog_sysdesim_validate.py` + `pyfcstm.convert.sysdesim` | XML → 多状态机 DSL |
| Excel / Word 导出 | `app/utils/export_to_{excel,word}.py` | openpyxl / python-docx |

---

## 运行环境要求

### 用打包产物时（最小集合）

- **OS**：Ubuntu 22.04.5 LTS（x86_64），其它较新的 glibc ≥ 2.35 的 Linux 一般也行。
- **Java**：`default-jre` / `openjdk-11-jre-headless` 之类，目标机自带 `java` 命令即可（**JRE 不在 artifact 里，按策略需要自己装**）。
- **Qt / X11 系统库**：**已经全部打进 artifact，不需要再 `apt install`**。
  - 包括 `libxcb-*` 全套子库、`libxkbcommon`、`libxkbcommon-x11`、`libfontconfig`、`libfreetype`、`libstdc++`、`libdbus-1`、`libpng16`、`libz`，以及我们额外补的 `libGL.so.1` / `libGLdispatch` / `libGLX` / `libX11` / `libX11-xcb` / `libXext` / `libxcb` / `libXau` / `libXdmcp` / `libbsd`。
  - 在干净的 `ubuntu:22.04` docker 容器里**只装** `default-jre-headless` 就能跑通全部 76 项 smoke check（不装 java 也能跑通 72 项，剩 4 项 WARN 标 java 缺失，不算失败）。
- **可选**：`graphviz`（PlantUML 在复杂层级状态图里调用 `dot` 做布局，没装也能出基本图，但复杂图会被退化）。
- **可选**：`xvfb`（无显示器机器上跑，配合 `QT_QPA_PLATFORM=offscreen`）。

### 从源码开发时

- Python **3.7.17**（不要用过旧的 3.7.1，本依赖栈里会触发 z3 / ctypes / Qt 相关崩溃）
- 上面的全部 Qt / Java / graphviz 系统依赖
- `make`（用于触发 `app/ui/Makefile` 的 `pyuic5` 转换）

---

## 使用打包好的 portable 版本

每次 `master` 分支推送都会触发 GitHub Actions，构建后会上传两份产物：

| Artifact 名 | 形态 | 用途 |
|-------------|------|------|
| `fcstm-ui-linux-x86_64` | 单个 ELF 可执行文件 | "丢一个文件就能跑" 场景（PyInstaller onefile） |
| `fcstm-ui-linux-x86_64.zip` | 解压即用的目录 | 启动更快、内部资源可见，附带 `run.sh` 包装脚本 |

下载方式：

1. 进入仓库的 **Actions** 标签页 → 选最近一次成功的 `Build & Verify` workflow
2. 在页面底部找 **Artifacts** 区，下载需要的 zip
3. 解压（onefile 解压后是单文件，onedir 解压后是目录）

运行：

```bash
# onefile
chmod +x fcstm-ui-linux-x86_64
./fcstm-ui-linux-x86_64

# onedir
unzip fcstm-ui-linux-x86_64.zip
cd fcstm-ui
./run.sh        # 包装脚本，等价于 ./fcstm-ui
```

带显示器的开发机直接双击 / 在 shell 里跑就行；无显示器的机器（CI、SSH 远程）用：

```bash
QT_QPA_PLATFORM=offscreen ./fcstm-ui --smoke-test    # 76 项自检
xvfb-run -a ./fcstm-ui                                # 在虚拟 X server 里跑真实 GUI
```

---

## 从源码运行

```bash
# 1. clone
git clone git@github.com:SingDanceRapPingPang/fcstm-ui.git
cd fcstm-ui

# 2. 系统依赖（见上一节）
sudo apt-get install -y \
    libxkbcommon-x11-0 libxcb-icccm4 libxcb-image0 libxcb-keysyms1 libxcb-randr0 \
    libxcb-render-util0 libxcb-shape0 libxcb-sync1 libxcb-xfixes0 \
    libxcb-xinerama0 libxcb-xkb1 libxcb-cursor0 \
    libegl1 libgl1 libglx-mesa0 libopengl0 \
    libfontconfig1 libdbus-1-3 libxkbcommon0 \
    default-jre-headless graphviz

# 3. venv + Python 依赖
python3.7 -m venv venv37
source venv37/bin/activate
python -m pip install "pip<23.1" "setuptools<69" "wheel<0.43"
python -m pip install -U -r requirements-build.txt -r requirements-test.txt -r requirements.txt

# 4. 把 Qt Designer 的 .ui 文件编译成 *_ui.py
make -C app/ui build

# 5. 跑起来
python main.py
# 或者跑无头自检
QT_QPA_PLATFORM=offscreen python main.py --smoke-test
```

`pyfcstm` 是从 `git+https://github.com/HansBug/pyfcstm.git@dev/damnx` 拉的，pip 会自己拉源码 + build wheel + 安装。如果网络不通可改用本地 path 安装：

```bash
pip install -e /path/to/pyfcstm
```

---

## 本地打包（PyInstaller）

`main.spec` 同时支持 onefile / onedir，通过环境变量切换：

```bash
# onedir（默认）：dist/fcstm-ui/ 目录
FCSTM_UI_BUILD_MODE=onedir pyinstaller --noconfirm main.spec

# onefile：dist/fcstm-ui 单个 ELF
FCSTM_UI_BUILD_MODE=onefile pyinstaller --noconfirm main.spec
```

打包完后建议立刻自检：

```bash
# 直接调内置自检
QT_QPA_PLATFORM=offscreen ./dist/fcstm-ui/fcstm-ui --smoke-test
QT_QPA_PLATFORM=offscreen ./dist/fcstm-ui --smoke-test
```

正常输出末尾应该是：

```
fcstm-ui smoke test: 76 OK / 0 WARN / 0 FAIL
fcstm-ui smoke test: PASSED
```

`main.spec` 里关键的几件事：

- `collect_dynamic_libs('z3', destdir='z3/lib')` + `pyinstaller_rthook_z3.py` —— 把 libz3 打进去，并通过 runtime hook 设置 `Z3_LIBRARY_PATH`，否则 frozen 后 `import z3` 会找不到 `libz3.so`。
- `collect_data_files('pyfcstm', includes=[...])` —— 把 `.g4` / `.tokens` / `.interp` / 模板 zip 等数据资源带进去，`pyfcstm` 在运行时通过 `importlib.resources` 读这些。
- `collect_data_files('qtawesome')` —— 带上 FontAwesome / Material 字体。
- `docs/plantuml.jar` 通过 `datas` 单独添加（**只带 jar，不带 JRE**）。
- `docs/StateMachine.fcstm` 同样作为 datas 打入，给 smoke test 当样本。
- `sys.path.insert(0, dirname(SPEC))` —— 让 `collect_submodules('app')` 在 spec 评估期能 import 到 `app` 包；不加这一行的话 `collect_submodules` 只返回顶层包名，后果就是 `app.utils.export_to_excel` 等懒加载模块全被漏掉。

---

## GitHub Actions CI 流程

`.github/workflows/build.yml` 分两个阶段：

### 阶段 1 · build

- 矩阵：`ubuntu-22.04` / `windows-2022` / `macos-15-intel`，**全部 x86_64**（不打 ARM）。三个 label 都在 GitHub free 矩阵上，无需 paid runner。
- 装 Qt 系统库 + JRE（Temurin 11，对齐目标机的 OpenJDK 11）。
- 先固定 Python 3.7 兼容的 pip 工具链，再 `python -m pip install -U -r requirements-build.txt -r requirements-test.txt -r requirements.txt`。
- 用 `python -m PyQt5.uic.pyuic` 现场编译 `.ui` → `*_ui.py`（这些文件在 `.gitignore` 里）。
- 跑两轮 PyInstaller：onedir + onefile。
- 每一轮打完都立刻在同一 runner 上跑 `--smoke-test`，跑通才继续。
- onedir 用 `shutil.make_archive` 压成 zip，并在目录内塞一个 `run.sh` 方便直接双击式启动。
- 上传两份 artifact。

### 阶段 2 · verify

- 全新的 `ubuntu-22.04` runner，**故意不装 Python deps、不 checkout 仓库**，只装：
  - 同一组 Qt 系统库
  - `default-jre-headless`
  - Temurin 11（保险冗余）
- `actions/download-artifact` 下载阶段 1 的产物。
- 解压 zip（onedir）。
- 对 onefile 和 onedir 各跑一遍 `--smoke-test`。
- 这一阶段证明：artifact 是真正自包含的，目标机只要有 Java + Qt 系统库就能跑。

---

## Smoke Test：最后一道防线

`app/smoke.py` 是 76 个独立的小检查，核心设计原则：

1. **任何一项失败都不能让其它项跑不下去** —— 每个 check 都包在自己的 try / except 里，最后统一打印 OK / WARN / FAIL 计数。
2. **入口尽量薄** —— `main.py` 解析 `--smoke-test` 后直接 import `app.smoke`，**绕过** `app/__init__.py`、`app.app` 那些会 eager-import PyQt5 / pyfcstm 的模块，所以即便依赖整个炸了 smoke test 还能启动并输出诊断。
3. **Java 是可选的环境依赖** —— 如果 `java` 不在 `PATH` 上，相关检查报 WARN 而不是 FAIL，并明确告诉你"jar 已经带了，但找不到 Java，无法进一步验证"。

检查项分四组：

| 组 | 检查 |
|----|------|
| Runtime | `python` 版本 / `frozen=True` / `_MEIPASS` / Qt 版本 / qtawesome 字体目录 |
| 模块 import | 60+ 个模块独立 import：PyQt5 子模块、qtmodern、qtawesome、qtpy、hbutils、plantumlcli、openpyxl、docx、jinja2、lxml、pyquery、antlr4、rich、prompt_toolkit、click、z3，以及全部 `pyfcstm.*` 与 `app.*` 子模块 |
| 资源 | `plantuml.jar` 存在且 ≥ 1MB / sample DSL 存在 |
| 端到端 | `java -version` / `java -jar plantuml.jar -version` / DSL parse + roundtrip / 生成 PUML 文本 / **PUML → PNG** 真正渲染并校验文件大小 / z3 跑一道简单 SAT / `SimulationRuntime` 实例化 / Qt event loop 跑 0.5s 后干净退出 |

跑法：

```bash
QT_QPA_PLATFORM=offscreen python main.py --smoke-test
QT_QPA_PLATFORM=offscreen ./dist/fcstm-ui/fcstm-ui --smoke-test
FCSTM_UI_SMOKE_TEST=1 QT_QPA_PLATFORM=offscreen ./fcstm-ui    # 等价于 --smoke-test
```

---

## 项目结构

```
.
├── main.py                    # 入口；先解析 --smoke-test，否则 from app import run_app
├── main.spec                  # PyInstaller spec（onefile / onedir 二合一）
├── pyinstaller_rthook_z3.py   # 把 _MEIPASS/z3/lib 写进 Z3_LIBRARY_PATH
├── requirements.txt           # 运行时依赖
├── requirements-build.txt     # PyInstaller 工具链
├── requirements-test.txt      # pytest / pytest-qt / pytest-xvfb
├── docs/
│   ├── plantuml.jar           # 打包资源（JRE 不打）
│   ├── StateMachine.fcstm     # smoke test 用的样本 DSL
│   └── *.fcstm / *.xml / *.docx
├── app/
│   ├── __init__.py            # 懒加载 run_app
│   ├── app.py                 # QApplication + 主题
│   ├── smoke.py               # 76 项自检
│   ├── config/                # 常量 + frozen-aware resource_path
│   ├── model/                 # UI 侧状态机模型
│   ├── ui/                    # .ui XML + Makefile (pyuic5 → *_ui.py)
│   ├── widget/                # QMainWindow / QDialog 子类
│   └── utils/                 # DSL ↔ UI、导出器、PlantUML 包装、校验
└── .github/workflows/
    └── build.yml              # 两阶段 CI（详见上文）
```

---

## 踩过的坑 / 常见问题

> 这一节是真的"踩过"，不是泛泛而谈，每条都对应具体的 commit / PR 修复。

### 1. `pyfcstm@dev/damnx` 与 `hbutils==0.9.3` 死锁

最初 `requirements.txt` 把 `hbutils` 钉在 `0.9.3`，但 `pyfcstm 0.3.0` 要求 `hbutils>=0.14.0`，pip 直接报 `ResolutionImpossible`。

**修法**：把 fcstm-ui 自己不强依赖的精确版本号全去掉，只列出真正直接用到的运行时库（`PyQt5`、`qtmodern`、`qtawesome`、`openpyxl`、`python-docx`、`hbutils`、`plantumlcli`、`z3-solver`），其它全交给 `pyfcstm` 通过传递依赖去解。

### 2. `app.utils.export_to_excel` 等子模块没被打进 PyInstaller 产物

`app/utils/__init__.py` 只显式 import 了 `create_formLayout_dialog`，其它 util 是被 widget 通过字符串 `importlib.import_module(...)` 或 `subprocess` 间接拉起来的，PyInstaller 静态分析看不到。

**修法**：

- `main.spec` 里加 `hiddenimports += collect_submodules('app')`、`collect_submodules('openpyxl')`、`collect_submodules('docx')`。
- 但只加这一行还不够：`collect_submodules('app')` 在 spec 评估期会因为 `app` 不在 `sys.path` 上而**静默返回空**。所以 spec 顶部还要加：
  ```python
  _PROJECT_ROOT = os.path.dirname(os.path.abspath(SPEC))
  if _PROJECT_ROOT not in sys.path:
      sys.path.insert(0, _PROJECT_ROOT)
  ```

### 3. PyInstaller frozen 后 `import z3` 找不到 `libz3.so`

`z3-solver` Python wrapper 在 `import` 时会去找原生库，PyInstaller 默认不打 `libz3.*`。

**修法**：spec 里 `binaries += collect_dynamic_libs('z3', destdir='z3/lib')`，再写一个 runtime hook `pyinstaller_rthook_z3.py`：

```python
import builtins, os, sys
base = getattr(sys, "_MEIPASS", None)
dirs = [os.path.join(base, "z3", "lib"), os.path.join(base, "z3"), base] if base else []
dirs = [d for d in dirs if os.path.isdir(d)]
if dirs:
    builtins.Z3_LIB_DIRS = dirs
    os.environ["Z3_LIBRARY_PATH"] = os.pathsep.join(dirs + [os.environ.get("Z3_LIBRARY_PATH", "")]).strip(os.pathsep)
```

### 4. 二阶段 verify 在 `ls -lhR extracted | head -40` 这一步炸成 exit 141

GitHub Actions 默认 `set -o pipefail`，`head` 关闭 stdin → `ls` 收到 SIGPIPE → 退出码 141 → 整步标记失败，但其实解压本身完全成功。

**修法**：把 `ls | head` 改成普通 `ls extracted` + `ls extracted/<dir> || true`，不再走管道。

### 5. macOS-13 已经在 2025-12 全面下线

最初想用 `macos-13` 当免费 x86_64 macOS runner，但它 2025-12-08 起就被 GitHub 下掉了。当前可用的 free x86_64 macOS label 是 `macos-15-intel`（参考 `actions/runner-images` 仓库主页的 "Available Images" 表），本仓库现在 macOS 矩阵就用这个。`macos-14` / `macos-latest` 现在默认指向 ARM Apple Silicon，与"只构建 x86_64"的策略不匹配，不要用。

### 6. Windows 上 `plantumlcli` 的 `NamedTemporaryFile` 触发 `PermissionError`

`plantumlcli.models.local._generate_uml_data` 用 `NamedTemporaryFile(prefix='puml', suffix='.puml')` 建临时文件，然后另开一个进程 (`save_text_file`) 再次以 `w+b` 打开同一个路径写入。Linux / macOS 上没问题；Windows 默认对 `NamedTemporaryFile` 持有独占句柄，第二次打开直接 `[Errno 13] Permission denied: '...puml'`。

这是 plantumlcli 的兼容性 bug，不是我们的。本仓库的对策：在 `app/utils/plantuml_safe_dump.py` 里写一个 `render_plantuml(plantuml_code, output_path, fmt)`，**直接调 `java -jar plantuml.jar -t<fmt> -o <outdir> <input.puml>`**，把 .puml 写到一个普通的 `tempfile.TemporaryDirectory` 里再跑——既不依赖 `NamedTemporaryFile` 的独占行为，也不依赖 `plantumlcli.LocalPlantuml._generate_uml_data` 的内部实现。Linux/macOS 行为与之前完全一致（PNG 字节相同），Windows 不再炸。`ShowStateGraph.dump_state_graph` 与 `app.utils.plantuml_render_cli` 都改走这条新路径。

### 7. `xcb plugin not found` 与 PyInstaller system-lib 行为

老版本 PyInstaller 默认会跳过一长串"系统提供的"库，因此早期文档里"目标机必须 apt install libxcb-* / libxkbcommon-x11-0 / libfontconfig1 …"的结论曾经是对的。

PyInstaller 会把 PyQt5 platform plugin 真正依赖的 **libxcb 子模块全套 / libxkbcommon / libfontconfig / libfreetype / libstdc++ / libdbus / libpng / libz / libglib** 自动 collect 进 onedir / onefile，所以那条结论现在过时了。本仓库实测过：本机 build 出 dist/ 后扔到一个**全新 `ubuntu:22.04`、零 `apt install`** 的 docker 容器里，PyQt5 还能起来，挡路的只剩下 **OpenGL / GLX / libX11 / libxcb 本体** 这一组。

这一组之所以默认不带，是 PyInstaller 维护着一份"system-driver excludelist"——`libGL.so.1` 等通常需要匹配目标机的 GPU 驱动，所以官方默认让目标机自己出。但对一个 **PyQt5 offscreen / 不真正 issue GL draw call** 的应用，把 build runner 上的 `libGL` 带过去**只要保证 dlopen 能拿到符号**就够了。所以 `main.spec` 里我们加了一个 `_collect_linux_system_libs()` helper，从 build 机的 `/usr/lib/x86_64-linux-gnu` 收下面这 10 个 SONAME 并塞进 `binaries`：

```
libGL.so.1   libGLdispatch.so.0   libGLX.so.0
libX11.so.6  libX11-xcb.so.1      libXext.so.6
libxcb.so.1  libXau.so.6          libXdmcp.so.6
libbsd.so.0
```

⚠️ 必须**用 SONAME 路径**（如 `/usr/lib/.../libGL.so.1`）传给 `binaries`，不是 `os.path.realpath`。PyInstaller 用 source basename 当 destination 文件名，dlopen 需要 SONAME 而不是 real name（`libGL.so.1.7.0`），realpath 一下产出的 dist 跑不起来。

⚠️ `libc.so.6` / `libpthread.so.0` / `libdl.so.2` / `ld-linux-x86-64.so.2` 这些 glibc 套件**不要带**——动态链接器是 ABI 边界。当前 build 用 `ubuntu-22.04` runner（glibc 2.35），所以目标机 glibc 必须 ≥ 2.35。

### 8. Java 版本对齐

目标 Ubuntu 22.04.5 LTS 的 `default-jre` 装的是 OpenJDK 11.0.30，所以 CI 的 `actions/setup-java@v4` 也固定到 `temurin/11`，避免 build 用 17、目标机用 11 出现 class file version 兼容性差异。

### 9. PlantUML 状态图缺 `dot`（graphviz）

PlantUML 渲染 state diagram 默认调 `dot` 做布局。如果目标机没装 `graphviz`，PlantUML 会回退成简单序列图并打印 `Error: Dot executable does not exist`。安装步骤里把 `graphviz` 列上是稳妥做法，特别是要画复杂层级状态图的时候。

### 10. 在 PyInstaller 产物里点"显示状态图"竟然又起了一个主程序

复现路径：双击打包好的 `fcstm-ui` → 加载一个 `.fcstm` → 点"显示状态图" → 弹出**第二个独立的主窗口**，然后第一个窗口里的对话框报"未能读取生成的 PNG 图像"。

根因：`dialog_show_graph._run_render_task` 用 `progress.start(sys.executable, ['-m', 'app.utils.plantuml_render_cli', ...])` 启子进程渲染。源码模式下 `sys.executable` 是 `python`，`-m foo.bar` 会被 Python 解释器消费；但 frozen 后 `sys.executable` 是 `fcstm-ui` 自己——**PyInstaller 的 bootloader 不实现 `-m`**，它把 `-m`、`app.utils.plantuml_render_cli`、`--input`、… 当成普通 `sys.argv` 再交给应用。应用的入口看到不是 `--smoke-test`，于是 `from app import run_app; run_app()` —— 一个新的 GUI 窗口就这么起来了。同时旧 dialog 等不到 PNG，于是报错。

修法：让打包好的 binary 同时充当 CLI dispatcher。`main.py` 里检测 `sys.argv[1] == '--plantuml-render-cli'`，把工作交给 `app.utils.plantuml_render_cli.main()`，然后退出。`dialog_show_graph._run_render_task` 在 `getattr(sys, "frozen", False)` 时用新的 `--plantuml-render-cli` 标志，源码模式继续走 `-m`。

`app/smoke.py` 里专门加了一项 `frozen self-dispatch render`，只在 frozen build 里激活，跑 `subprocess.run([sys.executable, '--plantuml-render-cli', ...])` 端到端验证子进程真的去渲染 PNG 而不是又起一个主程序。CI 每次都会跑到这一项。

---

## 致谢与许可

- 状态机后端：[`pyfcstm`](https://github.com/HansBug/pyfcstm)
- PlantUML：[plantuml.com](https://plantuml.com)
- 求解器：[Z3](https://github.com/Z3Prover/z3)
- 图标主题：[QtAwesome](https://github.com/spyder-ide/qtawesome)、[qtmodern](https://github.com/gmarull/qtmodern)

仓库根目录的 `LICENSE` 文件给出最终授权条款。

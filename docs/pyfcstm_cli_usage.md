> ![](media/image1.png){width="6.17995406824147in"
> height="1.0421041119860017e-2in"}![](media/image2.png){width="4.168525809273841e-2in"
> height="2.0217716535433072in"}**pyfcstm** 命令行使用整理
>
> ![](media/image3.png){width="5.179490376202975in"
> height="0.39601706036745404in"}来源:
>
> [![](media/image4.png){width="5.210739282589676e-2in"
> height="5.210739282589676e-2in"} 当前 PR: [HansBug/pyfcstm#74 ---
> docs(mds): plan timeline-based continuous-time]{.underline} [scenario
> verification]{.underline}](https://github.com/HansBug/pyfcstm/pull/74)
>
> ![](media/image5.png){width="5.210739282589676e-2in"
> height="5.210739282589676e-2in"} 上文对话中给出的 CLI 相关说明
>
> 本文所有 \"实跑输出\" 段落均为本机当前 dev/damnx 分支(HEAD =
> 4cb08343)实际重新执行
>
> pyfcstm 命令的真实输出,不是直接照搬 **PR** 评论里的旧片段(PR
> 里的输出在 CLI 收紧成 compact表格后已经过时)。运行环境: Python
> 3.10.10,样例 tmp/model1_fixed_v2 .xml 。
>
> 整理时间: 2026-04-28

![](media/image6.png){width="6.17995406824147in"
height="2.0843175853018373e-2in"}

+--------+---------------+-----------------------------------------------------+
| > 一、 | > **pyfcstm** | > 标准 **CLI** 速查 **(**附真实输出**)**            |
+--------+---------------+-----------------------------------------------------+

pyfcstm 是 Python Finite Control State Machine Framework
的命令行工具,通过控制台脚本 pyfcstm (或 python -m pyfcstm )调用
。下文⽰例中输入为以下最小 DSL 文件

  -----------------------------------
  ( ./
  .tmp/pr74_cli_demo/simple_machine
  .fcstm

  -----------------------------------

+----------------------------------------------------------------------+
| > def int counter = 0;                                               |
| >                                                                    |
| > state SimpleMachine {                                              |
| >                                                                    |
| > state Idle;                                                        |
| >                                                                    |
| > state Running;                                                     |
| >                                                                    |
| > state Stopped;                                                     |
| >                                                                    |
| > \[\*\] -\> Idle;                                                   |
| >                                                                    |
| > Idle -\> Running : : Start effect {                                |
| >                                                                    |
| > counter = 0;                                                       |
| >                                                                    |
| > };                                                                 |
| >                                                                    |
| > Running -\> Stopped : : Stop effect {                              |
| >                                                                    |
| > counter = counter + 1;                                             |
| >                                                                    |
| > };                                                                 |
| >                                                                    |
| > Stopped -\> Idle : : Reset;                                        |
| >                                                                    |
| > }                                                                  |
+----------------------------------------------------------------------+

> **1. pyfcstm plantuml ---** 生成 **PlantUML** 图

+----------------------------------------------------------------------+
| > venv/bin/python -m pyfcstm plant uml \\                            |
| >                                                                    |
| > -i ./ .tmp/pr74_cli_demo/simple_machine .fcstm \\                  |
| >                                                                    |
| > -o ./ .tmp/pr74_cli_demo/simple_machine .puml                      |
+----------------------------------------------------------------------+

> 实跑输出: 命令本身不在 stdout 打印任何内容,直接写出 simple_machine
> .puml 。文件前几行如下:
>
> **2. pyfcstm generate ---** 基于模板生成代码
>
> 模板可来自仓库内置 \--template ) 或外部目录 -t)。下面用内置 python
> 模板:

+----------------------------------------------------------------------+
| > venv/bin/python -m pyfcstm generate \\                             |
| >                                                                    |
| > -i ./ .tmp/pr74_cli_demo/simple_machine .fcstm \\                  |
| >                                                                    |
| > \--template python \\                                              |
| >                                                                    |
| > -o ./ .tmp/pr74_cli_demo/gen_python \\                             |
| >                                                                    |
| > \--clear                                                           |
+----------------------------------------------------------------------+

> 实跑输出: 命令在 stdout 静默,生成目录内容如下:

+----------------------------------------------------------------------+
| > ./ .tmp/pr74_cli_demo/gen_python/                                  |
| >                                                                    |
| > ├── machine .py                                                    |
| >                                                                    |
| > ├── README .md                                                     |
| >                                                                    |
| > └── README_zh .md                                                  |
+----------------------------------------------------------------------+

> **3. pyfcstm simulate ---** 仿真执行 **/ REPL**
>
> 支持交互 REPL 与批处理两种模式。这里用 -e 串接命令,以分号分隔:

+----------------------------------------------------------------------+
| > venv/bin/python -m pyfcstm simulate \\                             |
| >                                                                    |
| > -i ./ .tmp/pr74_cli_demo/simple_machine .fcstm \\                  |
| >                                                                    |
| > -e \"current; cycle; current; cycle Start; current\"               |
+----------------------------------------------------------------------+

> 实跑输出:

![](media/image7.png){width="4.386726815398076in"
height="1.2004593175853019e-2in"}

> \>\>\> current

![](media/image8.png){width="4.386726815398076in"
height="1.2004593175853019e-2in"}

> Cycle : 0
>
> Current State : SimpleMachine
>
> Variables :
>
> counter = 0
>
> REPL 中的热启动指令⽰例 (无单独本地实跑,语法参考):

+----------------------------------------------------------------------+
| > \> init SimpleMachine .Running counter=10                          |
| >                                                                    |
| > \> cycle                                                           |
+----------------------------------------------------------------------+

> **4. pyfcstm sysdesim --- SysDeSim XMI** 兼容导入 **/** 导出
>
> 把 SysDeSim 工具产出的 UML/XMI 状态机转换成 FCSTM
> 输出,并提供后续验证子命令。详细的真实运行⽰例见下文 \"二、 PR #74 中的
> CLI 实跑⽰例\"。

![](media/image9.png){width="6.17995406824147in"
height="2.0842082239720033e-2in"}

> ![](media/image10.jpeg){width="6.17995406824147in"
> height="1.0421041119860017e-2in"}![](media/image11.png){width="4.168525809273841e-2in"
> height="0.6357119422572178in"}二、 **PR #74** 中的 **CLI** 实跑⽰例
> **(**本机重新执行**)**
>
> 以下内容来源于 PR #74 的更新评论(原始发布时间 2026-04-16 14:27:02
> UTC),但所有 \"实跑输出\"段落都是 **2026-04-28** 在本机 **dev/damnx**
> 分支重新执行采集的,与 PR 里贴的旧版输出存在差异 ---当前 CLI 已经把
> conversion / validate 的摘要部分收紧成 compact table 形式。
>
> 准备
>
> 仓库根目录下先准备一个相对路径样例入口 :

+----------------------------------------------------------------------+
| > mkdir -p ./ .tmp/pr74_cli_demo                                     |
| >                                                                    |
| > ln -sfn \"\$(pwd)/tmp/model1_fixed_v2 .xml\" ./                    |
| > .tmp/pr74_cli_demo/model1_fixed_v2 .xml                            |
+----------------------------------------------------------------------+

> 后续命令统一使用:
>
> . 输入 XML: ./ .tmp/pr74_cli_demo/model1_fixed_v2 .xml
>
> . 输出目录: ![](media/image12.png){width="1.81334208223972in"
> height="0.16674431321084865in"}./.tmp/pr74clidemo/
>
> **1.** 兼容导出**: pyfcstm sysdesim**
>
> 命令:

+----------------------------------------------------------------------+
| > venv/bin/python -m pyfcstm sysdesim \\                             |
| >                                                                    |
| > -i ./ .tmp/pr74_cli_demo/model1_fixed_v2 .xml \\                   |
| >                                                                    |
| > -o ./ .tmp/pr74_cli_demo/convert_out \\                            |
| >                                                                    |
| > \--clear                                                           |
+----------------------------------------------------------------------+

> 实跑输出:

+-----------------------------------------------------------------------------------------------------------+
| > SysDeSim Conversion Complete                                                                            |
| >                                                                                                         |
| > Machine : StateMachine \[\_6t5EAIMsEfC7Audqg6Dubw\]                                                     |
| >                                                                                                         |
| > Source : ./ .tmp/pr74_cli_demo/model1_fixed_v2 .xml                                                     |
| >                                                                                                         |
| > Output Dir : .tmp/pr74_cli_demo/convert_out                                                             |
| >                                                                                                         |
| > Tick : not required                                                                                     |
| >                                                                                                         |
| > Outputs : 5                                                                                             |
|                                                                                                           |
| +-----------------------------------------------------+-----------------------------------+------+------+ |
| | \+                                                  | > file                            | > \+ | > \+ | |
| |                                                     |                                   | >    | >    | |
| | ![](media/image13.png){width="1.8075087489063868in" |                                   | > \| | > \| | |
| | height="6.072178477690289e-2in"}                    |                                   | > ln | >    | |
| |                                                     |                                   | >    | > \+ | |
| | > output                                            |                                   | > \+ |      | |
| | >                                                   |                                   |      |      | |
| | > status \| diag \|                                 |                                   |      |      | |
| |                                                     |                                   |      |      | |
| | \+                                                  |                                   |      |      | |
| +-----------------------------------------------------+-----------------------------------+------+------+ |
| | > \-\--+\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\--+    |                                   |      |      | |
| +-----------------------------------------------------+-----------------------------------+------+------+ |
| | > StateMachine                                      | > StateMachine .fcstm             | > \| | > \| | |
| |                                                     |                                   | > 24 | > OK | |
| +-----------------------------------------------------+-----------------------------------+------+------+ |
| | > \| ignored-unsuppo . . . \|                       |                                   |      |      | |
| +-----------------------------------------------------+-----------------------------------+------+------+ |
| | > StateMachine\_\_Control_region1                   | > StateMachine\_\_Control_region1 | > \| | > \| | |
| | >                                                   | > .fcstm                          | > 44 | > OK | |
| | > \| ignored-unsuppo . . . \|                       |                                   |      |      | |
| +-----------------------------------------------------+-----------------------------------+------+------+ |
| | > StateMachine\_\_Control_region2                   | > StateMachine\_\_Control_region2 | > \| | > \| | |
| | >                                                   | > .fcstm                          | > 50 | > OK | |
| | > \| ignored-unsuppo . . . \|                       |                                   |      |      | |
| +-----------------------------------------------------+-----------------------------------+------+------+ |
| | > StateMachine\_\_Control_region3                   | > StateMachine\_\_Control_region3 | > \| | > \| | |
| | >                                                   | > .fcstm                          | > 44 | > OK | |
| | > \| ignored-unsuppo . . . \|                       |                                   |      |      | |
| +-----------------------------------------------------+-----------------------------------+------+------+ |
| | > StateMachine\_\_Control_region4                   | > StateMachine\_\_Control_region4 | > \| | > \| | |
| | >                                                   | > .fcstm                          | > 29 | > OK | |
| | > \| ignored-unsuppo . . . \|                       |                                   | >    | >    | |
| |                                                     |                                   | > \+ | > \+ | |
| | \+                                                  |                                   |      |      | |
| +-----------------------------------------------------+-----------------------------------+------+------+ |
|                                                                                                           |
| > \-\--+\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\--+                                                          |
| >                                                                                                         |
| > Notes : compact diagnostics shown; use \--report-file to export full JSON diagnostics .                 |
+-----------------------------------------------------------------------------------------------------------+

> 与 PR 评论里的差异: 当前 CLI 已经把每个输出的
> validation/lines/semantic/diagnostics详情压缩进了一个紧凑表格,完整
> JSON 仍可通过 \--report-file 导出。

**2.** 仅做导入链路检查和报告**: pyfcstm sysdesim validate (**不带
**Phase11** 查询**)**

> 命令:

+----------------------------------------------------------------------+
| > venv/bin/python -m pyfcstm sysdesim validate \\                    |
| >                                                                    |
| > -i ./ .tmp/pr74_cli_demo/model1_fixed_v2 .xml \\                   |
| >                                                                    |
| > \--report-file ./ .tmp/pr74_cli_demo/timeline_import_report .json  |
+----------------------------------------------------------------------+

> 当前 CLI 语义:
>
> . 这是 **import report only**,不会假装做状态共存验证。
>
> ![](media/image14.png){width="5.210739282589676e-2in"
> height="5.210739282589676e-2in"} CLI 会打印导入摘要。
>
> . 完整 JSON 写到 \--report-file 。
>
> 实跑输出:

+-------------------------------------------------------------------------------------------+
| > SysDeSim Timeline Import Report Complete                                                |
| >                                                                                         |
| > Mode : import report only                                                               |
| >                                                                                         |
| > Machine : StateMachine                                                                  |
| >                                                                                         |
| > Interaction : 测试用例                                                                  |
| >                                                                                         |
| > Source : ./ .tmp/pr74_cli_demo/model1_fixed_v2 .xml                                     |
| >                                                                                         |
| > Tick : not required                                                                     |
| >                                                                                         |
| > Report : .tmp/pr74_cli_demo/timeline_import_report .json                                |
| >                                                                                         |
| > Model Import : graph_edges=21 inputs=4 events=16 steps=28 windows=2 durations=9         |
| >                                                                                         |
| > diagnostics=8                                                                           |
| >                                                                                         |
| > Outputs : 5                                                                             |
|                                                                                           |
| +-----------------------------------+---------------+---------------+-------------------+ |
| | \+                                | > defines     | > events      | > \+              | |
| |                                   |               |               | >                 | |
| | > output                          |               |               | > \| diag +       | |
| |                                   |               |               |                   | |
| | \+                                |               |               |                   | |
| +-----------------------------------+---------------+---------------+-------------------+ |
| | > StateMachine \| 0 \| 1                                          | > \|              | |
| |                                                                   | > duplicate-trans | |
| |                                                                   | > . . .           | |
| +-----------------------------------+---------------+---------------+-------------------+ |
| | > StateMachine\_\_Control_region1 | > 2           | > 3           | > \|              | |
| |                                   |               |               | > duplicate-trans | |
| |                                   |               |               | > . . .           | |
| +-----------------------------------+---------------+---------------+-------------------+ |
| | > StateMachine\_\_Control_region2 | > 1           | > 5           | > \|              | |
| |                                   |               |               | > duplicate-trans | |
| |                                   |               |               | > . . .           | |
| +-----------------------------------+---------------+---------------+-------------------+ |
| | > StateMachine\_\_Control_region3 | > 0           | > 4           | > \|              | |
| |                                   |               |               | > duplicate-trans | |
| |                                   |               |               | > . . .           | |
| +-----------------------------------+---------------+---------------+-------------------+ |
| | > StateMachine\_\_Control_region4 \| 0 \| 1                       | > \|              | |
| |                                                                   | > duplicate-trans | |
| | \+ + +                                                            | > . . . +         | |
| +-------------------------------------------------------------------+-------------------+ |
|                                                                                           |
| > Notes : compact diagnostics shown; full details are in timeline_import_report .json .   |
| >                                                                                         |
| > Scenario : scenario=测试用例 steps=28 temporal_constraints=11 bindings=5 traces=5       |
| >                                                                                         |
| > diagnostics=6                                                                           |
| >                                                                                         |
| > Initial States :                                                                        |
| >                                                                                         |
| > StateMachine -\> StateMachine .Idle                                                     |
| >                                                                                         |
| > StateMachine\_\_Control_region1 -\> StateMachine .Idle                                  |
| >                                                                                         |
| > StateMachine\_\_Control_region2 -\> StateMachine .Idle                                  |
| >                                                                                         |
| > StateMachine\_\_Control_region3 -\> StateMachine .Idle                                  |
| >                                                                                         |
| > StateMachine\_\_Control_region4 -\> StateMachine .Idle State Query : not requested .    |
| >                                                                                         |
| > Wrote SysDeSim timeline import report to                                                |
| >                                                                                         |
| > .tmp/pr74_cli_demo/timeline_import_report .json .                                       |
+-------------------------------------------------------------------------------------------+

> ![](media/image15.png){width="3.60584208223972in"
> height="2.0842082239720033e-2in"}![](media/image16.png){width="0.6878193350831147in"
> height="2.083880139982502e-2in"}![](media/image17.png){width="0.6878182414698163in"
> height="2.083880139982502e-2in"}![](media/image18.png){width="4.168525809273841e-2in"
> height="0.87540135608049in"}与 PR 评论里的差异: 旧输出标题为
> ![](media/image19.png){width="2.0842082239720033e-2in"
> height="0.1667432195975503in"}[Mode : import report only (no Phase11
> state query
> provided)]{.underline}![](media/image20.png){width="2.5380577427821523e-2in"
> height="0.16673775153105863in"} / Import Phase78 / Import Phase9
> Outputs / Import Phase10 /
> ![](media/image21.png){width="2.5380577427821523e-2in"
> height="0.16673775153105863in"}[Phase11 :]{.underline} . . .
> ![](media/image22.png){width="2.0842082239720033e-2in"
> height="0.1667432195975503in"};当前 CLI 已重命名为 Mode : import
> report only / Model Import / Outputs (table) / Scenario / State Query
> : not requested. ,层级和命名都更直观。
>
> **3.** 指定 **Phase11** 查询**,**且结果为 **SAT: CLI** 同时打印摘要
> **+ witness table**
>
> 这里查询 region2 .H .L 和 region3 .X 是否可共存。
>
> 命令:

+----------------------------------------------------------------------+
| > venv/bin/python -m pyfcstm sysdesim validate \\                    |
| >                                                                    |
| > -i ./ .tmp/pr74_cli_demo/model1_fixed_v2 .xml \\                   |
| >                                                                    |
| > \--left-machine-alias StateMachine\_\_Control_region2 \\           |
| >                                                                    |
| > \--left-state H .L \\                                              |
| >                                                                    |
| > \--right-machine-alias StateMachine\_\_Control_region3 \\          |
| >                                                                    |
| > \--right-state X \\                                                |
| >                                                                    |
| > \--report-file ./ .tmp/pr74_cli_demo/phase11_sat_report .json      |
+----------------------------------------------------------------------+

> 当前 CLI 语义:
>
> . 这是 **import report + state query**。
>
> . 当结果是 SAT 时,除了 JSON,还会在 CLI 上完整打印一个 witness timeline
> table。
>
> . 表格列里: Main/R1/R2/R3/R4 分别对应主输出和各 region 输出
> co=start/yes 标记首次共存点和后续持续共存点。
>
> 实跑输出:

![](media/image23.png){width="4.168525809273841e-2in"
height="0.6565540244969379in"}

+---------------------------------------------------------------------------+
| +------------------------------------------------------------------+----+ |
| | > StateMachine\_\_Control_region1 -\> StateMachine .Idle         | \| | |
| | >                                                                |    | |
| | > StateMachine\_\_Control_region2 -\> StateMachine .Idle         |    | |
| | >                                                                |    | |
| | > StateMachine\_\_Control_region3 -\> StateMachine .Idle         |    | |
| | >                                                                |    | |
| | > StateMachine\_\_Control_region4 -\> StateMachine .Idle         |    | |
| | >                                                                |    | |
| | > State Query : StateMachine\_\_Control_region2 :StateMachine    |    | |
| | > .Control .H .L \<-\>                                           |    | |
| | >                                                                |    | |
| | > StateMachine\_\_Control_region3 :StateMachine .Control .X      |    | |
| | >                                                                |    | |
| | > scope : both \| candidates : 101 \| status : SAT               |    | |
| | >                                                                |    | |
| | > first coexistence :                                            |    | |
| | > tau\_\_StateMachine\_\_Control_region3\_\_s20\_\_1 = 67        |    | |
| | >                                                                |    | |
| | > note : 从                                                      |    | |
| | > \`tau\_\_StateMachine\_\_Control_region3\_\_s20\_\_1\`         |    | |
| | > 对应的时刻开始,\`StateMachine\_\_Control_region2\` 处于        |    | |
| | >                                                                |    | |
| | > \`StateMachine .Control .H                                     |    | |
| | > .L\`,\`StateMachine\_\_Control_region3\` 处于\`StateMachine    |    | |
| | > .Control.X\`,因此两者开始共存。                                |    | |
| | >                                                                |    | |
| | > witness timeline :                                             |    | |
| | >                                                                |    | |
| | > \- t : solved continuous-time value .                          |    | |
| | >                                                                |    | |
| | > \- pt : \`sXX\` is one imported step, \`tau@ . . .\` is one    |    | |
| | > hidden auto point .                                            |    | |
| | >                                                                |    | |
| | > \- act : actions observed at that point .                      |    | |
| | >                                                                |    | |
| | > \- co : \`start\` marks the first coexistence point; \`yes\`   |    | |
| | > means coexistence still holds .                                |    | |
| | >                                                                |    | |
| | > \| t \| pt \| act \| Main \| R1 \| R2 \| R3 \| R4 \| co        |    | |
| +------------------------------------------------------------------+----+ |
| | > \| \-\-- \| \-\-\-\-\-\-- \| \-\-\-\-\-\-\-\-\-\-- \|          | \| | |
| | > \-\-\-\-\-\-- \| \-\-\-\-\-- \| \-\-\-- \| \-\-\-- \| \-\-\--  |    | |
| | > \| \-\-\-\--                                                   |    | |
| +------------------------------------------------------------------+----+ |
| | > \| 0 \| initial \| - \| Idle \| Idle \| Idle \| Idle \| Idle   | \| | |
| | > \|                                                             |    | |
| +------------------------------------------------------------------+----+ |
| | > \| 0 \| s01 \| emit(Sig1) \| Control \| A \| F \| J \| V \|    | \| | |
| +------------------------------------------------------------------+----+ |
| | > \| 0 \| s02 \| y=2300 \| Control \| A \| F \| J \| V \|        | \| | |
| +------------------------------------------------------------------+----+ |
| | > \| 0 \| s03 \| z=2000 \| Control \| A \| F \| J \| V \|        | \| | |
| +------------------------------------------------------------------+----+ |
| | > \| 0 \| s04 \| z=1800 \| Control \| A \| F \| J \| V \|        | \| | |
| +------------------------------------------------------------------+----+ |
| | > \| 1 \| s05 \| - \| Control \| A \| F \| J \| V \|             | \| | |
| +------------------------------------------------------------------+----+ |
| | > \| 1 \| s06 \| y=2099 \| Control \| B \| F \| J \| V \|        | \| | |
| +------------------------------------------------------------------+----+ |
| | > \| 1 \| s07 \| z=1300 \| Control \| B \| F \| J \| V \|        | \| | |
| +------------------------------------------------------------------+----+ |
| | > \| 1 \| s08 \| z=1100 \| Control \| B \| W \| J \| V \|        | \| | |
| +------------------------------------------------------------------+----+ |
| | > \| 1 \| s09 \| - \| Control \| B \| W \| J \| V \|             | \| | |
| +------------------------------------------------------------------+----+ |
| | > \| 1 \| s10 \| y=1300 \| Control \| B \| W \| J \| V \|        | \| | |
| +------------------------------------------------------------------+----+ |
| | > \| 2 \| s11 \| - \| Control \| B \| W \| J \| V \|             | \| | |
| +------------------------------------------------------------------+----+ |
| | > \| 2 \| s12 \| y=1199 \| Control \| B \| W \| J \| V \|        | \| | |
| +------------------------------------------------------------------+----+ |
| | > \| 2 \| s13 \| - \| Control \| B \| W \| J \| V \|             | \| | |
| +------------------------------------------------------------------+----+ |
| | > \| 21 \| s14 \| emit(Sig2) \| Control \| C \| H .L \| K \| V   | \| | |
| | > \|                                                             |    | |
| +------------------------------------------------------------------+----+ |
| | > \| 21 \| s15 \| - \| Control \| D \| H .L \| K \| V \|         | \| | |
| +------------------------------------------------------------------+----+ |
| | > \| 31 \| s16 \| - \| Control \| D \| H .L \| K \| V \|         | \| | |
| +------------------------------------------------------------------+----+ |
| | > \| 46 \| s17 \| emit(Sig9) \| Control \| D \| H .M \| K \| V   | \| | |
| | > \|                                                             |    | |
| +------------------------------------------------------------------+----+ |
| | > \| 56 \| s18 \| emit(Sig6) \| Control \| D \| H .L \| K \| V   | \| | |
| | > \|                                                             |    | |
| +------------------------------------------------------------------+----+ |
| | > \| 56 \| s19 \| - \| Control \| D \| H .L \| K \| V \|         | \| | |
| +------------------------------------------------------------------+----+ |
| | > \| 66 \| s20 \| emit(Sig4) \| Control \| D \| H .L \| S \| V   | \| | |
| | > \|                                                             |    | |
| +------------------------------------------------------------------+----+ |
| | > \| 67 \| tau@s20 \| tau :R3 S-\>X \| Control \| D \| H .L \| X | \| | |
| | > \| V \| start                                                  |    | |
| +------------------------------------------------------------------+----+ |
| | > \| 68 \| s21 \| - \| Control \| D \| H .L \| X \| V \| yes     | \| | |
| +------------------------------------------------------------------+----+ |
| | > \| 78 \| s22 \| - \| Control \| D \| H .L \| X \| V \| yes     | \| | |
| +------------------------------------------------------------------+----+ |
| | > \| 83 \| s23 \| emit(Sig4) \| Control \| D \| H .L \| S \| V   | \| | |
| | > \|                                                             |    | |
| +------------------------------------------------------------------+----+ |
| | > \| 84 \| tau@s23 \| tau :R3 S-\>X \| Control \| D \| H .L \| X | \| | |
| | > \| V \| yes                                                    |    | |
| +------------------------------------------------------------------+----+ |
| | > \| 85 \| s24 \| rmt=4999 \| Control \| D \| H .L \| X \| V \|  | \| | |
| | > yes                                                            |    | |
| +------------------------------------------------------------------+----+ |
| | > \| 113 \| s25 \| - \| Control \| D \| H .L \| X \| V \| yes    | \| | |
| +------------------------------------------------------------------+----+ |
| | > \| 118 \| s26 \| emit(Sig5) \| Control \| EState \| H .L \| X  | \| | |
| | > \| V \| yes                                                    |    | |
| +------------------------------------------------------------------+----+ |
| | > \| 118 \| s27 \| emit(Sig8) \| Control \| EState \| G \| X \|  | \| | |
| | > V \|                                                           |    | |
| +------------------------------------------------------------------+----+ |
| | > \| 118 \| s28 \| emit(Sig7) \| Control \| EState \| G \| X \|  | \| | |
| | > V \|                                                           |    | |
| +------------------------------------------------------------------+----+ |
| | Wrote SysDeSim timeline validation report to                     |    | |
| |                                                                  |    | |
| | > .tmp/pr74_cli_demo/phase11_sat_report .json .                  |    | |
| +------------------------------------------------------------------+----+ |
+---------------------------------------------------------------------------+

> ![](media/image24.png){width="0.4689665354330709in"
> height="2.083880139982502e-2in"}与 PR 评论里的差异: 标题已从 SysDeSim
> State Query Validation Complete /
> ![](media/image25.png){width="2.0842082239720033e-2in"
> height="0.16674103237095364in"}[Mode :]{.underline}
>
> ![](media/image26.png){width="2.58453302712161in"
> height="2.0843175853018373e-2in"}![](media/image27.png){width="0.45854549431321084in"
> height="2.0843175853018373e-2in"}![](media/image28.png){width="2.0009284776902887in"
> height="2.084536307961505e-2in"}[import report + Phase11 state
> query]{.underline}![](media/image29.png){width="2.3532370953630796e-2in"
> height="0.16674103237095364in"} 等改成 SysDeSim State Query Complete /
> ![](media/image30.png){width="2.353127734033246e-2in"
> height="0.16674103237095364in"}[Mode : import report + state
> query]{.underline}![](media/image31.png){width="2.7358923884514434e-2in"
> height="0.16674212598425198in"},核心 witness table
> 内容(t/pt/act/Main/R1\.../co)未变。
>
> **4.** 指定 **Phase11** 查询**,**但结果为 **UNSAT: CLI**
> 只打印结论和原因**,**不打印 **witness table**
>
> 这里查询 region2 .H .M 和 region3 .X 是否可共存。
>
> 命令:

+----------------------------------------------------------------------+
| > venv/bin/python -m pyfcstm sysdesim validate \\                    |
| >                                                                    |
| > -i ./ .tmp/pr74_cli_demo/model1_fixed_v2 .xml \\                   |
| >                                                                    |
| > \--left-machine-alias StateMachine\_\_Control_region2 \\           |
| >                                                                    |
| > \--left-state M \\                                                 |
| >                                                                    |
| > \--right-machine-alias StateMachine\_\_Control_region3 \\          |
| >                                                                    |
| > \--right-state X \\                                                |
| >                                                                    |
| > \--report-file ./ .tmp/pr74_cli_demo/phase11_unsat_report .json    |
+----------------------------------------------------------------------+

> 实跑输出:

+-------------------------------------------------------------------------------------------+
| > SysDeSim State Query Complete                                                           |
| >                                                                                         |
| > Mode : import report + state query                                                      |
| >                                                                                         |
| > Machine : StateMachine                                                                  |
| >                                                                                         |
| > Interaction : 测试用例                                                                  |
| >                                                                                         |
| > Source : ./ .tmp/pr74_cli_demo/model1_fixed_v2 .xml                                     |
| >                                                                                         |
| > Tick : not required                                                                     |
| >                                                                                         |
| > Report : .tmp/pr74_cli_demo/phase11_unsat_report .json                                  |
| >                                                                                         |
| > Model Import : graph_edges=21 inputs=4 events=16 steps=28 windows=2 durations=9         |
| >                                                                                         |
| > diagnostics=8                                                                           |
| >                                                                                         |
| > Outputs : 5                                                                             |
|                                                                                           |
| +-----------------------------------+---------------+---------------+-------------------+ |
| | \+                                | > defines     | > events      | > \+              | |
| |                                   |               |               | >                 | |
| | > output                          |               |               | > \| diag +       | |
| |                                   |               |               |                   | |
| | \+                                |               |               |                   | |
| +-----------------------------------+---------------+---------------+-------------------+ |
| | > StateMachine \| 0 \| 1                                          | > \|              | |
| |                                                                   | > duplicate-trans | |
| |                                                                   | > . . .           | |
| +-----------------------------------+---------------+---------------+-------------------+ |
| | > StateMachine\_\_Control_region1 | > 2           | > 3           | > \|              | |
| |                                   |               |               | > duplicate-trans | |
| |                                   |               |               | > . . .           | |
| +-----------------------------------+---------------+---------------+-------------------+ |
| | > StateMachine\_\_Control_region2 | > 1           | > 5           | > \|              | |
| |                                   |               |               | > duplicate-trans | |
| |                                   |               |               | > . . .           | |
| +-----------------------------------+---------------+---------------+-------------------+ |
| | > StateMachine\_\_Control_region3 | > 0           | > 4           | > \|              | |
| |                                   |               |               | > duplicate-trans | |
| |                                   |               |               | > . . .           | |
| +-----------------------------------+---------------+---------------+-------------------+ |
| | > StateMachine\_\_Control_region4 \| 0 \| 1                       | > \|              | |
| |                                                                   | > duplicate-trans | |
| | \+ + +                                                            | > . . . +         | |
| +-------------------------------------------------------------------+-------------------+ |
|                                                                                           |
| > Notes : compact diagnostics shown; full details are in phase11_unsat_report .json .     |
| >                                                                                         |
| > Scenario : scenario=测试用例 steps=28 temporal_constraints=11 bindings=5 traces=5       |
| >                                                                                         |
| > diagnostics=6                                                                           |
| >                                                                                         |
| > Initial States :                                                                        |
| >                                                                                         |
| > StateMachine -\> StateMachine .Idle                                                     |
| >                                                                                         |
| > StateMachine\_\_Control_region1 -\> StateMachine .Idle                                  |
| >                                                                                         |
| > StateMachine\_\_Control_region2 -\> StateMachine .Idle                                  |
| >                                                                                         |
| > StateMachine\_\_Control_region3 -\> StateMachine .Idle                                  |
| >                                                                                         |
| > StateMachine\_\_Control_region4 -\> StateMachine .Idle                                  |
| >                                                                                         |
| > State Query : StateMachine\_\_Control_region2 :StateMachine .Control .H .M \<-\>        |
| >                                                                                         |
| > StateMachine\_\_Control_region3 :StateMachine .Control .X                               |
| >                                                                                         |
| > scope : both \| candidates : 8 \| status : UNSAT                                        |
| >                                                                                         |
| > reason : Both states appear in the discrete trajectories, but the timing constraints    |
| > leave no overlapping observation point .                                                |
| >                                                                                         |
| > Wrote SysDeSim timeline validation report to .tmp/pr74_cli_demo/phase11_unsat_report    |
| > .json .                                                                                 |
+-------------------------------------------------------------------------------------------+

![](media/image32.png){width="5.210739282589676e-2in"
height="5.210739282589676e-2in"}**5.** 当前 **CLI** 用法总结

  -----------------
   pyfcstm sysdesim
              . . .

  -----------------

> ![](media/image33.png){width="6.252843394575679e-2in"
> height="6.252843394575679e-2in"} 做兼容导出,写
> ![](media/image34.png){width="0.5002318460192476in"
> height="0.1667432195975503in"}fcstm 输出族;摘要以紧凑表格在 stdout
> 给出,完整 conversion report 通过 \--report-file 导出 JSON。
>
> ![](media/image35.png){width="5.210739282589676e-2in"
> height="5.210739282589676e-2in"} pyfcstm sysdesim validate . . .
> \--report-file . . .
>
> ![](media/image36.png){width="0.9796216097987751in"
> height="2.083989501312336e-2in"}![](media/image37.png){width="6.252843394575679e-2in"
> height="6.252843394575679e-2in"} 不带 \--left/\--right-\* : 只做
> import/report pipeline 检查,CLI 明确标成
> ![](media/image38.png){width="2.0842082239720033e-2in"
> height="0.16673884514435697in"}[Mode : import]{.underline}
>
> report only 。
>
> ![](media/image39.png){width="6.252843394575679e-2in"
> height="6.252843394575679e-2in"} 带齐 \--left-machine-alias /
> \--left-state / \--right-machine-alias / \--right-state : 做状态共存
> (Phase11) 查询,标题为 Mode : import report + state query。
>
> ![](media/image40.png){width="6.252843394575679e-2in"
> height="6.252952755905512e-2in"} 查询结果如果是 SAT : CLI 会打印完整
> witness timeline table。
>
> ![](media/image41.png){width="6.252843394575679e-2in"
> height="6.252952755905512e-2in"} 查询结果如果是 UNSAT : CLI
> 只打印结论和 reason,不伪造 witness。
>
> . 如果不传 \--report-file , validate 仍然保持脚本友好的行为: 完整 JSON
> 直接输出到 stdout。

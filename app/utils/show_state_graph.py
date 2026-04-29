from pyfcstm.model import parse_dsl_node_to_state_machine
from pyfcstm.model.plantuml import PlantUMLOptions
from pyfcstm.dsl import parse_with_grammar_entry
from plantumlcli import LocalPlantuml, RemotePlantuml
from plantumlcli.models.base import PlantumlResourceType
import os

from ..model import StateManager
from ..config import PLANTUML_JAR_PATH
from ..utils.plantuml_safe_dump import render_plantuml
from ..utils.ui_to_dsl import state_manager_to_dsl


class ShowStateGraph:
    FORMAT_TYPES = {
        "png": PlantumlResourceType.PNG,
        "svg": PlantumlResourceType.SVG,
        "eps": PlantumlResourceType.EPS,
        "pdf": PlantumlResourceType.PDF,
        "txt": PlantumlResourceType.TXT,
    }

    @classmethod
    def build_plantuml_code(cls, state_manager: StateManager, options=None) -> str:
        dsl_str = state_manager_to_dsl(state_manager)
        ast_node = parse_with_grammar_entry(dsl_str, entry_name='state_machine_dsl')
        model = parse_dsl_node_to_state_machine(ast_node)
        plantuml_options = PlantUMLOptions.from_value(options)
        return model.to_plantuml(plantuml_options)

    @classmethod
    def _backend(cls):
        if PLANTUML_JAR_PATH and os.path.exists(PLANTUML_JAR_PATH):
            return LocalPlantuml.autoload(plantuml=PLANTUML_JAR_PATH)
        return RemotePlantuml.autoload(
            host=os.environ.get("PLANTUML_HOST", "http://www.plantuml.com/plantuml")
        )

    @classmethod
    def dump_state_graph(cls, state_manager: StateManager, output_file: str, output_format: str = "png", options=None):
        plantuml_code = cls.build_plantuml_code(state_manager, options)
        output_format = (output_format or "png").lower()
        if output_format in {"puml", "plantuml", "txt"}:
            with open(output_file, "w", encoding="utf-8") as f:
                f.write(plantuml_code)
            return

        # Prefer the local-jar path via our cross-platform safe dumper.
        # plantumlcli's own LocalPlantuml backend has a Windows-specific
        # NamedTemporaryFile bug; we sidestep it entirely.
        if PLANTUML_JAR_PATH and os.path.exists(PLANTUML_JAR_PATH):
            render_plantuml(plantuml_code, output_file, output_format)
            return

        # Fall back to remote rendering when no JAR is available.
        backend = cls._backend()
        backend.dump(output_file, cls.FORMAT_TYPES.get(output_format, output_format), plantuml_code)

    @classmethod
    def show_state_graph(cls, state_manager: StateManager, png_file, options=None):
        cls.dump_state_graph(state_manager, png_file, "png", options)

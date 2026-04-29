"""
XML to FCSTM converter utility.
"""
import os
import re
import json
from typing import Any, Dict, List, Optional, Tuple

from pyfcstm.convert.sysdesim import build_sysdesim_conversion_report, convert_sysdesim_xml_to_dsls
from pyfcstm.dsl import parse_with_grammar_entry
from pyfcstm.model import parse_dsl_node_to_state_machine


DEFAULT_TICK_DURATION_MS = None


def _safe_output_name(name: str) -> str:
    name = re.sub(r'[<>:"/\\|?*\x00-\x1f]+', "_", name).strip().strip(".")
    return name or "StateMachine"


def _unique_output_path(output_directory: str, output_name: str) -> str:
    base_name = _safe_output_name(output_name)
    candidate = os.path.join(output_directory, f"{base_name}.fcstm")
    index = 2
    while os.path.exists(candidate):
        candidate = os.path.join(output_directory, f"{base_name}_{index}.fcstm")
        index += 1
    return candidate


def convert_xml_to_fcstm(
    xml_file_path: str,
    output_directory: str,
    tick_duration_ms: Optional[float] = DEFAULT_TICK_DURATION_MS,
    machine_name: Optional[str] = None,
    machine_id: Optional[str] = None,
    report_file: Optional[str] = None,
    generate_report: bool = False,
) -> Tuple[List[str], str, Optional[Dict[str, Any]]]:
    try:
        if not os.path.exists(xml_file_path):
            raise Exception(f"XML文件不存在: {xml_file_path}")

        os.makedirs(output_directory, exist_ok=True)
        dsl_outputs = convert_sysdesim_xml_to_dsls(
            xml_file_path,
            machine_name=machine_name,
            machine_id=machine_id,
            tick_duration_ms=tick_duration_ms,
        )
        if not dsl_outputs:
            raise Exception("转换失败: 未能生成有效的状态机")

        generated_files = []
        output_file_by_name = {}
        for output_name, dsl_code in dsl_outputs.items():
            ast_node = parse_with_grammar_entry(dsl_code, entry_name="state_machine_dsl")
            parse_dsl_node_to_state_machine(ast_node)

            output_path = _unique_output_path(output_directory, output_name)
            with open(output_path, "w", encoding="utf-8") as f:
                f.write(dsl_code)
            generated_files.append(output_path)
            output_file_by_name[output_name] = output_path

        report_data = None
        if generate_report or report_file:
            report = build_sysdesim_conversion_report(
                xml_file_path,
                machine_name=machine_name,
                machine_id=machine_id,
                tick_duration_ms=tick_duration_ms,
            )
            report_data = report.to_dict()
            for output_item in report_data.get("outputs", []):
                output_name = output_item.get("output_name")
                if output_name in output_file_by_name:
                    output_item["output_file"] = output_file_by_name[output_name]

        if report_file and report_data is not None:
            write_sysdesim_conversion_report(report_data, report_file)

        return generated_files, "", report_data
    except Exception as e:
        raise Exception(f"XML转换失败: {str(e)}")


def _short_diagnostic_code(code: str) -> str:
    short_code_map = {
        "parallel_main_machine_semantic_downgrade": "parallel-main",
        "parallel_split_semantic_downgrade": "parallel-split",
        "transition_effect_semantic_downgrade": "tx-effect",
    }
    if code in short_code_map:
        return short_code_map[code]
    if code.endswith("_semantic_downgrade"):
        code = code[: -len("_semantic_downgrade")]
    return code.replace("_", "-")


def _conversion_output_status(output_item: Dict[str, Any]) -> str:
    failed_checks = []
    checks = [
        ("parser", "parser_roundtrip_ok"),
        ("model", "model_build_ok"),
        ("guards", "guard_variables_defined"),
        ("events", "event_paths_valid"),
        ("init", "composite_states_have_init"),
    ]
    for label, key in checks:
        if output_item.get(key) is False:
            failed_checks.append(label)
    return "OK" if not failed_checks else "FAIL({})".format(",".join(failed_checks))


def _conversion_output_diagnostics(output_item: Dict[str, Any]) -> str:
    diagnostics = output_item.get("diagnostics") or []
    codes = [
        item.get("code", "")
        for item in diagnostics
        if isinstance(item, dict) and item.get("code")
    ]
    if codes:
        summary = ",".join(_short_diagnostic_code(code) for code in codes)
    elif output_item.get("semantic_note"):
        summary = "semantic"
    else:
        summary = "-"
    if len(summary) > 36:
        return summary[:33] + "..."
    return summary


def format_sysdesim_conversion_report_table(report_data: Dict[str, Any]) -> str:
    headers = ["output", "file", "ln", "status", "diag"]
    rows = []
    for output_item in report_data.get("outputs", []) or []:
        if not isinstance(output_item, dict):
            continue
        output_file = output_item.get("output_file") or "{}.fcstm".format(output_item.get("output_name", ""))
        rows.append(
            [
                str(output_item.get("output_name", "")),
                os.path.basename(str(output_file)),
                str(output_item.get("dsl_line_count", "")),
                _conversion_output_status(output_item),
                _conversion_output_diagnostics(output_item),
            ]
        )

    widths = []
    max_widths = [36, 42, 4, 24, 36]
    for index, header in enumerate(headers):
        max_len = max([len(header)] + [len(row[index]) for row in rows])
        widths.append(min(max_len, max_widths[index]))

    def fit(text: str, width: int, align_right: bool = False) -> str:
        if len(text) > width:
            text = text[: max(width - 3, 0)] + ("..." if width > 3 else "")
        return text.rjust(width) if align_right else text.ljust(width)

    border = "+-" + "-+-".join("-" * width for width in widths) + "-+"
    lines = [
        "SysDeSim 转换诊断报告",
        f"XML: {report_data.get('source_xml_path', '')}",
        f"Selected machine: {report_data.get('selected_machine_name', '')}",
        f"Outputs: {report_data.get('output_count', len(rows))}",
        "",
        border,
        "| " + " | ".join(fit(header, width) for header, width in zip(headers, widths)) + " |",
        border,
    ]
    for row in rows:
        lines.append(
            "| "
            + " | ".join(
                fit(value, width, align_right=(headers[index] == "ln"))
                for index, (value, width) in enumerate(zip(row, widths))
            )
            + " |"
        )
    lines.extend(
        [
            border,
            "",
            "Notes: compact diagnostics shown; use 保存详细 JSON to export full diagnostics.",
        ]
    )
    return "\n".join(lines)


def write_sysdesim_conversion_report(report_data: Dict[str, Any], report_file: str) -> None:
    report_dir = os.path.dirname(os.path.abspath(report_file))
    if report_dir:
        os.makedirs(report_dir, exist_ok=True)
    with open(report_file, "w", encoding="utf-8") as f:
        json.dump(report_data, f, ensure_ascii=False, indent=2, sort_keys=True)


def get_fcstm_files_in_directory(directory: str) -> List[str]:
    if not os.path.exists(directory):
        return []
    return sorted(
        os.path.join(directory, filename)
        for filename in os.listdir(directory)
        if filename.endswith(".fcstm")
    )

from ..model import State, StateManager


def _indent_text(text: str, indent: int) -> str:
    prefix = "    " * indent
    return "\n".join(prefix + line if line else line for line in text.splitlines())


def _format_statement_block(action: str, indent: int) -> str:
    action = (action or "").strip()
    if not action:
        return ""

    if "\n" in action or action.startswith("if "):
        return _indent_text(action, indent)

    lines = []
    for item in action.split(";"):
        item = item.strip()
        if item:
            lines.append(("    " * indent) + item.rstrip(";") + ";")
    return "\n".join(lines)


def _strip_raw_semicolon(text: str) -> str:
    return text.strip()


def format_lifecycle_item(lifecycle_item, indent=0):
    if not lifecycle_item:
        return ""
    if lifecycle_item.get("raw"):
        return _strip_raw_semicolon(lifecycle_item["raw"])

    lifecycle_type = lifecycle_item.get("type", "")
    lifecycle_name = lifecycle_item.get("name", "")
    action = lifecycle_item.get("action", "")
    is_abstract = lifecycle_item.get("is_abstract", False)
    comment = lifecycle_item.get("comment", "")
    ref = lifecycle_item.get("ref", "")

    prefix = ">> " if lifecycle_type.startswith(">> ") else ""
    base_type = lifecycle_type[3:] if prefix else lifecycle_type
    result = f"{prefix}{base_type}"

    if is_abstract:
        result += " abstract"
    if lifecycle_name:
        result += f" {lifecycle_name}"
    if ref:
        return f"{result} ref {ref};"
    if is_abstract:
        if comment:
            return f"{result} /*\n{_indent_text(comment, indent + 1)}\n{'    ' * indent}*/"
        return f"{result};"

    body = _format_statement_block(action, indent + 1)
    if body:
        return f"{result} {{\n{body}\n{'    ' * indent}}}"
    return f"{result} {{}}"


def format_transition_item(transition_item, indent=0):
    if not transition_item:
        return ""
    if transition_item.get("raw"):
        return _strip_raw_semicolon(transition_item["raw"])

    source = transition_item.get("source", "")
    target = transition_item.get("target", "")
    event = transition_item.get("event", "")
    condition = transition_item.get("condition", "")
    action = transition_item.get("action", "")
    is_forced = transition_item.get("is_forced", False) or source.strip().startswith("!")

    source = source.strip()
    if is_forced:
        source = source.lstrip("!").strip() or "*"
        result = f"! {source} -> {target}"
    else:
        result = f"{source} -> {target}"

    if event:
        if event.startswith("::") or event.startswith(":"):
            result += f" {event}"
        else:
            result += f" : {event}"
    if condition:
        if not event:
            result += " :"
        result += f" if [{condition}]"
    if action and not is_forced:
        body = _format_statement_block(action, indent + 1)
        return f"{result} effect {{\n{body}\n{'    ' * indent}}};"
    return f"{result};"


def _format_event_item(event_item):
    if event_item.get("raw"):
        return event_item["raw"].strip()
    name = event_item.get("name", "").strip()
    if not name:
        return ""
    extra_name = event_item.get("extra_name", "").strip()
    if extra_name:
        return f"event {name} named {extra_name!r};"
    return f"event {name};"


def _state_header(state: State) -> str:
    prefix = "pseudo state" if getattr(state, "is_pseudo", False) else "state"
    header = f"{prefix} {state.name}"
    if getattr(state, "extra_name", None):
        header += f" named {state.extra_name!r}"
    return header


def format_state(state, lines, state_manager: StateManager, indent=0):
    ind = "    " * indent
    body_lines = []

    for lifecycle_item in state.lifecycle:
        lifecycle_line = format_lifecycle_item(lifecycle_item, indent + 1)
        if lifecycle_line.strip():
            body_lines.append(_indent_text(lifecycle_line, 1))

    for child in state.children:
        child_lines = []
        format_state(child, child_lines, state_manager, 0)
        body_lines.append(_indent_text("\n".join(child_lines), 1))

    for event_item in getattr(state, "events", []):
        event_line = _format_event_item(event_item)
        if event_line:
            body_lines.append("    " + event_line)

    for transition_item in state.transitions:
        transition_line = format_transition_item(transition_item, indent + 1)
        if transition_line.strip():
            body_lines.append(_indent_text(transition_line, 1))

    if body_lines:
        lines.append(f"{ind}{_state_header(state)} {{")
        lines.extend(f"{ind}{line}" for line in "\n".join(body_lines).splitlines())
        lines.append(f"{ind}}}")
    else:
        lines.append(f"{ind}{_state_header(state)};")


def state_manager_to_dsl(state_manager: StateManager) -> str:
    lines = []
    if state_manager.variable_definitions:
        for line in state_manager.variable_definitions.split("\n"):
            if line.strip():
                lines.append(line.strip())

    root_state = state_manager.get_root_state()
    if root_state:
        format_state(root_state, lines, state_manager, 0)
    return "\n".join(lines)

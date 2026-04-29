from typing import Dict, List, Optional, Tuple, Union
import warnings

import z3
from pyfcstm.dsl import EXIT_STATE
from pyfcstm.model import State, StateMachine
from pyfcstm.solver import (
    create_z3_vars_from_state_machine,
    execute_operations,
    expr_to_z3,
    solve as solve_constraints,
    substitute_and_literalize,
    z3_and,
    z3_not,
    z3_or,
)
from pyfcstm.verify import bfs_search
from pyfcstm.verify.search import (
    SearchFrame,
    StateSearchContext,
    _normalize_bfs_init_constraint,
    _normalize_search_limits,
)


def resolve_state_path(state_machine: StateMachine, raw_path: str) -> State:
    return state_machine.resolve_state(raw_path.strip())


def get_state_frame_types(state: State) -> Tuple[str, ...]:
    if state.is_leaf_state:
        return ("leaf",)
    return "composite_in", "composite_out"


def z3_value_to_literal(value: z3.ExprRef) -> Union[bool, int, float]:
    if z3.is_true(value):
        return True
    if z3.is_false(value):
        return False
    if z3.is_int_value(value):
        return value.as_long()
    if z3.is_rational_value(value):
        return float(value.numerator_as_long()) / float(value.denominator_as_long())
    if z3.is_algebraic_value(value):
        return float(value.approx(20).as_decimal(20))
    raise ValueError(f"Unsupported evaluated Z3 value: {value!r}.")


def build_complete_solution_for_frame(
    state_machine: StateMachine,
    frame: SearchFrame,
    partial_solution: Optional[Dict[str, Union[bool, int, float]]] = None,
) -> Dict[str, Union[bool, int, float]]:
    solver = z3.Solver()
    solver.add(frame.constraints)
    partial_solution = partial_solution or {}

    machine_vars = create_z3_vars_from_state_machine(state_machine)
    for name, value in partial_solution.items():
        var_expr = machine_vars.get(name, z3.Bool(name))
        if z3.is_bool(var_expr):
            solver.add(var_expr == z3.BoolVal(bool(value)))
        elif z3.is_int(var_expr):
            solver.add(var_expr == z3.IntVal(int(value)))
        elif z3.is_real(var_expr):
            solver.add(var_expr == z3.RealVal(str(value)))
        else:
            raise ValueError(f"Unsupported variable sort for {name!r}: {var_expr.sort()!r}.")

    check_result = solver.check()
    if check_result != z3.sat:
        raise ValueError(f"Failed to materialize concrete witness: {check_result!r}.")

    model = solver.model()
    solution: Dict[str, Union[bool, int, float]] = {}
    for var_name, var_expr in machine_vars.items():
        solution[var_name] = z3_value_to_literal(model.eval(var_expr, model_completion=True))

    for history_frame in frame.get_history():
        if history_frame.event_var is None:
            continue
        event_name = str(history_frame.event_var)
        if event_name not in solution:
            solution[event_name] = z3_value_to_literal(
                model.eval(history_frame.event_var, model_completion=True)
            )
    return solution


def run_search_from_initial_frames(
    initial_frames: List[SearchFrame],
    max_cycle: Optional[int],
    max_depth: Optional[int],
) -> StateSearchContext:
    max_cycle, max_depth = _normalize_search_limits(max_cycle=max_cycle, max_depth=max_depth)
    ctx = StateSearchContext()
    for initial_frame in initial_frames:
        ctx.try_append_frame(initial_frame)

    while len(ctx.queue) > 0:
        head: SearchFrame = ctx.queue.popleft()
        if max_depth is not None and head.depth >= max_depth:
            continue
        if max_cycle is not None and head.cycle >= max_cycle:
            continue

        if head.type == "leaf" or head.type == "composite_out":
            transitions = head.state.transitions_from
        elif head.type == "composite_in":
            transitions = head.state.init_transitions
        elif head.type == "end":
            transitions = []
        else:
            raise RuntimeError(f"Unsupported search frame type: {head.type!r}.")

        prev_conditions = []
        for transition in transitions:
            if head.type == "composite_in":
                to_state = transition.to_state_obj
                to_type = "leaf" if to_state.is_leaf_state else "composite_in"
            else:
                if transition.to_state == EXIT_STATE:
                    if head.state.is_root_state:
                        to_state = None
                    else:
                        to_state = transition.from_state_obj.parent
                    to_type = "end" if head.state.is_root_state else "composite_out"
                else:
                    to_state = transition.to_state_obj
                    to_type = "leaf" if to_state.is_leaf_state else "composite_in"

            if transition.guard:
                condition = expr_to_z3(expr=transition.guard, z3_vars=head.var_state)
                event_var = None
            elif transition.event:
                condition = ctx.get_z3_event(head.cycle, transition.event, force=True)
                event_var = condition
            else:
                condition = z3.BoolVal(True)
                event_var = None
            actual_condition = z3_and([z3_not(z3_or(prev_conditions)), condition])
            z3_vars = head.var_state

            if head.type == "composite_in":
                for action in head.state.list_on_durings(is_abstract=False, aspect="before"):
                    z3_vars = execute_operations(action.operations, z3_vars)
            elif head.type == "leaf" or head.type == "composite_out":
                for action in head.state.list_on_exits(is_abstract=False):
                    z3_vars = execute_operations(action.operations, z3_vars)

            z3_vars = execute_operations(transition.effects, z3_vars)

            if to_type == "composite_out":
                for action in to_state.list_on_durings(is_abstract=False, aspect="after"):
                    z3_vars = execute_operations(action.operations, z3_vars)
            elif to_type == "leaf" or to_type == "composite_in":
                for action in to_state.list_on_enters(is_abstract=False):
                    z3_vars = execute_operations(action.operations, z3_vars)

            if to_state and to_state.is_leaf_state:
                for _, action in to_state.list_on_during_aspect_recursively(is_abstract=False):
                    z3_vars = execute_operations(action.operations, z3_vars)

            ctx.try_append_frame(
                SearchFrame(
                    state=to_state,
                    type=to_type,
                    var_state=z3_vars,
                    constraints=z3_and([head.constraints, actual_condition]),
                    event_var=event_var,
                    depth=head.depth + 1,
                    cycle=head.cycle + (1 if to_state is None or to_state.is_stoppable else 0),
                    prev_frame=head,
                )
            )
            prev_conditions.append(condition)

        if head.type == "leaf" and head.state.is_stoppable:
            actual_condition = z3_not(z3_or(prev_conditions))
            z3_vars = head.var_state
            for _, action in head.state.iter_on_during_aspect_recursively(is_abstract=False):
                z3_vars = execute_operations(action.operations, z3_vars)
            ctx.try_append_frame(
                SearchFrame(
                    state=head.state,
                    type=head.type,
                    var_state=z3_vars,
                    constraints=z3_and([head.constraints, actual_condition]),
                    event_var=None,
                    depth=head.depth + 1,
                    cycle=head.cycle + 1,
                    prev_frame=head,
                )
            )
    return ctx


def run_validate_search(
    state_machine: StateMachine,
    source_state: State,
    constraint: Optional[str],
    max_path_length: int,
    max_cycle_length: int,
) -> StateSearchContext:
    init_frame_types = get_state_frame_types(source_state)
    if init_frame_types == ("leaf",):
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", UserWarning)
            return bfs_search(
                state_machine=state_machine,
                init=(source_state, constraint) if constraint is not None else source_state,
                max_cycle=max_cycle_length,
                max_depth=max_path_length,
            )

    z3_vars = create_z3_vars_from_state_machine(state_machine)
    init_constraints = _normalize_bfs_init_constraint(
        raw_init_constraints=constraint,
        z3_vars=z3_vars,
        source_name="'constraint'",
    )
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UserWarning)
        return run_search_from_initial_frames(
            initial_frames=[
                SearchFrame(
                    state=source_state,
                    type=frame_type,
                    var_state=z3_vars,
                    constraints=init_constraints,
                    event_var=None,
                    depth=0,
                    cycle=0,
                    prev_frame=None,
                )
                for frame_type in init_frame_types
            ],
            max_cycle=max_cycle_length,
            max_depth=max_path_length,
        )


def collect_target_frames(
    ctx: StateSearchContext,
    target_state: State,
    target_frame_types: Tuple[str, ...],
) -> List[SearchFrame]:
    target_frames = []
    state_key = ".".join(target_state.path)
    for frame_type in target_frame_types:
        space = ctx.spaces.get((state_key, frame_type))
        if space is not None:
            target_frames.extend(space.frames)
    target_frames.sort(key=lambda frame: (frame.cycle, frame.depth, len(frame.get_history()), frame.type))
    return target_frames


def build_target_constraint(target_frames: List[SearchFrame]) -> z3.BoolRef:
    return z3_or([frame.constraints for frame in target_frames])


def does_frame_match_partial_solution(
    frame: SearchFrame,
    partial_solution: Dict[str, Union[bool, int, float]],
) -> bool:
    result = substitute_and_literalize(frame.constraints, partial_solution)
    return result is True or z3.is_true(result)


def find_matching_target_frame(
    target_frames: List[SearchFrame],
    partial_solution: Dict[str, Union[bool, int, float]],
) -> Optional[SearchFrame]:
    for frame in target_frames:
        if does_frame_match_partial_solution(frame, partial_solution):
            return frame
    return None


def build_path_constraint(
    model: StateMachine,
    source_state: str,
    destination_state: str,
    max_path_length: int,
    max_cycle_length: int,
) -> z3.BoolRef:
    source_obj = resolve_state_path(model, source_state)
    destination_obj = resolve_state_path(model, destination_state)
    ctx = run_validate_search(model, source_obj, None, max_path_length, max_cycle_length)
    target_frames = collect_target_frames(ctx, destination_obj, get_state_frame_types(destination_obj))
    return build_target_constraint(target_frames)

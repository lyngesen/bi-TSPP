# imports
from functools import reduce
from collections import deque
import time
from bitsp.utils.all import (
    pareto_filter,
)
from bitsp.classes.instance import (
    Solution,
    SolutionList,
    Instance,
    Timer,
    AlgorithmResult,
)
from bitsp.classes.classes import MIP


def combine_two_fronts(Y1: SolutionList, Y2: SolutionList) -> SolutionList:
    """
    Pareto convolution of two fronts.
    Y1, Y2: iterable of (w, p)
    """
    combined = SolutionList()
    for y1 in Y1:
        for y2 in Y2:
            combined.append(y1 + y2)
    return combined.N()


def MIP_solve(
    I: Instance,
    formulation="mtz",
    verbose=False,
    max_solution_time=None,
    starting="lr",
):
    """MIP approach."""

    timer = Timer(verbose=verbose)

    with timer.measure("metric_closure"):
        I_closed = I.metric_closure()

    with timer.measure("init_graph"):
        I_closed.init_graph()

    with timer.measure("create_problem"):
        problem = MIP(I_closed.G)

    problem.verbose = verbose

    match formulation:
        case "mtz":
            setup_method = problem.setup_mip
        case "flow":
            setup_method = problem.setup_mip_flow
        case "lazy-sec":
            setup_method = problem.setup_mip_lazy_SEC
        case _:
            raise ValueError(f"Unknown formulation: {formulation}")

    with timer.measure(f"setup_{formulation}"):
        setup_method()

    with timer.measure("solve_epsilon_constraint"):
        solutions = problem.solve_epsilon_constraint(
            max_solution_time=max_solution_time, starting=starting
        )

    timer.stop()
    return AlgorithmResult(
        front=SolutionList(solutions).N(),
        solution_method_name=f"MIP-{formulation}",
        instance=I,
        events=timer.events,
        node_name=I.name_short,
        total_time=timer.total_time,
        time_limit_exceeded=(
            max_solution_time is not None and timer.total_time >= max_solution_time
        )
        or problem._time_limit_exceeded,
    )


def MIP_solve_decomposed(
    I: Instance,
    formulation="mtz",
    verbose=False,
    max_solution_time: bool | int | float = None,
):
    """Decomposed MIP approach."""

    timer = Timer(verbose=verbose)

    with timer.measure("set_subgraphs"):
        I.set_subgraphs()

    fronts = []
    subresults = []

    time_limit_exceeded = False
    for s in I.subgraphs:
        if s == 0:
            continue

        with timer.measure("extract_subgraph"):
            I_s = I.from_subgraph(s)

        # Child AlgorithmResult
        result_s = MIP_solve(
            I_s,
            formulation=formulation,
            verbose=verbose,
            max_solution_time=(max_solution_time / I.S if max_solution_time else None),
        )
        if result_s.time_limit_exceeded:
            time_limit_exceeded = True
        subresults.append(result_s)
        fronts.append(result_s.front)

    with timer.measure("combine_fronts"):
        Y = reduce(combine_two_fronts, fronts)

    timer.stop()
    return AlgorithmResult(
        front=Y,
        solution_method_name=f"MIP-{formulation}-decomposed",
        instance=I,
        events=timer.events,
        children=subresults,
        total_time=timer.total_time,
        time_limit_exceeded=time_limit_exceeded,
    )


# A label-correcting algorithm
def label_correcting(
    G,
    root=0,
    max_capacity: None | int = None,
    max_solution_time: None | float | int = None,
) -> tuple[SolutionList, bool]:
    if root not in G:
        raise ValueError(f"Root {root} not in graph.")

    node_profit = {v: G.nodes[v].get("p", 0) for v in G.nodes()}

    # --- Correct dominance with visited sets ---
    def dominates(a, b):
        l1, p1, S1 = a
        l2, p2, S2 = b

        return (
            l1 <= l2
            and p1 >= p2
            and S1.issubset(S2)
            and (l1 < l2 or p1 > p2 or S1 != S2)
        )

    start_set = frozenset({root})
    start_path = [root]

    # labels[(node, visited)] = list of (length, profit, path, visited)
    labels = {root: [(0, node_profit[root], start_path, start_set)]}

    queue = deque([(root, start_set, 0, node_profit[root], start_path)])

    # # --- time limit tracking ---
    time_limit_hit = False
    if max_solution_time is not None:
        deadline = time.perf_counter() + max_solution_time

    while queue:
        if max_solution_time is not None and time.perf_counter() >= deadline:
            time_limit_hit = True
            break
        #
        # while queue:
        v, visited, length, profit, path = queue.popleft()
        #
        # skip stale labels
        if v not in labels or not any(
            (length, profit, visited) == (l, p, S) for l, p, _, S in labels[v]
        ):
            continue

        if max_capacity is not None and length >= max_capacity:
            continue

        for u in G.neighbors(v):
            w = G[v][u]["w"]

            new_length = length + w

            if u in visited:
                new_visited = visited
                new_profit = profit
            else:
                new_visited = visited | {u}
                new_profit = profit + node_profit[u]

            new_path = path + [u]

            state = u
            existing = labels.get(state, [])

            # --- check dominance ---
            dominated_flag = False
            for l, p, _, S in existing:
                # same label or dominated
                if (
                    l == new_length and p == new_profit and S == new_visited
                ) or dominates((l, p, S), (new_length, new_profit, new_visited)):
                    dominated_flag = True
                    break

            if dominated_flag:
                continue

            # --- remove labels dominated by the new one ---
            filtered = [
                (l, p, path_, S)
                for l, p, path_, S in existing
                if not dominates((new_length, new_profit, new_visited), (l, p, S))
            ]

            filtered.append((new_length, new_profit, new_path, new_visited))
            labels[state] = filtered

            queue.append((u, new_visited, new_length, new_profit, new_path))

    # --- collect labels returning to root ---
    root_labels = []
    for v, front in labels.items():
        if v == root:
            root_labels.extend(front)

    # --- Pareto filter on (length, profit) only ---
    wp = [(l, p) for l, p, _, _ in root_labels]
    efficient_wp = set(pareto_filter(wp))

    # --- build solutions ---
    return (
        SolutionList(
            [
                Solution.from_path(path, l, p)
                for l, p, path, _ in root_labels
                if (l, p) in efficient_wp and (max_capacity is None or l < max_capacity)
            ]
        ),
        time_limit_hit,
    )


def label_solve(
    I: Instance,
    root=0,
    verbose=False,
    max_solution_time: None | float | int = None,
    formulation="setting",
):
    if formulation == "correction":
        label_alg = label_correcting
    else:
        raise ValueError(f"Unknown formulation: {formulation}")
    """Label-setting approach."""
    timer = Timer(verbose=verbose)
    with timer.measure("init_graph"):
        I.init_graph()
    with timer.measure("label_solve"):
        solutions, time_limit_reached = label_alg(
            I.G, root=root, max_solution_time=max_solution_time
        )
    with timer.measure("pareto_filter"):
        solutions = solutions.N()
    timer.stop()
    return AlgorithmResult(
        front=solutions,
        solution_method_name="Label",
        instance=I,
        events=timer.events,
        node_name=I.name_short,
        total_time=timer.total_time,
        time_limit_exceeded=(
            max_solution_time is not None and timer.total_time >= max_solution_time
        )
        or time_limit_reached,
    )


def label_solve_decomposed(
    I: Instance,
    root=0,
    verbose=False,
    max_solution_time: None | float | int = None,
    formulation="correction",
):
    """Decomposed label-setting approach."""
    timer = Timer(verbose=verbose)
    with timer.measure("set_subgraphs"):
        I.set_subgraphs()
    time_per_subgraph = max_solution_time / I.S if max_solution_time else None
    fronts = []
    subresults = []
    time_limit_exceeded = False
    for s in I.subgraphs:
        if s == 0:
            continue
        with timer.measure("extract_subgraph"):
            I_s = I.from_subgraph(s)
        # Child AlgorithmResult
        result_s = label_solve(
            I_s,
            root=root,
            verbose=verbose,
            max_solution_time=time_per_subgraph,
            formulation=formulation,
        )
        if result_s.time_limit_exceeded:
            time_limit_exceeded = True
        subresults.append(result_s)
        fronts.append(result_s.front)
    with timer.measure("combine_fronts"):
        Y = reduce(combine_two_fronts, fronts)
    timer.stop()
    return AlgorithmResult(
        front=Y,
        solution_method_name="Label-Decomposed",
        instance=I,
        events=timer.events,
        children=subresults,
        total_time=timer.total_time,
        time_limit_exceeded=time_limit_exceeded,
    )

import networkx as nx
from typing import ClassVar, Literal, Optional
from time import perf_counter
from contextlib import contextmanager
import os
from collections import defaultdict, Counter
import matplotlib.cm as cm
import matplotlib.pyplot as plt
from collections import defaultdict
import networkx as nx
from dataclasses import dataclass, field
from typing import Any, Dict, List, Tuple
import json
import os
import networkx as nx
from bitsp.utils.all import pareto_filter

# import numpy as np
import matplotlib.pyplot as plt

ObjType = Literal[0, 1]  # 0 = weight, 1 = profit
DirType = Literal["lr", "ul"]


class Solution:
    def __init__(self, x, y):
        self.x = x
        self.y = y

    def __repr__(self):
        return f"Solution(obj={self.y})"

    @classmethod
    def from_path(cls, path, w, p):
        edges = list(zip(path, path[1:]))
        x = {e: 1 for e in edges}
        x.update({(v, u): 1 for u, v in edges})
        return cls(x, (w, p))

    @classmethod
    def from_edges(cls, x, w, p):
        clean = {e: int(round(v)) for e, v in x.items() if v > 0.5}
        return cls(clean, (w, p))

    def as_path(self):
        path = [0]
        visited = {0}

        while True:
            current = path[-1]
            nxt = next(
                (
                    v
                    for (u, v), val in self.x.items()
                    if u == current and val > 0.5 and v not in visited
                ),
                None,
            )
            if nxt is None:
                break
            path.append(nxt)
            visited.add(nxt)

        return path, *self.y

    def as_path(self):
        path = [0]
        visited = set()

        while True:
            current = path[-1]

            nxt = next(
                (
                    v
                    for (u, v), val in self.x.items()
                    if u == current and val > 0.5 and (v == 0 or v not in visited)
                ),
                None,
            )

            if nxt is None:
                break

            path.append(nxt)

            if nxt != 0:
                visited.add(nxt)

        return path, *self.y

    @property
    def weight(self):
        return self.y[0]

    @property
    def profit(self):
        return self.y[1]

    def evaluate(self, instance):
        mc = instance.metric_closure()

        w = sum(mc.edge_cost[canon_edge(*e)] * val for e, val in self.x.items())
        visited = self.as_path()[0]
        print(f"{visited=}")
        print(f"{self.x=}")
        p = sum(instance.profits[v] for v in visited)

        return (w, p)

    def __add__(self, other):
        if not isinstance(other, Solution):
            return NotImplemented
        new_x = self.x.copy()
        for e, val in other.x.items():
            new_x[e] = new_x.get(e, 0) + val
        new_y = (self.y[0] + other.y[0], self.y[1] + other.y[1])
        return Solution(new_x, new_y)


class SolutionList(list):
    """List of Solution objects with Pareto utilities."""

    # -----------------------
    # ADD WITH OPTIONAL FILTER
    # -----------------------
    def add(self, sol):
        """Append solution (no filtering)."""
        self.append(sol)

    # -----------------------
    # PARETO FILTER
    # -----------------------
    def N(self):
        """Return non-dominated solutions, one per objective pair."""

        # extract objective pairs
        wp = [s.y for s in self]

        # fast Pareto filter
        efficient_wp = set(pareto_filter(wp))

        # keep one solution per (w,p)
        unique = {}
        for s in self:
            if s.y in efficient_wp and s.y not in unique:
                unique[s.y] = s

        return SolutionList(unique.values())

    # -----------------------
    # SORTING
    # -----------------------
    def sort_by_weight(self):
        self.sort(key=lambda s: s.y[0])
        return self

    def sort_by_profit(self):
        self.sort(key=lambda s: s.y[1], reverse=True)
        return self

    # -----------------------
    # DEDUPLICATE (optional)
    # -----------------------
    def unique(self):
        seen = set()
        out = []
        for s in self:
            if s.y not in seen:
                seen.add(s.y)
                out.append(s)
        return SolutionList(out)

    # -----------------------
    # PLOT
    # -----------------------
    def plot(self, ax=None, show=True, **kwargs):

        pts = [s.y for s in self]
        w = [p[0] for p in pts]
        p = [p[1] for p in pts]

        if ax is None:
            _, ax = plt.subplots()

        ax.scatter(w, p, **kwargs)
        ax.set_xlabel("Weight")
        ax.set_ylabel("Profit")
        ax.set_title("Solutions")

        if show:
            plt.show()

        return ax

    # -----------------------
    # NICE PRINTING
    # -----------------------
    def __repr__(self):
        return f"SolutionList(n={len(self)})"

    def __eq__(self, other):

        if not isinstance(other, SolutionList):
            return NotImplemented
        self_Y = {s.y for s in self}
        other_Y = {s.y for s in other}

        return self_Y == other_Y

    def lex_sort(self):
        """Sort solutions lexicographically by (weight, profit)."""
        self.sort(key=lambda s: (s.y[0], -s.y[1]))
        return self


@dataclass
class Instance:
    nodes: List[Any]
    edges: List[Tuple[Any, Any]]
    edge_cost: Dict[Tuple[Any, Any], Any]
    profits: Dict[Any, Any]
    data: Dict[str, Any]
    root: Any = 0
    subgraphs: Dict[int, Tuple[int, ...]] = field(
        default_factory=dict, compare=False, repr=True
    )
    # Lazy-initialized graph
    G: nx.Graph = field(init=False, repr=False, compare=False)

    # Class vars
    INSTANCE_DIR: ClassVar[str] = "instances"

    @property
    def name(self) -> str:
        return self.data.get("name", "instance")

    @property
    def S(self) -> int:
        # read from name n-10_S-4_type-float-33_weights-random_seed-0
        return int(self.name.split("_S-")[1].split("_")[0])

    @property
    def name_short(self) -> str:
        name = self.name
        return "subgraph " + name.split("subgraph_")[-1]

    # -------------------------
    # Initialization helpers
    # -------------------------
    def __post_init__(self):
        # Normalize edges and edge_cost for undirected graph
        self.edges = [canon_edge(u, v) for u, v in self.edges]
        self.edge_cost = {
            canon_edge(u, v): cost for (u, v), cost in self.edge_cost.items()
        }

    # -------------------------
    # Constructors
    # -------------------------
    @classmethod
    def from_dict(cls, data_dict: Dict[str, Any]) -> "Instance":
        required = ["nodes", "edges", "edge_cost", "profits", "subgraphs", "data"]
        missing = [k for k in required if k not in data_dict]
        if missing:
            raise ValueError(f"Missing required keys: {missing}")

        def canon(u, v):
            return (u, v) if u <= v else (v, u)

        edges = [tuple(e) for e in data_dict["edges"]]

        edge_cost = {
            canon(item["u"], item["v"]): item["cost"] for item in data_dict["edge_cost"]
        }

        # ✅ FIX: restore key types
        profits = {int(k): v for k, v in data_dict["profits"].items()}

        return cls(
            nodes=data_dict["nodes"],
            edges=edges,
            edge_cost=edge_cost,
            profits=profits,
            subgraphs=data_dict["subgraphs"],
            data=data_dict["data"],
        )

    @classmethod
    def from_json(cls, filename: str, path=False) -> "Instance":
        if not path:
            filename = os.path.join(cls.INSTANCE_DIR, filename)
        with open(filename, "r") as f:
            data_dict = json.load(f)
        return cls.from_dict(data_dict)

    @classmethod
    def from_graph(cls, G: nx.Graph) -> "Instance":
        nodes = list(G.nodes())
        edges = [canon_edge(u, v) for u, v in G.edges()]

        edge_cost = {canon_edge(u, v): G[u][v].get("w") for u, v in G.edges()}

        profits = {node: G.nodes[node].get("p") for node in G.nodes()}

        data = G.graph.copy()  # Copy graph attributes if any
        subgraphs = {}
        return cls(
            nodes=nodes,
            edges=edges,
            edge_cost=edge_cost,
            profits=profits,
            data=data,
            subgraphs=subgraphs,
        )

    # -------------------------
    # Serialization
    # -------------------------
    def as_dict(self) -> Dict[str, Any]:
        return {
            "nodes": sorted(self.nodes),
            "edges": sorted([list(e) for e in self.edges]),
            "edge_cost": sorted(
                (
                    {"u": u, "v": v, "cost": cost}
                    for (u, v), cost in self.edge_cost.items()
                ),
                key=lambda x: (x["u"], x["v"]),
            ),
            "profits": dict(sorted(self.profits.items())),
            "subgraphs": self.subgraphs,  # or sort if needed
            "data": self.data,
        }

    def to_json(self, indent: int = 4) -> str:
        return json.dumps(self.as_dict(), indent=indent)

    def default_filename(self) -> str:
        return self.data.get("name", "instance") + ".json"

    def save_json(
        self, filename: Optional[str] = None, overwrite: bool = True, path: bool = False
    ):
        if filename is None:
            filename_str = self.default_filename()
        else:
            filename_str = filename

        if not path:
            filename_str = os.path.join(self.INSTANCE_DIR, filename_str)

        if os.path.exists(filename_str) and not overwrite:
            raise ValueError(f"File already exists: {filename_str}")

        with open(filename_str, "w") as f:
            # json.dump(self.as_dict(), f, indent=2)
            json.dump(self.as_dict(), f, separators=(",", ":"), sort_keys=True)

    def is_closed(self):
        # check if graph is complete
        self_closed = self.metric_closure()
        return (
            self_closed.edges == self.edges and self_closed.edge_cost == self.edge_cost
        )

    def __eq__(self, other):
        if not isinstance(other, Instance):
            return NotImplemented
        return self.as_dict() == other.as_dict()

    def set_subgraphs(self, root: int = 0) -> dict[int, tuple[int, ...]]:
        if not hasattr(self, "G") or self.G is None:
            self.init_graph()

        G = self.G

        if root not in G:
            raise ValueError(f"Root {root} is not in the graph.")

        G_without_root = G.copy()
        G_without_root.remove_node(root)

        components = list(nx.connected_components(G_without_root))

        subgraphs: dict[int, tuple[int, ...]] = {0: (root,)}

        for i, comp in enumerate(components, start=1):
            subgraphs[i] = tuple(sorted(comp))
        self.subgraphs = subgraphs
        return subgraphs

    def from_subgraph(self, subgraph_id: int) -> "Instance":
        if subgraph_id not in self.subgraphs:
            raise ValueError(f"Subgraph ID {subgraph_id} not found.")
        # nodes = list(self.subgraphs[subgraph_id]) + [self.root]  # include root
        # edges = [
        #     e for e in self.edges if e[0] in nodes and e[1] in nodes
        # ]  # filter edges
        #

        #  Build a set ONCE for O(1) lookups
        node_set = set(self.subgraphs[subgraph_id])
        node_set.add(self.root)

        # Keep a list for ordering if the Instance constructor needs it
        nodes = list(self.subgraphs[subgraph_id]) + [self.root]

        #  Now O(E) instead of O(E × N)
        edges = [e for e in self.edges if e[0] in node_set and e[1] in node_set]

        # set root as the node in the subgraph adjecent to root of original graph, else throw error
        root = self.root
        edge_cost = {e: self.edge_cost[e] for e in edges}
        profits = {n: self.profits[n] for n in nodes}
        data = self.data.copy()
        data["name"] = f"{data.get('name', 'instance')}_subgraph_{subgraph_id}"
        return Instance(
            nodes=nodes,
            edges=edges,
            edge_cost=edge_cost,
            root=root,
            profits=profits,
            data=data,
            subgraphs={subgraph_id: self.subgraphs[subgraph_id]},
        )

    # -------------------------
    # Graph handling
    # -------------------------
    def init_graph(self):
        G = nx.Graph()
        G.add_nodes_from(self.nodes)
        G.add_edges_from(self.edges)

        for (u, v), cost in self.edge_cost.items():
            G[u][v]["w"] = cost

        for node, profit in self.profits.items():
            G.nodes[node]["p"] = profit

        self.G = G

    def plot_graph(
        self,
        save_path=None,
        show=True,
        color_subgraph=True,
        pos=False,
        solution: Optional[Solution] = None,
        ax=None,
    ):
        if not hasattr(self, "G") or self.G is None:
            self.init_graph()

        G = self.G

        if not pos:
            pos = nx.spring_layout(G, seed=42)
            G.graph["pos"] = pos

        # --- Edge weights -> widths ---
        edge_weights = nx.get_edge_attributes(G, "w")
        weights = list(edge_weights.values())

        if weights:
            w_min, w_max = min(weights), max(weights)
            edge_widths = [
                1 + 4 * (w - w_min) / (w_max - w_min) if w_max > w_min else 2
                for w in weights
            ]
        else:
            edge_widths = 1

        edges = list(edge_weights.keys())

        # --- Node profits ---
        node_profits = nx.get_node_attributes(G, "p")
        profits = list(node_profits.values())

        if profits:
            p_min, p_max = min(profits), max(profits)
        else:
            p_min = p_max = 0

        # --- Node sizes ---
        node_sizes = []
        for n in G.nodes():
            p = node_profits.get(n, 0)

            if p_max > p_min:
                norm = (p - p_min) / (p_max - p_min)
            else:
                norm = 0.5

            node_sizes.append(100 + 400 * norm)

        # --- Node colors ---
        if color_subgraph:
            if not self.subgraphs:
                self.set_subgraphs(root=0)

            cmap = plt.get_cmap("tab10")
            node_colors = []

            node_to_sub = {}
            for sid, nodes in self.subgraphs.items():
                for n in nodes:
                    node_to_sub[n] = sid

            for n in G.nodes():
                if n == 0:
                    node_colors.append("red")
                else:
                    sid = node_to_sub.get(n, -1)
                    node_colors.append(cmap(sid % 10))

        else:
            cmap = cm.Blues
            node_colors = []

            for n in G.nodes():
                if n == 0:
                    node_colors.append((1, 0, 0))
                else:
                    p = node_profits.get(n, 0)
                    norm = (p - p_min) / (p_max - p_min) if p_max > p_min else 0.5
                    node_colors.append(cmap(norm))

        created_fig = False

        if ax is None:
            fig, ax = plt.subplots(figsize=(15, 10))
            created_fig = True

        nx.draw(
            G,
            pos,
            ax=ax,
            with_labels=False,
            node_color=node_colors,
            node_size=node_sizes,
            edgelist=edges,
            width=edge_widths,
        )

        nx.draw_networkx_edge_labels(
            G,
            pos,
            edge_labels=edge_weights,
            ax=ax,
        )

        nx.draw_networkx_labels(
            G,
            pos,
            labels={n: f"{n}\n(p={node_profits.get(n, 0)})" for n in G.nodes()},
            font_color="black",
            font_size=8,
            ax=ax,
        )

        if solution:
            nx.draw_networkx_edges(
                G,
                pos,
                edgelist=self.get_expanded_edges(solution),
                edge_color="green",
                width=3,
                ax=ax,
            )

            ax.set_title(
                f"Graph with Solution Highlighted (green edges), y={solution.y}"
            )

        if save_path and created_fig:
            plt.savefig(save_path, bbox_inches="tight")

        if created_fig:
            if show:
                plt.show()
            else:
                plt.close()

    def get_expanded_path(self, solution):
        import networkx as nx

        paths = dict(nx.all_pairs_dijkstra_path(self.G, weight="w"))

        # --- expand closure edges into multiset ---
        edge_multiset = Counter()

        for (u, v), val in solution.x.items():
            if val > 0.5:
                path = paths[u][v]
                for a, b in zip(path, path[1:]):
                    edge_multiset[(a, b)] += 1
                    edge_multiset[
                        (b, a)
                    ] += 0  # ensure symmetry handling via canon_edge if needed

        # --- build adjacency with multiplicities ---
        adj = defaultdict(list)
        for (a, b), count in edge_multiset.items():
            for _ in range(count):
                adj[a].append(b)
                adj[b].append(a)

        # sort adjacency lists for lexicographic tie-breaking
        for v in adj:
            adj[v].sort()

        # --- Hierholzer (Eulerian circuit) ---
        stack = [0]
        circuit = []

        adj_copy = {v: list(neigh) for v, neigh in adj.items()}

        while stack:
            v = stack[-1]

            if adj_copy[v]:
                u = adj_copy[v].pop(0)  # smallest neighbor

                # remove reverse edge
                adj_copy[u].remove(v)

                stack.append(u)
            else:
                circuit.append(stack.pop())

        # reverse → correct order
        return circuit[::-1]

    def get_expanded_edges(self, solution):
        paths = dict(nx.all_pairs_dijkstra_path(self.G, weight="w"))

        expanded_edges = []

        for (u, v), val in solution.x.items():
            if val > 0.5:
                path = paths[u][v]
                expanded_edges.extend(canon_edge(a, b) for a, b in zip(path, path[1:]))

        return expanded_edges

    def metric_closure(self) -> "Instance":
        # Ensure graph exists
        if not hasattr(self, "G") or self.G is None:
            self.init_graph()

        G = self.G

        # Compute all-pairs shortest path lengths
        dist = dict(nx.all_pairs_dijkstra_path_length(G, weight="w"))

        nodes = list(G.nodes())

        # Complete edge set
        edges = []
        edge_cost = {}

        for u in nodes:
            for v in nodes:
                if u == v:
                    continue

                e = canon_edge(u, v)
                if e not in edge_cost:
                    edges.append(e)
                    edge_cost[e] = dist[u][v]

        # Keep original profits
        profits = self.profits.copy()

        # Reset subgraphs (they don't carry over meaningfully)
        subgraphs = {}

        # Update metadata
        data = self.data.copy()
        data["name"] = data.get("name", "instance") + "_metric_closure"

        return Instance(
            nodes=nodes,
            edges=edges,
            edge_cost=edge_cost,
            profits=profits,
            data=data,
            subgraphs=subgraphs,
        )


def canon_edge(u: Any, v: Any) -> Tuple[Any, Any]:
    """Canonical ordering for undirected edges."""
    return (u, v) if u <= v else (v, u)


from dataclasses import dataclass, field
import matplotlib.pyplot as plt
from dataclasses import dataclass
from typing import ClassVar


@dataclass(frozen=True)
class TimingEvent:
    name: str
    duration: float

    # Global set shared by all instances
    _names: ClassVar[set[str]] = set()

    def __post_init__(self):
        type(self)._names.add(self.name)


@dataclass(frozen=True)
class AlgorithmResult:
    front: SolutionList
    events: list[TimingEvent]
    solution_method_name: str
    instance: Instance
    total_time: float | None
    children: list["AlgorithmResult"] = field(default_factory=list)
    node_name: str | None = None
    time_limit_exceeded: bool | None = None

    def get_all_events(self):
        events = list(self.events)

        for child in self.children:
            events.extend(child.get_all_events())

        return events

    def get_timings(self):
        timer = Timer()
        timer.events = self.get_all_events()
        return timer.get_timings()

    def print_table(self):
        timings = self.get_timings()

        total_time = sum(event.duration for event in self.events)

        print(f"Instance: {self.instance.name}")
        print(f"Method:   {self.solution_method_name}")
        print(f"|Y|: {len(self.front)}")
        print()

        header = f"{'Name':<30}" f"{'Count':>8}" f"{'Total (s)':>15}" f"{'Avg (s)':>15}"

        print(header)
        print("-" * len(header))

        for name, data in timings.items():
            print(
                f"{name:<30}"
                f"{data['count']:>8}"
                f"{data['total_time']:>15.3f}"
                f"{data['avg_time']:>15.3f}"
            )

        print("-" * len(header))
        print(f"{'TOTAL':<30}" f"{'':>8}" f"{total_time:>15.3f}" f"{'':>15}")

    def _print_hierarchy(self, prefix="", is_root=False):
        total = 0.0

        n_events = len(self.events)
        n_children = len(self.children)

        entries = [("event", e) for e in self.events] + [
            ("child", c) for c in self.children
        ]

        for i, (kind, obj) in enumerate(entries):
            last = i == len(entries) - 1

            branch = "└── " if last else "├── "

            if kind == "event":
                print(f"{prefix}{branch}" f"{obj.name:<30}" f"{obj.duration:.3f}")
                total += obj.duration

            else:
                child_time = sum(e.duration for e in obj.get_all_events())

                name = obj.node_name or obj.solution_method_name

                print(f"{prefix}{branch}" f"{name:<30}" f"{child_time:.3f}")

                # print(f"{prefix}{branch}" f"subproblem" f"{'':<21}" f"{child_time:.3f}")

                child_prefix = prefix + "    " if last else prefix + "│   "

                total += obj._print_hierarchy(child_prefix)

        return total

    def print_table_hierarchy(self):
        print(self.solution_method_name)

        total_time = self._print_hierarchy("", True)

        print()
        print(f"Total: {total_time:.3f}")

    def _collect_gantt(self, row=0, start=0.0):
        """
        Returns:
            timeline : [(row, start_time, event)]
            labels   : [str]
            next_row : int
            end_time : float
        """

        timeline = []

        label = self.node_name or "ALL"
        labels = [label[:3]]

        current = start

        # own events
        for event in self.events:
            timeline.append((row, current, event))
            current += event.duration

        next_row = row + 1

        # children executed sequentially
        child_start = start

        for child in self.children:

            child_timeline, child_labels, next_row, child_end = child._collect_gantt(
                row=next_row,
                start=child_start,
            )

            timeline.extend(child_timeline)
            labels.extend(child_labels)

            child_start = child_end

        return timeline, labels, next_row, max(current, child_start)

    def plot(
        self,
        ax=None,
        show=False,
        filename=None,
        title=None,
    ):
        """
        Hierarchical gantt-style timing plot.
        """

        timeline, labels, _, _ = self._collect_gantt()

        if not timeline:
            return

        if ax is None:
            fig, ax = plt.subplots(figsize=(12, max(2, 0.5 * len(labels))))

        event_names = list(dict.fromkeys(event.name for _, _, event in timeline))

        cmap = plt.get_cmap("tab20")
        colors = {name: cmap(i % 20) for i, name in enumerate(event_names)}

        legend_added = set()

        for row, start, event in timeline:

            label = event.name if event.name not in legend_added else None

            ax.barh(
                y=row,
                width=event.duration,
                left=start,
                color=colors[event.name],
                edgecolor="black",
                linewidth=0.5,
                label=label,
            )

            legend_added.add(event.name)

        ax.set_yticks(range(len(labels)))
        ax.set_yticklabels(labels)

        ax.invert_yaxis()

        if title is not None:
            ax.set_title(title)
        else:
            ax.set_title(f"{self.solution_method_name} ({self.instance.name})")

        ax.set_xlabel("Time (s)")

        ax.legend(
            bbox_to_anchor=(1.02, 1),
            loc="upper left",
        )

        plt.tight_layout()

        if filename:
            plt.savefig(filename, bbox_inches="tight")

        if show:
            plt.show()


class Timer:
    def __init__(self, verbose=False):
        self.events = []
        self.verbose = verbose
        self._start_time = perf_counter()

    def stop(self):
        self._end_time = perf_counter()
        self.total_time = self._end_time - self._start_time
        return self.total_time

    @contextmanager
    def measure(self, name):
        start = perf_counter()
        yield
        duration = perf_counter() - start
        self.events.append(TimingEvent(name, duration))

        if self.verbose:
            print(f"{name}: {duration:.3f}s")

    def get_timings(self):
        timings = defaultdict(lambda: {"count": 0, "total_time": 0.0})

        for event in self.events:
            timings[event.name]["count"] += 1
            timings[event.name]["total_time"] += event.duration

        for data in timings.values():
            data["avg_time"] = data["total_time"] / data["count"]

        return dict(timings)

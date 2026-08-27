import os
import uuid
import subprocess

#
# def subtree_from_nodes(G, nodes):
#     """Return edges induced by a node set"""
#     edges = []
#     for u, v in G.edges():
#         if u in nodes and v in nodes:
#             edges.append((u, v))
#     return edges
#


# def pareto_filter_naive(front):
#     """Remove dominated (w, p) points."""
#
#     efficient = []
#     for w, p in front:
#         dominated = False
#         for w2, p2 in front:
#             if w2 <= w and p2 >= p and (w2 < w or p2 > p):
#                 dominated = True
#                 break
#         if not dominated:
#             efficient.append((w, p))
#     return efficient
#
#
def pareto_filter_fast(front):
    """
    Fast Pareto filter for (w, p) pairs.
    Complexity: O(n log n)
    """
    if not front:
        return []

    # 1) Sort by increasing weight, and for equal w by decreasing profit
    front_sorted = sorted(front, key=lambda x: (x[0], -x[1]))

    efficient = []
    max_profit_so_far = -float("inf")

    # 2) Sweep from smallest w to largest
    for w, p in front_sorted:
        if p > max_profit_so_far:
            efficient.append((w, p))
            max_profit_so_far = p
        # else: dominated by some (w',p') with w'<=w and p'>=p

    return efficient


def pareto_filter_lang(front):
    """
    Pareto filter using the nondom C binary (Bruno Lang's NonDomDC).
    Drop-in replacement for pareto_filter_fast for (w, p) pairs.

    The binary minimizes both objectives, so profit p is sent as (C - p)
    where C = max(p) + 1, ensuring all values are strictly positive.
    The shift is undone after filtering.
    """
    if not front:
        return []

    call_id = str(uuid.uuid4())
    in_file = rf"temp/pointsIn-{call_id}"
    out_file = rf"temp/pointsOut-{call_id}"

    # --- Negate p and shift to make all values strictly > 0 ---
    C = max(p for _, p in front) + 1  # shift constant
    transformed = [(w, C - p) for w, p in front]

    dim, n = 2, len(transformed)
    try:
        with open(in_file, "w") as f:
            f.write(f"{dim}\n")
            f.write(f"{n}\n")
            for w, p_neg in transformed:
                f.write(f"{w:.6f} {p_neg:.6f}\n")
    except FileNotFoundError as e:
        raise FileNotFoundError(
            f"Could not write to {in_file}. Does temp/ exist? {os.getcwd()}"
        ) from e

    # --- Call the binary ---
    assert "nondom" in os.listdir(), os.listdir()
    try:
        subprocess.Popen(["./nondom", call_id]).wait()
    finally:
        os.remove(in_file)

    # --- Read back and undo the transformation ---
    assert os.path.exists(out_file), f"Output not found: {out_file}"
    try:
        with open(out_file, "r") as f:
            _dim = int(f.readline())
            _n = int(f.readline())
            result = [
                (w, C - p_neg)  # undo: p = C - p_neg
                for line in f.read().splitlines()
                if line.strip()
                for w, p_neg in [tuple(float(v) for v in line.split())]
            ]
    finally:
        if os.path.exists(out_file):
            os.remove(out_file)

    return list(dict.fromkeys(result))


NONDOM_EXISTS = os.path.exists("./nondom")


def pareto_filter(front):
    if NONDOM_EXISTS and len(front) > 1000:
        return pareto_filter_lang(front)
    else:
        return pareto_filter_fast(front)


#
# def subtours_generator(G: nx.Graph):
#     """
#     Generate all connected subtrees containing the root.
#     """
#     root = 0
#     all_nodes = list(G.nodes())
#     others = [v for v in all_nodes if v != root]
#
#     subtours = []
#
#     # try all subsets that include root
#     for r in range(len(others) + 1):
#         for subset in combinations(others, r):
#             nodes = set(subset) | {root}
#             if nx.is_connected(G.subgraph(nodes)):
#                 subtours.append(nodes)
#
#     return subtours
#
#
# def evaluate_tour(G, P):
#     """
#     Returns (total_weight, total_profit)
#     """
#     # profit
#     profit = sum(G.nodes[v]["p"] for v in P)
#
#     # tour length = 2 * sum of subtree edges
#     weight = 0
#     for u, v in G.subgraph(P).edges():
#         weight += G[u][v]["w"]
#
#     return 2 * weight, profit
#
#
# def efficient_tours(G, subtours):
#     """
#     Computes Pareto-efficient tours.
#     Returns list of (path, weight, profit).
#     """
#     # normalize paths to lists
#     evaluated = [(list(P), *evaluate_tour(G, P)) for P in subtours]
#
#     # extract (w, p)
#     wp_pairs = [(w, p) for _, w, p in evaluated]
#
#     # filter Pareto-efficient objective values
#     efficient_wp = set(pareto_filter(wp_pairs))
#
#     # keep matching tours
#     return [(P, w, p) for P, w, p in evaluated if (w, p) in efficient_wp]
#
#
# # =========================
# # Visualization helpers
# # =========================
#
#
# def plot_fronts(n, S, fronts, save_path):
#     plt.figure()
#
#     for name, front in fronts.items():
#         if name == "full":
#             w, p = zip(*[(w, p) for _, w, p in front])
#         else:
#             w, p = zip(*front)
#
#         plt.scatter(w, p, label=name + "#" + str(len(front)))
#
#     plt.xlabel("Total Weight")
#     plt.ylabel("Total Profit")
#     plt.title(f"Pareto Front (n={n}, S={S})")
#     plt.legend()
#     plt.tight_layout()
#     plt.savefig(save_path)
#     if __debug__:
#         plt.savefig("plots/latest_front.pdf")
#     plt.close()
#
#
# def plot_tours(G, tours, title, color="lightgray"):
#     pos = nx.spring_layout(G, seed=42)
#
#     plt.figure(figsize=(6, 6))
#     # nx.draw(G, pos, node_color=color, with_labels=True)
#
#     for P in tours:
#         edges = G.subgraph(P).edges()
#         nx.draw_networkx_edges(G, pos, edgelist=edges, width=2, edge_color="red")
#
#     plt.title(title)
#
#
# def split_up_graph(G, S):
#     """
#     Split a rooted tree into S subtrees, each rooted at 0,
#     one per child of the root.
#     """
#     root = 0
#     children = list(G.neighbors(root))
#
#     if len(children) != S:
#         raise ValueError(f"Expected {S} children of root, got {len(children)}")
#
#     # Build BFS tree once
#     T = nx.bfs_tree(G, root)
#
#     subtrees = []
#
#     for child in children:
#         # include the child itself!
#         nodes = {root, child}
#         nodes |= nx.descendants(T, child)
#
#         H = G.subgraph(nodes).copy()
#
#         # ✅ now always true
#         assert 0 in H.nodes()
#         assert nx.is_tree(H)
#
#         subtrees.append(H)
#
#     return subtrees
#
#
# def combine_two_fronts(Y1, Y2):
#     """
#     Pareto convolution of two fronts.
#     Y1, Y2: iterable of (w, p)
#     """
#     combined = []
#     for w1, p1 in Y1:
#         for w2, p2 in Y2:
#             combined.append((w1 + w2, p1 + p2))
#
#     return pareto_filter(combined)
#
#
# def plot_graph(G, save_path, title="Tree", P=None):
#     plt.figure()
#     pos = nx.spring_layout(G)
#     nx.draw(G, pos, with_labels=True, node_color="lightblue", node_size=500)
#     labels = nx.get_edge_attributes(G, "w")
#     nx.draw_networkx_edge_labels(G, pos, edge_labels=labels)
#     if P is not None:
#         # Highlight the tour
#         edges_in_P = [(P[i], P[i + 1]) for i in range(len(P) - 1)]
#         nx.draw_networkx_edges(G, pos, edgelist=edges_in_P, width=2.5, edge_color="red")
#     plt.title(title)
#     # plt.tight_layout()
#     if save_path:
#         plt.savefig(save_path)
#     else:
#         plt.show()
#     plt.close()
#

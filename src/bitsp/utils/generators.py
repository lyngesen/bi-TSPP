import networkx as nx
import random
import math
from itertools import combinations


def generate_weights(G: nx.Graph, type: str = "nondecreasing", M: int = 100, sigma=10):

    if type not in {"random", "nondecreasing", "nonincreasing"}:
        raise ValueError(f"Unknown weight type: {type}")

    G.graph["weight_type"] = type
    G.graph["name"] += f"_weights-{type}"
    root = 0

    # --------------------------------------------------
    # Step 1: assign edge weights
    # --------------------------------------------------
    for u, v in G.edges():
        G[u][v]["w"] = random.randint(1, M)

    # --------------------------------------------------
    # Step 2: build a rooted tree structure
    # --------------------------------------------------
    T = nx.bfs_tree(G, root)
    parent = {root: None}
    for u, v in T.edges():
        parent[v] = u

    # --------------------------------------------------
    # Step 3: assign profits
    # --------------------------------------------------

    G.nodes[root]["p"] = 0

    if type in {"nondecreasing", "nonincreasing"}:
        # set a base ratio per branch
        depth = nx.single_source_shortest_path_length(T, root)
        max_depth = max(depth.values()) if len(T) > 1 else 1

        for v in nx.topological_sort(T):
            if v == root:
                continue

            u = parent[v]
            w_v = G[u][v]["w"]

            d = depth[v]

            if type == "nondecreasing":
                # mean increases linearly with depth: 0 → 100
                mu_v = 100.0 * d / max_depth

            elif type == "nonincreasing":
                # mean decreases linearly with depth: 100 → 0
                mu_v = 100.0 * (1 - d / max_depth)

            # truncated normal draw
            p_raw = random.gauss(mu_v, sigma)
            p_clamped = max(1, min(100, p_raw))

            G.nodes[v]["p"] = int(math.floor(p_clamped))
    # --------------------------------------------------
    # Random
    # --------------------------------------------------
    if type == "random":
        for v in G.nodes():
            G.nodes[v]["p"] = random.randint(1, M) if v != root else 0


def generate_graph(n, S, type: float = 0.5, root_in_subgraphs: bool = True):

    assert n >= S + 1, "Need at least S+1 nodes"

    type_str = f"{type}" if isinstance(type, str) else f"float-{type*100:.0f}"
    arg_string = f"n-{n}_S-{S}_type-{type_str}"

    G = nx.Graph()
    G.add_node(0)
    # save metadata
    G.graph["name"] = arg_string
    G.graph["type"] = type
    G.graph["n"] = n
    G.graph["S"] = S

    nodes = list(range(1, n))
    random.shuffle(nodes)

    # root children (exactly S)
    root_children = nodes[:S]
    rest = nodes[S:]

    # elif isinstance(type, float):
    if isinstance(type, (int, float)):
        parts = [[] for _ in range(S)]
        # create balanced distribution of remaining nodes to S subtrees
        for i, v in enumerate(rest):
            parts[i % S].append(v)
        assert 0.0 <= type <= 1.0, f"type as float must be in [0,1] {type=}"
        for c, part in zip(root_children, parts):
            nodes_in_subtree = [c] + part

            # Step 1: create a random spanning tree
            nodes = nodes_in_subtree[:]
            random.shuffle(nodes)

            for i in range(1, len(nodes)):
                # connect each node to a random earlier node → ensures connectivity
                u = nodes[i]
                v = random.choice(nodes[:i])
                G.add_edge(u, v)

            # step 2: connect the root to the subtree if root_in_subgraphs is True
            if root_in_subgraphs:
                _random_node = random.choice(nodes_in_subtree)
                G.add_edge(0, _random_node)

            # Step 3: optionally densify (like your "complete" case but probabilistic)
            p = type
            for u, v in combinations(nodes_in_subtree + [0], 2):
                if not G.has_edge(u, v) and random.random() < p:
                    G.add_edge(u, v)
    else:
        raise ValueError(f"Unknown tree type: {type}")

    return G

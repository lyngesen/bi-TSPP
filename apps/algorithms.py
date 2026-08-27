import marimo

__generated_with = "0.23.4"
app = marimo.App()


@app.cell
def _():
    import marimo as mo
    from bitsp.utils.generators import generate_graph, generate_weights
    from bitsp.classes.instance import Instance
    import matplotlib.pyplot as plt
    import networkx as nx
    import random

    random.seed(1)

    n_slider = mo.ui.slider(6, 40, value=20, step=1, label="n")
    p_slider = mo.ui.slider(0, 1, value=0.5, step=0.01, label="p")

    weight_type_dropdown = mo.ui.dropdown(
        options=["nonincreasing", "nondecreasing", "random"],
        value="nonincreasing",
        label="weight_type",
    )

    mo.hstack([n_slider, p_slider, weight_type_dropdown])
    return (
        Instance,
        generate_graph,
        generate_weights,
        mo,
        n_slider,
        nx,
        p_slider,
        plt,
        weight_type_dropdown,
    )


@app.cell
def _(mo, n_slider):
    S_slider = mo.ui.slider(2, n_slider.value - 1, value=2, step=1, label="S")
    S_slider
    return (S_slider,)


@app.cell
def _(I, plot_graph_interactive):
    # --- Call it ---
    plot_graph_interactive(I)
    return


@app.cell
def _(
    Instance,
    S_slider,
    generate_graph,
    generate_weights,
    n_slider,
    nx,
    p_slider,
    plt,
    weight_type_dropdown,
):
    n = n_slider.value
    S = S_slider.value
    p = p_slider.value
    weight_type = weight_type_dropdown.value


    G = generate_graph(n, S, p, root_in_subgraphs=True)
    generate_weights(G, weight_type)


    if False:
    # read saved version
        G = nx.read_gpickle("plots/example_plot_paper/graph.gpickle")



    I = Instance.from_graph(G)

    if False:
        Instance.from_json("presets/testbank/n-18_S-2_type-float-33_weights-random_seed-3.json")


    I.init_graph()



    fig, ax = plt.subplots()
    I.set_subgraphs()
    I.plot_graph(ax=ax)

    #
    plt.savefig("results/plots/example_repo.png", dpi=300)

    plt.show()
    return G, I


@app.cell
def _(I, mo, plt):

    fig2, ax2 = plt.subplots()
    I.set_subgraphs()
    I.plot_graph(ax=ax2)

    # Wrap the figure for interactive box/lasso selection
    mo.ui.matplotlib(ax2)
    return


@app.cell
def _(G, mo):
    from pyvis.network import Network as _Network

    _net = _Network(notebook=True, cdn_resources="in_line", height="500px", width="100%")
    _net.from_nx(G)
    _net.toggle_physics(True)

    _html = _net.generate_html()

    mo.iframe(_html)
    return


@app.cell(hide_code=True)
def _(mo):
    import networkx as _nx
    from matplotlib import cm as _cm
    from matplotlib.colors import to_hex as _to_hex
    from pyvis.network import Network as _Network


    def plot_graph_interactive(_instance, _solution=None):
        """Interactive PyVis plot of an Instance graph, mirroring plot_graph() styling.

        Args:
            _instance: Instance object with .G, .subgraphs, .set_subgraphs()
            _solution: optional Solution — its expanded edges are highlighted in green.

        Returns:
            marimo iframe element embedding the interactive graph.
        """
        if not hasattr(_instance, "G") or _instance.G is None:
            _instance.init_graph()

        _G = _instance.G
        _pos = _nx.spring_layout(_G, seed=42)

        # --- Ensure subgraphs exist ---
        if not getattr(_instance, "subgraphs", None):
            _instance.set_subgraphs(root=0)

        # --- Node profits ---
        _node_profits = _nx.get_node_attributes(_G, "p")
        _profits = list(_node_profits.values())
        _p_min, _p_max = (min(_profits), max(_profits)) if _profits else (0, 0)

        # --- Edge weights ---
        _edge_weights = _nx.get_edge_attributes(_G, "w")
        _weights = list(_edge_weights.values())
        _w_min, _w_max = (min(_weights), max(_weights)) if _weights else (0, 0)

        # --- Subgraph colors (tab10) ---
        _cmap = _cm.get_cmap("tab10")
        _node_to_sub = {}
        for _sid, _nodes in _instance.subgraphs.items():
            for _n in _nodes:
                _node_to_sub[_n] = _sid

        # --- Build PyVis network ---
        _net = _Network(notebook=True, cdn_resources="in_line", height="600px", width="100%")
        _net.toggle_physics(False)

        # Set node positions from spring_layout so layout matches matplotlib
        for _n in _G.nodes():
            _x, _y = _pos[_n]
            _net.add_node(
                _n,
                label=str(_n),
                x=_x * 800,          # scale to pixel space
                y=-_y * 800,         # flip y (matplotlib y-up, screen y-down)
                color="red" if _n == 0 else _to_hex(_cmap(_node_to_sub.get(_n, -1) % 10)),
                size=15 + 35 * (
                    ((_node_profits.get(_n, 0) - _p_min) / (_p_max - _p_min))
                    if _p_max > _p_min else 0.5
                ),
                title=f"Node {_n}\nProfit: {_node_profits.get(_n, 0)}",
            )

        # Add edges
        for _u, _v, _w in _G.edges(data="w"):
            _ewidth = (
                1 + 4 * (_w - _w_min) / (_w_max - _w_min)
                if _w_max > _w_min else 2
            )
            _net.add_edge(
                _u, _v,
                width=_ewidth,
                label=str(_w) if _w is not None else "",
                title=f"Edge {_u}–{_v}\nWeight: {_w}",
            )

        # --- Highlight solution edges in green ---
        if _solution is not None:
            _sol_edges = _instance.get_expanded_edges(_solution)
            _sol_set = {(min(_a, _b), max(_a, _b)) for _a, _b in _sol_edges}
            for _edge in _net.edges:
                _a, _b = _edge["from"], _edge["to"]
                if (min(_a, _b), max(_a, _b)) in _sol_set:
                    _edge["color"] = "green"
                    _edge["width"] = 5

        _html = _net.generate_html()
        return mo.iframe(_html)





    return (plot_graph_interactive,)


@app.cell
def _(G, I, nx, plt):
    # x = edge attribute 'w' (distance to root=0), y = node attribute 'p'

    _dists = nx.single_source_dijkstra_path_length(I.G, 0, weight="w")
    _xs = [_dists[_v] for _v in G.nodes()]
    _ys = [G.nodes[_v].get("p") for _v in G.nodes()]

    plt.figure(figsize=(8, 5))
    plt.scatter(_xs, _ys, zorder=3)
    plt.xlabel("distance to root (0) [edge attr 'w']")
    plt.ylabel("p")
    plt.title("Node p vs. weighted distance to root")
    plt.grid(True, linestyle="--", alpha=0.4)
    plt.tight_layout()
    plt.gca()
    return


@app.cell
def _(G, I, edge_color):
    from networkx.drawing.nx_agraph import graphviz_layout

    pos = graphviz_layout(G, prog="neato", root=0) # or prog="dot"

    # make edge weights euclidiean but rounded to int

    #for u, v, d in G.edges(data=True):
    #    d["w"] = int(round(d.get("w", 1)))


    # save nx object

    #nx.write_gpickle(G, "plots/example_plot_paper/graph.gpickle", protocol=4)


    # load G


    #pos = nx.spring_layout(G, seed=42)

    _color_dict = { 
        0: "red",
        1: "cyan",
        2: "green",
        3: "orange",
        4: "purple",
        5: "brown",
        6: "pink",
        7: "gray",
        8: "olive",
        9: "cyan", 
    }

    _node_color = {
        _n: _color_dict.get(_sid % 10, "black")
        for _sid, _nodes in I.subgraphs.items()
        for _n in _nodes
    }

    #_node_label = {
    #    _n: "("+str(_n) + "\\\\ p=" + str(G.nodes[_n].get("p")) + ")"
    #    for _n in G.nodes()
    #}

    _node_label = {
        _n: r"{\nodelab{_n}{_p}}".replace("_n",str(_n)).replace("_p", str(G.nodes[_n].get("p")))
        for _n in G.nodes()
    }


    #import networkx as nx
    from network2tikz import plot

    style = {
        "edge_label": [G[u][v]["w"] for u, v in G.edges()],
        "node_label": _node_label,
        "node_color": _node_color,
        "layout": pos,
        "canvas": (20, 15),
        "node_size":1.5,
        "node_label_size":10,
        "edge_label_size":10,
        "node_opacity": 0.5,
        "edge_color" : edge_color
    }


    _graph_path =     "plots/example_plot_paper/graph.tex"
    plot(
        G,
        _graph_path,
       **style,
    )

    def add_new_command(filename):

        # inject command
        with open(filename, "r") as f:
            content = f.read()

        macro = r"""
        \newcommand{\nodelab}[2]{
        \begin{math}
        \begin{matrix}
        v=#1\\p=#2
        \end{matrix}
        \end{math}
        }
        """

        with open(filename, "w") as f:
            f.write(macro + "\n" + content)

    add_new_command(_graph_path)
    return


@app.cell
def _(Instance, nx, plot_graph_interactive):
    # read graph from gpickle and plot it

    _G = nx.read_gpickle("plots/example_plot_paper/graph.gpickle")
    _I = Instance.from_graph(_G)
    plot_graph_interactive(_I)
    return


@app.cell
def _(G, chosen_P, nx):
    # redundant edges

    # for each pair u,v where (u,v) in E, check if the shortest path between u,v has total edge weight 'e' shorter than w_e. Use _ in front of all variables.
    edge_color = {}

    for _u, _v, _w in G.edges(data="w"):
        _shortest_path_length = nx.dijkstra_path_length(G, _u, _v, weight="w")
        if _shortest_path_length < _w:
            print(f"Redundant edge: ({_u}, {_v}) with weight {_w} has shorter path length {_shortest_path_length}")
        edge_color[(_u, _v)] = "red" if _shortest_path_length < _w else "black"

    edge_color



    if True: # color chosen_P
        #edge_color = {}
        for _u, _v in G.edges():
            if chosen_P and (_u, _v) in eval(chosen_P):
                edge_color[(_u, _v)] = "green"
            elif chosen_P and (_v, _u) in eval(chosen_P):
                edge_color[(_u, _v)] = "green"
    return (edge_color,)


@app.cell
def _(G, I):
    # add node color dependent on subgraph membership

    # get G attributes


    G.nodes(data=True)
    I.subgraphs
    G.edges(data=True)
    return


@app.cell
def _(I):
    # Example paths

    from bitsp.utils.methods import label_solve

    # create a df with
    import pandas as pd
    # set Y,Y1,Y2...YS| cost | profit | other attributes
    front_df = pd.DataFrame(columns=["Y", "cost", "profit","name","x"])




    res = label_solve(I)

    for _i,_sol in enumerate(res.front, start=1):
        front_df = front_df._append({
            "Y": "Y",
            "cost": _sol.weight,
            "profit": _sol.profit,
                        'id': _i,
            "name": r"$\mathcal{Y}$",
                "x" : _sol.as_path()[0],
                        "edges": str(list(_sol.x.keys()))
        }, ignore_index=True)

    res_sub = []

    for _s in I.set_subgraphs():
        if _s == 0:
            continue
        _I_s = I.from_subgraph(_s)

        _res_s = label_solve(_I_s)

        for _i,_sol in enumerate(_res_s.front, start=1):
            front_df = front_df._append({
                "Y": f"Y{_s}",
                "cost": _sol.weight,
                "profit": _sol.profit,
                'id': _i,
                "name": r"$\mathcal{Y}^{%s}$" % _s,
                "x" : _sol.as_path()[0],
                "edges": str(list(_sol.x.keys()))
            }, ignore_index=True)

        res_sub.append(_res_s)
        print(f"Subgraph {_s}: {len(_res_s.front)} solutions")



    print(front_df.head())
    front_df

    # save as csv
    front_df.to_csv("plots/example_plot_paper/front_df.csv", index=False)
    return front_df, pd


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    # Pareto front plots
    """)
    return


@app.cell
def _(chosen_P, chosen_P1, chosen_P2):
    def plot_fronts():
        import pandas as pd
        import numpy as np
        standalone = True
        show_labels = False
        df = pd.read_csv("plots/example_plot_paper/front_df.csv")

        unique_names = df["name"].unique()
        colors = ["red", "blue", "green", "orange", "purple", "brown", "cyan"]
        markers = ["*", "triangle*", "square*", "diamond*", "pentagon*", "otimes*", "oplus*"]
        color_map = {name: colors[i % len(colors)] for i, name in enumerate(unique_names)}
        marker_map = {name: markers[i % len(markers)] for i, name in enumerate(unique_names)}

        lines = []
        if standalone:
            lines.append(r"\documentclass{standalone}")
            lines.append(r"\usepackage{pgfplots}")
            lines.append(r"\pgfplotsset{compat=1.18}")
            lines.append(r"\begin{document}")
        lines.append(r"\begin{tikzpicture}")
        lines.append(r"\begin{axis}[")
        lines.append(r"    xlabel={$cost$},")
        lines.append(r"    ylabel={$profit$},")
        lines.append(r"    legend style={font=\large, at={(.85,0.5)}, anchor=north west},")
        lines.append(r"    grid=both,")
        lines.append(r"    width=14cm, height=10cm,")
        lines.append(r"    xmin=0,")
        lines.append(r"    ymin=0,")
        lines.append(r"]")

        for name, group in df.groupby("name"):
            color = color_map[name]
            marker = marker_map[name]

            # --- Marks: different shapes + transparency ---
            coords = [f"({row['cost']},{row['profit']})" for _, row in group.iterrows()]
            lines.append(
                r"\addplot[only marks, mark=" + marker +
                r", mark size=2.5pt, color=" + color +
                r", mark options={fill opacity=0.5, draw opacity=0.8}] coordinates {"
            )
            lines.append("    " + " ".join(coords))
            lines.append(r"};")
            lines.append(r"\addlegendentry{" + name + "}")

            if show_labels:
                # --- Labels ---
                lines.append(
                    r"\addplot[mark=none, only marks, forget plot, "
                    r"nodes near coords={\tiny $y^{\pgfplotspointmeta}$}, "
                    r"every node near coord/.append style={anchor=south, font=\tiny}, "
                    r"point meta=explicit symbolic] coordinates {"
                )
                for _, row in group.iterrows():
                    lines.append(f"    ({row['cost']},{row['profit']}) [{int(row['id'])}]")

            if chosen_P:
                # --- Highlight selected point ---
                selected_rows = group[group["edges"] == chosen_P]
                if not selected_rows.empty:
                    for _, sel_row in selected_rows.iterrows():
                        #lines.append(
                        #    r"\addplot[only marks, mark=square, mark size=3pt, color=black] coordinates {"
                        #    f"({sel_row['cost']},{sel_row['profit']})"
                        #    r"};"
                        #)
                        lines.append(
                            r"\node[anchor=south west, font=\small, color=black] at (axis cs:"
                            f"{sel_row['cost']},{sel_row['profit']}) {{$f(P)$}};"
                        )
            if chosen_P1 is not None:
                if chosen_P1['name'] == name:
                    lines.append(
                        r"\node[anchor=south west, font=\small, color=black] at (axis cs:"
                        #f"{sel_row['cost']},{sel_row['profit']}) {{$f(P^1)$}};"
                        f"{chosen_P1['cost']},{chosen_P1['profit']}) {{$f(P^1)$}};"
                    )
            if chosen_P2 is not None:
                if chosen_P2['name'] == name:
                    lines.append(
                        r"\node[anchor=south west, font=\small, color=black] at (axis cs:"
                        #f"{sel_row['cost']},{sel_row['profit']}) {{$f(P^2)$}};"
                        f"{chosen_P2['cost']},{chosen_P2['profit']}) {{$f(P^2)$}};"
                    )

        #lines.append(r"};")

        lines.append(r"\end{axis}")
        lines.append(r"\end{tikzpicture}")
        if standalone:
            lines.append(r"\end{document}")

        output_path = "plots/example_plot_paper/scatter.tex"
        tex_content = "\n".join(lines)
        with open(output_path, "w") as f:
            f.write(tex_content)

        print(f"Written to {output_path}")
        print(f"Groups: {list(unique_names)}")
        print(f"Colors: {color_map}")
        print(f"Markers: {marker_map}")

    plot_fronts()
    return


@app.cell
def _(mo, pd):
    #import marimo as mo
    import plotly.express as px


    _df = pd.read_csv("plots/example_plot_paper/front_df.csv")

    #_df = front_df

    _fig = px.scatter(
        _df,
        x="cost",
        y="profit",
        color="name",
        hover_data=["id", "edges"],
        title="Pareto Fronts (SELECT BY MARKING AN AREA)",
        labels={"cost": "Cost", "profit": "Profit", "name": "Subgraph"},
    )
    _fig.update_traces(marker=dict(size=12, opacity=0.6), selector=dict(mode='markers'))

    selected_point = mo.ui.plotly(_fig, label="Select a point")

    selected_point
    return (selected_point,)


@app.cell
def _(front_df, mo, selected_point):
    _selection = selected_point.value

    if _selection:
        _row = _selection[0]
        _id = int(_row["id"])
        _edges = _row.get("edges", "")
        _nodes = _row.get("x", "")
        chosen_P_nodes = _nodes
        chosen_P = _edges
    else:
        if False:
            chosen_P = None
            chosen_P_nodes = None
        else: #choose random
            #_row = front_df.sample(n=1).iloc[0] 
            #choose row where Y="Y" and id is largest
            _row = front_df[front_df["Y"] == "Y"].sort_values(by="id", ascending=False).iloc[0]
            chosen_P = _row["edges"]
            chosen_P_nodes = _row["x"]

    def get_subpaths(P, front_df):
        # find two rows P1 and P2 for which P1.profit + P2.profit = P.profit and P1.cost + P2.cost = P.cost
        if not P:
            return None, None
        else:
            _row = front_df[front_df["edges"] == P]
            if _row.empty:
                return None, None
            else:
                _profit = _row["profit"].values[0]
                _cost = _row["cost"].values[0]
                # find two rows P1 and P2 for which P1.profit + P2.profit = P.profit and P1.cost + P2.cost = P.cost
                for _, row1 in front_df.iterrows():
                    for _, row2 in front_df.iterrows():
                        if (row1["profit"] + row2["profit"] == _profit and
                            row1["cost"] + row2["cost"] == _cost and row1["Y"] != "Y" and row2["Y"] != "Y"):
                            return row1, row2
                return None, None

    chosen_P1, chosen_P2 = get_subpaths(chosen_P, front_df)

    try:
        chosen_P_row = list(front_df[front_df["edges"] == chosen_P].iterrows())[0][1]
    except IndexError:
        chosen_P_row = None
    #chosen_P1 = [e for e in eval(chosen_P) if e[0] in I.subgraphs[1] and e[1] in I.subgraphs[1]]

    mo.md(f"**Selected:** `chosen_P = {chosen_P}`n" +
          f" (edges in subgraph 1: {chosen_P_nodes}) "
         )
    return chosen_P, chosen_P1, chosen_P2, chosen_P_row


@app.cell
def _(chosen_P1, chosen_P_row):
    def write_path_paper(path_object,name):
        edges = eval(path_object["edges"])
        nodes = (path_object["x"])

        #for v,e in zip(nodes, edges):
        #    print(f"Node: {v}, Edge: {e}")

        out = f"${name} = ("
        #for v,e in zip(nodes, edges):
        for e in edges:
            v = e[0]

            e = (min(e), max(e))  # ensure edge is in (min, max) order)
            if v == 0:
                out += r"r,e_{%e},".replace("%v", str(v)).replace("%e", str(e))

            else:

                out += r"v_{%v},e_{%e},".replace("%v", str(v)).replace("%e", str(e))

        out += "r)$"
        return(out)

    write_path_paper(chosen_P_row, "P")
    write_path_paper(chosen_P1, "P^1")
    write_path_paper(chosen_P1, "P^2")
    return (write_path_paper,)


@app.cell
def _(chosen_P1, chosen_P2, chosen_P_row, mo, write_path_paper):
    # example for paper
    # The path P = (r,e^1,v^1,e^2,\dots,r) can be split up into P^1 and P^2.
    paper_str = f"The path {write_path_paper(chosen_P_row, 'P')} can be split up into {write_path_paper(chosen_P1, 'P^1')} and {write_path_paper(chosen_P2, 'P^2')}."



    out_str = f"""
    {paper_str}

    Where the excursions P1 and P2 has total distance ${chosen_P1['cost']}$ and ${chosen_P2['cost']}$ respectively, and total profits ${chosen_P1['profit']}$ and ${chosen_P2['profit']}$ respectively. This  ${chosen_P_row['cost']}$ and total profit ${chosen_P_row['profit']}$. 
    """

    print(out_str)

    mo.md(out_str)

    # save to markdown file
    return (out_str,)


@app.cell
def _(out_str):

    with open("plots/example_plot_paper/paper_str.md", "w") as f:
        f.write(out_str)
    return


if __name__ == "__main__":
    app.run()

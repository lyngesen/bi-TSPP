# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "marimo",
#     "pandas",
#     "plotly",
# ]
# ///

import marimo

__generated_with = "0.23.4"
app = marimo.App(width="medium")


@app.cell
def _():
    import marimo as mo
    import pandas as pd
    import plotly.express as px
    import json
    import tabulate
    import os
    from bitsp.classes.instance import Instance
    import matplotlib.pyplot as plt
    import re

    return Instance, json, mo, os, pd, plt


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    # Results

    To run this notebook, download and follow the installation instructions in the repository [lyngesen/bi-TSPP](https://github.com/lyngesen/bi-TSPP).
    """)
    return


@app.cell
def _():
    # define test to read

    test_name = "small-test"
    test_name = "testbed_100"
    return (test_name,)


@app.cell(hide_code=True)
def _(mo, os, test_name):
    # add slider int between 0-8280
    _instance_dir = f"instances/presets/{test_name.split('_')[0]}"
    instances = [f for f in os.listdir(_instance_dir) if f.endswith(".json") and not f.startswith("config")]

    instance_slider = mo.ui.slider(0, len(instances)-1, value=2, step=1, label="instance_id (for plot)")
    instance_slider
    return instance_slider, instances


@app.cell(hide_code=True)
def _(Instance, instance_slider, instances, mo, plt, test_name):
    # plot the instance with instance_id
    _instance_dir = f"instances/presets/{test_name.split('_')[0]}"

    _I_name = instances[instance_slider.value]
    #if True:
    #    _I_name ="n-26_S-2_type-float-0_weights-random_seed-3.json"
    _I_name
    _I = Instance.from_json(f"instances/presets/{test_name.split('_')[0]}/" + _I_name, path=True)
    fig2, ax2 = plt.subplots()
    _I.set_subgraphs()
    _I.plot_graph(ax=ax2)
    ax2.set_title(f"Instance: {_I_name}\nS={_I.S}, S_subgraphs={len(_I.subgraphs)-1}")
    mo.ui.matplotlib(ax2)
    return


@app.function(hide_code=True)
def compute_decomposition_gain(df):
    """Compute the decomposition gain DG^m_I = 1 - T^m_dec / T^m for each instance and method.

    Only defined when both T^m (non-decomposition) and T^m_dec (decomposition) exist
    for the same instance and base method.
    """
    # Split into decomposition and non-decomposition rows
    df_dec = df[df["dec"] == True].copy()
    df_nondec = df[df["dec"] == False].copy()

    # Match on instance + basename (the base method, e.g. "MIP-MTZ", "MIP-LazyS", "MIP-Flow")
    merged = df_nondec.merge(
        df_dec,
        on=["instance", "basename", "n", "m", "S", "weight_type", "p_value", "seed"],
        suffixes=("", "_dec"),
        how="inner",
    )

    # Compute decomposition gain
    merged["decomposition_gain"] = 1.0 - merged["total_time_dec"] / merged["total_time"]

    # count only where both where solved within the allocated time
    merged =merged[(merged['too_long']==False) & (merged['too_long_dec']==False)]

    # Select relevant columns for the result
    result = merged[
        [
            "instance",
            "basename",
            "n",
            "S",
            "seed",
            "total_time",
            "total_time_dec",
            "decomposition_gain",
            "Y",
            "Y_dec",
            "too_long",
            "too_long_dec",
        ]
    ].copy()

    result.rename(
        columns={
            "total_time": "T_m",
            "total_time_dec": "T_m_dec",
        },
        inplace=True,
    )

    return result.sort_values("decomposition_gain", ascending=False)


@app.cell
def _(pd):
    # filters and transformations
    def filter_mutate_df(df):
        # read Seed and S
        df = df.copy()
        df["seed"] = (
            df["instance"].str.extract(r"seed-(\d+)", expand=False).astype("Int64")
        )
        df["S"] = df["S"]
        # calculate time per ND point
        df["time_pr_Y"] = df["total_time"] / df["Y"]
        df = df[df["skipped"] == False] # remove all rows that were skipped
        # remove if time-limit-exceeded, skipped
        df = df[df['time_limit_exceeded']==False] # removes those cases where the algorithm were terminated early
        df = df[df['too_long']==False] # removes the cases where algorithms were not stopped early, but total time exceeded the limit. (ie solver time + overhead > time limit). This happened in 4 cases.


        df["m_s_n_count"] = df.groupby(["method", "S", "n"])["n"].transform("size")

        df["m_s_n_count_max"] = (
            df.groupby(["method", "S"])["m_s_n_count"]
              .transform("max")
        )

        #df = df[df["m_s_n_count"] == df["m_s_n_count_max"]]

        for col in df.columns:
            if col not in ["instance", "method", "weight_type", "p_value", "basename"]:
                df[col] = pd.to_numeric(df[col], errors="coerce")

        return df

    return (filter_mutate_df,)


@app.cell(hide_code=True)
def _(json, pd, test_name):
    # load json
    # print instance config
    with open(f"instances/presets/{test_name.split('_')[0]}/config.json", "r") as _f:
        instance_config_dir = json.load(_f)

    config_df = pd.DataFrame(
        [(k, str(v)) for k, v in instance_config_dir.items()], columns=["Parameter", "Value"]
    )

    # print to markdown file (imported in Obsidian)
    with open(f"results/data/{test_name}_config.md", "w", encoding="utf-8") as _f:
        _f.write(config_df.to_markdown(index=False))
    config_df
    return


@app.cell(hide_code=True)
def _(filter_mutate_df, pd, test_name):
    # Read the data
    df = pd.read_csv(f"results/data/results_{test_name}.csv")
    df_raw = df.copy()
    df = filter_mutate_df(df)
    dg = compute_decomposition_gain(df)
    return df, df_raw, dg


@app.cell(hide_code=True)
def _(mo):
    mo.md("""
    # Computational Study Analysis
    """)
    return


@app.cell
def _(df):
    df
    return


@app.cell(hide_code=True)
def _(alt, df):
    # Identify subtask time columns
    _time_cols = [
        _c
        for _c in df.columns
        if _c.endswith("_time")
        and _c not in ["max_solution_time", "config_skip_time", "total_time"]
    ]

    # Clean method names
    _df = df.copy()
    _df["method"] = _df["method"].astype(str).str.strip()

    _facet = "n"

    # Aggregate by method, n, and S
    _df_agg = _df.groupby(["method", _facet, "S"], as_index=False)[_time_cols].mean()

    _plots = []

    for _method, _method_df in _df_agg.groupby("method"):

        _plot_df = _method_df.melt(
            id_vars=["method", _facet, "S"],
            value_vars=_time_cols,
            var_name="subtask",
            value_name="time",
        )

        _plot_df["subtask"] = _plot_df["subtask"].str.replace("_time", "", regex=False)

        _plot_df = _plot_df[_plot_df["time"] > 0]

        _chart = (
            alt.Chart(_plot_df)
            .mark_bar()
            .encode(
                y=alt.Y(
                    "S:O",
                    title="S",
                    sort="ascending",
                ),
                x=alt.X(
                    "sum(time):Q",
                    title="Time (s)",
                    stack="zero",
                ),
                color=alt.Color(
                    "subtask:N",
                    title="Subtask",
                ),
                column=alt.Column(
                    f"{_facet}:N",
                    title=_facet,
                ),
                tooltip=[
                    alt.Tooltip("S:O"),
                    alt.Tooltip(f"{_facet}:N"),
                    alt.Tooltip("subtask:N"),
                    alt.Tooltip("sum(time):Q", format=".4f"),
                ],
            )
            .properties(
                title=f"{_method} — Time Breakdown",
                width=180,
                height=300,
            )
            .resolve_scale(
        x="independent",
        #y="independent",
    )
        )

        _plots.append(_chart)

    _plots
    return


@app.cell(hide_code=True)
def _(alt, df):


    _df = df[(df["too_long"] == False) & (df["time_limit_exceeded"] == False) ] .copy()
    #_df = filter_mutate_df(df)
    #_df = df.copy()
    # --- compute counts per (method, n) ---
    counts = (
        _df.groupby(["method", "n"])
        .size()
        .reset_index(name="count")
    )

    I_max = counts["count"].max()

    # --- assign y-band per method ---
    methods = (
        counts[["method"]]
        .drop_duplicates()
        .sort_values("method")
        .reset_index(drop=True)
    )
    methods["y_base"] = methods.index * (I_max + 5)
    counts = counts.merge(methods, on="method")

    counts["y_top"] = counts["y_base"] + counts["count"]

    # --- y-axis tick labels ---
    tick_vals = methods["y_base"].tolist()
    tick_labels = methods["method"].tolist()

    _chart = (
        alt.Chart(counts)
        .mark_area(opacity=0.7)
        .encode(
            x=alt.X("n:Q", title="n", sort="ascending"),
            y=alt.Y(
                "y_top:Q",
                title="Solved instances",
                axis=alt.Axis(
                    values=tick_vals,
                    labelExpr="{"
                    + ", ".join([f'"{v}": "{l}"' for v, l in zip(tick_vals, tick_labels)])
                    + "}[datum.value]",
                    labelFontSize=10,
                    titleFontSize=10,
                ),
            ),
            y2=alt.Y2("y_base:Q"),
            color=alt.Color("method:N", legend=alt.Legend(title="Method", labelFontSize=10, titleFontSize=10)),
            tooltip=[
                alt.Tooltip("method:N"),
                alt.Tooltip("n:Q"),
                alt.Tooltip("count:Q"),
            ],
        )
        .properties(height=200, width=500)
        .configure_axis(grid=False)
    )

    _chart.save("results/plots/solved_per_method_area.pdf")
    _chart
    return


@app.cell(hide_code=True)
def _(df):
    # save as tex
    import matplotlib
    # Prepare data
    _df = df[(df["too_long"] == False) & (df["time_limit_exceeded"] == False) ].copy()
    _counts = _df.groupby(["basename", "dec", "n"]).size().reset_index(name="count")
    _I_max = _counts["count"].max()
    _methods = _counts[["basename", "dec"]].drop_duplicates().sort_values(["basename", "dec"]).reset_index(drop=True)
    _methods["y_base"] = _methods.index * (_I_max + 5)
    _counts = _counts.merge(_methods, on=["basename", "dec"])
    _counts["y_top"] = _counts["y_base"] + _counts["count"]

    # Configs
    _basenames = sorted(_counts["basename"].unique())
    _dec_vals = [False, True]  # Explicitly order: False, then True
    _hatch_styles = {"False": "", "True": "north west lines"}
    _colors_mpl = matplotlib.colormaps["tab10"]
    _color_map = {b: _colors_mpl(i / max(len(_basenames), 1)) for i, b in enumerate(_basenames)}

    # Build TikZ

    _lines = [
        "% Auto-generated TikZ plot",
        r'\documentclass{standalone}',
    r'\usepackage{pgfplots}',
        r'\usetikzlibrary{patterns}',
    r'\pgfplotsset{compat=1.18}',
    r'\begin{document}',
        "\\begin{tikzpicture}",
        "\\begin{axis}[",
        "    width=\\linewidth, height=8cm, axis lines=left, grid=none,",
        "    legend style={at={(1.05,1)}, anchor=north west, cells={anchor=west}},",
        "    legend entries={\\textbf{Algorithm}," + ",".join(_basenames) + ",\\textbf{Decomposed}," + ",".join(map(str, _dec_vals)) + "}",
        "]",
        "% Legend definitions",
        "\\addlegendimage{empty legend}", 
        *[f"\\addlegendimage{{fill=color{i}, draw=color{i}}}" for i in range(len(_basenames))],
        "\\addlegendimage{empty legend}",
        "\\addlegendimage{{pattern=north east lines, draw=black}}",
        "\\addlegendimage{{pattern=north west lines, draw=black}}",
    ]

    # Add plot data
    for _i, _b in enumerate(_basenames):
        _lines.append(f"\\definecolor{{color{_i}}}{{rgb}}{{{_color_map[_b][0]:.3f},{_color_map[_b][1]:.3f},{_color_map[_b][2]:.3f}}}")

    for _, _row in _methods.iterrows():
        _sub = _counts[(_counts["basename"] == _row["basename"]) & (_counts["dec"] == _row["dec"])].sort_values("n")
        if _sub.empty: continue

        _color_idx = _basenames.index(_row["basename"])
        _coords = " ".join(f"({_x},{_y:.2f})" for _x, _y in zip(_sub["n"], _sub["y_top"]))
        _base_coords = " ".join(f"({_x},{_row['y_base']:.2f})" for _x, _y in reversed(list(zip(_sub["n"], _sub["y_top"]))))

        _lines.append(f"\\addplot[fill=color{_color_idx}, fill opacity=0.6, pattern={_hatch_styles[str(_row['dec'])]}, pattern color=color{_color_idx}, draw=color{_color_idx}] coordinates {{{_coords} {_base_coords} ({_sub.iloc[0]['n']},{_row['y_base']:.2f})}};")

    _lines += ["\\end{axis}", "\\end{tikzpicture}" + "\n\\end{document}"]

    with open("results/plots/solved_per_method_area.tex", "w") as f:
        f.write("\n".join(_lines))
    return (matplotlib,)


@app.cell(hide_code=True)
def _(df, matplotlib, os):
    # save as tex

    def plot_solved_per_method_area(df, output_path="results/plots/solved_per_method_area.tex"):
        # Prepare data
        _spacing =50
        _df = df[(df["too_long"] == False) & (df["time_limit_exceeded"] == False)].copy()
        _counts = _df.groupby(["basename", "dec", "n"]).size().reset_index(name="count")
        _I_max = _counts["count"].max()
        _methods = (
            _counts[["basename", "dec"]]
            .drop_duplicates()
            .sort_values(["basename", "dec"])
            .reset_index(drop=True)
        )
        _methods["y_base"] = _methods.index * (_I_max + _spacing)
        # set y_base based on only basename
        _methods["y_base"] = _methods.groupby("basename").ngroup() * (_I_max + _spacing)
        _counts = _counts.merge(_methods, on=["basename", "dec"])
        _counts["y_top"] = _counts["y_base"] + _counts["count"]

        # Configs
        _basenames = sorted(_counts["basename"].unique())
        _dec_vals = [False, True]
        _hatch_styles = {"False": "fill", "True": "north west lines"}
        _colors_mpl = matplotlib.colormaps["tab10"]
        _color_map = {b: _colors_mpl(i / max(len(_basenames), 1)) for i, b in enumerate(_basenames)}


        _vega_category10 = [
        "#4c78a8", "#f58518", "#e45756", "#72b7b2", "#54a24b",
        "#eeca3b", "#b279a2", "#ff9da6", "#9d755d", "#bab0ac",
        ]

        def _hex_to_rgb(hex_color):
            hex_color = hex_color.lstrip("#")
            return tuple(int(hex_color[i : i + 2], 16) / 255.0 for i in (0, 2, 4))

        _color_map = {
            b: _hex_to_rgb(_vega_category10[i % len(_vega_category10)])
            for i, b in enumerate(_basenames)
        }

        # Y-axis ticks: place a tick at each y_base, labelled with "basename (dec)" for readability
        _ytick_positions = ",".join(f"{row['y_base']:.2f}" for _, row in _methods.iterrows())
        #_ytick_labels = ",".join(
        #    f"{{{row['basename']}{'*' if row['dec'] else ''}}}"
        #    for _, row in _methods.iterrows()
        #)

        _istance_count = 180
        _y_ticks = '{0,180,190,,0,180}}'
        #
        _y_ticks = [0]
        for _ in range(3):
            _y_ticks.append(_y_ticks[-1] + _istance_count)
            _y_ticks.append(_y_ticks[-1] + _spacing)
        _y_ticks = f"{{{','.join(map(str, _y_ticks))}}}"
        #print(_y_ticks)
        _tick_labels = '{0,180,0,180,0,180}}'

        # Build TikZ
        _lines = [
            "% Auto-generated TikZ plot",
            r'\documentclass{standalone}',
            r'\usepackage{pgfplots}',
            r'\usetikzlibrary{patterns}',
            r'\pgfplotsset{compat=1.18}',
            r'\begin{document}',
            r'\begin{tikzpicture}',
            r'\begin{axis}[',
            r'    width=\linewidth, height=8cm, axis lines=left, grid=none,',
            #r'    width=\linewidth, height=8cm, axis y line=none, axis x line=left, grid=none,',
    #r'    width=\linewidth, height=8cm, axis lines=left, grid=none,',
    #r'    axis y line style={draw=none},',
    #r'    separate axis lines,',
    #r'    width=\linewidth, height=8cm, axis lines=none, axis y line style={-}, grid=none,',

            # ── Change 1: Y-axis shows band intervals, not 0-based ticks ──
            #f'    ytick={{{_ytick_positions}}},',
            #f'    yticklabels={{{_ytick_labels}}},',
            #f'    yticklabels=(10,20,30)',
            # yticks 0 at 0, 45 at 45
            #'    ytick={0,180},',
            #r'    yticklabels={0,180},',
            r'    ytick=' + _y_ticks + ',',
            r'    yticklabels={0,180,0,180,0,180},',
            # ── Change 3: no black box around legend (draw=none) ──
            r'    legend style={at={(1.05,1)}, anchor=north west, cells={anchor=west}, draw=none},',
            r'    legend entries={\textbf{Algorithm},'
            + ",".join(_basenames)
            + r',\textbf{Decomposed},'
            + ",".join(map(str, _dec_vals))
            + "}",
            r']',
            r'% Legend definitions',
            r'\addlegendimage{empty legend}',
            # ── Change 2: legend shows filled areas, not lines ──
            *[
                f"\\addlegendimage{{area legend, fill=color{i}, draw=color{i}}}"
                for i in range(len(_basenames))
            ],
            r'\addlegendimage{empty legend}',
            r'\addlegendimage{area legend, draw=black}',
            r'\addlegendimage{area legend, pattern=north west lines, draw=black}',
        ]



        # Color definitions
        for _i, _b in enumerate(_basenames):
            _lines.append(
                f"\\definecolor{{color{_i}}}{{rgb}}"
                f"{{{_color_map[_b][0]:.3f},{_color_map[_b][1]:.3f},{_color_map[_b][2]:.3f}}}"
            )

        # Plot data
        for _, _row in _methods.iterrows():
            _sub = (
                _counts[(_counts["basename"] == _row["basename"]) & (_counts["dec"] == _row["dec"])]
                .sort_values("n")
            )
            if _sub.empty:
                continue

            _color_idx = _basenames.index(_row["basename"])
            _coords = " ".join(f"({_x},{_y:.2f})" for _x, _y in zip(_sub["n"], _sub["y_top"]))
            _base_coords = " ".join(
                f"({_x},{_row['y_base']:.2f})"
                for _x, _y in reversed(list(zip(_sub["n"], _sub["y_top"])))
            )

            _lines.append(
                f"\\addplot["
                f"fill=color{_color_idx}, fill opacity=0.5, "
                f"pattern={_hatch_styles[str(_row['dec'])]}, "
                f"pattern color=color{_color_idx}, "
                f"draw=color{_color_idx}"
                f"] coordinates "
                f"{{{_coords} {_base_coords} ({_sub.iloc[0]['n']},{_row['y_base']:.2f})}};"
            )


        _lines += [r'\end{axis}', r'\end{tikzpicture}' + "\n\\end{document}"]

        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        with open(output_path, "w") as f:
            f.write("\n".join(_lines))

    plot_solved_per_method_area(df, output_path="results/plots/solved_per_method_area.tex")
    return


@app.cell
def _(alt, df):
    _df = df[(df["too_long"] == False) & (df["time_limit_exceeded"] == False)]

    # replace _df with your data source
    _chart = (
        alt.Chart(_df)
        .mark_bar()
        .encode(
            x=alt.X(aggregate="count", type="quantitative"),
            y=alt.Y(field="n", type="quantitative", stack=False, sort="ascending"),
            color=alt.Color(field="method", type="nominal"),
            tooltip=[
                alt.Tooltip(field="n", format=",.0f"),
                alt.Tooltip(aggregate="count"),
                alt.Tooltip(field="method"),
            ],
        )
        .properties(height=290, width="container", config={"axis": {"grid": False}})
    )

    _chart.save("results/plots/solved_per_method.pdf") 
    _chart
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## Filter out partially solved

    We will now remove row for each method, where only a subset of the S were solved.
    """)
    return


@app.cell
def _(df):
    # Start from non-exceeded, non-too-long rows
    df_filtered = df[
        (df["time_limit_exceeded"] == False)
        #    (df['too_long'] == False)
    ].copy()
    # df_filtered =df.copy()
    # For each (basename, dec, n, S), count how many distinct p_values were solved
    method_p_solved = df_filtered.groupby(["basename", "dec", "n", "S"])[
        "p_value"
    ].transform("nunique")

    # Keep only rows where all 3 p_values were solved for that (basename, dec, n, S)
    df_filtered = df_filtered[method_p_solved == 3]
    return (df_filtered,)


@app.cell
def _():
    import altair as alt

    return (alt,)


@app.cell
def _(alt, df_filtered):
    _df = df_filtered
    _chart = (
        alt.Chart(_df)
        .mark_line()
        .encode(
            x=alt.X("n:Q", sort="ascending"),
            y=alt.Y(
                "mean(total_time):Q",
                stack=False,
                sort="ascending",
                # scale=alt.Scale(domain=[0, 3], clamp=True),
                title="Mean solution time (seconds)",
            ),
            color=alt.Color("basename:N", legend=alt.Legend(title="Algorithm")),
            strokeDash=alt.StrokeDash("dec:N", legend=alt.Legend(title="Decomposed")),
            tooltip=[
                alt.Tooltip("n:Q", format=",.0f"),
                alt.Tooltip("mean(total_time):Q", format=",.2f"),
                alt.Tooltip("basename:N"),
                alt.Tooltip("dec:N"),
            ],
        )
        .properties(
            height=290,
            width="container",
        )
        .configure_axis(grid=False)
    )

    _chart.save("results/plots/run_time.pdf")
    # _chart
    return


@app.cell
def _(alt, df_filtered):
    _df = df_filtered
    #_df = _df[(_df["m_s_n_count"] == _df["m_s_n_count_max"])]
    _df["all_m_s_n"] = (_df["m_s_n_count"] == _df["m_s_n_count_max"])
    _df["alpha"] =(_df["all_m_s_n"]
        .map({True: 1, False: .4})
    )


    _point_markers = (
        _df.groupby(["S", "n", "method"])["all_m_s_n"]
        .all()
        .reset_index(name="all_solved")
        .query("all_solved")
        .groupby(["S", "method"])["n"]
        .max()
        .reset_index(name="max_n_all_solved")
    )
    # set point_markers['height'] = mean solution time of solved instances for S, n and method
    _point_markers["height"] = (
        _df.groupby(["S", "n", "method"])["total_time"]
        .mean()
        .reset_index(name="height")["height"]
    )

    # Bridge keys: add S_label and merge back to get mean(total_time) at that n
    _point_markers["S_label"] = _point_markers["S"].apply(lambda s: f"S = {s:.0f}")

    _marker_df = _df.merge(
        _point_markers,
        left_on=["S", "method", "n"],
        right_on=["S", "method", "max_n_all_solved"],
    ).merge(
        _df.groupby(["S", "method", "n"])["total_time"].mean().reset_index(),
        on=["S", "method", "n"],
        suffixes=("", "_mean"),
    )

    _points = (
        alt.Chart(_marker_df)
        .mark_square(size=150, color="black", opacity=0.9)
        .encode(
            x=alt.X("max_n_all_solved:Q", title="n"),
            y=alt.Y(
                "total_time_mean:Q",
                #scale=alt.Scale(domain=[0, 30], clamp=False),
                            scale=alt.Scale(type="log",clamp=False),
                title="Mean solution time (seconds)",
            ),
            column=alt.Column("S_label:N", title=None, header=alt.Header(labelFontSize=13)),
        )
    )


    _df["S_label"] = _df["S"].apply(lambda s: f"S = {s}")

    _chart = (
        alt.Chart(_df)
        .mark_line(clip=True, strokeWidth=3, point=False, opacity=0.8)
        .encode(
            x=alt.X("n:Q", sort="ascending", title="n"),
            y=alt.Y(
                "mean(total_time):Q",
                #"mean(Y):Q",
                stack=False,
                sort="ascending",
                scale=alt.Scale(type="log",clamp=False),
                title="Mean solution time (seconds)",
            ),
            #opacity=alt.value(0.5),
            color=alt.Color("basename:N", legend=alt.Legend(title="Algorithm")),
            column=alt.Column(
                "S_label:N",
                header=alt.Header(labelFontSize=13),
                title=None,
            ),
            strokeDash=alt.StrokeDash("dec:N", legend=alt.Legend(title="Decomposed")),
            tooltip=[
                alt.Tooltip("n:Q", format=",.0f"),
                alt.Tooltip("mean(total_time):Q", format=",.2f"),
                alt.Tooltip("basename:N"),
                alt.Tooltip("dec:N"),
            ],
        )
        #.properties(height=200, width=100, config={"axis": {"grid": False}})
         #   .properties(height=100, width=150, config={"axis": {"grid": False}})

    )

    _chart.save("results/plots/run_time_all_S_log.pdf")
    #_chart
    #_point_markers
    return


@app.cell
def _(alt, df_filtered):
    def plot_run_time_all_S(df_filtered, output_path="results/plots/run_time_all_S.pdf"):
        _df = df_filtered.copy()
        _df["dec"] = _df["dec"].astype(str)
        _df["all_m_s_n"] = (_df["m_s_n_count"] == _df["m_s_n_count_max"])
        _df["S_label"] = _df["S"].apply(lambda s: f"S = {int(s)}")
        _df["method"] = _df["basename"] + "_" + _df["dec"].astype(str)

        # Find largest n where all instances solved, per (S, method)
        _point_markers = (
            _df.groupby(["S", "n", "method"])["all_m_s_n"]
            .all()
            .reset_index(name="all_solved")
            .query("all_solved")
            .groupby(["S", "method"])["n"]
            .max()
            .reset_index(name="max_n_all_solved")
        )

        # Merge marker info back into _df
        _df = _df.merge(
            _point_markers[["S", "method", "max_n_all_solved"]],
            on=["S", "method"],
            how="left",
        )
        _df["is_marker"] = _df["n"] == _df["max_n_all_solved"]

        _S_values = sorted(_df["S"].unique())
        _panels = []

        for _i, _s in enumerate(_S_values):
            _dfs = _df[_df["S"] == _s].copy()
            _label = f"S = {int(_s)}"
            _is_first = _i == 0
            _is_first = 1

            _lines = (
                alt.Chart(_dfs)
                .mark_line(clip=True, strokeWidth=4, point=False, opacity=0.8)
                .encode(
                    x=alt.X("n:Q", sort="ascending", title="n"),
                    y=alt.Y(
                        "mean(total_time):Q",
                        stack=False,
                        scale=alt.Scale(domain=[0, 40], clamp=False),
                        title="Solution time (seconds)" if _i == 0 else " ",
                        axis=alt.Axis() if _is_first else alt.Axis(labels=False, ticks=False),
                    ),
                    color=alt.Color(
                        "basename:N",
                        legend=alt.Legend(title="Solver", labelFontStyle="italic",) if _is_first else None,
                    ),
                    strokeDash=alt.StrokeDash(
                        "dec:N",
                        legend=alt.Legend(title="Decomposed") if _is_first else None,
                    ),
                    tooltip=[
                        alt.Tooltip("n:Q", format=",.0f"),
                        alt.Tooltip("mean(total_time):Q", format=",.2f"),
                        alt.Tooltip("basename:N"),
                        alt.Tooltip("dec:N"),
                    ],
                )
                .properties(
        height=150, width=100,
        title=alt.TitleParams(
            text=_label,
            anchor="middle",
            frame="group",
            dy=-10,
        ),
    )

            )

            _points = (
                alt.Chart(_dfs[_dfs["is_marker"]])
                .mark_square(size=40, filled=False, strokeWidth=1, opacity=0.9)
                .encode(
                    x=alt.X("n:Q"),
                    y=alt.Y(
                        "mean(total_time):Q",
                        scale=alt.Scale(domain=[0, 30], clamp=False),
                    ),
                    color=alt.Color("basename:N", legend=None),
                    tooltip=[
                        alt.Tooltip("basename:N"),
                        alt.Tooltip("dec:N"),
                        alt.Tooltip("n:Q", format=",.0f"),
                        alt.Tooltip("mean(total_time):Q", format=",.2f"),
                    ],
                )
            )

            _panels.append(_lines + _points)

        _chart = (
            alt.concat(*_panels, spacing=10)
            .configure_axis(grid=False)
            .configure_view(stroke=None)
        )

        _chart.save(output_path)
        return _chart


    plot_run_time_all_S(df_filtered)

    # read and plot the graph
    return


@app.cell
def _(alt, df):
    # replace _df with your data source
    _df = df
    _chart = (
        alt.Chart(_df)
        .mark_line()
        .encode(
            x=alt.X("n:Q", sort="ascending"),
            y=alt.Y(
                "mean(Y):Q",
                stack=False,
                sort="ascending",
                scale=alt.Scale(domain=[0, 60], clamp=True),
                title="Mean solution time (seconds)",
            ),
            color=alt.Color("basename:N", legend=alt.Legend(title="Algorithm")),
            column=alt.Column(field="S", type="nominal"),
            strokeDash=alt.StrokeDash("dec:N", legend=alt.Legend(title="Decomposed")),
            tooltip=[
                alt.Tooltip("n:Q", format=",.0f"),
                alt.Tooltip("mean(Y):Q", format=",.2f"),
                alt.Tooltip("basename:N"),
                alt.Tooltip("dec:N"),
            ],
        )
        .properties(height=290, width=300, config={"axis": {"grid": False}})
    )
    _chart.save("results/plots/Y_all_S.pdf")

    # _chart
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## Decomposition gain measure


    The following analysis considers instances where *normal* and *Decomposition* methods are sussesfully solved (within the time-limit).
    """)
    return


@app.cell
def _(dg):
    dg
    return


@app.cell
def _(alt, dg):
    _df = dg

    base_plots = []

    for cols in [None, "n", "S"]:
        # ✅ Build encoding pieces conditionally
        encoding = {
            "x": alt.X("basename:N", title="Method"),
            "y": alt.Y(
                "decomposition_gain:Q",
                #scale=alt.Scale(domain=[-0.1, 1.05], clamp=True),
                title="Decomposition Gain",
            ),
            "color": alt.Color("basename:N", legend=alt.Legend(title="Method")),
            "tooltip": [
                alt.Tooltip("n:N", title="n"),
                alt.Tooltip("basename:N", title="Method"),
                alt.Tooltip("decomposition_gain:Q", format=".3f"),
            ],
        }

        # ✅ Only add column + tooltip when cols is not None
        if cols is not None:
            encoding["column"] = alt.Column(field=cols, type="nominal")
            encoding["tooltip"].append(alt.Tooltip(f"{cols}:N", title=cols))

        _base = (
            alt.Chart(_df)
            .mark_boxplot(extent=1.5)
            .encode(**encoding)
            .properties(
                height=100,
                width=200,
                config={"axis": {"grid": False}},
            )
        )
        base_plots.append(_base)
        _base.save(f"results/plots/decomposition_gain_{cols}.pdf")
    return (base_plots,)


@app.cell
def _(base_plots):
    base_plots
    return


@app.cell
def _(alt, dg):
    _df = dg.copy()

    _encoding = {
        "y": alt.Y("basename", title="",axis=alt.Axis(labels=False,ticks=False,)),
        "x": alt.X(
            "decomposition_gain:Q",
            scale=alt.Scale(domain=[-1.4, 1.1], clamp=True),
            title="",
                axis=alt.Axis(format=".0%",tickCount=6,grid=True,domain=False,labels=True,ticks=True),

        ),
        "color": alt.Color("basename:N", legend=alt.Legend(title="Solver",labelFontStyle="italic",)),
        "tooltip": [
            alt.Tooltip("n:N", title="n"),
            alt.Tooltip("basename:N", title="Method"),
            alt.Tooltip("decomposition_gain:Q", format=".3f"),
        ],
    }


    _base = (
        alt.Chart(_df)
        .mark_boxplot(extent=1.5)
        .encode(**_encoding)
        .properties(
            height=100,
            width=300,
            config={"axis": {"grid": False}},
        )
    )
    _base.save(f"results/plots/decomposition_gain_boxplot.pdf")
    return


@app.cell
def _(alt, dg):
    # average dg

    dg_average = dg["decomposition_gain"].mean()
    print(f"{dg_average=:.4f}")

    # average per S
    dg_average_S = (
        dg.groupby("S")["decomposition_gain"].mean().reset_index(name="dg_average")
    )

    #print(dg_average_S)

    # average per n
    dg_average_n = (
        dg.groupby("n")["decomposition_gain"].mean().reset_index(name="dg_average")
    )

    print(dg_average_n)

    chart = (
        alt.Chart(dg_average_n)
        .mark_line(point=True)
        .encode(
            x=alt.X("n:Q", title="n"),
            y=alt.Y("dg_average:Q", title="Average decomposition gain"),
            tooltip=["n", alt.Tooltip("dg_average", format=".4f")],
        )
        .properties(title="Average decomposition gain by n", width=600, height=400)
    )

    chart
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    # Numbers used in paper
    """)
    return


@app.cell
def _(df):
    df[["skipped"]].value_counts()
    return


@app.cell
def _(df, os, pd, test_name):
    # create a df of all instances read from instances/presets/{test_name.split('_')[0]} not ending in .json
    instance_dir = f"instances/presets/{test_name.split('_')[0]}"

    os.listdir(instance_dir)[:4]
    _methods = df["method"].unique()
    instance_files = [f.replace(".json","") for f in os.listdir(instance_dir) if f.endswith(".json")
                      and not f.startswith("config")]
    instance_files

    # df containing _instance_files and _methods columns. Join with df to find out which instances were not solved by any method.
    df_all = pd.DataFrame(
        [(f, m) for f in instance_files for m in _methods],
        columns=["instance", "method"],
    )

    df_all = df_all.merge(
        df,
        left_on=["instance", "method"],
        right_on=["instance", "method"],
        how="left",
        indicator=True,
    )

    #df_all
    return df_all, instance_files


@app.cell
def _(df_all, instance_files, mo, pd):
    # in total X out of Y (X/Y*100)\% expereiments were solved withing the 60 second timelimit.
    # _X if df_all has _merge=='both' nrow
    _X = df_all[df_all["_merge"] == "both"].shape[0]
    _Y = df_all.shape[0]
    mo.md(f"""
    In total {_X} out of {_Y} ({_X/_Y*100:.2f}\%) experiments were solved within the 60 second timelimit.
    """)

    _X = df_all[df_all["_merge"] == "both"].shape[0]
    _Y = df_all.shape[0]


    df_all["solved"] = df_all["_merge"] == "both"
    _total_instances = len(instance_files)

    df_summary = df_all.groupby(["basename", "dec"]).agg(
        solved_count=pd.NamedAgg(column="solved", aggfunc="sum"),
    ).reset_index().assign(
        total_count=_total_instances,
        solved_percentage=lambda x: x["solved_count"] / _total_instances * 100
    )

    # Pivot to one row per method, separate columns for dec and non-dec
    df_pivot = df_summary.pivot(index="basename", columns="dec", values=["solved_count", "solved_percentage"])

    # Flatten column names
    df_pivot.columns = [f"{col}_{dec}" for col, dec in df_pivot.columns]
    df_pivot = df_pivot.reset_index().assign(
        total=_total_instances
    ).rename(columns={
        "solved_count_False":      "solved_nondec",
        "solved_percentage_False": "pct_nondec",
        "solved_count_True":       "solved_dec",
        "solved_percentage_True":  "pct_dec",
    })

    df_pivot


    # For the methods methods[0],...,methods[2]
    # the algorithms 1,2 and 3 were able to solve pct_nondec[1], pct_nondec[2] and pct_nondec[3] percent of the instances without decompositon, but with decomposition they were able to solve pct_dec[1], pct_dec[2] and pct_dec[3] percent of the instances, respectively.

    mo.md(f"""
    In total {_X} out of {_Y} ({_X/_Y*100:.2f}\\%) experiments were solved within the 60 second timelimit.

    For the methods {df_pivot['basename'].iloc[0]}, {df_pivot['basename'].iloc[1]} and {df_pivot['basename'].iloc[2]}, the algorithms were able to solve {df_pivot['pct_nondec'].iloc[0]:.2f}\%, {df_pivot['pct_nondec'].iloc[1]:.2f}\% and {df_pivot['pct_nondec'].iloc[2]:.2f}\% of the {_total_instances} instances without decomposition, but with decomposition they were able to solve {df_pivot['pct_dec'].iloc[0]:.2f}\%, {df_pivot['pct_dec'].iloc[1]:.2f}\% and {df_pivot['pct_dec'].iloc[2]:.2f}\% of the instances, respectively.
    """)
    return


@app.cell
def _(df_raw, mo):
    df_raw[(df_raw["too_long"]) & (df_raw["time_limit_exceeded"]==False)]
    # too_long True: 75 vs False: 49,605
    # time_limit exceeded True: 139 vs False: 49,541
    skipped_count = df_raw[df_raw["skipped"]].shape[0]
    skipped_count_false = df_raw[~df_raw["skipped"]].shape[0]
    # skipped True: 30,960 vs  False: 18,720

    mo.md(r"""
    The skip rule was used for skip_count_true instances, while skipped_count_false instances were not skipped.
    """.replace("skip_count_true", str(skipped_count)).replace("skipped_count_false", str(skipped_count_false)))
    return


@app.cell
def _(df_raw, pd):
    _df = df_raw[
        (df_raw["too_long"] == False) & (df_raw["time_limit_exceeded"] == False)
    ].copy()

    total_instances = _df["instance"].nunique()
    num_algorithms = _df[["basename", "dec"]].drop_duplicates().shape[0]  # = 6
    total_experiments = num_algorithms * total_instances

    # Counts per (basename, dec)
    _solved = (
        _df[_df["skipped"] == False]
        .groupby(["basename", "dec"])["instance"]
        .nunique()
        .rename("solved_count")
    )

    _skipped = (
        _df[_df["skipped"] == True]
        .groupby(["basename", "dec"])["instance"]
        .nunique()
        .rename("skipped_count")
    )

    _table = (
        pd.concat([_solved, _skipped], axis=1)
        .reset_index()
        .assign(
            total_count=total_instances,
            solved_count=lambda x: x["solved_count"].fillna(0).astype(int),
            skipped_count=lambda x: x["skipped_count"].fillna(0).astype(int),
        )
        .assign(
            solved_percentage=lambda x: x["solved_count"] / x["total_count"] * 100,
            skipped_percentage=lambda x: x["skipped_count"] / x["total_count"] * 100,
        )
        .sort_values(by=["basename", "dec"])
    )

    # --- Subtotals per dec value (across all methods) ---
    num_methods = _df["basename"].nunique()  # = 3
    total_per_dec = num_methods * total_instances

    def _dec_subtotal(dec_val, label):
        mask = _table["dec"] == dec_val
        s  = _table[mask]["solved_count"].sum()
        sk = _table[mask]["skipped_count"].sum()
        return {
            "basename": label,
            "dec": dec_val,
            "solved_count": s,
            "skipped_count": sk,
            "total_count": total_per_dec,
            "solved_percentage": s  / total_per_dec * 100,
            "skipped_percentage": sk / total_per_dec * 100,
        }

    _subtotals = pd.DataFrame([
        _dec_subtotal(False, r"\textbf{All methods}"),
        _dec_subtotal(True,  r"\textbf{All methods}"),
    ])

    # --- Grand total row ---
    total_solved  = _table["solved_count"].sum()
    total_skipped = _table["skipped_count"].sum()

    _totals = pd.DataFrame([{
        "basename": r"\textbf{All experiments}",
        "dec": "",
        "solved_count":  total_solved,
        "skipped_count": total_skipped,
        "total_count":   total_experiments,
        "solved_percentage":  total_solved  / total_experiments * 100,
        "skipped_percentage": total_skipped / total_experiments * 100,
    }])

    _table = pd.concat([_table, _subtotals, _totals], ignore_index=True)

    # Thousand separators — now includes total_count too
    def fmt_thousands(n):
        return f"{int(n):,}".replace(",", r"\,")

    for col in ["total_count", "solved_count", "skipped_count"]:  # ← added total_count
        _table[col] = _table[col].apply(fmt_thousands)

    # Rename methods to LaTeX commands
    _method_map = {
        "Label":    r"\Label",
        "MIP-Lazy": r"\Lazy",
        "MIP-MTZ":  r"\MTZ",
    }
    _table["basename"] = _table["basename"].replace(_method_map)

    _col_order = [
        "basename", "dec", "total_count",          # ← total_count after dec
        "solved_count", "solved_percentage",
        "skipped_count", "skipped_percentage",
    ]

    latex_table = _table[_col_order].to_latex(
        index=False,
        escape=False,
        float_format="%.2f",
        header=["Method", "Decomposed", "Experiments",   # ← new header
                "Solved Count", "Solved \\%", "Skipped Count", "Skipped \\%"],
        caption="Summary of solved and skipped instances per method.",
        label="tab:solved_skipped_summary",
        column_format="llrrrrr",                         # ← one more r
    )

    # Add \midrule before subtotals and before grand total
    lines = latex_table.splitlines()
    br_idx = next(i for i, l in enumerate(lines) if r"\bottomrule" in l)
    lines.insert(br_idx - 1, r"\midrule")   # before "All experiments"
    lines.insert(br_idx - 3, r"\midrule")   # before "All methods" False row

    print("\n".join(lines))
    return


@app.cell
def _(df_filtered, mo):
    # For the decomposition methods on average \nrrel of the time were spent on the filtering operations (Line \nrval in Alg), while the remainder was spend solving the subproblems $I^s$. The time spend on decomposing the graph took less than \nrrel one average. BASED on df

    _time_spend_total_dec = df_filtered[df_filtered["dec"] == True]["total_time"].sum()
    _time_spend_filtering_dec = df_filtered[df_filtered["dec"] == True]["combine_fronts_time"].sum()
    _time_spend_extract_dec = df_filtered[df_filtered["dec"] == True]["extract_subgraph_time"].sum()

    mo.md(f"""
    For the decomposition methods on average {(_time_spend_filtering_dec/_time_spend_total_dec*100):.2f}\% of the time were spent on the filtering operations, while the remainder was spent solving the subproblems $I^s$. The time spent on decomposing the graph took less than {(_time_spend_extract_dec/_time_spend_total_dec*100):.2f}\% on average.
    """)
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    # RQ 3
    """)
    return


@app.cell
def _(dg, mo):


    dg["s_ratio"] = dg["S"] / dg["n"]

    _solved = len(dg[dg["decomposition_gain"] < 0])
    _rows = len(dg)
    _rel = _solved / _rows * 100
    _slowest = dg[dg["decomposition_gain"] < 0]["s_ratio"].min()
    _slowest_quantile = dg[dg["T_m"] <= _slowest].count()["s_ratio"] / len(dg) * 100


    _median_worse = dg[dg["decomposition_gain"] < 0]["T_m"].median()
    _median_all = dg["T_m"].median()

    _average_worse = dg[dg["decomposition_gain"] < 0]["T_m"].mean()
    _average_all = dg["T_m"].mean()
    _average_dg_all = dg["decomposition_gain"].mean()
    # In fact all instance with negative DG were among the _fastest fastest solved cases (_fastest_rel), and all took less than _slowest seconds to solve.
    rq3_str = r"""

    In total _\nval{_rows} instances were solved for both decomposed and non-decomposed algorithms, and the average decomposition gain was \nrval{_average_dg_all}.}

    The only cases with a negative decomposition gain, was in \nrval{_solved} out of \nrval{_rows} (\nrrel{_rel}) cases.

    For these cases the overhead of setting up several subproblems were relatively high, since the total computational costs were low. The median (average) running time for all instances were \nrval{_median_all} (\nrval{_average_all}) seconds, while the median (average) running time for instances with negative DG were \nrval{_median_worse} (\nrval{_average_worse}) seconds..

    These were cases with few nodes and many subgraphs. 

    """.replace("_solved", str(_solved)
        ).replace("_rows", str(_rows)).replace("_rel", f"{_rel:.2f}").replace("_fastest", f"{_slowest_quantile}").replace("_slowest", str(_slowest)).replace("_median_all", f"{_median_all:.2f}").replace("_median_worse", f"{_median_worse:.2f}").replace("_average_all", f"{_average_all:.2f}").replace("_average_worse", f"{_average_worse:.2f}").replace("_average_dg_all",f"{_average_dg_all*100:.2f}")

    mo.md(rq3_str)

    #_slowest
    #_slowest_quantile
    #dg
    return


@app.cell
def _(alt, dg):
    dg["dec_worse"] = dg["decomposition_gain"] < 0

    _dg = dg

    _boxplot = (
        alt.Chart(_dg)
        .mark_boxplot()
        .encode(
            x=alt.X("T_m:Q", title="Total running time"),
        )
    )

    _points = (
        alt.Chart(_dg)
        .mark_circle(size=60, opacity=0.7)
        .encode(
            x=alt.X("T_m:Q", title="Total running time"),
            y=alt.Y("dec_worse:N", title="Decomposition worse"),
            color=alt.Color("dec_worse:N", title="Decomposition worse"),
            tooltip=[
                alt.Tooltip("T_m:Q"),
                alt.Tooltip("decomposition_gain:Q"),
                alt.Tooltip("dec_worse:N"),
            ],
        )
    )

    _chart = _boxplot + _points
    _chart

    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    # Code correctness checks
    """)
    return


@app.cell
def _(dg):
    # make sure decomposed and non-decomposed find the same number of ND points.
    if len(dg[(dg["Y"] != dg["Y_dec"])]) > 0:
        print("Warning: Found instances where Y != Y_dec.")
        print(dg[(dg["Y"] != dg["Y_dec"])][["instance", "Y", "Y_dec"]])
    else:
        print("All instances have |Y| == |Y_dec|. i.e. decomposed and non-decomposed version found the same number of solutions")
    return


@app.cell
def _(df_filtered, np):
    # check that each all methods solved for the same instance give same number of ND points.

    # 1. Define a function to get the first mode of a group
    def get_first_mode(x):
        m = x.mode()
        return m.iloc[0] if not m.empty else np.nan

    # 2. Calculate the 'majority' Y value for each instance
    df_filtered['Y_mode'] = df_filtered.groupby('instance')['Y'].transform(get_first_mode)

    # 3. Identify rows where the actual Y differs from the majority/mode
    df_filtered['is_outlier'] = df_filtered['Y'] != df_filtered['Y_mode']

    # 4. Filter and display the inconsistencies
    outlier_rows = df_filtered[df_filtered['is_outlier']]

    print(f"Found {len(outlier_rows)} rows where Y differs from the majority value.")

    # Display the interesting columns for debugging
    debug_columns = ['instance', 'method', 'Y', 'Y_mode']

    return


@app.cell
def _(df_filtered, mo):
    # plot S read from name and S_subgraphs
    df_filtered["S_from_name"] = df_filtered["instance"].str.extract(r"S-(\d+)_", expand=False).astype(int)

    #df_filtered where method==Label-cor
    df_filtered[df_filtered["method"] == "Label-cor-dec"][["instance", "S","p_value", "S_from_name","extract_subgraph_count"]]
    #df_filtered[["instance", "method","S", "S_from_name","extract_subgraph_count"]]

    _diff_df = df_filtered[df_filtered["dec"] &(df_filtered["S_from_name"] != df_filtered["extract_subgraph_count"])][["instance", "S","p_value", "S_from_name","extract_subgraph_count","dec"]]

    _diff_df["S_diff"] = _diff_df["S_from_name"] - _diff_df["extract_subgraph_count"]



    if _diff_df.shape[0] > 0:

        _out_str = (f"""
        Found {_diff_df.shape[0]} rows where S_from_name != extract_subgraph_count for decomposed methods.
        """)
        print(_diff_df.sort_values("instance"))
    else:
        _out_str = (f"""
        No rows found where S_from_name != extract_subgraph_count for decomposed methods.
        Meaning that the number of subgraphs extracted matches the S value in the instance name for all decomposed methods.
        """)
    mo.md(_out_str)
    return


@app.cell
def _(df_filtered):
    # why do we see a dip in S=2, Lazy-dec, n around 25-28? The outlier row is shown on top of the following table.
    _df_test = df_filtered[(df_filtered["S"] == 2) & (df_filtered["method"] == "MIP-Lazy-dec") & (df_filtered["n"]==26)].copy()
    _df_test.sort_values("total_time", ascending=False)
    return


if __name__ == "__main__":
    app.run()

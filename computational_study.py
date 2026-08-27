import datetime
import json
import csv
from pathlib import Path
from functools import partial
from bitsp.classes.instance import Instance, TimingEvent
import argparse


def read_preset(name):
    presets_dir = Path("instances/presets")
    preset_dir = presets_dir / name
    assert preset_dir.exists(), f"Preset {name} does not exist."
    with open(preset_dir / "config.json", "r") as f:
        instance_dict = json.load(f)

    # instance_name_list
    # read all json files in preset_dir and return list of instance names
    for json_file in preset_dir.glob("*.json"):
        if json_file.name == "config.json":
            continue
        instance_dict.setdefault("instance_name_list", []).append(json_file.stem)

    # sort instance_name_list
    instance_dict["instance_name_list"].sort(
        key=lambda x: (int(x.split("n-")[1].split("_")[0]), int(x.split("_seed-")[1]))
    )

    return instance_dict


import argparse


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run experiments with configurable presets."
    )

    import os

    presets = os.listdir("instances/presets")
    filter(lambda x: not x.startswith("."), presets)

    parser.add_argument(
        "--preset",
        "-p",
        choices=presets,
        default="medium",
        help="Experiment preset to use (default: medium).",
    )

    parser.add_argument(
        "--exclude-methods",
        nargs="+",
        default=["MIP-Flow", "MIP-Flow-dec"],
        help="Methods to exclude (space-separated).",
    )

    parser.add_argument(
        "--skip-time",
        type=int,
        default=60,
        help="Skip time in seconds (default: 60).",
    )

    parser.add_argument(
        "--max-solution-time",
        type=int,
        default=None,
        help="Kill solver after this many seconds. Defaults to skip_time + 2.",
    )

    parser.add_argument(
        "--reset-csv",
        action=argparse.BooleanOptionalAction,
        default=False,
        help="Reset CSV files before running (default: True).",
    )

    # csv file suffix

    parser.add_argument(
        "--suffix",
        type=str,
        default="",
        help="Suffix for the CSV file (default: '').",
    )

    # add no-skip option. Such that skip_rule always returns False
    parser.add_argument(
        "--no-skip",
        action=argparse.BooleanOptionalAction,
        default=False,
        help="If set, skip_rule will always return False, and no methods will be skipped based on previous runs.",
    )

    args = parser.parse_args()

    # Derive max_solution_time if not explicitly set
    if args.max_solution_time is None:
        args.max_solution_time = args.skip_time + 2

    return args


def main():
    # run python computational_study.py --help to see the options

    args = parse_args()
    # unpack args
    preset_name = args.preset
    exclude_methods = args.exclude_methods
    skip_time = args.skip_time
    max_solution_time = args.max_solution_time
    reset_csv = args.reset_csv
    SUFFIX = args.suffix
    no_skip = args.no_skip

    from tqdm import tqdm
    from bitsp.utils.methods import (
        MIP_solve,
        MIP_solve_decomposed,
        label_solve,
        label_solve_decomposed,
    )
    import builtins

    # overwrite print to use tqdm.write for better output in tqdm progress bars
    original_print = builtins.print
    builtins.print = tqdm.write

    instances = read_preset(preset_name)

    # methods

    _MIP_args = {
        "verbose": False,
        "max_solution_time": max_solution_time,
    }

    methods = [
        (
            "MIP-MTZ",
            partial(MIP_solve, formulation="mtz", **_MIP_args),
        ),
        (
            "MIP-MTZ-dec",
            partial(MIP_solve_decomposed, formulation="mtz", **_MIP_args),
        ),
        (
            "MIP-Lazy",
            partial(MIP_solve, formulation="lazy-sec", **_MIP_args),
        ),
        (
            "MIP-Lazy-dec",
            partial(MIP_solve_decomposed, formulation="lazy-sec", **_MIP_args),
        ),
        (
            "Label",
            partial(
                label_solve,
                verbose=False,
                max_solution_time=max_solution_time,
                formulation="correction",
            ),
        ),
        (
            "Label-dec",
            partial(
                label_solve_decomposed,
                verbose=False,
                max_solution_time=max_solution_time,
                formulation="correction",
            ),
        ),
    ]

    # filter out excluded methods
    methods = [
        (method_name, method_fct)
        for method_name, method_fct in methods
        if method_name not in exclude_methods
    ]

    # initial run of all methods to init all the TimingEvent._names
    # test that all methods work on a small instance, also initialize the TimingEvent._names
    for method_name, method_fct in methods:
        I = Instance.from_json("example.json")
        print(f"Testing method {method_name} on instance {I.name}")
        res = method_fct(I)

    # Compute once, before the main loop, AFTER the warm-up (so _names is populated)
    ALL_TIMING_NAMES = sorted(TimingEvent._names)

    # hardcode fields for csv file
    BASE_FIELDS = [
        "instance",
        "method",
        "total_time",
        "dec",
        "basename",
        "Y",
        "n",
        "m",
        "S",
        "weight_type",
        "p_value",
        "too_long",
        "config_skip_time",
        "max_solution_time",
        "time_limit_exceeded",
        "skipped",
    ]
    TIMING_FIELDS = [n + "_time" for n in ALL_TIMING_NAMES] + [
        n + "_count" for n in ALL_TIMING_NAMES
    ]
    FIELDNAMES = BASE_FIELDS + TIMING_FIELDS

    csv_file = Path(f"results/data/results_{preset_name}{SUFFIX}.csv")
    if reset_csv or not csv_file.exists():
        with open(csv_file, "w") as f:
            f.write("")

    already_solved = set()
    with open(csv_file, "r") as f:
        reader = csv.DictReader(f)
        for row in reader:
            already_solved.add((row["instance"], row["method"]))
    # for debug
    # solve_again_csv = "results/data/run_again.csv"
    # with open(solve_again_csv, "r") as f:
    #     reader = csv.DictReader(f)
    #     for row in reader:
    #         print(f" running again {row['method']} on {row['instance']}")
    #         already_solved.discard((row["instance"], row["method"]))
    #
    header_written = False

    skip_methods = {}
    # read skip_methods from csv_file if it exists
    if csv_file.exists():
        with open(csv_file, "r") as f:
            reader = csv.DictReader(f)
            for row in reader:
                if row["too_long"] == "True" or row["time_limit_exceeded"] == "True":
                    method_name = row["method"]
                    n = int(row["n"])
                    S = int(row["S"])
                    if method_name not in skip_methods:
                        skip_methods[method_name] = {}
                    if n not in skip_methods[method_name]:
                        skip_methods[method_name][n] = set([S])
                    else:
                        skip_methods[method_name][n].add(S)

    def skip_rule(I, method_name, skip_methods):

        # if --no-skip is set, always return False
        if no_skip:
            return False
        # a max dict: meaning that after iteration (key) the method (value) is too slow and should be skipped
        for n in skip_methods.get(method_name, {}):
            if n < len(I.nodes) and I.S in skip_methods[method_name][n]:
                print(
                    f"Skipping method {method_name} on instance {I.name} because it is too slow for n={len(I.nodes)} and S={(I.S)}"
                )
                return True

        return False

    try:
        total = len(instances["instance_name_list"])
        starting_index = (
            len(set([row[0] for row in already_solved])) if already_solved else 0
        )
        with tqdm(
            total=total,
            desc="Instances",
            position=0,
            initial=starting_index,
        ) as pbar:
            for I_name in instances["instance_name_list"]:

                for method_name, method_fct in tqdm(
                    methods, position=1, leave=False, desc="Methods"
                ):

                    if (I_name, method_name) in already_solved:
                        print(
                            f"Skipping method {method_name} on instance {I_name} because it is already solved."
                        )
                        # pbar.update(1)

                        continue
                    I = Instance.from_json(
                        f"instances/presets/{preset_name}/{I_name}.json", path=True
                    )
                    if skip_rule(I, method_name, skip_methods):
                        print(f"Skipping method {method_name} on instance {I.name}")
                        # pbar.update(1)
                        # add row with skipped=True to csv file
                        row = {
                            "instance": I_name,
                            "method": method_name,
                            "total_time": None,
                            "dec": "dec" in method_name,
                            "basename": method_name.strip("-dec"),
                            "Y": None,
                            "n": None,
                            "m": None,
                            "S": None,
                            "weight_type": None,
                            "p_value": None,
                            "too_long": False,
                            "config_skip_time": skip_time,
                            "max_solution_time": max_solution_time,
                            "time_limit_exceeded": False,
                            "skipped": True,
                        }
                        with open(csv_file, "a", newline="") as f:
                            writer = csv.DictWriter(
                                f, fieldnames=FIELDNAMES
                            )  # fixed, not per-row
                            writer.writerow(row)

                        continue
                    print(f"Testing method {method_name} on instance {I.name}")

                    res = method_fct(I)

                    timings = res.get_timings()

                    for name in ALL_TIMING_NAMES:  # fixed set, not the live global
                        timings.setdefault(
                            name, {"count": 0, "total_time": 0.0, "avg_time": 0.0}
                        )  # floats!

                    I.set_subgraphs()

                    if len(I.subgraphs) - 1 != I.S:
                        print(
                            f"Warning: instance {I.name} has S={I.S} but {len(I.subgraphs)-1} subgraphs found."
                        )
                        raise ValueError(
                            f"Warning: instance {I.name} has S={I.S} but {len(I.subgraphs)-1} subgraphs found."
                        )
                    row = {
                        "instance": I.name,
                        "method": method_name,
                        "total_time": res.total_time,
                        "dec": "dec" in method_name,
                        "basename": method_name.strip("-dec"),
                        "Y": len(res.front),
                        "n": len(I.nodes),
                        "m": len(I.edges),
                        "S": I.S,
                        "weight_type": I.name.split("_weights-")[1].split("_")[0],
                        "p_value": I.name.split("_type-")[1].split("_")[0],
                        "too_long": res.total_time > skip_time,
                        "config_skip_time": skip_time,
                        "max_solution_time": max_solution_time,
                        "time_limit_exceeded": res.time_limit_exceeded,
                        "skipped": False,
                    }

                    row.update(
                        {
                            n + "_time": timings[n]["total_time"]
                            for n in ALL_TIMING_NAMES
                        }
                    )
                    row.update(
                        {n + "_count": timings[n]["count"] for n in ALL_TIMING_NAMES}
                    )

                    with open(csv_file, "a", newline="") as f:
                        writer = csv.DictWriter(
                            f, fieldnames=FIELDNAMES
                        )  # fixed, not per-row
                        if not header_written and reset_csv:
                            writer.writeheader()
                            header_written = True
                        writer.writerow(row)

                    if res.total_time > skip_time or res.time_limit_exceeded:
                        if method_name not in skip_methods:
                            skip_methods[method_name] = {}
                        if len(I.nodes) not in skip_methods[method_name]:
                            skip_methods[method_name][len(I.nodes)] = set([I.S])
                        else:
                            skip_methods[method_name][len(I.nodes)].add(I.S)
                        print(
                            f"Skipping {method_name} for future instances due to time {res.total_time} > {skip_time}s, and S={I.S}"
                        )

                    # run method...

                pbar.update(1)

    finally:
        builtins.print = original_print


if __name__ == "__main__":
    main()

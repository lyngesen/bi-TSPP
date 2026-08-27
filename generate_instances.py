from bitsp.classes.instance import Instance
from bitsp.utils.generators import generate_graph, generate_weights
from itertools import product
import datetime
import json
from pathlib import Path
import shutil


def make_preset():

    reset = True
    plots = False

    if True:  # instances with root in subproblems
        instance_dict = {
            "name": "testbed",
            "N_VALUES": list(range(10, 102, 2)),
            "S_VALUES": [2, 4, 6, 8],
            "WEIGHT_TYPES": ["nondecreasing", "nonincreasing", "random"],
            "P_VALUES": [0, 0.33, 0.66],
            "SEED_VALUES": [0, 1, 2, 3, 4],
            "root_in_subgraphs": True,
            "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }

    if False:  # TESTING - a small set for testing code base
        instance_dict = {
            "name": "small-test",
            "N_VALUES": list(range(10, 20, 4)),
            "S_VALUES": [2, 4],
            "WEIGHT_TYPES": ["random"],
            "P_VALUES": [0, 0.33, 0.66],
            "SEED_VALUES": [0],
            "root_in_subgraphs": True,
            "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }

    if not "root_in_subgraphs" in instance_dict:
        instance_dict["root_in_subgraphs"] = False

    # add are you sure you want to generate preset

    # Count instances: product of len() of all iterable values
    num_instances = 1
    for value in instance_dict.values():
        if isinstance(value, (list, tuple, set, range)):
            num_instances *= len(value)

    if (
        input(
            f"Are you sure you want to generate preset with name {instance_dict['name']} and {num_instances} instances? (y/n): "
        )
        != "y"
    ):
        print("Aborting.")
        return

    # if plots
    if (
        input("Do you want to generate plots for each instance? (y/n): ") == "y"
    ) and not plots:
        plots = True

    name = instance_dict["name"]
    instance_dict["path"] = f"instances/presets/{name}"

    presets_dir = Path("instances/presets")
    assert presets_dir.exists()

    preset_dir = presets_dir / name

    if preset_dir.exists():
        if not reset:
            print(f"Preset {name} already exists. Use reset=True to overwrite.")
            raise FileExistsError(preset_dir)

        shutil.rmtree(preset_dir)

    preset_dir.mkdir()

    if plots:
        (preset_dir / "plots").mkdir()

    with open(preset_dir / "config.json", "w") as f:
        json.dump(instance_dict, f, indent=3)

    for n, S, p_value, W_type, seed in product(
        instance_dict["N_VALUES"],
        instance_dict["S_VALUES"],
        instance_dict["P_VALUES"],
        instance_dict["WEIGHT_TYPES"],
        instance_dict["SEED_VALUES"],
    ):
        G = generate_graph(
            n, S, type=p_value, root_in_subgraphs=instance_dict["root_in_subgraphs"]
        )
        generate_weights(G, type=W_type)
        P = Instance.from_graph(G)
        P.init_graph()
        P.set_subgraphs()
        P.data["seed"] = seed
        P.data["name"] = P.data.get("name", "instance") + f"_seed-{seed}"
        filename = P.data.get("name", "instance")

        P.save_json(filename=preset_dir / P.default_filename(), path=True)
        if plots:
            P.plot_graph(preset_dir / "plots" / f"{filename}.pdf", show=False)


if __name__ == "__main__":

    make_preset()

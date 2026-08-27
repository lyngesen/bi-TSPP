# Repo for bi-objective TSP



## Installation

(inside the `code` directory).

- (assuming Python3 is installed) setup venv `python3 -m venv .venv`
- Install `bitsp` package:
  - Update setuptools `python -m pip install --upgrade pip setuptools wheel`
  - Install package `pip install -e . `
- Install dependencies `pip install -r requirements.txt`.
- Install `CPLEX` to use callbacks, and solve large MIPS.
  - Inside venv go to CPLEX location and run the `setup.py`.
- Run Marimo dashboard app with `Marimo edit apps/dataview.py`
 - Some plots are quite large, and cannot pre shown directly. Therefore, they are saved as pdfs.
- Run `python computational_study.py` to generate new csv result file, to read in the `Marimo app`.

```
usage: computational_study.py [-h]
                              [--preset {medium,medium-sampl}]
                              [--exclude-methods EXCLUDE_METHODS [EXCLUDE_METHODS ...]] [--skip-time SKIP_TIME]
                              [--max-solution-time MAX_SOLUTION_TIME] [--reset-csv | --no-reset-csv]

Run experiments with configurable presets.

options:
  -h, --help            show this help message and exit
  --preset {.DS_Store,large,seed-test,medium,small,medium-sample,small-test,large-test,test_comp_study,medium-test}, -p {.DS_Store,l
arge
,seed-test,medium,small,medium-sample,small-test,large-test,test_comp_study,medium-test}
                        Experiment preset to use (default: medium).
  --exclude-methods EXCLUDE_METHODS [EXCLUDE_METHODS ...]
                        Methods to exclude (space-separated).
  --skip-time SKIP_TIME
                        Skip time in seconds (default: 60).
  --max-solution-time MAX_SOLUTION_TIME
                        Kill solver after this many seconds. Defaults to skip_time + 2.
  --reset-csv, --no-reset-csv
                        Reset CSV files before running (default: True). (default: False)
```




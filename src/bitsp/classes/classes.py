from docplex.mp.model import Model
from typing import Literal
import networkx as nx

from bitsp.classes.instance import Solution, SolutionList
from cplex.callbacks import LazyConstraintCallback
from docplex.mp.callbacks.cb_mixin import ConstraintCallbackMixin

# import numpy as np
from functools import wraps
import time

ObjType = Literal[0, 1]  # 0 = weight, 1 = profit
DirType = Literal["lr", "ul"]


def update_stats(stat_key):
    def decorator(func):
        @wraps(func)
        def wrapper(self, *args, **kwargs):
            start = time.time()
            res = func(self, *args, **kwargs)
            elapsed = time.time() - start
            self.stats[stat_key] += elapsed
            return res

        return wrapper

    return decorator


class _LazySEC(ConstraintCallbackMixin, LazyConstraintCallback):
    def __init__(self, env):
        LazyConstraintCallback.__init__(self, env)
        ConstraintCallbackMixin.__init__(self)

    def __call__(self):
        sol = self.make_solution()

        model = self.model

        # get x values
        x_vals = {arc: sol.get_value(model._x[arc]) for arc in model._arcs}

        subtours = model._find_subtours(x_vals)

        for S in subtours:
            # Keep the unique tour component that contains the depot.
            # In selective TSP, non-selected nodes do not appear in S at all.
            if model._depot in S:
                continue
            if len(S) <= 1:
                continue

            # add cut: sum_{i,j in S} x[i,j] <= |S|-1
            cut = model.sum(model._x[i, j] for i in S for j in S if i != j)
            cpx_lhs, cpx_sense, cpx_rhs = self.linear_ct_to_cplex(cut <= len(S) - 1)
            self.add(cpx_lhs, cpx_sense, cpx_rhs)


class MIP(object):
    def __init__(self, G):
        self.model: Model | None = None
        self.G: nx.Graph = G
        self.stats = {"IP-calls": 0, "IP-time": 0.0}
        self.X: SolutionList = SolutionList()
        self.verbose = False

        assert 0 in G.nodes(), "Depot 0 must exist"

        # epsilon constraints
        self.eps_profit = None
        self.eps_weight = None

        self._time_limit_exceeded = False

    # -----------------------
    # SETUP MODEL (FLOW-BASED)
    # -----------------------
    def setup_mip_flow(self):
        self.model = Model(name="bi-tsp-flow")

        V = list(self.G.nodes())
        n = len(V)

        # complete directed arcs
        self.arcs = [(i, j) for i in V for j in V if i != j]

        # decision variables
        self.x = self.model.binary_var_dict(self.arcs, name="x")
        self.y = self.model.binary_var_dict(V, name="y")

        # flow variables
        self.f = self.model.continuous_var_dict(self.arcs, lb=0, ub=n - 1, name="f")

        # -----------------------
        # Depot must be visited
        # -----------------------
        self.model.add_constraint(self.y[0] == 1)

        # -----------------------
        # Degree constraints
        # -----------------------
        for i in V:
            self.model.add_constraint(
                self.model.sum(self.x[i, j] for j in V if j != i) == self.y[i]
            )
            self.model.add_constraint(
                self.model.sum(self.x[j, i] for j in V if j != i) == self.y[i]
            )

        # -----------------------
        # FLOW CONSTRAINTS
        # -----------------------

        # Flow conservation (non-depot nodes)
        for i in V:
            if i == 0:
                continue

            self.model.add_constraint(
                self.model.sum(self.f[j, i] for j in V if j != i)
                - self.model.sum(self.f[i, j] for j in V if j != i)
                == self.y[i]
            )

        # Depot flow balance
        self.model.add_constraint(
            self.model.sum(self.f[0, j] for j in V if j != 0)
            == self.model.sum(self.y[i] for i in V) - 1
        )

        # Capacity linking (flow only on used arcs)
        for i, j in self.arcs:
            self.model.add_constraint(self.f[i, j] <= (n - 1) * self.x[i, j])

        # -----------------------
        # (Optional but recommended) tightening
        # -----------------------
        for i in V:
            if i != 0:
                self.model.add_constraint(
                    self.model.sum(self.f[j, i] for j in V if j != i)
                    <= (n - 1) * self.y[i]
                )

        # -----------------------
        # Objective expressions
        # -----------------------
        self.weight_expr = self.model.sum(
            self.G[i][j]["w"] * self.x[i, j] for (i, j) in self.arcs
        )

        self.profit_expr = self.model.sum(self.G.nodes[v]["p"] * self.y[v] for v in V)

        # default objective
        self.model.minimize(self.weight_expr)

        # -----------------------
        # epsilon constraints
        # -----------------------
        self.eps_profit = self.model.add_constraint(
            self.profit_expr >= 0, ctname="eps_profit"
        )

        self.eps_weight = self.model.add_constraint(
            self.weight_expr <= 1e12, ctname="eps_weight"
        )

    # -----------------------
    # SETUP MODEL (complete graph + node selection)
    # -----------------------
    def setup_mip(self):
        self.model = Model(name="bi-tsp")

        V = list(self.G.nodes())
        n = len(V)

        # complete directed arcs
        self.arcs = [(i, j) for i in V for j in V if i != j]

        self.x = self.model.binary_var_dict(self.arcs, name="x")
        self.y = self.model.binary_var_dict(V, name="y")

        # MTZ order vars
        self.u = self.model.continuous_var_dict(V, lb=0, ub=n - 1, name="u")

        # depot must be visited
        self.model.add_constraint(self.y[0] == 1)

        # -----------------------
        # Degree constraints WITH selection
        # -----------------------
        for i in V:
            self.model.add_constraint(
                self.model.sum(self.x[i, j] for j in V if j != i) == self.y[i]
            )
            self.model.add_constraint(
                self.model.sum(self.x[j, i] for j in V if j != i) == self.y[i]
            )

        # -----------------------
        # MTZ subtour elimination
        # -----------------------
        for i in V:
            for j in V:
                if i != j and i != 0 and j != 0:
                    self.model.add_constraint(
                        self.u[i] - self.u[j] + n * self.x[i, j] <= n - 1
                    )

        # -----------------------
        # Objective expressions
        # -----------------------
        self.weight_expr = self.model.sum(
            self.G[i][j]["w"] * self.x[i, j] for (i, j) in self.arcs
        )

        self.profit_expr = self.model.sum(self.G.nodes[v]["p"] * self.y[v] for v in V)

        # default objective
        self.model.minimize(self.weight_expr)

        # -----------------------
        # epsilon constraints (non-restrictive init)
        # -----------------------
        self.eps_profit = self.model.add_constraint(
            self.profit_expr >= 0, ctname="eps_profit"
        )

        self.eps_weight = self.model.add_constraint(
            self.weight_expr <= 1e12, ctname="eps_weight"
        )

    def _find_subtours(self, x_vals):
        G_sol = nx.DiGraph()

        for (i, j), val in x_vals.items():
            if val > 0.5:
                G_sol.add_edge(i, j)

        components = list(nx.strongly_connected_components(G_sol))

        return components

    def _attach_lazy_sec_callback(self, V):
        self.model._x = self.x
        self.model._arcs = self.arcs
        self.model._V = V
        self.model._depot = 0
        self.model._find_subtours = self._find_subtours

        self.model.register_callback(_LazySEC)

    def setup_mip_lazy_SEC(self):
        self.model = Model(name="bi-tsp-lazy-sec")
        V = list(self.G.nodes())
        # arcs
        self.arcs = [(i, j) for i in V for j in V if i != j]
        self.x = self.model.binary_var_dict(self.arcs, name="x")
        self.y = self.model.binary_var_dict(V, name="y")
        # depot must be visited
        self.model.add_constraint(self.y[0] == 1)

        # -----------------------
        # Degree constraints
        # -----------------------
        for i in V:
            self.model.add_constraint(
                self.model.sum(self.x[i, j] for j in V if j != i) == self.y[i]
            )
            self.model.add_constraint(
                self.model.sum(self.x[j, i] for j in V if j != i) == self.y[i]
            )

        # -----------------------
        # Objective expressions
        # -----------------------
        self.weight_expr = self.model.sum(
            self.G[i][j]["w"] * self.x[i, j] for (i, j) in self.arcs
        )

        self.profit_expr = self.model.sum(self.G.nodes[v]["p"] * self.y[v] for v in V)

        self.model.minimize(self.weight_expr)

        # -----------------------
        # epsilon constraints
        # -----------------------
        self.eps_profit = self.model.add_constraint(
            self.profit_expr >= 0, ctname="eps_profit"
        )

        self.eps_weight = self.model.add_constraint(
            self.weight_expr <= 1e12, ctname="eps_weight"
        )

        # -----------------------
        # Attach lazy SEC callback
        # -----------------------
        self._attach_lazy_sec_callback(V)

    # -----------------------
    # UPDATE EPS CONSTRAINTS
    # -----------------------
    def _set_profit_bound(self, val):
        self.eps_profit.rhs = float(val)

    def _set_weight_bound(self, val):
        self.eps_weight.rhs = float(val)

    # -----------------------
    # SOLVE SINGLE
    # -----------------------
    def _solve_single_objective(self):

        start = time.time()
        self.stats["IP-calls"] += 1
        if __debug__ and self.verbose:
            print(
                f"Solving MIP... y={self.retrieve_solution().y if self.model.solution else 'N/A'}"
            )

        assert isinstance(self.model, Model), "Model is not set up."
        self.model.context.cplex_parameters.threads = 6
        # abs error = 1
        self.model.context.cplex_parameters.mip.tolerances.absmipgap = (
            0.5  # just under 1
        )
        self.model.context.cplex_parameters.mip.tolerances.mipgap = 1e-6
        self.model.context.cplex_parameters.mip.tolerances.integrality = 1e-10
        self.model.parameters.emphasis.numerical = 1

        # calculate remaining solver time - for early termination.
        # remaining = max - now + start
        # remaining_time = (
        #     self._max_solution_time - (time.perf_counter() - self._solve_start_time)
        #     if self._max_solution_time
        #     else None
        # )
        # if remaining_time is not None:
        #     if remaining_time < 0:
        #         self._time_limit_exceeded = True
        #         return None
        #     else:
        #         # round to 1 decimal place for CPLEX
        #         remaining_time = 1 if remaining_time < 1 else remaining_time
        #
        # Calculate remaining solver time for early termination.
        remaining_time = None
        if self._max_solution_time is not None:
            elapsed = time.perf_counter() - self._solve_start_time
            remaining_time = self._max_solution_time - elapsed

            if remaining_time <= 0:
                self._time_limit_exceeded = True
                return None

            # CPLEX accepts the value as-is; the floor of 1s is just to avoid
            # calling solve() with a uselessly tiny time limit.
            remaining_time = max(remaining_time, 1.0)

        sol = self.model.solve(time_limit=remaining_time)

        # check if time limit exceeded
        # if "time limit exceeded" in self.model.solve_details.status:
        details = self.model.solve_details
        # print(f"{self.model.solve_details.status=},{sol=}, {details.status=}")
        if details.has_hit_limit():
            self._time_limit_exceeded = True
            if __debug__:
                print("Time limit exceeded during MIP solve.")
            return None

        self.stats["IP-time"] += time.time() - start

        if __debug__:
            print("No solution found. ", self.model.solve_details.status)
            print(f"{self.eps_profit.rhs=}")
            print(f"{self.eps_weight.rhs=}")
        if sol is None:
            return None

        return self.retrieve_solution()

    def retrieve_solution(self, tol=1e-6):
        sol = self.model.solution

        def clean(v):
            r = round(v)
            if abs(v - r) > tol:
                raise ValueError(f"Value {v} not within {tol} of an integer")
            return int(r)

        return Solution(
            {
                (i, j): clean(sol.get_value(self.x[i, j]))
                for (i, j) in self.arcs
                if clean(sol.get_value(self.x[i, j])) > 0
            },
            (
                clean(sol.get_value(self.weight_expr)),
                clean(sol.get_value(self.profit_expr)),
            ),
        )

    # -----------------------
    # EPSILON CONSTRAINT METHOD
    # -----------------------
    def solve_epsilon_constraint(
        self, starting="lr", epsilon_step=0.90, max_solution_time: None | int = None
    ):
        # Keep the trivial "select nothing" alternative in all MIP fronts.
        pareto = [Solution({}, (0, 0))]

        self._solve_start_time = time.perf_counter()
        self._max_solution_time = max_solution_time
        # self.setup_mip()

        if starting == "lr":
            # start: minimize weight
            self.model.minimize(self.weight_expr)
            sol = self._solve_single_objective()

            if sol is None:
                return pareto

            current_profit = sol.y[1]

            while True:
                pareto.append(sol)

                new_bound = current_profit + epsilon_step
                self._set_profit_bound(new_bound)

                # self.model.minimize(self.weight_expr)
                sol = self._solve_single_objective()

                if sol is None:
                    break

                current_profit = sol.y[1]

        else:
            # start: maximize profit
            self.model.maximize(self.profit_expr)
            sol = self._solve_single_objective()

            if sol is None:
                return pareto

            current_weight = sol.y[0]

            while True:
                pareto.append(sol)

                new_bound = current_weight - epsilon_step
                self._set_weight_bound(new_bound)

                # self.model.maximize(self.profit_expr)
                sol = self._solve_single_objective()

                if sol is None:
                    break

                current_weight = sol.y[0]

        self.X.extend(pareto)
        return pareto

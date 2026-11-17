## Homework 3: Conditional Assignment and Meta Analysis

The original Jinja 3.1.6 release commit,
`15206881c006c79667fe5154fe80c01c65410679`, is an ancestor of this branch.
The patch tracks which names every conditional path assigns before use. This
analysis runs in the meta API. Rendering keeps the original compiler’s lookup
behavior.

### Where to Find the Fix and Tests

- **Implementation:** `_TrackingSymbols` and `_TrackingSymbolVisitor` in
  `src/jinja2/meta.py` analyze branch assignments and reads. `src/jinja2/compiler.py`
  and `src/jinja2/idtracking.py` let the meta generator select that analysis.
- **Original reproductions:** `test_assigned_in_every_branch` in
  `tests/test_meta_conditionals.py` covers both if/else and if/elif/else.
- **Additional tests:** `test_conditional_paths`,
  `test_branch_assignments_render_correctly`, and
  `test_partial_assignment_keeps_context_value` in
  `tests/test_meta_conditionals.py` cover nested and partial assignments,
  context reads, scope, and rendering.
- **Inner-scope regressions:** `test_reads_in_inner_scope_before_assignment` in
  the same file checks meta results and rendered output for a `set` block, a
  loop, and a `with` block that read a value before the enclosing assignment.

### Setup

Use Python 3.9 or newer and create a virtual environment:

```sh
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -e . pytest trio Babel
```

### Reproduce the Original Failure

The following commands extract the original commit into a temporary directory,
copy the test file, and run only the reproducing cases against the original source.
The two parametrized cases should fail because `output` appears in the result.
Run these commands from the repository root with the virtual environment active.

```sh
baseline_dir=$(mktemp -d)
git archive 15206881c006c79667fe5154fe80c01c65410679 | tar -x -C "$baseline_dir"
cp tests/test_meta_conditionals.py "$baseline_dir/tests/"
(cd "$baseline_dir" && PYTHONPATH=src python -m pytest -q \
    tests/test_meta_conditionals.py::test_assigned_in_every_branch)
```

The expected failures exit with a nonzero status. The captured output from the
original run is in `homework3/evidence/baseline-test.txt`.

### Validate the Patch

```sh
PYTHONPATH=src python -m pytest -q tests/test_meta_conditionals.py tests/test_api.py
PYTHONPATH=src python -m pytest -q
```

On Python 3.9, the focused suite passed 57 tests and the full suite passed 932.
See `homework3/evidence/focused-test.txt` and `homework3/evidence/regression-test.txt`
for the test output. The earlier patch failed all six new inner-scope cases.
See `homework3/evidence/initial-patch-scope-failures.txt` for those failures.

# Jinja

Jinja is a fast, expressive, extensible templating engine. Special
placeholders in the template allow writing code similar to Python
syntax. Then the template is passed data to render the final document.

It includes:

-   Template inheritance and inclusion.
-   Define and import macros within templates.
-   HTML templates can use autoescaping to prevent XSS from untrusted
    user input.
-   A sandboxed environment can safely render untrusted templates.
-   AsyncIO support for generating templates and calling async
    functions.
-   I18N support with Babel.
-   Templates are compiled to optimized Python code just-in-time and
    cached, or can be compiled ahead-of-time.
-   Exceptions point to the correct line in templates to make debugging
    easier.
-   Extensible filters, tests, functions, and even syntax.

Jinja's philosophy is that while application logic belongs in Python if
possible, it shouldn't make the template designer's job difficult by
restricting functionality too much.


## In A Nutshell

```jinja
{% extends "base.html" %}
{% block title %}Members{% endblock %}
{% block content %}
  <ul>
  {% for user in users %}
    <li><a href="{{ user.url }}">{{ user.username }}</a></li>
  {% endfor %}
  </ul>
{% endblock %}
```

## Donate

The Pallets organization develops and supports Jinja and other popular
packages. In order to grow the community of contributors and users, and
allow the maintainers to devote more time to the projects, [please
donate today][].

[please donate today]: https://palletsprojects.com/donate

## Contributing

See our [detailed contributing documentation][contrib] for many ways to
contribute, including reporting issues, requesting features, asking or answering
questions, and making PRs.

[contrib]: https://palletsprojects.com/contributing/

## Homework 3: Conditional Assignment and Meta Analysis

This checkout starts at Jinja 3.1.6, commit
`15206881c006c79667fe5154fe80c01c65410679`. The patch tracks names
assigned on every path through a conditional, while preserving context lookups
when a path does not assign a name or reads it before assignment. The tests are
in `tests/test_meta_conditionals.py`.

### Setup

Use Python 3.9 or newer and create a virtual environment:

```sh
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -e . pytest trio Babel
```

### Reproduce the Original Failure

The following commands extract the original commit into a temporary directory,
copy only the new reproducing tests, and run them against the original source.
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

On Python 3.9, the full suite passed: 924 tests. The output is in
`homework3/evidence/regression-test.txt`. The analysis is conservative: it does
not prove conditions mutually exclusive or unreachable, and it retains an
existing context lookup once one is required on an analyzed path.

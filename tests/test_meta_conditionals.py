import pytest

from jinja2 import meta


@pytest.mark.parametrize(
    "source",
    [
        "{% if control %}{% set output = 1 %}{% else %}"
        "{% set output = 2 %}{% endif %}{{ output }}",
        "{% if control == 1 %}{% set output = 1 %}"
        "{% elif control == 2 %}{% set output = 2 %}"
        "{% else %}{% set output = 3 %}{% endif %}{{ output }}",
    ],
    ids=["if-else", "if-elif-else"],
)
def test_assigned_in_every_branch(env, source):
    assert meta.find_undeclared_variables(env.parse(source)) == {"control"}


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        ("{% if a %}{% set x = 1 %}{% endif %}{{ x }}", {"a", "x"}),
        (
            "{% if a %}{% set x = 1 %}{% elif b %}{% set x = 2 %}"
            "{% else %}{{ x }}{% endif %}{{ x }}",
            {"a", "b", "x"},
        ),
        (
            "{% if a %}{% if b %}{% set x = 1 %}{% else %}"
            "{% set x = 2 %}{% endif %}{% else %}"
            "{% set x = 3 %}{% endif %}{{ x }}",
            {"a", "b"},
        ),
        (
            "{% if a %}{% if b %}{% set x = 1 %}{% endif %}"
            "{% else %}{% set x = 2 %}{% endif %}{{ x }}",
            {"a", "b", "x"},
        ),
        (
            "{% if a %}{{ x }}{% set x = 1 %}{% else %}"
            "{% set x = 2 %}{% endif %}{{ x }}",
            {"a", "x"},
        ),
        (
            "{% if a %}{% set x = 1 %}{% elif x %}{% set x = 2 %}"
            "{% else %}{% set x = 3 %}{% endif %}{{ x }}",
            {"a", "x"},
        ),
        (
            "{% if a %}{% set x, y = 1, 2 %}{% else %}"
            "{% set x, y = 3, 4 %}{% endif %}{{ x }}{{ y }}",
            {"a"},
        ),
        (
            "{% set x = 0 %}{% if a %}{% set x = 1 %}"
            "{% endif %}{{ x }}",
            {"a"},
        ),
        (
            "{% if a %}{% set x = 1 %}{% else %}"
            "{% set x = 2 %}{% endif %}{{ x }}{{ unrelated }}",
            {"a", "unrelated"},
        ),
        (
            "{% for item in items %}{% if flag %}{% set x = item %}"
            "{% else %}{% set x = 0 %}{% endif %}{{ x }}{% endfor %}{{ x }}",
            {"items", "flag", "x"},
        ),
        (
            "{% macro f(a) %}{% if a %}{% set x = 1 %}{% else %}"
            "{% set x = 2 %}{% endif %}{{ x }}{% endmacro %}{{ f(arg) }}",
            {"arg"},
        ),
        (
            "{% if flag %}{% set x = 1 %}{% with %}{{ x }}{% endwith %}"
            "{% else %}{% set x = 2 %}{% endif %}{{ x }}",
            {"flag"},
        ),
        (
            "{% if flag %}{% set x %}{% with x = 'local' %}{{ x }}{% endwith %}"
            "{% endset %}{% else %}{% set x = 'other' %}{% endif %}{{ x }}",
            {"flag"},
        ),
    ],
    ids=[
        "missing-else",
        "partial-elif-chain",
        "nested-complete",
        "nested-incomplete",
        "read-before-assignment",
        "elif-test-reads-name",
        "tuple-assignment",
        "prior-assignment",
        "unrelated-name",
        "loop-scope",
        "macro-scope",
        "inner-scope-read-after-assignment",
        "inner-scope-shadowing",
    ],
)
def test_conditional_paths(env, source, expected):
    assert meta.find_undeclared_variables(env.parse(source)) == expected


def test_branch_assignments_render_correctly(env):
    source = (
        "{% if a %}{% set x = 'first' %}{% elif b %}"
        "{% set x = 'second' %}{% else %}{% set x = 'last' %}"
        "{% endif %}{{ x }}"
    )
    template = env.from_string(source)
    assert template.render(a=True, b=False, x="context") == "first"
    assert template.render(a=False, b=True, x="context") == "second"
    assert template.render(a=False, b=False, x="context") == "last"


def test_partial_assignment_keeps_context_value(env):
    template = env.from_string("{% if a %}{% set x = 1 %}{% endif %}{{ x }}")
    assert template.render(a=False, x="context") == "context"
    assert template.render(a=True, x="context") == "1"


@pytest.mark.parametrize(
    "body",
    [
        "{% set x %}{{ x }}!{% endset %}{{ x }}",
        "{% for _ in [1] %}{{ x }}!{% endfor %}{% set x = 'new' %}",
        "{% with %}{{ x }}!{% endwith %}{% set x = 'new' %}",
    ],
    ids=["set-block", "loop", "with"],
)
@pytest.mark.parametrize("check", ["render", "meta"])
def test_reads_in_inner_scope_before_assignment(env, body, check):
    source = "{% if flag %}" + body + "{% else %}{% set x = 'other' %}{% endif %}"

    if check == "render":
        assert env.from_string(source).render(flag=True, x="input") == "input!"
    else:
        assert meta.find_undeclared_variables(env.parse(source)) == {"flag", "x"}

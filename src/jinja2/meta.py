"""Functions that expose information about templates that might be
interesting for introspection.
"""

import typing as t

from . import nodes
from .compiler import CodeGenerator
from .compiler import find_undeclared
from .compiler import Frame
from .idtracking import FrameSymbolVisitor
from .idtracking import Symbols
from .idtracking import VAR_LOAD_RESOLVE
from .idtracking import VAR_LOAD_UNDEFINED

if t.TYPE_CHECKING:
    import typing_extensions as te

    from .environment import Environment


class _TrackingSymbols(Symbols):
    """Track which branch assignments can hide a context lookup from meta."""

    def __init__(
        self, parent: t.Optional[Symbols] = None, level: t.Optional[int] = None
    ) -> None:
        super().__init__(parent, level)
        self.definite_stores: t.Set[str] = set()
        self.early_reads: t.Set[str] = set()

    def make_visitor(self) -> "_TrackingSymbolVisitor":
        return _TrackingSymbolVisitor(self)

    def copy(self) -> "te.Self":
        rv = super().copy()
        rv.definite_stores = self.definite_stores.copy()
        rv.early_reads = self.early_reads.copy()
        return rv

    def store(self, name: str) -> None:
        self.definite_stores.add(name)
        super().store(name)

    def declare_parameter(self, name: str) -> str:
        self.definite_stores.add(name)
        return super().declare_parameter(name)

    def load(self, name: str) -> None:
        if name not in self.definite_stores:
            self.early_reads.add(name)
        super().load(name)

    def branch_update(self, branch_symbols: t.Sequence[Symbols]) -> None:
        branches = t.cast(t.Sequence[_TrackingSymbols], branch_symbols)
        prior_stores = self.stores.copy()
        super().branch_update(branch_symbols)
        self.definite_stores = set.intersection(
            *(branch.definite_stores for branch in branches)
        )
        self.early_reads.update(*(branch.early_reads for branch in branches))

        # The normal compiler still initializes these names from the context.
        # Meta can ignore the fallback when all paths assign before any read.
        for name in self.definite_stores - prior_stores - self.early_reads:
            ref = self.refs[name]
            if self.loads[ref][0] == VAR_LOAD_RESOLVE:
                self.loads[ref] = (VAR_LOAD_UNDEFINED, None)


class _TrackingSymbolVisitor(FrameSymbolVisitor):
    def __init__(self, symbols: _TrackingSymbols) -> None:
        self.symbols = symbols

    def visit_If(self, node: nodes.If, **kwargs: t.Any) -> None:
        def visit_body(body: t.Iterable[nodes.Node]) -> _TrackingSymbols:
            state = fallthrough.copy()
            visitor = state.make_visitor()
            for child in body:
                visitor.visit(child, **kwargs)
            return state

        fallthrough = self.symbols.copy()
        branches = []
        visitor = fallthrough.make_visitor()
        for branch in (node, *node.elif_):
            visitor.visit(branch.test, **kwargs)
            branches.append(visit_body(branch.body))

        branches.append(visit_body(node.else_))
        self.symbols.branch_update(branches)

    def _read_scope(
        self, node: nodes.Node, parameters: t.Iterable[str] = (), **kwargs: t.Any
    ) -> None:
        # Analyze each inner scope on its own. Propagate its free reads, but
        # keep its assignments and parameters local to the inner scope.
        scope = _TrackingSymbols()
        for param in parameters:
            scope.declare_parameter(param)
        scope.analyze_node(node, **kwargs)
        if isinstance(node, nodes.AssignBlock) and node.filter is not None:
            scope.make_visitor().visit(node.filter)
        self.symbols.early_reads.update(scope.early_reads - self.symbols.definite_stores)

    def visit(self, node: nodes.Node, *args: t.Any, **kwargs: t.Any) -> t.Any:
        if isinstance(node, nodes.For):
            self._read_scope(node, ("loop",), for_branch="body")
            if node.test is not None:
                self._read_scope(node, for_branch="test")
            if node.else_:
                self._read_scope(node, for_branch="else")
        elif isinstance(node, (nodes.Macro, nodes.CallBlock)):
            self._read_scope(
                node, find_undeclared(node.body, ("caller", "kwargs", "varargs"))
            )
        elif isinstance(
            node, (nodes.AssignBlock, nodes.FilterBlock, nodes.Scope, nodes.With)
        ) or (isinstance(node, nodes.Block) and node.scoped):
            self._read_scope(node)

        return super().visit(node, *args, **kwargs)


class _TrackingFrame(Frame):
    symbols_class = _TrackingSymbols


class TrackingCodeGenerator(CodeGenerator):
    """We abuse the code generator for introspection."""

    frame_class = _TrackingFrame

    def __init__(self, environment: "Environment") -> None:
        super().__init__(environment, "<introspection>", "<introspection>")
        self.undeclared_identifiers: t.Set[str] = set()

    def write(self, x: str) -> None:
        """Don't write."""

    def enter_frame(self, frame: Frame) -> None:
        """Remember all undeclared identifiers."""
        super().enter_frame(frame)

        for _, (action, param) in frame.symbols.loads.items():
            if action == "resolve" and param not in self.environment.globals:
                self.undeclared_identifiers.add(param)


def find_undeclared_variables(ast: nodes.Template) -> t.Set[str]:
    """Returns a set of all variables in the AST that will be looked up from
    the context at runtime.  Because at compile time it's not known which
    variables will be used depending on the path the execution takes at
    runtime, all variables are returned.

    >>> from jinja2 import Environment, meta
    >>> env = Environment()
    >>> ast = env.parse('{% set foo = 42 %}{{ bar + foo }}')
    >>> meta.find_undeclared_variables(ast) == {'bar'}
    True

    .. admonition:: Implementation

       Internally the code generator is used for finding undeclared variables.
       This is good to know because the code generator might raise a
       :exc:`TemplateAssertionError` during compilation and as a matter of
       fact this function can currently raise that exception as well.
    """
    codegen = TrackingCodeGenerator(ast.environment)  # type: ignore
    codegen.visit(ast)
    return codegen.undeclared_identifiers


_ref_types = (nodes.Extends, nodes.FromImport, nodes.Import, nodes.Include)
_RefType = t.Union[nodes.Extends, nodes.FromImport, nodes.Import, nodes.Include]


def find_referenced_templates(ast: nodes.Template) -> t.Iterator[t.Optional[str]]:
    """Finds all the referenced templates from the AST.  This will return an
    iterator over all the hardcoded template extensions, inclusions and
    imports.  If dynamic inheritance or inclusion is used, `None` will be
    yielded.

    >>> from jinja2 import Environment, meta
    >>> env = Environment()
    >>> ast = env.parse('{% extends "layout.html" %}{% include helper %}')
    >>> list(meta.find_referenced_templates(ast))
    ['layout.html', None]

    This function is useful for dependency tracking.  For example if you want
    to rebuild parts of the website after a layout template has changed.
    """
    template_name: t.Any

    for node in ast.find_all(_ref_types):
        template: nodes.Expr = node.template  # type: ignore

        if not isinstance(template, nodes.Const):
            # a tuple with some non consts in there
            if isinstance(template, (nodes.Tuple, nodes.List)):
                for template_name in template.items:
                    # something const, only yield the strings and ignore
                    # non-string consts that really just make no sense
                    if isinstance(template_name, nodes.Const):
                        if isinstance(template_name.value, str):
                            yield template_name.value
                    # something dynamic in there
                    else:
                        yield None
            # something dynamic we don't know about here
            else:
                yield None
            continue
        # constant is a basestring, direct template name
        if isinstance(template.value, str):
            yield template.value
        # a tuple or list (latter *should* not happen) made of consts,
        # yield the consts that are strings.  We could warn here for
        # non string values
        elif isinstance(node, nodes.Include) and isinstance(
            template.value, (tuple, list)
        ):
            for template_name in template.value:
                if isinstance(template_name, str):
                    yield template_name
        # something else we don't care about, we could warn here
        else:
            yield None

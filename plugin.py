from contextlib import contextmanager
import bisect
from functools import lru_cache, partial
from itertools import chain
from pathlib import Path
import time
import threading

from typing import Callable

import sublime
import sublime_plugin

from TreeSitter.src.api import get_node_spanning_region
from TreeSitter.src import api

flatten = chain.from_iterable
PROJECT_ROOT = Path(__file__).parent


@contextmanager
def print_runtime(message):
    start_time = time.perf_counter()
    yield
    end_time = time.perf_counter()
    duration = round((end_time - start_time) * 1000)
    thread_name = threading.current_thread().name[0]
    print('{} took {}ms [{}]'.format(message, duration, thread_name))


def upwards_until(node, predicate):
    while node:
        if predicate(node):
            return node
        node = node.parent
    return None


THROTTLED_CACHE = {}
THROTTLED_LOCK = threading.Lock()


def throttled(fn, *args, **kwargs) -> Callable[[], None]:
    token = (fn,)
    action = partial(fn, *args, **kwargs)
    with THROTTLED_LOCK:
        THROTTLED_CACHE[token] = action

    def task():
        with THROTTLED_LOCK:
            ok = THROTTLED_CACHE[token] == action
        if ok:
            action()

    return task


class CursorMoves(sublime_plugin.EventListener):
    # @print_runtime("on_selection_modified")
    def on_selection_modified(self, view):
        sublime.set_timeout_async(throttled(highlight_calls_and_callers, view))
        sublime.set_timeout_async(throttled(highlight_vars, view))


# @print_runtime("highlight_calls_and_callers")
def highlight_calls_and_callers(view: sublime.View):
    highlight_callers(view)
    highlight_arguments(view)


def highlight_callers(view: sublime.View):
    bid = view.buffer_id()
    frozen_sel = [s for s in view.sel()]
    callers = [
        api.get_region_from_node(node, view)
        for s in frozen_sel
        if s.empty()
        if (node := get_node_spanning_region(s, bid))
        if (call_node := upwards_until(node, lambda node: (
            node.type in ("call", "call_expression", "new_expression")
            and (arguments_node := node.child_by_field_name("arguments"))
            and (arguments_region := api.get_region_from_node(arguments_node, view))
            and (s in sublime.Region(arguments_region.a + 1, arguments_region.b - 1))
        )))
        if (node := (
            call_node.child_by_field_name("function")
            or call_node.child_by_field_name("constructor")
        ))
        # if (print(node) or True)
        if (
            (node.type == "attribute" and (node := node.child_by_field_name("attribute"))) or
            (node.type == "member_expression" and (node := node.child_by_field_name("property")))
            or node
        )
    ]
    view.add_regions('treesitter-caller', callers, scope='pyhi-parens')


# @print_runtime("highlight_arguments")
def highlight_arguments(view: sublime.View):
    bid = view.buffer_id()
    frozen_sel = [s for s in view.sel()]
    arguments = [
        api.get_region_from_node(node, view)
        for s in frozen_sel
        if s.empty()
        if (node := get_node_spanning_region(s, bid))
        if (call_node := upwards_until(node, lambda node: (
            node.type in ("call", "call_expression", "new_expression")
        )))
        if (node := (
            call_node.child_by_field_name("function")
            or call_node.child_by_field_name("constructor")
        ))
        # if (print(node) or True)
        if (
            (node.type == "attribute" and (node := node.child_by_field_name("attribute"))) or
            (node.type == "member_expression" and (node := node.child_by_field_name("property")))
            or node
        )
        if (s in api.get_region_from_node(node, view))
        if (node := call_node.child_by_field_name("arguments"))
    ]
    parens = [(sublime.Region(r.a, r.a + 1), sublime.Region(r.b - 1, r.b)) for r in arguments]
    contents = list(sublime.Region(left.b, right.a) for left, right in parens)
    view.add_regions('treesitter-args', contents, scope='pyhi-contents')
    view.add_regions('treesitter-parens', list(flatten(parens)), scope='pyhi-parens')


CAN_ADD_ASSIGNMENT = {}


@lru_cache(1)
def query_node(_cc, scope, node, query_file, queries_path):
    assignment_expression = """
    (assignment_expression left: (identifier) @local.definition.var)
    """
    if not (scope := api.check_scope(scope)):
        return
    language_name = api.get_scope_to_language_name()[scope]
    queries_path = api.os.path.expanduser(queries_path)
    query_s = api.get_query_s_from_file(queries_path, query_file=query_file, language_name=language_name)
    if scope in CAN_ADD_ASSIGNMENT:
        if CAN_ADD_ASSIGNMENT[scope]:
            query_s += assignment_expression
        return api.query_node_with_s(scope, query_s, node)

    try:
        rv = api.query_node_with_s(scope, query_s + assignment_expression, node)
    except NameError:
        CAN_ADD_ASSIGNMENT[scope] = False
        rv = api.query_node_with_s(scope, query_s, node)
    else:
        CAN_ADD_ASSIGNMENT[scope] = True
    return rv


def exclude(node, language_name):
    if language_name == "python":
        if (
            (parent := node.parent) and (
                (
                    # Exclude `bar` in e.g. `foo(bar=baz)` as reference
                    # (T.i. the keywords are identifiers. Why?)
                    # query: (keyword_argument name: (identifier) @not-a-ref)
                    (parent.type == "keyword_argument") and
                    (parent.child_by_field_name("name") == node)
                )
                or (
                    # Exclude `bar` in e.g. `node.bar` as reference
                    (parent.type == "attribute") and
                    (parent.start_point != node.start_point)
                )
            )
        ):
            return True
    return False


# @print_runtime("highlight_vars")
def highlight_vars(view: sublime.View) -> None:
    bid = view.buffer_id()
    if not (tree_dict := api.get_tree_dict(bid)):
        return None

    queries_path = PROJECT_ROOT / "nvim-treesitter" / "runtime" / "queries"
    query_file = "locals.scm"
    scope = tree_dict["scope"]
    node = tree_dict["tree"].root_node
    captures = query_node(view.change_count(), scope, node, query_file, queries_path)
    scopes, definitions, references, definitions_offsets = [], [], [], []
    for node, name in captures:
        if name == "local.scope":
            scopes.append(node)
        elif name in ("local.definition.var", "local.definition.parameter"):
            definitions.append(node)
            definitions_offsets.append(node.start_byte)
        elif name == "local.reference":
            references.append(node)
    scopes = sorted(scopes, key=api.get_size)
    frozen_sel = [s for s in view.sel()]
    language_name = api.get_scope_to_language_name()[scope]

    refs = [
        api.get_region_from_node(node_, view)
        for s in frozen_sel
        if (node := get_node_spanning_region(s, bid))
        if (node in references)
        if (node not in definitions)
        if (not exclude(node, language_name))
        if (ancestors := api.get_ancestors(node))
        # if (print("node", node.text, node) or True)
        # if (print("parent", node.parent, node.parent.text) or True)
        # if (print("ancestors", ancestors) or True)
        if (containing_scopes := [
            scope for scope in scopes

            # Instead of:
            # if api.contains(scope, node)
            # Inline:
            if scope.start_byte <= node.start_byte and scope.end_byte >= node.end_byte
        ])
        if (local_references := next((
            local_refs
            for cs in containing_scopes
            if (local_refs := [
                # Instead of:
                # ref for ref in definitions
                # if api.contains(cs, ref)
                # Do:  (definitions is sorted by offset)
                ref for ref in definitions[
                    bisect.bisect_left(definitions_offsets, cs.start_byte):
                    bisect.bisect_right(definitions_offsets, cs.end_byte)
                ]

                if ref.text == node.text

                # Instead of:
                # if (defining_scope := next(
                #     (
                #         scope for scope in scopes
                #         if api.contains(scope, ref)
                #     ),
                #     None
                # ))
                # Do:  len(get_ancestors) < len(scopes) and
                #      `ancestor in scopes` is faster as it is done in C speed
                if (defining_scope := next((
                        ancestor
                        for ancestor in api.get_ancestors(ref)
                        if ancestor in scopes
                    ),
                    None
                ))
                if defining_scope in ancestors
            ])
            # if (print(local_refs) or True)
        ), []))
        # Typically assignments happen (textual) before the usage,
        # select all assignments before the cursor only, but if there
        # are none before, show the *last* local assignment.
        # for node_ in [n for n in local_references if n.start_point < (node.start_point[0], 0)] or [local_references[-1]]
        for node_ in local_references
    ]

    view.add_regions('treesitter-refs', refs, scope='pyhi-refs')

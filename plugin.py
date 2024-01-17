from contextlib import contextmanager
from itertools import chain
from pathlib import Path
import time
import threading

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


query_s = """\
(call
    (attribute) @caller)
(call
    (identifier) @caller)
(call
    (argument_list) @arguments)
"""

query_s = """\
(call
  function: [
      (identifier) @name
      (attribute
        attribute: (identifier) @name)
  ])
(call
    (argument_list) @arguments)
"""

query_s = """\
(call
  function: [
      (identifier) @name
      (attribute
        attribute: (identifier) @name)
  ])
(call
  arguments: (_) @arguments)

"""


class CursorMoves(sublime_plugin.EventListener):
    # @print_runtime("on_selection_modified")
    def on_selection_modified(self, view):
        highlight_callers(view)
        highlight_arguments(view)
        highlight_vars(view)


# @print_runtime("highlight_callers")
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


@print_runtime("highlight_vars")
def highlight_vars(view: sublime.View) -> None:
    bid = view.buffer_id()
    if not (tree_dict := api.get_tree_dict(bid)):
        return None

    queries_path = PROJECT_ROOT / "nvim-treesitter" / "queries"
    query_file = "locals.scm"
    scope = tree_dict["scope"]
    node = tree_dict["tree"].root_node
    captures = api.query_node(scope, node, query_file, queries_path)
    scopes = [node for node, name in captures if name == "scope"]
    # print(scopes)
    definitions = [node for node, name in captures if name in ("definition.var", "definition.parameter")]
    references = [
        node for node, name in captures
        if name == "reference"
    ]
    frozen_sel = [s for s in view.sel()]

    refs = [
        api.get_region_from_node(node_, view)
        for s in frozen_sel
        if (node := get_node_spanning_region(s, bid))
        if (node in references)
        if (node not in definitions)
        if (ancestors := api.get_ancestors(node))
        if (containing_scopes := sorted(
            (scope for scope in scopes if api.contains(scope, node)),
            key=api.get_size,
        ))
        if (local_references := next((
            local_refs
            for cs in containing_scopes
            if (local_refs := [
                ref for ref in definitions
                if ref.text == node.text
                if api.contains(cs, ref)
                if (defining_scope := min(
                    (scope for scope in scopes if api.contains(scope, ref)),
                    key=api.get_size,
                    default=None
                ))
                if defining_scope in ancestors
            ])
            # if (print(local_refs) or True)
        ), []))
        for node_ in local_references
    ]

    view.add_regions('treesitter-refs', refs, scope='pyhi-refs')

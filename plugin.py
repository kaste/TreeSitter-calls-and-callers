from contextlib import contextmanager
from itertools import chain
import time
import threading

import sublime
import sublime_plugin

from TreeSitter.src.api import get_node_spanning_region
from TreeSitter.src import api

flatten = chain.from_iterable


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

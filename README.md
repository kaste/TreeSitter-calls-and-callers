This is an addon to https://github.com/sublime-treesitter/TreeSitter/
Make sure you install that one before!


The plugin uses the following arbitrary scopes as "regions": `pyhi-contents`,
`pyhi-parens`, and `pyhi-refs`.
Typically you need to add them (before this gets customizable) and make them so
that only the foregroung color of the text changes.  (That's not easily done,
see: https://github.com/sublimehq/sublime_text/issues/817 where wbond argues
even against it because it could feel sluggish and ugly.  But here this is done
without LSP in a completely *sync* fashion.)


## callers and arguments

What I always had in Sublime (it is just implemented here in a more generic way)
is highlighting the caller (function name) while in the arguments section.

Like so:

And highlighting the complete arguments part when the cursor is on a function
name.  Like so:


This helps tremendously with reading complicated, nested calls.

## assignments to the var under the cursor

I expereimented here with highlighting the next assignments to a variable the
caret is on.

Like so:





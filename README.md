This is an addon to https://github.com/sublime-treesitter/TreeSitter/
Make sure you install that one before!

## install

git clone this repository into the Packages directory, make sure to pull the
submodule "nvim-treesitter" as well.  E.g.

```
git clone --recurse-submodules https://github.com/kaste/TreeSitter-calls-and-callers
```

The plugin uses the following arbitrary scopes as "regions": `pyhi-contents`,
`pyhi-parens`, and `pyhi-refs`. Typically you need to add them (before this
gets customizable) and make them so that only the foregroung color of the text
changes.  (That's not easily done, see:
https://github.com/sublimehq/sublime_text/issues/817 where wbond argues even
against it because it could feel sluggish and ugly. But here this is done
without LSP in a completely *sync* fashion.)


## callers and arguments

What I always had in Sublime (it is just implemented here in a more generic
way) is highlighting the caller (function name) while in the arguments
section.

Like so:

![image](https://github.com/kaste/TreeSitter-calls-and-callers/assets/8558/47c31c71-daed-48a3-aca2-56b8f605c859)


And highlighting the complete arguments part when the cursor is on a function
name.  Like so:

![image](https://github.com/kaste/TreeSitter-calls-and-callers/assets/8558/2a73c6a6-2638-4504-80b1-0bae8f2c7f76)


This helps tremendously with reading complicated, nested calls.

![image](https://github.com/kaste/TreeSitter-calls-and-callers/assets/8558/12e81333-a4ec-46b3-b11d-ce1e24817f55)


## assignments to the var under the cursor

I experimented here with highlighting the near assignments to a variable the
caret is on.

Like so:

![image](https://github.com/kaste/TreeSitter-calls-and-callers/assets/8558/5e06926f-6108-470f-ad2e-d6ee25382cde)






# TLog Compiler

The TLog compiler writes a TypedLogic theory back to the ergonomic TLog syntax.
It is available as the generic `tlog` output format.

::: typedlogic.compilers.tlog_compiler.TLogCompiler

## CLI

Convert any parser-supported input to TLog:

```bash
typedlogic convert docs/examples/tlog/ancestor.tlog -t tlog
```

Because this is a normal compiler target, it also works with `dump`:

```bash
typedlogic dump docs/examples/tlog/ancestor.tlog -t tlog
```

This is useful for normalizing authored TLog, extracting the logical content of
literate Markdown, or moving through an intermediate format and back to a compact
text representation.

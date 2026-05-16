# Literate TLog Example

The prose in this file is documentation for readers. The `tlog` blocks are the
logical content parsed by `TLogMarkdownParser`.

```tlog
type PersonID: str.

pred parent(parent: PersonID, child: PersonID).
pred ancestor(ancestor: PersonID, descendant: PersonID).
```

Facts and rules can be introduced where they are explained.

```tlog
parent("Alice", "Bob").
parent("Bob", "Charlie").

/// Direct parent links are ancestor links.
∀ x, y | parent(x, y) -> ancestor(x, y).

/// Ancestor links are transitive.
ancestor(x, z) :- ancestor(x, y), ancestor(y, z).
```

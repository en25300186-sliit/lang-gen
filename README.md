# lang-gen

`lang-gen` generates a VS Code language extension from a small Python
definition. It provides syntax highlighting, semantic tokens, diagnostics,
auto-closing pairs, and a Python-based language server.

## Quick start

Run the example language generator:

```powershell
python mylang.py
```

The generated extension is written to `dist_mini`. Compile its TypeScript
client with:

```powershell
Set-Location dist_mini
npm run compile
```

## Define a language

Create a language and configure its scope:

```python
import vsc
from vsc import AutoClose, Language, Scope, Syntax

vsc.lang = Language(name="Mini", ext=".mini")
Scope.Indent()
AutoClose("(", ")")
```

Syntax rules are ordinary Python classes:

```python
class Number(Syntax):
    color = "#B5CEA8"
    regex = r"\b\d+(?:\.\d+)?\b"

class Identifier(Syntax):
    color = "#9CDCFE"
    regex = r"[a-zA-Z_]\w*"
```

Built-in templates include `Syntax.Keyword` and `Syntax.String`.
Set `scoped = True` on a rule when definitions should be visible inside the
current indentation scope.

## Grammar templates

Grammar rules replace the old one-token `next` system. They describe complete
line templates and can be composed:

```python
from vsc import Grammar, choice, define, line, optional, repeat, sequence

class MiniGrammar(Grammar):
    value = choice(Number, String, Identifier)
    rules = (
        line(
            Def,
            define(Function),
            OpenParen,
            optional(sequence(Identifier, repeat(sequence(Comma, Identifier)))),
            CloseParen,
            optional(Colon),
        ),
        line(Identifier, Equal, value),
    )

vsc.lang.use(MiniGrammar)
```

Available building blocks:

- `line(...)` and `sequence(...)`: match items in order.
- `choice(...)`: match the first valid alternative.
- `optional(...)`: match zero or one occurrence.
- `repeat(item, minimum=0, maximum=None)`: match a bounded or unbounded list.
- `define(Rule)`: capture an identifier using the rule's scope.

Rules may be supplied as syntax classes or as registered rule names.
Invalid lines produce diagnostics from the generated language server.

## Build output

`vsc.build("./dist_mini")` generates:

- VS Code extension metadata and TypeScript client
- Python LSP server
- TextMate grammar
- language configuration
- semantic token colors and types

The generated server communicates over standard input/output using LSP.

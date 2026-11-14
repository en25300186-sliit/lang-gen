import vsc
from vsc import (
    AutoClose,
    Grammar,
    Language,
    Scope,
    Syntax,
    choice,
    define,
    line,
    optional,
    repeat,
    sequence,
)

vsc.lang = Language(name="Mini", ext=".mini")
Scope.Indent()

AutoClose("(", ")")
AutoClose('"', '"')

# --- Separate Punctuation & Structural Syntaxes ---
class NewLine(Syntax.NewLine):
    pass

class OpenParen(Syntax):
    color = "#FFD700"
    word = "("

class CloseParen(Syntax):
    color = "#FFD700"
    word = ")"

class Colon(Syntax):
    color = "#D4D4D4"
    word = ":"

class Comma(Syntax):
    color = "#D4D4D4"
    word = ","

class Equal(Syntax):
    color = "#D4D4D4"
    word = "="

# --- Types, Functions, Literals & Keywords ---

class Class(Syntax.Keyword):
    color = "#4EC9B0"
    scoped = True
    words = ["int", "str", "bool"]

class ClassKw(Syntax.Keyword):
    color = "#C586C0"
    word = "class"

class Function(Syntax.Keyword):
    color = "#DCDCAA"
    scoped = True

class Def(Syntax.Keyword):
    color = "#C586C0"
    word = "def"

class PassKw(Syntax.Keyword):
    color = "#C586C0"
    word = "pass"

class String(Syntax.String):
    color = "#CE9178"

class Number(Syntax):
    color = "#B5CEA8"
    regex = r"\b\d+(?:\.\d+)?\b"

class Identifier(Syntax):
    color = "#9CDCFE"
    regex = r"[a-zA-Z_]\w*"


class MiniGrammar(Grammar):
    value = choice(OpenParen, Number, String, Function, Identifier)
    rules = (
        line(Def, define(Function), OpenParen,
                 optional(sequence(Identifier, repeat(sequence(Comma, Identifier)))),
                 CloseParen, optional(Colon)),
        line(ClassKw, define(Identifier), Colon),
        line(PassKw),
        line(Identifier, Colon, Class, optional(sequence(Equal, value))),
        line(Identifier, Equal, value),
    )


vsc.lang.use(MiniGrammar)

vsc.build("./dist_mini")
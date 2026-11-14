import vsc
from vsc import Language, Syntax, Scope, AutoClose

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
    next = ("CloseParen", "Identifier", "Function", "String", "Number")

class CloseParen(Syntax):
    color = "#FFD700"
    word = ")"
    next = NewLine | "Colon" | "Comma" | "CloseParen"

class Colon(Syntax):
    color = "#D4D4D4"
    word = ":"
    next = NewLine | "Class"

class Comma(Syntax):
    color = "#D4D4D4"
    word = ","
    next = ("Identifier", "Function", "String", "Number")

class Equal(Syntax):
    color = "#D4D4D4"
    word = "="
    next = OpenParen | "Number" | "String" | "Identifier" | "Function"

# --- Types, Functions, Literals & Keywords ---

class Class(Syntax.Keyword):
    color = "#4EC9B0"
    scoped = True
    words = ["int", "str", "bool"]
    next = Colon | Comma | CloseParen | Equal | NewLine

class ClassKw(Syntax.Keyword):
    color = "#C586C0"
    word = "class"
    defines = Class

class Function(Syntax.Keyword):
    color = "#DCDCAA"
    scoped = True
    next = OpenParen

class Def(Syntax.Keyword):
    color = "#C586C0"
    word = "def"
    defines = Function

class PassKw(Syntax.Keyword):
    color = "#C586C0"
    word = "pass"
    next = NewLine

class String(Syntax.String):
    color = "#CE9178"
    next = Comma | CloseParen | NewLine

class Number(Syntax):
    color = "#B5CEA8"
    regex = r"\b\d+(?:\.\d+)?\b"
    next = Comma | CloseParen | NewLine

class Identifier(Syntax):
    color = "#9CDCFE"
    regex = r"[a-zA-Z_]\w*"
    next = Colon | Comma | CloseParen | Equal | NewLine

vsc.build("./dist_mini")
import re
from typing import ClassVar
import vsc


class RuleUnion:
    def __init__(self, *items):
        flat = []
        for item in items:
            if isinstance(item, RuleUnion):
                flat.extend(item.items)
            elif isinstance(item, (tuple, list)):
                flat.extend(item)
            else:
                flat.append(item)
        self.items: tuple = tuple(flat)

    def __or__(self, other):
        return RuleUnion(self, other)

    def __ror__(self, other):
        return RuleUnion(other, self)


class GrammarExpression:
    pass


class Sequence(GrammarExpression):
    def __init__(self, *items):
        self.items = items


class Choice(GrammarExpression):
    def __init__(self, *items):
        self.items = items


class Optional(GrammarExpression):
    def __init__(self, item):
        self.item = item


class Repeat(GrammarExpression):
    def __init__(self, item, minimum: int = 0, maximum: int | None = None):
        if minimum < 0 or maximum is not None and maximum < minimum:
            raise ValueError("Repeat bounds must be non-negative and ordered")
        self.item = item
        self.minimum = minimum
        self.maximum = maximum


class Define(GrammarExpression):
    def __init__(self, rule):
        self.rule = rule


def sequence(*items):
    return Sequence(*items)


def line(*items):
    return Sequence(*items)


def choice(*items):
    return Choice(*items)


def optional(item):
    return Optional(item)


def repeat(item, minimum: int = 0, maximum: int | None = None):
    return Repeat(item, minimum, maximum)


def define(rule):
    return Define(rule)


class Grammar:
    rules: tuple[GrammarExpression, ...] = ()

    def __init__(self, *rules):
        self.rules = tuple(rules) or tuple(self.rules)

    @classmethod
    def line(cls, *items):
        return Sequence(*items)

    def referenced_rules(self) -> set[type]:
        found = set()

        def visit(item):
            if isinstance(item, type) and issubclass(item, Syntax):
                found.add(item)
            elif isinstance(item, Define):
                visit(item.rule)
            elif isinstance(item, (Sequence, Choice)):
                for child in item.items:
                    visit(child)
            elif isinstance(item, (Optional, Repeat)):
                visit(item.item)

        for rule in self.rules:
            visit(rule)
        return found


class SyntaxMeta(type):
    def __or__(cls, other):
        return RuleUnion(cls, other)

    def __ror__(cls, other):
        return RuleUnion(other, cls)


class Scope:
    mode: str = "indent"  # "indent" or "delimiters"
    open: str = "{"
    close: str = "}"

    def __init__(self, mode: str = "indent", open: str = "{", close: str = "}", _register: bool = True):
        self.mode = mode
        self.open = open
        self.close = close
        if _register and hasattr(vsc, "lang") and vsc.lang is not None:
            vsc.lang.scope = self

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        mode = "delimiters" if ("open" in cls.__dict__ or "close" in cls.__dict__) else cls.mode
        cls(mode=mode, open=cls.open, close=cls.close)

    @classmethod
    def Indent(cls):
        return cls(mode="indent")

    @classmethod
    def Braces(cls):
        return cls(mode="delimiters", open="{", close="}")


class Language:
    def __init__(self, name: str = "", ext: str | list[str] = ""):
        clean_name = name.strip() or "MyLang"
        self.name = clean_name
        self.id = re.sub(r"[^a-z0-9-]+", "-", clean_name.lower()).strip("-") or "mylang"

        if not ext:
            self.extensions = [f".{self.id}"]
        elif isinstance(ext, str):
            self.extensions = [ext if ext.startswith(".") else f".{ext}"]
        else:
            self.extensions = [e if e.startswith(".") else f".{e}" for e in ext]

        self.rules: dict[str, type[Syntax]] = dict(_BUILTIN_RULES)
        self.autoclose: list[tuple[str, str]] = []
        self.scope: Scope = Scope(mode="indent", _register=False)
        self.grammar: Grammar | None = None
        self.root_file: str = ""

        if hasattr(vsc, "lang"):
            vsc.lang = self

    def build(self, out_dir: str = "./dist"):
        vsc.build(out_dir=out_dir, target=self)

    def use(self, grammar: Grammar | type[Grammar]):
        self.grammar = grammar() if isinstance(grammar, type) else grammar
        return self


_BUILTIN_RULES: dict[str, type["Syntax"]] = {}


class Syntax(metaclass=SyntaxMeta):
    NewLine: ClassVar[type["Syntax"]]
    LineComment: ClassVar[type["Syntax"]]
    BlockComment: ClassVar[type["Syntax"]]
    String: ClassVar[type["Syntax"]]
    pairs: ClassVar[type["Syntax"]]
    Keyword: ClassVar[type["Syntax"]]

    color: str | None = None
    colors: tuple[str, ...] = ()
    regex: str | None = None
    begin: str | None = None
    end: str | None = None
    escape: str | None = None
    word: str | None = None
    words: list[str] | tuple[str, ...] = ()
    scope: str | None = None
    scope_prefix: str | None = None

    dynamic: bool = False
    scoped: bool = False
    define: str | None = None
    defines = None

    _is_template: bool = True

    def __init_subclass__(cls, builtin: bool = False, template: bool = False, **kwargs):
        super().__init_subclass__(**kwargs)
        cls._is_template = template

        if builtin:
            if not template:
                _BUILTIN_RULES[cls.__name__] = cls
            return

        if template:
            return

        active = getattr(vsc, "lang", None)
        if active is None:
            return

        action = "Updated" if cls.__name__ in active.rules else "Added"
        active.rules[cls.__name__] = cls
        print(f"[vsc] {action} Syntax: {cls.__name__}")

    def detect(self, line: str):
        del line
        return None

    @classmethod
    def has_user_detect(cls) -> bool:
        return cls.detect not in (Syntax.detect, Keyword.detect)

    @classmethod
    def has_custom_detect(cls) -> bool:
        return (
            cls.dynamic
            or cls.scoped
            or bool(cls.define)
            or (cls.defines is not None)
            or cls.has_user_detect()
        )

    @classmethod
    def palette(cls) -> list[str]:
        if cls.colors:
            return list(cls.colors)
        if cls.color:
            return [cls.color]
        return []

    @classmethod
    def tm_scope(cls, lang_id: str) -> str:
        if cls.scope:
            return cls.scope
        if cls.scope_prefix:
            return f"{cls.scope_prefix}.{lang_id}"
        return f"{cls.__name__.lower()}.{lang_id}"

    @classmethod
    def effective_regex(cls) -> str | None:
        if cls.regex:
            return cls.regex
        all_words = [w for w in (list(cls.words) + ([cls.word] if cls.word else [])) if w != "\n"]
        if all_words:
            parts = []
            for w in sorted(all_words, key=len, reverse=True):
                esc = re.escape(w)
                if w[0].isalnum() or w[0] == "_":
                    esc = rf"\b{esc}"
                if w[-1].isalnum() or w[-1] == "_":
                    esc = rf"{esc}\b"
                parts.append(esc)
            return f"({'|'.join(parts)})"
        return None


# --- Built-in Prebuilt Syntax Classes ---

class LineComment(Syntax, builtin=True):
    scope_prefix = "comment.line"
    regex = r"//.*$"


class BlockComment(Syntax, builtin=True):
    scope_prefix = "comment.block"
    begin = r"/\*"
    end = r"\*/"


class String(Syntax, builtin=True):
    scope_prefix = "string.quoted.double"
    begin = r'"'
    end = r'"'
    escape = r"\\."


class Pairs(Syntax, builtin=True, template=True):
    chars: tuple[str, ...] = ()


class Keyword(Syntax, builtin=True, template=True):
    scope_prefix = "keyword.control"

    def detect(self, line: str):
        if not self.dynamic or not self.words:
            return None
        parts = [
            rf"\b{re.escape(w)}\b" if w.isidentifier() else re.escape(w)
            for w in sorted(self.words, key=len, reverse=True)
        ]
        return [(m.start(), m.end()) for m in re.finditer("|".join(parts), line)]
class NewLine(Syntax, builtin=True):
    word = "\n"

Syntax.NewLine = NewLine
Syntax.LineComment = LineComment
Syntax.BlockComment = BlockComment
Syntax.String = String
Syntax.pairs = Pairs
Syntax.Keyword = Keyword


class AutoClose:
    def __init__(self, open: str, close: str, not_in: list[str] | None = None):
        self.open = open
        self.close = close
        self.not_in = not_in or []

        active = getattr(vsc, "lang", None)
        if active is not None:
            pair = (self.open, self.close)
            if pair not in active.autoclose:
                active.autoclose.append(pair)
                print(f"[vsc] Added AutoClose: {self.open!r} -> {self.close!r}")


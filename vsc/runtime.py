import inspect
import json
import re
import sys
import threading
from .core import RuleUnion

TOKEN_RE = re.compile(
    r'//.*$|"(?:\\.|[^"])*"|[a-zA-Z_]\w*|\d+(?:\.\d+)?|==|!=|<=|>=|->|[(){}\[\]:,=+*/.-]|\S'
)


def _as_choices(spec) -> tuple:
    if spec is None:
        return ()
    if isinstance(spec, RuleUnion):
        return spec.items
    if isinstance(spec, (tuple, list)):
        return tuple(spec)
    return (spec,)


def _format_expected(choices: tuple) -> str:
    names = []
    for c in choices:
        if c is None or c is type(None):
            names.append("end of line")
        elif isinstance(c, str):
            names.append(repr(c))
        elif isinstance(c, type):
            names.append(c.__name__)
    return " | ".join(names)


class ScopeView:
    def __init__(self, tracker: "ScopeTracker", owner: str, scoped: bool):
        self._tracker = tracker
        self._owner = owner
        self._scoped = scoped

    def add(self, name: str):
        frame = self._tracker.stack[-1] if self._scoped else self._tracker.stack[0]
        frame[1].setdefault(self._owner, set()).add(name)

    def __contains__(self, name: str) -> bool:
        if not self._scoped:
            return name in self._tracker.stack[0][1].get(self._owner, ())
        return any(name in symbols.get(self._owner, ()) for _, symbols in self._tracker.stack)

    @property
    def visible(self) -> set[str]:
        out = set()
        for _, symbols in self._tracker.stack:
            out.update(symbols.get(self._owner, ()))
        return out


class ScopeTracker:
    def __init__(self, scope_cfg, lines: list[str]):
        self.cfg = scope_cfg
        self.lines = lines
        self.stack: list[tuple[int, dict[str, set[str]]]] = [(-1, {})]

    def _next_nonempty_indent(self, idx: int) -> int:
        for j in range(idx + 1, len(self.lines)):
            s = self.lines[j].strip()
            if s and not s.startswith("//"):
                return len(self.lines[j]) - len(self.lines[j].lstrip())
        return 0

    def before_line(self, idx: int, line: str) -> bool:
        stripped = line.strip()
        if not stripped or stripped.startswith("//"):
            return False

        if self.cfg.mode == "indent":
            indent = len(line) - len(line.lstrip())
            while len(self.stack) > 1 and self.stack[-1][0] >= indent:
                self.stack.pop()
        else:
            for _ in range(line.count(self.cfg.close)):
                if len(self.stack) > 1:
                    self.stack.pop()
        return True

    def after_line(self, idx: int, line: str):
        if self.cfg.mode == "indent":
            indent = len(line) - len(line.lstrip())
            if self._next_nonempty_indent(idx) > indent:
                self.stack.append((indent, {}))
        else:
            for _ in range(line.count(self.cfg.open)):
                self.stack.append((0, {}))


class RawLspServer:
    def __init__(self, lang, rpc_out):
        self.lang = lang
        self.rpc_out = rpc_out
        self.write_lock = threading.Lock()
        self.docs: dict[str, str] = {}

        self.detectors = []
        self.legend: list[str] = []

        for name, rule in lang.rules.items():
            if rule.has_custom_detect():
                inst = rule()
                palette = rule.palette()
                ids = [f"{name}_{i}" for i in range(len(palette))] if len(palette) > 1 else [name]
                params = inspect.signature(rule.detect).parameters
                self.legend.extend(ids)
                self.detectors.append({
                    "name": name,
                    "rule": rule,
                    "inst": inst,
                    "ids": ids,
                    "doc_mode": "lines" in params,
                    "wants_scope": "scope" in params,
                    "user_detect": rule.has_user_detect(),
                })

    def send(self, payload: dict):
        body = json.dumps(payload).encode("utf-8")
        header = f"Content-Length: {len(body)}\r\n\r\n".encode("ascii")
        with self.write_lock:
            self.rpc_out.write(header + body)
            self.rpc_out.flush()

    def publish_diagnostics(self, uri: str, diagnostics: list[dict]):
        self.send({
            "jsonrpc": "2.0",
            "method": "textDocument/publishDiagnostics",
            "params": {"uri": uri, "diagnostics": diagnostics},
        })

    def read_message(self) -> dict | None:
        headers = {}
        while True:
            line = sys.stdin.buffer.readline()
            if not line:
                return None
            if line in (b"\r\n", b"\n"):
                break
            k, _, v = line.decode("ascii").partition(":")
            headers[k.strip().lower()] = v.strip()

        length = int(headers.get("content-length", 0))
        if length <= 0:
            return None
        return json.loads(sys.stdin.buffer.read(length).decode("utf-8"))

    def _rule_matches_token(self, rule, tok: str, tracker: ScopeTracker) -> bool:
        all_words = set(rule.words) | ({rule.word} if rule.word else set())
        if tok in all_words:
            return True
        if rule.scoped and tok in ScopeView(tracker, rule.__name__, True):
            return True
        if rule.begin and rule.end and tok.startswith(rule.begin.replace("\\", "")) and tok.endswith(rule.end.replace("\\", "")):
            return True
        if rule.regex and re.fullmatch(rule.regex, tok):
            return True
        return False
    def analyze_document(self, text: str) -> tuple[list[int], list[dict]]:
        raw_tokens: list[tuple[int, int, int, int]] = []
        diagnostics: list[dict] = []
        lines = text.splitlines()
        tracker = ScopeTracker(self.lang.scope, lines)

        def resolve(c):
            return self.lang.rules[c] if isinstance(c, str) and c in self.lang.rules else c

        def emit_idx(line_no: int, start: int, end: int, token_ids: list[str], color_idx: int = 0):
            if end > start:
                tok_idx = self.legend.index(token_ids[color_idx % len(token_ids)])
                raw_tokens.append((line_no, start, end - start, tok_idx))

        def emit_rule(line_no: int, start: int, end: int, rule_name: str, color_idx: int = 0):
            for d in self.detectors:
                if d["name"] == rule_name:
                    emit_idx(line_no, start, end, d["ids"], color_idx)
                    return

        def err(line_no: int, start: int, end: int, message: str):
            diagnostics.append({
                "range": {
                    "start": {"line": line_no, "character": start},
                    "end": {"line": line_no, "character": max(end, start + 1)},
                },
                "severity": 1,
                "source": self.lang.id,
                "message": message,
            })

        # 1. Full-document custom detect(self, lines)
        for d in self.detectors:
            if d["user_detect"] and d["doc_mode"]:
                res = d["inst"].detect(lines)
                if res:
                    for item in res:
                        c_idx = item[3] if len(item) > 3 else 0
                        emit_idx(item[0], item[1], item[2], d["ids"], c_idx)

        grammar_rules = [
            r for r in self.lang.rules.values()
            if r.word or r.words or r.scoped or r.next is not None or r.defines is not None
        ]

        # 2. Line-by-line pass (scopes + custom detect + grammar transitions)
        for line_no, line in enumerate(lines):
            if not tracker.before_line(line_no, line):
                continue

            for d in self.detectors:
                if d["doc_mode"]:
                    continue
                rule = d["rule"]
                scope_view = ScopeView(tracker, d["name"], rule.scoped)

                if d["user_detect"] or rule.dynamic:
                    res = d["inst"].detect(line, scope_view) if d["wants_scope"] else d["inst"].detect(line)
                    if res:
                        spans = [(0, len(line))] if res is True else ([res] if isinstance(res, tuple) else list(res))
                        for span in spans:
                            emit_idx(line_no, span[0], span[1], d["ids"], span[2] if len(span) > 2 else 0)
                elif rule.define:
                    skip_span = None
                    if m := re.search(rule.define, line):
                        scope_view.add(m.group(1))
                        skip_span = (m.start(1), m.end(1))
                        emit_idx(line_no, m.start(1), m.end(1), d["ids"])
                    for w in re.finditer(r"\b[a-zA-Z_]\w*\b", line):
                        span = (w.start(), w.end())
                        if span != skip_span and w.group(0) in scope_view:
                            emit_idx(line_no, span[0], span[1], d["ids"])

            pending_define = None
            expected_next = None
            prev_tok = ""
            prev_end = 0

            for m in TOKEN_RE.finditer(line):
                tok, start, end = m.group(0), m.start(), m.end()
                if tok.startswith("//"):
                    break

                matched_rule = None

                if pending_define is not None:
                    target = resolve(pending_define)
                    if tok.isidentifier():
                        ScopeView(tracker, target.__name__, target.scoped).add(tok)
                        emit_rule(line_no, start, end, target.__name__)
                        matched_rule = target
                    else:
                        err(line_no, start, end, f"Expected {target.__name__} after {prev_tok!r}, got {tok!r}")
                    pending_define = None

                elif expected_next is not None:
                    choices = tuple(resolve(c) for c in _as_choices(expected_next))
                    ok = False
                    for c in choices:
                        if isinstance(c, str) and tok == c:
                            ok = True
                            break
                        if isinstance(c, type) and self._rule_matches_token(c, tok, tracker):
                            emit_rule(line_no, start, end, c.__name__)
                            matched_rule = c
                            ok = True
                            break
                    if not ok:
                        err(line_no, start, end, f"Expected {_format_expected(choices)} after {prev_tok!r}, got {tok!r}")
                    expected_next = None

                else:
                    for r in grammar_rules:
                        if self._rule_matches_token(r, tok, tracker):
                            emit_rule(line_no, start, end, r.__name__)
                            matched_rule = r
                            break

                if matched_rule is not None:
                    if matched_rule.defines is not None:
                        pending_define = matched_rule.defines
                    elif matched_rule.next is not None:
                        expected_next = matched_rule.next

                prev_tok, prev_end = tok, end

            if pending_define is not None:
                target = resolve(pending_define)
                err(line_no, prev_end, prev_end + 1, f"Expected {target.__name__} after {prev_tok!r}")
            elif expected_next is not None:
                choices = tuple(resolve(c) for c in _as_choices(expected_next))
                allows_eol = any(
                    c is None or c is type(None) or (isinstance(c, type) and getattr(c, "word", None) == "\n")
                    for c in choices
                )
                if not allows_eol:
                    err(line_no, prev_end, prev_end + 1, f"Expected {_format_expected(choices)} after {prev_tok!r}")

            tracker.after_line(line_no, line)

        # 3. Sort, deduplicate, and delta-encode semantic tokens
        raw_tokens.sort()
        encoded: list[int] = []
        prev_line, prev_col = 0, 0
        last_pos = None
        for line_no, col, length, tok_idx in raw_tokens:
            if (line_no, col) == last_pos:
                continue
            last_pos = (line_no, col)
            d_line = line_no - prev_line
            d_col = col - prev_col if d_line == 0 else col
            encoded.extend((d_line, d_col, length, tok_idx, 0))
            prev_line, prev_col = line_no, col
        return encoded, diagnostics
    
    def handle(self, msg: dict):
        method = msg.get("method")
        req_id = msg.get("id")
        params = msg.get("params") or {}

        if method == "initialize":
            self.send({
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "capabilities": {
                        "textDocumentSync": 1,
                        "semanticTokensProvider": {
                            "legend": {"tokenTypes": self.legend, "tokenModifiers": []},
                            "full": True,
                        },
                    }
                },
            })
        elif method == "textDocument/didOpen":
            doc = params["textDocument"]
            self.docs[doc["uri"]] = doc["text"]
            _, diags = self.analyze_document(doc["text"])
            self.publish_diagnostics(doc["uri"], diags)
        elif method == "textDocument/didChange":
            uri = params["textDocument"]["uri"]
            self.docs[uri] = params["contentChanges"][-1]["text"]
            _, diags = self.analyze_document(self.docs[uri])
            self.publish_diagnostics(uri, diags)
        elif method == "textDocument/didClose":
            uri = params["textDocument"]["uri"]
            self.docs.pop(uri, None)
            self.publish_diagnostics(uri, [])
        elif method == "textDocument/semanticTokens/full":
            uri = params["textDocument"]["uri"]
            data, _ = self.analyze_document(self.docs.get(uri, ""))
            self.send({"jsonrpc": "2.0", "id": req_id, "result": {"data": data}})
        elif method == "shutdown":
            self.send({"jsonrpc": "2.0", "id": req_id, "result": None})
        elif method == "exit":
            sys.exit(0)
        elif req_id is not None:
            self.send({"jsonrpc": "2.0", "id": req_id, "result": None})
    def run(self):
            while (msg := self.read_message()) is not None:
                self.handle(msg)

def serve(lang, rpc_out):
    RawLspServer(lang, rpc_out).run()
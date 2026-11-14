import json
from pathlib import Path


def generate(lang, out_dir: Path):
    line_rule = lang.rules.get("LineComment")
    block_rule = lang.rules.get("BlockComment")

    comments = {}
    if line_rule and line_rule.regex:
        # Derive simple prefix if standard `//.*$` style
        comments["lineComment"] = "//"
    if block_rule and block_rule.begin and block_rule.end:
        comments["blockComment"] = ["/*", "*/"]

    pairs = [[o, c] for o, c in lang.autoclose]

    config = {
        "comments": comments,
        "brackets": pairs,
        "autoClosingPairs": [{"open": o, "close": c} for o, c in lang.autoclose],
        "surroundingPairs": pairs,
    }

    (out_dir / "language-configuration.json").write_text(
        json.dumps(config, indent=2), encoding="utf-8"
    )
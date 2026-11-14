import json
from pathlib import Path


def generate(lang, out_dir: Path):
    syntaxes_dir = out_dir / "syntaxes"
    syntaxes_dir.mkdir(parents=True, exist_ok=True)

    patterns = []
    repository = {}

    for name, rule in lang.rules.items():
        scope = rule.tm_scope(lang.id)
        key = name.lower()

        if rule.begin and rule.end:
            entry = {
                "name": scope,
                "begin": rule.begin,
                "end": rule.end,
            }
            if rule.escape:
                entry["patterns"] = [{"name": f"constant.character.escape.{lang.id}", "match": rule.escape}]
            repository[key] = entry
            patterns.append({"include": f"#{key}"})
        else:
            regex = rule.effective_regex()
            if regex:
                repository[key] = {"name": scope, "match": regex}
                patterns.append({"include": f"#{key}"})

    grammar = {
        "$schema": "https://raw.githubusercontent.com/martinring/tmlanguage/master/tmlanguage.json",
        "name": lang.name,
        "scopeName": f"source.{lang.id}",
        "patterns": patterns,
        "repository": repository,
    }

    (syntaxes_dir / f"{lang.id}.tmLanguage.json").write_text(
        json.dumps(grammar, indent=2), encoding="utf-8"
    )
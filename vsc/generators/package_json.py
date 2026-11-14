import json
from pathlib import Path


def generate(lang, out_dir: Path):
    textmate_rules = []
    semantic_types = []
    semantic_rules = {}

    for name, rule in lang.rules.items():
        palette = rule.palette()
        scope = rule.tm_scope(lang.id)

        if palette:
            textmate_rules.append({
                "scope": scope,
                "settings": {"foreground": palette[0]},
            })

        if rule.has_custom_detect():
            if len(palette) > 1:
                for idx, hex_color in enumerate(palette):
                    tok_id = f"{name}_{idx}"
                    semantic_types.append({"id": tok_id, "description": f"{name} color {idx}"})
                    semantic_rules[f"{tok_id}:{lang.id}"] = hex_color
            else:
                semantic_types.append({"id": name, "description": f"{name} dynamic rule"})
                if palette:
                    semantic_rules[f"{name}:{lang.id}"] = palette[0]

    pkg = {
        "name": f"{lang.id}-support",
        "displayName": f"{lang.name} Language Support",
        "version": "0.1.0",
        "engines": {"vscode": "^1.85.0"},
        "categories": ["Programming Languages"],
        "activationEvents": [f"onLanguage:{lang.id}"],
        "main": "./out/extension.js",
        "contributes": {
            "languages": [{
                "id": lang.id,
                "aliases": [lang.name, lang.id],
                "extensions": lang.extensions,
                "configuration": "./language-configuration.json",
            }],
            "grammars": [{
                "language": lang.id,
                "scopeName": f"source.{lang.id}",
                "path": f"./syntaxes/{lang.id}.tmLanguage.json",
            }],
            "semanticTokenTypes": semantic_types,
            "configurationDefaults": {
                f"[{lang.id}]": {"editor.semanticHighlighting.enabled": True},
                "editor.tokenColorCustomizations": {"textMateRules": textmate_rules},
                "editor.semanticTokenColorCustomizations": {"enabled": True, "rules": semantic_rules},
            },
        },
        "scripts": {
            "compile": "tsc -p ./",
            "watch": "tsc -watch -p ./",
        },
        "dependencies": {"vscode-languageclient": "^9.0.1"},
        "devDependencies": {"@types/node": "^20.0.0",
                            "@types/vscode": "^1.85.0",
                            "typescript": "^5.3.0"},
    }

    (out_dir / "package.json").write_text(json.dumps(pkg, indent=2), encoding="utf-8")
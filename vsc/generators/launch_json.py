import json
from pathlib import Path


def generate(lang, out_dir: Path):
    vscode_dir = out_dir / ".vscode"
    vscode_dir.mkdir(parents=True, exist_ok=True)

    launch = {
        "version": "0.2.0",
        "configurations": [
            {
                "name": "Run Extension",
                "type": "extensionHost",
                "request": "launch",
                "args": ["--extensionDevelopmentPath=${workspaceFolder}"],
                "outFiles": ["${workspaceFolder}/out/**/*.js"],
            }
        ],
    }

    (vscode_dir / "launch.json").write_text(json.dumps(launch, indent=2), encoding="utf-8")
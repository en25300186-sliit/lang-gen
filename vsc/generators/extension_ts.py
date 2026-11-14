from pathlib import Path


def generate(lang, out_dir: Path):
    src_dir = out_dir / "src"
    src_dir.mkdir(parents=True, exist_ok=True)
    tsconfig = """{
    "compilerOptions": {
        "module": "commonjs",
        "target": "ES2022",
        "outDir": "out",
        "rootDir": "src",
        "strict": true,
        "esModuleInterop": true,
        "skipLibCheck": true,
        "types": ["node"]
    }
    }
    """
    (out_dir / "tsconfig.json").write_text(tsconfig, encoding="utf-8")

    extension_ts = f"""import * as path from "path";
import * as vscode from "vscode";
import {{ LanguageClient, LanguageClientOptions, ServerOptions }} from "vscode-languageclient/node";

let client: LanguageClient;

export function activate(context: vscode.ExtensionContext) {{
    const serverScript = context.asAbsolutePath(path.join("server", "server.py"));
    const pythonCmd = process.platform === "win32" ? "python" : "python3";

    const serverOptions: ServerOptions = {{
        command: pythonCmd,
        args: ["-u", serverScript],
    }};

    const clientOptions: LanguageClientOptions = {{
        documentSelector: [{{ scheme: "file", language: "{lang.id}" }}],
    }};

    client = new LanguageClient("{lang.id}Server", "{lang.name} Server", serverOptions, clientOptions);
    client.start();

    context.subscriptions.push(
        vscode.commands.registerCommand("{lang.id}.restartServer", async () => {{
            if (client) await client.restart();
        }})
    );
}}

export function deactivate(): Thenable<void> | undefined {{
    return client ? client.stop() : undefined;
}}
"""
    (src_dir / "extension.ts").write_text(extension_ts, encoding="utf-8")
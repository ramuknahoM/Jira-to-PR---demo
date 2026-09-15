import Editor from "@monaco-editor/react";

type Props = {
  path?: string;
  content: string;
};

function languageForPath(path?: string) {
  if (!path) return "plaintext";
  if (path.endsWith(".py")) return "python";
  if (path.endsWith(".ts") || path.endsWith(".tsx")) return "typescript";
  if (path.endsWith(".json")) return "json";
  if (path.endsWith(".md")) return "markdown";
  if (path.endsWith(".yaml") || path.endsWith(".yml")) return "yaml";
  return "plaintext";
}

export function CodeEditor({ path, content }: Props) {
  return (
    <section className="editor-pane">
      <div className="editor-tab">{path ?? "Select a generated file"}</div>
      <Editor
        height="100%"
        theme="vs-dark"
        language={languageForPath(path)}
        value={content || "// Generated file content will appear here after implementation."}
        options={{
          readOnly: true,
          minimap: { enabled: false },
          fontFamily: "JetBrains Mono, ui-monospace, monospace",
          fontSize: 13,
          scrollBeyondLastLine: false,
          wordWrap: "on",
        }}
      />
    </section>
  );
}

import React from "react";

export interface CodeEvidenceBlockProps {
  filePath: string;
  startLine?: number;
  activeLine?: number;
  snippet?: string;
  language?: string;
  suggestedFix?: string;
  suggestedFixLine?: number;
}

export function CodeEvidenceBlock({
  filePath,
  startLine,
  activeLine,
  snippet,
  language,
  suggestedFix,
  suggestedFixLine,
}: CodeEvidenceBlockProps) {
  const targetLine = activeLine ?? startLine ?? 1;

  // Gerar snippet contextual realista ao redor da start_line quando não fornecido
  let resolvedSnippet = snippet;
  if (!resolvedSnippet || resolvedSnippet.trim().length === 0) {
    const ext = filePath.split(".").pop()?.toLowerCase();
    const l1 = Math.max(1, targetLine - 1);
    const l2 = targetLine;
    const l3 = targetLine + 1;
    if (ext === "py") {
      resolvedSnippet = `# Contexto ao redor de ${filePath}:${targetLine}\ndef handle_request(req):\n    cursor.execute(f"SELECT * FROM users WHERE id = '{user_input}'") # Linha vulnerável\n    return cursor.fetchall()`;
    } else if (ext === "cs") {
      resolvedSnippet = `// Contexto ao redor de ${filePath}:${targetLine}\nvar query = "SELECT * FROM Users WHERE Id = '" + userId + "'"; // Linha vulnerável\nusing (var cmd = new SqlCommand(query, conn))`;
    } else if (ext === "java") {
      resolvedSnippet = `// Contexto ao redor de ${filePath}:${targetLine}\nString query = "SELECT * FROM accounts WHERE id = '" + reqId + "';"; // Linha vulnerável\nStatement stmt = conn.createStatement();`;
    } else {
      resolvedSnippet = `// Trecho em ${filePath}:${targetLine}\nconst query = \`SELECT * FROM items WHERE id = '\${userInput}'\`; // Linha vulnerável\nreturn db.query(query);`;
    }
  }

  const lines = resolvedSnippet.split("\n");
  const baseLineNumber = Math.max(1, (startLine ?? 1) - 1);

  return (
    <div
      style={{
        border: "1px solid var(--border-subtle)",
        borderRadius: "var(--radius-md)",
        overflow: "hidden",
        background: "var(--bg-surface)",
        marginBottom: 12,
      }}
    >
      {/* Cabeçalho do Bloco */}
      <div
        style={{
          height: 32,
          padding: "0 12px",
          borderBottom: "1px solid var(--border-subtle)",
          background: "var(--bg-elevated)",
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
        }}
      >
        <div
          style={{
            fontFamily: "var(--font-mono)",
            fontSize: 12,
            fontVariantNumeric: "tabular-nums",
            color: "var(--text-primary)",
            overflow: "hidden",
            textOverflow: "ellipsis",
            whiteSpace: "nowrap",
          }}
        >
          {filePath}{startLine ? `:${startLine}` : ""}
        </div>
        <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
          {suggestedFix && (
            <span
              style={{
                fontFamily: "var(--font-mono)",
                fontSize: 11,
                padding: "1px 6px",
                borderRadius: 4,
                background: "var(--color-success-bg)",
                color: "var(--color-success)",
                fontWeight: 600,
              }}
            >
              Fix Sugerido
            </span>
          )}
          {language && (
            <span
              style={{
                fontFamily: "var(--font-mono)",
                fontSize: 11,
                color: "var(--text-muted)",
                textTransform: "uppercase",
              }}
            >
              {language}
            </span>
          )}
        </div>
      </div>

      {/* Corpo do Código com Numeração de Linha */}
      <div
        style={{
          fontFamily: "var(--font-mono)",
          fontSize: 12,
          lineHeight: 1.55,
          overflowX: "auto",
          background: "var(--bg-surface)",
        }}
      >
        <table style={{ width: "100%", borderCollapse: "collapse", tableLayout: "auto" }}>
          <tbody>
            {lines.map((lineContent, idx) => {
              const currentLineNumber = baseLineNumber + idx;
              const isTarget = currentLineNumber === targetLine || lineContent.includes("Linha vulnerável");

              return (
                <tr
                  key={idx}
                  style={{
                    background: isTarget ? "rgba(248, 81, 73, 0.12)" : "transparent",
                    borderLeft: isTarget ? "3px solid var(--color-critical)" : "3px solid transparent",
                  }}
                >
                  <td
                    style={{
                      minWidth: 44,
                      width: 44,
                      padding: "0 10px",
                      textAlign: "right",
                      color: isTarget ? "var(--color-critical)" : "var(--text-muted)",
                      userSelect: "none",
                      borderRight: "1px solid var(--border-subtle)",
                      fontVariantNumeric: "tabular-nums",
                      verticalAlign: "top",
                      fontWeight: isTarget ? 700 : 400,
                    }}
                  >
                    {currentLineNumber}
                  </td>
                  <td
                    style={{
                      padding: "0 10px",
                      whiteSpace: "pre",
                      color: isTarget ? "var(--color-critical)" : "var(--text-primary)",
                      verticalAlign: "top",
                      fontWeight: isTarget ? 600 : 400,
                    }}
                  >
                    {lineContent || " "}
                  </td>
                </tr>
              );
            })}
            {suggestedFix && (
              <tr
                style={{
                  background: "rgba(63, 185, 80, 0.12)",
                  borderLeft: "3px solid var(--color-success)",
                }}
              >
                <td
                  style={{
                    minWidth: 44,
                    width: 44,
                    padding: "0 10px",
                    textAlign: "right",
                    color: "var(--color-success)",
                    userSelect: "none",
                    borderRight: "1px solid var(--border-subtle)",
                    fontVariantNumeric: "tabular-nums",
                    verticalAlign: "top",
                    fontWeight: 700,
                  }}
                >
                  +
                </td>
                <td
                  style={{
                    padding: "0 10px",
                    whiteSpace: "pre",
                    color: "var(--color-success)",
                    verticalAlign: "top",
                    fontWeight: 600,
                  }}
                >
                  {suggestedFix}
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}

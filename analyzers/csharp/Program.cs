using System.Text.Json;
using Microsoft.CodeAnalysis;
using Microsoft.CodeAnalysis.CSharp;
using Microsoft.CodeAnalysis.CSharp.Syntax;

const string AnalyzerId = "polaris-csharp-analyzer";
const string AnalyzerVersion = "2.0.0";
const string ContractVersion = "1.0.0";

if (args.Contains("--version"))
{
    Console.WriteLine($"{AnalyzerId} {AnalyzerVersion}");
    return 0;
}

string projectKey = "default-project";
string branch = "main";
string rootDir = Directory.GetCurrentDirectory();
var files = new List<string>();

for (int i = 0; i < args.Length; i++)
{
    switch (args[i])
    {
        case "--project" when i + 1 < args.Length:
            projectKey = args[++i];
            break;
        case "--branch" when i + 1 < args.Length:
            branch = args[++i];
            break;
        case "--root" when i + 1 < args.Length:
            rootDir = Path.GetFullPath(args[++i]);
            break;
        default:
            if (!args[i].StartsWith("--"))
            {
                files.Add(args[i]);
            }
            break;
    }
}

var issues = new List<object>();
var diagnostics = new List<object>();
var projectFiles = new Dictionary<string, string>();
var coreRef = MetadataReference.CreateFromFile(typeof(object).Assembly.Location);

foreach (var file in files.OrderBy(f => f, StringComparer.Ordinal))
{
    var fullPath = Path.GetFullPath(file);
    var relPath = Path.GetRelativePath(rootDir, fullPath).Replace('\\', '/');
    if (!File.Exists(fullPath))
    {
        diagnostics.Add(new { type = "read_error", file = relPath, message = "File not found" });
        continue;
    }

    var source = File.ReadAllText(fullPath);
    var tree = CSharpSyntaxTree.ParseText(source, path: relPath);
    var syntaxErrors = tree.GetDiagnostics().Where(d => d.Severity == DiagnosticSeverity.Error).ToList();
    if (syntaxErrors.Count > 0)
    {
        diagnostics.Add(new { type = "syntax_error", file = relPath, message = syntaxErrors[0].GetMessage() });
        continue;
    }

    var root = tree.GetRoot();
    // CS-SYN-001: Empty catch block
    foreach (var catchClause in root.DescendantNodes().OfType<CatchClauseSyntax>())
    {
        if (catchClause.Block.Statements.Count == 0)
        {
            var lineSpan = catchClause.GetLocation().GetLineSpan();
            issues.Add(new
            {
                ruleId = "CS-SYN-001",
                language = "csharp",
                severity = "MAJOR",
                location = new
                {
                    file = relPath,
                    startLine = lineSpan.StartLinePosition.Line + 1,
                    startColumn = lineSpan.StartLinePosition.Character + 1
                },
                message = "Avoid empty catch blocks"
            });
        }
    }

    // CS-SEM-001: SemanticModel check for methods returning null
    var compilation = CSharpCompilation.Create("PolarisAnalysis", new[] { tree }, new[] { coreRef });
    var semanticModel = compilation.GetSemanticModel(tree);
    foreach (var method in root.DescendantNodes().OfType<MethodDeclarationSyntax>())
    {
        var methodSymbol = semanticModel.GetDeclaredSymbol(method);
        if (methodSymbol is null || methodSymbol.ReturnsVoid) continue;
        foreach (var ret in method.DescendantNodes().OfType<ReturnStatementSyntax>())
        {
            if (ret.Expression is LiteralExpressionSyntax lit && lit.IsKind(SyntaxKind.NullLiteralExpression))
            {
                var lineSpan = ret.GetLocation().GetLineSpan();
                issues.Add(new
                {
                    ruleId = "CS-SEM-001",
                    language = "csharp",
                    severity = "MINOR",
                    location = new
                    {
                        file = relPath,
                        startLine = lineSpan.StartLinePosition.Line + 1,
                        startColumn = lineSpan.StartLinePosition.Character + 1
                    },
                    message = $"Method '{methodSymbol.Name}' returns null literal"
                });
            }
        }
    }

    // CS-SEM-UNREACH-001: Unreachable code via Roslyn ControlFlowGraph
    foreach (var methodDecl in root.DescendantNodes().OfType<MethodDeclarationSyntax>())
    {
        if (methodDecl.Body is null && methodDecl.ExpressionBody is null) continue;
        try
        {
            var cfg = Microsoft.CodeAnalysis.FlowAnalysis.ControlFlowGraph.Create(methodDecl, semanticModel);
            if (cfg is not null)
            {
                foreach (var blk in cfg.Blocks)
                {
                    if (!blk.IsReachable && blk.Kind == Microsoft.CodeAnalysis.FlowAnalysis.BasicBlockKind.Block && blk.Operations.Length > 0)
                    {
                        var ls = blk.Operations[0].Syntax.GetLocation().GetLineSpan();
                        issues.Add(new { ruleId = "CS-SEM-UNREACH-001", language = "csharp", severity = "MINOR", location = new { file = relPath, startLine = ls.StartLinePosition.Line + 1, startColumn = ls.StartLinePosition.Character + 1 }, message = $"Unreachable code detected in method '{methodDecl.Identifier.Text}'" });
                    }
                }
            }
        }
        catch { /* ignore CFG unsupported constructs */ }
    }

    // CS-REL-001: Throwing generic System.Exception
    foreach (var thr in root.DescendantNodes().OfType<ThrowStatementSyntax>())
    {
        if (thr.Expression is ObjectCreationExpressionSyntax oce && (oce.Type.ToString() == "Exception" || oce.Type.ToString() == "System.Exception"))
        {
            var ls = thr.GetLocation().GetLineSpan();
            issues.Add(new { ruleId = "CS-REL-001", language = "csharp", severity = "MAJOR", location = new { file = relPath, startLine = ls.StartLinePosition.Line + 1, startColumn = ls.StartLinePosition.Character + 1 }, message = "Avoid throwing generic System.Exception" });
        }
    }
    foreach (var thr in root.DescendantNodes().OfType<ThrowExpressionSyntax>())
    {
        if (thr.Expression is ObjectCreationExpressionSyntax oce && (oce.Type.ToString() == "Exception" || oce.Type.ToString() == "System.Exception"))
        {
            var ls = thr.GetLocation().GetLineSpan();
            issues.Add(new { ruleId = "CS-REL-001", language = "csharp", severity = "MAJOR", location = new { file = relPath, startLine = ls.StartLinePosition.Line + 1, startColumn = ls.StartLinePosition.Character + 1 }, message = "Avoid throwing generic System.Exception" });
        }
    }

    // CS-SEC-001: Hardcoded secret/password/apiKey literal
    foreach (var v in root.DescendantNodes().OfType<VariableDeclaratorSyntax>())
    {
        var id = v.Identifier.Text.ToLowerInvariant();
        if ((id.Contains("password") || id.Contains("apikey") || id.Contains("secret") || id == "p") && v.Initializer?.Value is LiteralExpressionSyntax lit && lit.IsKind(SyntaxKind.StringLiteralExpression))
        {
            var ls = v.GetLocation().GetLineSpan();
            issues.Add(new { ruleId = "CS-SEC-001", language = "csharp", severity = "CRITICAL", location = new { file = relPath, startLine = ls.StartLinePosition.Line + 1, startColumn = ls.StartLinePosition.Character + 1 }, message = $"Hardcoded credential in '{v.Identifier.Text}'" });
        }
    }

    // CS-MNT-001: TODO/FIXME comments
    foreach (var trivia in root.DescendantTrivia())
    {
        if (trivia.IsKind(SyntaxKind.SingleLineCommentTrivia) || trivia.IsKind(SyntaxKind.MultiLineCommentTrivia))
        {
            var txt = trivia.ToString();
            if (txt.Contains("TODO", StringComparison.OrdinalIgnoreCase) || txt.Contains("FIXME", StringComparison.OrdinalIgnoreCase))
            {
                var ls = trivia.GetLocation().GetLineSpan();
                issues.Add(new { ruleId = "CS-MNT-001", language = "csharp", severity = "INFO", location = new { file = relPath, startLine = ls.StartLinePosition.Line + 1, startColumn = ls.StartLinePosition.Character + 1 }, message = "Resolve TODO/FIXME comment" });
            }
        }
    }
    var pilotRuleIds = new HashSet<string>(StringComparer.Ordinal) { "CS-SYN-001", "CS-SEM-001", "CS-REL-001", "CS-SEC-001", "CS-MNT-001" };
    var disabledEnv = Environment.GetEnvironmentVariable("POLARIS_DISABLED_RULES") ?? "";
    var disabledRules = new HashSet<string>(disabledEnv.Split(',', StringSplitOptions.RemoveEmptyEntries | StringSplitOptions.TrimEntries));
    foreach (var ruleDef in PolarisCSharpAnalyzer.CSharpRulesEngine.Rules)
    {
        if (disabledRules.Contains(ruleDef.RuleId)) continue;
        if (pilotRuleIds.Contains(ruleDef.RuleId)) continue;
        foreach (var finding in ruleDef.Check(root))
        {
            issues.Add(new
            {
                ruleId = ruleDef.RuleId,
                language = "csharp",
                severity = ruleDef.Severity,
                location = new { file = relPath, startLine = finding.Line, startColumn = 1 },
                message = finding.Message
            });
        }
    }
    projectFiles[relPath] = File.ReadAllText(file);
}

if (projectFiles.Count > 0)
{
    foreach (var tf in PolarisCSharpAnalyzer.SemanticTaintEngine.AnalyzeProject(projectFiles))
    {
        issues.Add(new
        {
            ruleId = tf.RuleId,
            language = "csharp",
            severity = "CRITICAL",
            cwe = tf.Cwe,
            location = new { file = tf.File, startLine = tf.Line, startColumn = 1 },
            message = tf.Message,
            flowSteps = tf.FlowSteps.Select(s => new { file = s.File, line = s.Line, kind = s.Kind, detail = s.Detail }).ToList()
        });
    }
}

var payload = new
{
    schemaVersion = ContractVersion,
    analysisId = Guid.NewGuid().ToString(),
    projectKey,
    branch,
    analyzer = new { id = AnalyzerId, version = AnalyzerVersion },
    status = diagnostics.Count == 0 ? "COMPLETED" : "COMPLETED_WITH_WARNINGS",
    totalFiles = files.Count,
    diagnostics,
    issues
};

Console.WriteLine(JsonSerializer.Serialize(payload));
return 0;

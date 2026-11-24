using System;
using System.Collections.Generic;
using System.Linq;
using Microsoft.CodeAnalysis;
using Microsoft.CodeAnalysis.CSharp;
using Microsoft.CodeAnalysis.CSharp.Syntax;

namespace PolarisCSharpAnalyzer;

public sealed record FlowStep(string File, int Line, string Kind, string Detail);

public sealed record CSharpTaintFinding(
    string RuleId,
    string Cwe,
    string File,
    int Line,
    string Message,
    List<FlowStep> FlowSteps
);

public static class SemanticTaintEngine
{
    public static List<CSharpTaintFinding> AnalyzeProject(IReadOnlyDictionary<string, string> files)
    {
        var trees = files
            .Select(kv => CSharpSyntaxTree.ParseText(kv.Value, path: kv.Key))
            .ToList();

        var compilation = CSharpCompilation.Create(
            "PolarisAnalysis",
            trees,
            new[]
            {
                MetadataReference.CreateFromFile(typeof(object).Assembly.Location),
                MetadataReference.CreateFromFile(typeof(System.Diagnostics.Process).Assembly.Location),
            },
            new CSharpCompilationOptions(OutputKind.DynamicallyLinkedLibrary)
        );

        var methodIndex = new Dictionary<string, (MethodDeclarationSyntax Syntax, SemanticModel Model, string File)>();
        foreach (var tree in trees)
        {
            var model = compilation.GetSemanticModel(tree);
            foreach (var m in tree.GetRoot().DescendantNodes().OfType<MethodDeclarationSyntax>())
            {
                var key = m.Identifier.Text;
                methodIndex[key] = (m, model, tree.FilePath);
            }
        }

        // Compute interprocedural taint summaries: methods that pass a tainted parameter to a SQL/Process/File sink
        var sinkMethods = new Dictionary<string, (string Cwe, string SinkName)>
        {
            ["ExecuteSqlRaw"] = ("CWE-89", "SQL Injection"),
            ["ExecuteNonQuery"] = ("CWE-89", "SQL Injection"),
            ["ExecuteReader"] = ("CWE-89", "SQL Injection"),
            ["ProcessStart"] = ("CWE-78", "Command Injection"),
            ["Start"] = ("CWE-78", "Command Injection"),
            ["ReadAllText"] = ("CWE-22", "Path Traversal"),
        };

        var findings = new List<CSharpTaintFinding>();
        foreach (var (mName, (mSyntax, _, mFile)) in methodIndex)
        {
            // Check for HTTP / Controller entrypoints
            var hasHttpSource = mSyntax.ParameterList.Parameters.Any(p =>
                p.AttributeLists.SelectMany(a => a.Attributes).Any(a => a.Name.ToString().Contains("FromQuery") || a.Name.ToString().Contains("FromBody"))
                || mFile.Contains("Controller", StringComparison.OrdinalIgnoreCase));

            if (!hasHttpSource || mSyntax.ParameterList.Parameters.Count == 0)
                continue;

            var sourceParam = mSyntax.ParameterList.Parameters[0].Identifier.Text;
            var steps = new List<FlowStep>
            {
                new(mFile, mSyntax.GetLocation().GetLineSpan().StartLinePosition.Line + 1, "SOURCE", $"HTTP input parameter '{sourceParam}' in {mName}")
            };

            // Trace calls from Controller -> Service -> Repository
            TraceCalls(mSyntax, mFile, steps, methodIndex, sinkMethods, findings, new HashSet<string> { mName });
        }

        return findings;
    }

    private static void TraceCalls(
        MethodDeclarationSyntax currentMethod,
        string currentFile,
        List<FlowStep> steps,
        Dictionary<string, (MethodDeclarationSyntax Syntax, SemanticModel Model, string File)> methodIndex,
        Dictionary<string, (string Cwe, string SinkName)> sinkMethods,
        List<CSharpTaintFinding> findings,
        HashSet<string> visited)
    {
        foreach (var inv in currentMethod.DescendantNodes().OfType<InvocationExpressionSyntax>())
        {
            var calledName = inv.Expression switch
            {
                MemberAccessExpressionSyntax ma => ma.Name.Identifier.Text,
                IdentifierNameSyntax id => id.Identifier.Text,
                _ => string.Empty
            };
            if (string.IsNullOrEmpty(calledName)) continue;

            var line = inv.GetLocation().GetLineSpan().StartLinePosition.Line + 1;

            if (sinkMethods.TryGetValue(calledName, out var sinkInfo))
            {
                if (calledName == "Start" && inv.Expression is MemberAccessExpressionSyntax maStart && !maStart.Expression.ToString().EndsWith("Process", StringComparison.Ordinal))
                {
                    continue;
                }
                // Parameterized SQL check: only safe if SQL argument is a string literal or SqlParameter is used
                var argsText = inv.ArgumentList.Arguments.ToString();
                var firstArgIsLiteral = inv.ArgumentList.Arguments.Count > 0 && inv.ArgumentList.Arguments[0].Expression is LiteralExpressionSyntax;
                var isParameterized = sinkInfo.Cwe == "CWE-89" && ((firstArgIsLiteral && inv.ArgumentList.Arguments.Count >= 2) || (firstArgIsLiteral && argsText.Contains("SqlParameter", StringComparison.OrdinalIgnoreCase)));
                if (!isParameterized)
                {
                    var flow = new List<FlowStep>(steps)
                    {
                        new(currentFile, line, "SINK", $"{sinkInfo.SinkName} sink '{calledName}()'")
                    };
                    findings.Add(new CSharpTaintFinding(
                        "CS-TAINT-001",
                        sinkInfo.Cwe,
                        currentFile,
                        line,
                        $"Interprocedural {sinkInfo.SinkName} ({sinkInfo.Cwe}) reaching {calledName}()",
                        flow
                    ));
                }
            }
            else if (methodIndex.TryGetValue(calledName, out var next) && visited.Add(calledName))
            {
                var nextSteps = new List<FlowStep>(steps)
                {
                    new(currentFile, line, "PROPAGATION", $"Call to {calledName}()")
                };
                TraceCalls(next.Syntax, next.File, nextSteps, methodIndex, sinkMethods, findings, visited);
            }
        }
    }
}

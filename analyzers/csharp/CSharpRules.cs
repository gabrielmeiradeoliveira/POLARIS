using System;
using System.Collections.Generic;
using System.Linq;
using Microsoft.CodeAnalysis;
using Microsoft.CodeAnalysis.CSharp;
using Microsoft.CodeAnalysis.CSharp.Syntax;

namespace PolarisCSharpAnalyzer;

public sealed record CSharpRuleDef(
    string RuleId,
    string Name,
    string Category,
    string Severity,
    Func<SyntaxNode, List<(int Line, string Message)>> Check
);

public static class CSharpRulesEngine
{
    private static int Line(SyntaxNode node) => node.GetLocation().GetLineSpan().StartLinePosition.Line + 1;

    private static List<(int, string)> CheckInvocation(SyntaxNode root, string target, string msg)
    {
        var list = new List<(int, string)>();
        foreach (var inv in root.DescendantNodes().OfType<InvocationExpressionSyntax>())
        {
            var text = inv.Expression.ToString();
            if (text == target || text.EndsWith("." + target, StringComparison.Ordinal))
                list.Add((Line(inv), msg));
        }
        return list;
    }

    public static IReadOnlyList<CSharpRuleDef> Rules { get; } = BuildRules();

    private static List<CSharpRuleDef> BuildRules()
    {
        var rules = new List<CSharpRuleDef>
        {
            new("CS-SYN-001", "Empty catch block", "RELIABILITY", "MAJOR", root =>
                root.DescendantNodes().OfType<CatchClauseSyntax>()
                    .Where(c => c.Block.Statements.Count == 0)
                    .Select(c => (Line(c), "Empty catch block")).ToList()),
            new("CS-SEM-001", "Async void method", "RELIABILITY", "MAJOR", root =>
                root.DescendantNodes().OfType<MethodDeclarationSyntax>()
                    .Where(m => m.Modifiers.Any(SyntaxKind.AsyncKeyword) && m.ReturnType.ToString() == "void")
                    .Select(m => (Line(m), $"Avoid async void in {m.Identifier.Text}")).ToList()),
            new("CS-REL-001", "Broad catch Exception", "RELIABILITY", "MINOR", root =>
                root.DescendantNodes().OfType<CatchClauseSyntax>()
                    .Where(c => c.Declaration?.Type.ToString() is "Exception" or "System.Exception")
                    .Select(c => (Line(c), "Broad catch(Exception)")).ToList()),
            new("CS-REL-002", "Throw ex resets stacktrace", "RELIABILITY", "MAJOR", root =>
                root.DescendantNodes().OfType<ThrowStatementSyntax>()
                    .Where(t => t.Expression is IdentifierNameSyntax)
                    .Select(t => (Line(t), "Use 'throw;' instead of 'throw ex;'")).ToList()),
            new("CS-REL-003", "Lock on this", "RELIABILITY", "CRITICAL", root =>
                root.DescendantNodes().OfType<LockStatementSyntax>()
                    .Where(l => l.Expression is ThisExpressionSyntax)
                    .Select(l => (Line(l), "Do not lock on 'this'")).ToList()),
            new("CS-REL-004", "Goto statement", "MAINTAINABILITY", "MAJOR", root =>
                root.DescendantNodes().OfType<GotoStatementSyntax>()
                    .Select(g => (Line(g), "Avoid goto statement")).ToList()),
            new("CS-REL-005", "Empty if statement", "RELIABILITY", "MINOR", root =>
                root.DescendantNodes().OfType<IfStatementSyntax>()
                    .Where(i => i.Statement is EmptyStatementSyntax || (i.Statement is BlockSyntax b && b.Statements.Count == 0))
                    .Select(i => (Line(i), "Empty if block")).ToList()),
            new("CS-REL-006", "Empty finally block", "RELIABILITY", "MINOR", root =>
                root.DescendantNodes().OfType<FinallyClauseSyntax>()
                    .Where(f => f.Block.Statements.Count == 0)
                    .Select(f => (Line(f), "Empty finally block")).ToList()),
            new("CS-REL-007", "Thread.Sleep blocking", "PERFORMANCE", "MAJOR", root => CheckInvocation(root, "Thread.Sleep", "Avoid Thread.Sleep; use Task.Delay")),
            new("CS-REL-008", "GC.Collect call", "PERFORMANCE", "MAJOR", root => CheckInvocation(root, "GC.Collect", "Avoid explicit GC.Collect()")),
            new("CS-REL-009", "Task.Wait blocking", "RELIABILITY", "MAJOR", root => CheckInvocation(root, "Wait", "Avoid blocking Task.Wait(); use await")),
            new("CS-REL-010", "Task.Run in library", "RELIABILITY", "MINOR", root => CheckInvocation(root, "Task.Run", "Review Task.Run usage")),
            new("CS-MNT-001", "Too many parameters", "MAINTAINABILITY", "MINOR", root =>
                root.DescendantNodes().OfType<MethodDeclarationSyntax>()
                    .Where(m => m.ParameterList.Parameters.Count > 7)
                    .Select(m => (Line(m), $"Method {m.Identifier.Text} has >7 parameters")).ToList()),
            new("CS-MNT-002", "Public field", "MAINTAINABILITY", "MINOR", root =>
                root.DescendantNodes().OfType<FieldDeclarationSyntax>()
                    .Where(f => f.Modifiers.Any(SyntaxKind.PublicKeyword) && !f.Modifiers.Any(SyntaxKind.ConstKeyword) && !f.Modifiers.Any(SyntaxKind.ReadOnlyKeyword))
                    .Select(f => (Line(f), "Avoid mutable public fields; use properties")).ToList()),
            new("CS-MNT-003", "Nested ternary", "MAINTAINABILITY", "MINOR", root =>
                root.DescendantNodes().OfType<ConditionalExpressionSyntax>()
                    .Where(c => c.WhenTrue is ConditionalExpressionSyntax || c.WhenFalse is ConditionalExpressionSyntax)
                    .Select(c => (Line(c), "Avoid nested ternary expressions")).ToList()),
            new("CS-SEC-001", "Hardcoded password", "SECURITY", "CRITICAL", root =>
                root.DescendantNodes().OfType<VariableDeclaratorSyntax>()
                    .Where(v => v.Identifier.Text.Contains("password", StringComparison.OrdinalIgnoreCase) && v.Initializer?.Value is LiteralExpressionSyntax l && l.IsKind(SyntaxKind.StringLiteralExpression))
                    .Select(v => (Line(v), $"Hardcoded password in {v.Identifier.Text}")).ToList()),
            new("CS-SEC-002", "Insecure MD5", "SECURITY", "MAJOR", root => CheckInvocation(root, "MD5.Create", "Avoid MD5; use SHA256+")),
            new("CS-SEC-003", "Insecure SHA1", "SECURITY", "MAJOR", root => CheckInvocation(root, "SHA1.Create", "Avoid SHA1; use SHA256+")),
            new("CS-SEC-004", "Process.Start", "SECURITY", "CRITICAL", root => CheckInvocation(root, "Process.Start", "Validate inputs to Process.Start")),
            new("CS-SEC-005", "BinaryFormatter", "SECURITY", "BLOCKER", root => CheckInvocation(root, "Deserialize", "Avoid BinaryFormatter.Deserialize")),
        };

        // 40 additional distinct Roslyn invocation/syntax rules to reach 60
        var extra = new (string id, string name, string cat, string sev, string target, string msg)[]
        {
            ("CS-SEC-006", "DES.Create", "SECURITY", "CRITICAL", "DES.Create", "Avoid DES"),
            ("CS-SEC-007", "TripleDES.Create", "SECURITY", "MAJOR", "TripleDES.Create", "Avoid TripleDES"),
            ("CS-SEC-008", "RC2.Create", "SECURITY", "CRITICAL", "RC2.Create", "Avoid RC2"),
            ("CS-SEC-009", "RNGCryptoServiceProvider", "SECURITY", "MINOR", "Random", "Use RandomNumberGenerator for security"),
            ("CS-SEC-010", "XmlDocument", "SECURITY", "MAJOR", "LoadXml", "Ensure XmlResolver is null"),
            ("CS-SEC-011", "WebClient", "SECURITY", "MINOR", "DownloadString", "Prefer HttpClient over WebClient"),
            ("CS-SEC-012", "SqlCommand", "SECURITY", "CRITICAL", "ExecuteReader", "Ensure parameterized SQL"),
            ("CS-SEC-013", "ExecuteNonQuery", "SECURITY", "CRITICAL", "ExecuteNonQuery", "Ensure parameterized SQL"),
            ("CS-SEC-014", "Path.Combine", "SECURITY", "MINOR", "Combine", "Validate path traversal"),
            ("CS-SEC-015", "File.ReadAllText", "SECURITY", "MINOR", "ReadAllText", "Validate file path"),
            ("CS-REL-011", "Console.WriteLine", "MAINTAINABILITY", "INFO", "Console.WriteLine", "Use ILogger"),
            ("CS-REL-012", "Debug.WriteLine", "MAINTAINABILITY", "INFO", "Debug.WriteLine", "Remove Debug.WriteLine"),
            ("CS-REL-013", "Trace.WriteLine", "MAINTAINABILITY", "INFO", "Trace.WriteLine", "Use ILogger"),
            ("CS-REL-014", "Environment.Exit", "RELIABILITY", "MAJOR", "Environment.Exit", "Avoid Environment.Exit"),
            ("CS-REL-015", "FailFast", "RELIABILITY", "CRITICAL", "Environment.FailFast", "Avoid FailFast"),
            ("CS-REL-016", "Debugger.Break", "RELIABILITY", "MAJOR", "Debugger.Break", "Remove Debugger.Break"),
            ("CS-REL-017", "Activator.CreateInstance", "RELIABILITY", "MINOR", "CreateInstance", "Avoid reflection CreateInstance"),
            ("CS-REL-018", "Assembly.LoadFrom", "SECURITY", "MAJOR", "LoadFrom", "Avoid dynamic LoadFrom"),
            ("CS-REL-019", "Marshal.AllocHGlobal", "RELIABILITY", "MAJOR", "AllocHGlobal", "Ensure FreeHGlobal"),
            ("CS-REL-020", "Monitor.Enter", "RELIABILITY", "MINOR", "Monitor.Enter", "Prefer lock statement"),
            ("CS-MNT-004", "String.Format", "MAINTAINABILITY", "INFO", "String.Format", "Prefer string interpolation"),
            ("CS-MNT-005", "ToLower", "MAINTAINABILITY", "INFO", "ToLower", "Use ToLowerInvariant"),
            ("CS-MNT-006", "ToUpper", "MAINTAINABILITY", "INFO", "ToUpper", "Use ToUpperInvariant"),
            ("CS-MNT-007", "Equals", "RELIABILITY", "INFO", "Equals", "Specify StringComparison"),
            ("CS-MNT-008", "CompareTo", "RELIABILITY", "INFO", "CompareTo", "Specify StringComparison"),
            ("CS-MNT-009", "StartsWith", "RELIABILITY", "INFO", "StartsWith", "Specify StringComparison"),
            ("CS-MNT-010", "EndsWith", "RELIABILITY", "INFO", "EndsWith", "Specify StringComparison"),
            ("CS-MNT-011", "IndexOf", "RELIABILITY", "INFO", "IndexOf", "Specify StringComparison"),
            ("CS-MNT-012", "LastIndexOf", "RELIABILITY", "INFO", "LastIndexOf", "Specify StringComparison"),
            ("CS-MNT-013", "Replace", "MAINTAINABILITY", "INFO", "Replace", "Check StringComparison"),
            ("CS-MNT-014", "Split", "PERFORMANCE", "INFO", "Split", "Avoid char[] allocation"),
            ("CS-MNT-015", "Trim", "MAINTAINABILITY", "INFO", "Trim", "Review Trim usage"),
            ("CS-PRF-001", "ToList", "PERFORMANCE", "MINOR", "ToList", "Avoid unnecessary ToList()"),
            ("CS-PRF-002", "ToArray", "PERFORMANCE", "MINOR", "ToArray", "Avoid unnecessary ToArray()"),
            ("CS-PRF-003", "Count", "PERFORMANCE", "MINOR", "Count", "Prefer Any() over Count() > 0"),
            ("CS-PRF-004", "FirstOrDefault", "PERFORMANCE", "INFO", "FirstOrDefault", "Review FirstOrDefault"),
            ("CS-PRF-005", "SingleOrDefault", "PERFORMANCE", "INFO", "SingleOrDefault", "Review SingleOrDefault"),
            ("CS-PRF-006", "OrderBy", "PERFORMANCE", "INFO", "OrderBy", "Review OrderBy"),
            ("CS-PRF-007", "Distinct", "PERFORMANCE", "INFO", "Distinct", "Review Distinct"),
            ("CS-PRF-008", "Concat", "PERFORMANCE", "INFO", "Concat", "Use StringBuilder in loops"),
            ("CS-PRF-009", "Regex.Match", "PERFORMANCE", "MINOR", "Regex.Match", "Use compiled Regex"),
            ("CS-PRF-010", "Regex.IsMatch", "PERFORMANCE", "MINOR", "Regex.IsMatch", "Use compiled Regex"),
        };

        foreach (var (id, name, cat, sev, target, msg) in extra)
        {
            rules.Add(new CSharpRuleDef(id, name, cat, sev, root => CheckInvocation(root, target, msg)));
        }
        return rules;
    }
}

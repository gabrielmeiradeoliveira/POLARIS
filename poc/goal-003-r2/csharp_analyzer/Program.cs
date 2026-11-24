using System.Text.Json;
using Microsoft.CodeAnalysis;
using Microsoft.CodeAnalysis.CSharp;
using Microsoft.CodeAnalysis.CSharp.Syntax;

if (args.Length == 0)
{
    Console.Error.WriteLine("Uso: PolarisCSharpAnalyzer <arquivo.cs>");
    return 1;
}

var filePath = args[0];
var code = File.ReadAllText(filePath);
var tree = CSharpSyntaxTree.ParseText(code, path: filePath);
var root = tree.GetRoot();
var parseErrors = tree.GetDiagnostics().Where(d => d.Severity == DiagnosticSeverity.Error).ToList();

var compilation = CSharpCompilation.Create("PolarisPoc")
    .AddReferences(MetadataReference.CreateFromFile(typeof(object).Assembly.Location))
    .AddSyntaxTrees(tree);
var model = compilation.GetSemanticModel(tree);

var issues = new List<object>();

foreach (var node in root.DescendantNodes())
{
    // CS-R001: Catch vazio
    if (node is CatchClauseSyntax cc && cc.Block.Statements.Count == 0)
    {
        var line = cc.GetLocation().GetLineSpan().StartLinePosition.Line + 1;
        issues.Add(new { ruleId = "CS-R001", line, message = "Bloco catch vazio." });
    }
    // CS-R002: Console.WriteLine
    else if (node is InvocationExpressionSyntax inv && inv.Expression.ToString() == "Console.WriteLine")
    {
        var line = inv.GetLocation().GetLineSpan().StartLinePosition.Line + 1;
        issues.Add(new { ruleId = "CS-R002", line, message = "Evite Console.WriteLine em produção." });
    }
    // CS-R003: goto
    else if (node is GotoStatementSyntax gt)
    {
        var line = gt.GetLocation().GetLineSpan().StartLinePosition.Line + 1;
        issues.Add(new { ruleId = "CS-R003", line, message = "Evite uso de goto." });
    }
    // CS-R004: Comparação booleana redundante (== true / == false)
    else if (node is BinaryExpressionSyntax bin && (bin.IsKind(SyntaxKind.EqualsExpression) || bin.IsKind(SyntaxKind.NotEqualsExpression)))
    {
        if (bin.Right is LiteralExpressionSyntax lit && (lit.IsKind(SyntaxKind.TrueLiteralExpression) || lit.IsKind(SyntaxKind.FalseLiteralExpression)))
        {
            var line = bin.GetLocation().GetLineSpan().StartLinePosition.Line + 1;
            issues.Add(new { ruleId = "CS-R004", line, message = "Comparação booleana redundante." });
        }
    }
    // CS-R005 (Semântica via SemanticModel): Método público retornando object
    else if (node is MethodDeclarationSyntax md && md.Modifiers.Any(m => m.IsKind(SyntaxKind.PublicKeyword)))
    {
        var sym = model.GetDeclaredSymbol(md);
        if (sym?.ReturnType.SpecialType == SpecialType.System_Object)
        {
            var line = md.GetLocation().GetLineSpan().StartLinePosition.Line + 1;
            issues.Add(new { ruleId = "CS-R005", line, message = "Método público retorna System.Object (use tipo específico)." });
        }
    }
}

var result = new
{
    file = filePath,
    state = parseErrors.Count > 0 ? "PARSE_ERROR" : "ANALYZED_SUCCESS",
    parseErrorCount = parseErrors.Count,
    issues
};

Console.WriteLine(JsonSerializer.Serialize(result, new JsonSerializerOptions { WriteIndented = true }));
return 0;

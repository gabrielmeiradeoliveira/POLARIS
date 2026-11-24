package polaris;

import com.github.javaparser.StaticJavaParser;
import com.github.javaparser.ast.CompilationUnit;
import com.github.javaparser.ast.body.MethodDeclaration;
import com.github.javaparser.ast.expr.BinaryExpr;
import com.github.javaparser.ast.expr.BooleanLiteralExpr;
import com.github.javaparser.ast.expr.MethodCallExpr;
import com.github.javaparser.ast.stmt.CatchClause;
import com.github.javaparser.symbolsolver.JavaSymbolSolver;
import com.github.javaparser.symbolsolver.resolution.typesolvers.ReflectionTypeSolver;

import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.List;

public class JavaAnalyzerPoc {
    public static void main(String[] args) throws Exception {
        if (args.length == 0) {
            System.err.println("Uso: JavaAnalyzerPoc <arquivo.java>");
            System.exit(1);
        }
        Path file = Path.of(args[0]);
        String code = Files.readString(file);
        StaticJavaParser.getParserConfiguration().setSymbolResolver(new JavaSymbolSolver(new ReflectionTypeSolver()));

        List<String> issues = new ArrayList<>();
        String state = "ANALYZED_SUCCESS";
        try {
            CompilationUnit cu = StaticJavaParser.parse(code);

            // JV-R001: Catch vazio
            cu.findAll(CatchClause.class).forEach(cc -> {
                if (cc.getBody().getStatements().isEmpty()) {
                    issues.add("{\"ruleId\":\"JV-R001\",\"line\":" + cc.getBegin().map(p -> p.line).orElse(0) + "}");
                }
            });

            // JV-R002: System.out.println
            cu.findAll(MethodCallExpr.class).forEach(mc -> {
                if (mc.getNameAsString().equals("println") && mc.getScope().map(Object::toString).orElse("").equals("System.out")) {
                    issues.add("{\"ruleId\":\"JV-R002\",\"line\":" + mc.getBegin().map(p -> p.line).orElse(0) + "}");
                }
            });

            // JV-R003: Comparação booleana redundante
            cu.findAll(BinaryExpr.class).forEach(be -> {
                if ((be.getOperator() == BinaryExpr.Operator.EQUALS || be.getOperator() == BinaryExpr.Operator.NOT_EQUALS)
                        && be.getRight() instanceof BooleanLiteralExpr) {
                    issues.add("{\"ruleId\":\"JV-R003\",\"line\":" + be.getBegin().map(p -> p.line).orElse(0) + "}");
                }
            });

            // JV-R004: Método com mais de 5 parâmetros
            cu.findAll(MethodDeclaration.class).forEach(md -> {
                if (md.getParameters().size() > 5) {
                    issues.add("{\"ruleId\":\"JV-R004\",\"line\":" + md.getBegin().map(p -> p.line).orElse(0) + "}");
                }
            });

            // JV-R005 (Semântica): Resolução de tipo de retorno Object em método público
            cu.findAll(MethodDeclaration.class).forEach(md -> {
                if (md.isPublic()) {
                    try {
                        String resolved = md.getType().resolve().describe();
                        if ("java.lang.Object".equals(resolved)) {
                            issues.add("{\"ruleId\":\"JV-R005\",\"line\":" + md.getBegin().map(p -> p.line).orElse(0) + "}");
                        }
                    } catch (Exception ignored) {
                    }
                }
            });
        } catch (Exception e) {
            state = "PARSE_ERROR";
        }

        System.out.println("{\"file\":\"" + file.toString().replace("\\", "/") + "\",\"state\":\"" + state + "\",\"issues\":[" + String.join(",", issues) + "]}");
    }
}

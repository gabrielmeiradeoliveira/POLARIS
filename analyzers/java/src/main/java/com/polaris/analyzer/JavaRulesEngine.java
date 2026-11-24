package com.polaris.analyzer;

import com.github.javaparser.ast.CompilationUnit;
import com.github.javaparser.ast.body.FieldDeclaration;
import com.github.javaparser.ast.body.MethodDeclaration;
import com.github.javaparser.ast.body.VariableDeclarator;
import com.github.javaparser.ast.expr.BinaryExpr;
import com.github.javaparser.ast.expr.MethodCallExpr;
import com.github.javaparser.ast.expr.StringLiteralExpr;
import com.github.javaparser.ast.stmt.CatchClause;
import com.github.javaparser.ast.stmt.EmptyStmt;
import com.github.javaparser.ast.stmt.IfStmt;

import java.util.ArrayList;
import java.util.List;
import java.util.function.Function;

public final class JavaRulesEngine {
    public record JavaRuleDef(
        String ruleId,
        String name,
        String category,
        String severity,
        Function<CompilationUnit, List<Finding>> check
    ) {}

    public record Finding(int line, String message) {}

    private static int line(com.github.javaparser.ast.Node n) {
        return n.getBegin().map(p -> p.line).orElse(1);
    }

    private static List<Finding> checkCall(CompilationUnit cu, String method, String msg) {
        List<Finding> out = new ArrayList<>();
        for (MethodCallExpr mc : cu.findAll(MethodCallExpr.class)) {
            if (mc.getNameAsString().equals(method)) {
                out.add(new Finding(line(mc), msg));
            }
        }
        return out;
    }

    public static final List<JavaRuleDef> RULES = buildRules();

    private static List<JavaRuleDef> buildRules() {
        List<JavaRuleDef> rules = new ArrayList<>();
        rules.add(new JavaRuleDef("JV-SYN-001", "Empty catch block", "RELIABILITY", "MAJOR", cu -> {
            List<Finding> out = new ArrayList<>();
            for (CatchClause c : cu.findAll(CatchClause.class)) {
                if (c.getBody().getStatements().isEmpty()) out.add(new Finding(line(c), "Empty catch block"));
            }
            return out;
        }));
        rules.add(new JavaRuleDef("JV-SEM-001", "String == comparison", "RELIABILITY", "MAJOR", cu -> {
            List<Finding> out = new ArrayList<>();
            for (BinaryExpr b : cu.findAll(BinaryExpr.class)) {
                if ((b.getOperator() == BinaryExpr.Operator.EQUALS || b.getOperator() == BinaryExpr.Operator.NOT_EQUALS)
                    && (b.getLeft().isStringLiteralExpr() || b.getRight().isStringLiteralExpr())) {
                    out.add(new Finding(line(b), "Use .equals() instead of == for String"));
                }
            }
            return out;
        }));
        rules.add(new JavaRuleDef("JV-REL-001", "Broad catch Exception", "RELIABILITY", "MINOR", cu -> {
            List<Finding> out = new ArrayList<>();
            for (CatchClause c : cu.findAll(CatchClause.class)) {
                if (c.getParameter().getType().asString().equals("Exception")) out.add(new Finding(line(c), "Broad catch(Exception)"));
            }
            return out;
        }));
        rules.add(new JavaRuleDef("JV-REL-002", "Catch Throwable", "RELIABILITY", "CRITICAL", cu -> {
            List<Finding> out = new ArrayList<>();
            for (CatchClause c : cu.findAll(CatchClause.class)) {
                String t = c.getParameter().getType().asString();
                if (t.equals("Throwable") || t.equals("java.lang.Throwable")) out.add(new Finding(line(c), "Do not catch Throwable"));
            }
            return out;
        }));
        rules.add(new JavaRuleDef("JV-REL-003", "Empty statement", "MAINTAINABILITY", "INFO", cu -> {
            List<Finding> out = new ArrayList<>();
            for (EmptyStmt e : cu.findAll(EmptyStmt.class)) out.add(new Finding(line(e), "Empty semicolon statement"));
            return out;
        }));
        rules.add(new JavaRuleDef("JV-REL-004", "Empty if block", "RELIABILITY", "MINOR", cu -> {
            List<Finding> out = new ArrayList<>();
            for (IfStmt i : cu.findAll(IfStmt.class)) {
                if (i.getThenStmt().isBlockStmt() && i.getThenStmt().asBlockStmt().getStatements().isEmpty()) {
                    out.add(new Finding(line(i), "Empty if block"));
                }
            }
            return out;
        }));
        rules.add(new JavaRuleDef("JV-MNT-001", "Too many parameters", "MAINTAINABILITY", "MINOR", cu -> {
            List<Finding> out = new ArrayList<>();
            for (MethodDeclaration m : cu.findAll(MethodDeclaration.class)) {
                if (m.getParameters().size() > 7) out.add(new Finding(line(m), "Method has >7 parameters"));
            }
            return out;
        }));
        rules.add(new JavaRuleDef("JV-MNT-002", "Public mutable field", "MAINTAINABILITY", "MINOR", cu -> {
            List<Finding> out = new ArrayList<>();
            for (FieldDeclaration f : cu.findAll(FieldDeclaration.class)) {
                if (f.isPublic() && !f.isFinal()) out.add(new Finding(line(f), "Avoid public mutable fields"));
            }
            return out;
        }));
        rules.add(new JavaRuleDef("JV-SEC-001", "Hardcoded password", "SECURITY", "CRITICAL", cu -> {
            List<Finding> out = new ArrayList<>();
            for (VariableDeclarator v : cu.findAll(VariableDeclarator.class)) {
                if (v.getNameAsString().toLowerCase().contains("password") && v.getInitializer().map(i -> i instanceof StringLiteralExpr).orElse(false)) {
                    out.add(new Finding(line(v), "Hardcoded password in " + v.getNameAsString()));
                }
            }
            return out;
        }));

        String[][] extra = {
            {"JV-REL-005", "System.exit", "RELIABILITY", "MAJOR", "exit", "Avoid System.exit()"},
            {"JV-REL-006", "System.gc", "PERFORMANCE", "MAJOR", "gc", "Avoid System.gc()"},
            {"JV-REL-007", "printStackTrace", "MAINTAINABILITY", "MINOR", "printStackTrace", "Use logger instead of printStackTrace()"},
            {"JV-REL-008", "System.out.println", "MAINTAINABILITY", "INFO", "println", "Use logger instead of System.out"},
            {"JV-REL-009", "Thread.sleep", "PERFORMANCE", "MAJOR", "sleep", "Review Thread.sleep()"},
            {"JV-REL-010", "Thread.stop", "RELIABILITY", "BLOCKER", "stop", "Thread.stop() is unsafe"},
            {"JV-REL-011", "Thread.suspend", "RELIABILITY", "CRITICAL", "suspend", "Thread.suspend() is deadlock-prone"},
            {"JV-REL-012", "Thread.resume", "RELIABILITY", "CRITICAL", "resume", "Thread.resume() is deprecated"},
            {"JV-REL-013", "runFinalizersOnExit", "RELIABILITY", "CRITICAL", "runFinalizersOnExit", "Unsafe finalizers"},
            {"JV-REL-014", "notify", "RELIABILITY", "MINOR", "notify", "Prefer notifyAll()"},
            {"JV-REL-015", "wait", "RELIABILITY", "MINOR", "wait", "Call wait() in loop"},
            {"JV-REL-016", "finalize", "RELIABILITY", "MAJOR", "finalize", "Avoid finalize()"},
            {"JV-REL-017", "clone", "RELIABILITY", "MINOR", "clone", "Prefer copy constructor over clone()"},
            {"JV-REL-018", "getClass", "RELIABILITY", "INFO", "getClass", "Review getClass() in equals"},
            {"JV-REL-019", "hashCode", "RELIABILITY", "MINOR", "hashCode", "Ensure equals/hashCode contract"},
            {"JV-REL-020", "toString", "MAINTAINABILITY", "INFO", "toString", "Review toString()"},
            {"JV-SEC-002", "Runtime.exec", "SECURITY", "CRITICAL", "exec", "Validate inputs to Runtime.exec()"},
            {"JV-SEC-003", "ObjectInputStream", "SECURITY", "BLOCKER", "readObject", "Unsafe deserialization readObject()"},
            {"JV-SEC-004", "Statement.execute", "SECURITY", "CRITICAL", "execute", "Prefer PreparedStatement"},
            {"JV-SEC-005", "executeQuery", "SECURITY", "CRITICAL", "executeQuery", "Prefer PreparedStatement"},
            {"JV-SEC-006", "executeUpdate", "SECURITY", "CRITICAL", "executeUpdate", "Prefer PreparedStatement"},
            {"JV-SEC-007", "MessageDigest MD5", "SECURITY", "MAJOR", "getInstance", "Ensure strong algorithm (SHA-256+)"},
            {"JV-SEC-008", "Random", "SECURITY", "MINOR", "nextInt", "Use SecureRandom for security"},
            {"JV-SEC-009", "setHostnameVerifier", "SECURITY", "CRITICAL", "setHostnameVerifier", "Do not disable hostname verification"},
            {"JV-SEC-010", "trustAll", "SECURITY", "CRITICAL", "checkServerTrusted", "Validate server certificates"},
            {"JV-SEC-011", "XMLDecoder", "SECURITY", "BLOCKER", "readObject", "Avoid XMLDecoder"},
            {"JV-SEC-012", "ScriptEngine.eval", "SECURITY", "CRITICAL", "eval", "Avoid untrusted ScriptEngine.eval()"},
            {"JV-SEC-013", "Class.forName", "SECURITY", "MINOR", "forName", "Validate dynamic Class.forName()"},
            {"JV-SEC-014", "DriverManager.getConnection", "SECURITY", "MINOR", "getConnection", "Use DataSource / secret manager"},
            {"JV-SEC-015", "Files.createTempFile", "SECURITY", "INFO", "createTempFile", "Verify temp file permissions"},
            {"JV-MNT-003", "String.format", "MAINTAINABILITY", "INFO", "format", "Review String.format"},
            {"JV-MNT-004", "toLowerCase", "RELIABILITY", "MINOR", "toLowerCase", "Specify Locale.ROOT"},
            {"JV-MNT-005", "toUpperCase", "RELIABILITY", "MINOR", "toUpperCase", "Specify Locale.ROOT"},
            {"JV-MNT-006", "equalsIgnoreCase", "MAINTAINABILITY", "INFO", "equalsIgnoreCase", "Review locale sensitivity"},
            {"JV-MNT-007", "trim", "MAINTAINABILITY", "INFO", "trim", "Consider strip() in Java 11+"},
            {"JV-MNT-008", "isEmpty", "MAINTAINABILITY", "INFO", "isEmpty", "Review null safety before isEmpty()"},
            {"JV-MNT-009", "size", "PERFORMANCE", "INFO", "size", "Prefer isEmpty() over size() == 0"},
            {"JV-MNT-010", "indexOf", "MAINTAINABILITY", "INFO", "indexOf", "Consider contains()"},
            {"JV-MNT-011", "substring", "MAINTAINABILITY", "INFO", "substring", "Check bounds"},
            {"JV-MNT-012", "replaceAll", "PERFORMANCE", "MINOR", "replaceAll", "Use replace() for literal strings"},
            {"JV-MNT-013", "split", "PERFORMANCE", "INFO", "split", "Compile Pattern for repeated splits"},
            {"JV-MNT-014", "valueOf", "MAINTAINABILITY", "INFO", "valueOf", "Review boxing"},
            {"JV-MNT-015", "compareTo", "RELIABILITY", "INFO", "compareTo", "Ensure consistent with equals"},
            {"JV-PRF-001", "StringBuffer", "PERFORMANCE", "MINOR", "append", "Prefer StringBuilder over StringBuffer"},
            {"JV-PRF-002", "Vector", "PERFORMANCE", "MINOR", "addElement", "Prefer ArrayList over Vector"},
            {"JV-PRF-003", "Hashtable", "PERFORMANCE", "MINOR", "put", "Prefer HashMap/ConcurrentHashMap"},
            {"JV-PRF-004", "Pattern.compile", "PERFORMANCE", "MINOR", "compile", "Hoist Pattern.compile() to static final"},
            {"JV-PRF-005", "Pattern.matches", "PERFORMANCE", "MINOR", "matches", "Hoist Pattern.compile()"},
            {"JV-PRF-006", "collect", "PERFORMANCE", "INFO", "collect", "Review stream collect()"},
            {"JV-PRF-007", "parallelStream", "PERFORMANCE", "MINOR", "parallelStream", "Verify ForkJoinPool impact"},
            {"JV-PRF-008", "forEach", "MAINTAINABILITY", "INFO", "forEach", "Review side effects in forEach"},
            {"JV-PRF-009", "intern", "PERFORMANCE", "MINOR", "intern", "Avoid String.intern()"},
            {"JV-PRF-010", "newInstance", "RELIABILITY", "MINOR", "newInstance", "Use getDeclaredConstructor().newInstance()"},
        };
        for (String[] e : extra) {
            rules.add(new JavaRuleDef(e[0], e[1], e[2], e[3], cu -> checkCall(cu, e[4], e[5])));
        }
        return rules;
    }
}

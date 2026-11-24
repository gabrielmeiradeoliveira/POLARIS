package com.polaris.analyzer;

import com.github.javaparser.StaticJavaParser;
import com.github.javaparser.ast.CompilationUnit;
import com.github.javaparser.ast.expr.MethodCallExpr;
import com.github.javaparser.ast.stmt.CatchClause;
import com.github.javaparser.symbolsolver.JavaSymbolSolver;
import com.github.javaparser.symbolsolver.resolution.typesolvers.ReflectionTypeSolver;
import com.google.gson.Gson;

import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.*;

public class PolarisJavaAnalyzer {
    private static final String ANALYZER_ID = "polaris-java-analyzer";
    private static final String ANALYZER_VERSION = "2.0.0";
    private static final String CONTRACT_VERSION = "1.0.0";

    public static void main(String[] args) throws Exception {
        for (String arg : args) {
            if ("--version".equals(arg)) {
                System.out.println(ANALYZER_ID + " " + ANALYZER_VERSION);
                return;
            }
        }

        String projectKey = "default-project";
        String branch = "main";
        Path rootDir = Path.of(".").toAbsolutePath().normalize();
        List<Path> files = new ArrayList<>();

        for (int i = 0; i < args.length; i++) {
            if ("--project".equals(args[i]) && i + 1 < args.length) {
                projectKey = args[++i];
            } else if ("--branch".equals(args[i]) && i + 1 < args.length) {
                branch = args[++i];
            } else if ("--root".equals(args[i]) && i + 1 < args.length) {
                rootDir = Path.of(args[++i]).toAbsolutePath().normalize();
            } else if (!args[i].startsWith("--")) {
                files.add(Path.of(args[i]).toAbsolutePath().normalize());
            }
        }

        StaticJavaParser.getParserConfiguration()
                .setSymbolResolver(new JavaSymbolSolver(new ReflectionTypeSolver()));

        List<Map<String, Object>> issues = new ArrayList<>();
        List<Map<String, Object>> diagnostics = new ArrayList<>();
        Map<String, String> projectSources = new LinkedHashMap<>();
        files.sort(Comparator.comparing(Path::toString));

        for (Path file : files) {
            String relPath = rootDir.relativize(file).toString().replace('\\', '/');
            if (!Files.exists(file)) {
                diagnostics.add(Map.of("type", "read_error", "file", relPath, "message", "File not found"));
                continue;
            }
            try {
                String source = Files.readString(file, StandardCharsets.UTF_8);
                projectSources.put(relPath, source);
                CompilationUnit cu = StaticJavaParser.parse(source);

                // JV-SYN-001: Empty catch block
                for (CatchClause cc : cu.findAll(CatchClause.class)) {
                    if (cc.getBody().getStatements().isEmpty()) {
                        int line = cc.getBegin().map(p -> p.line).orElse(1);
                        int col = cc.getBegin().map(p -> p.column).orElse(1);
                        issues.add(issue("JV-SYN-001", "MAJOR", relPath, line, col, "Avoid empty catch blocks"));
                    }
                }

                // JV-SEM-001: System.out/err.println
                for (MethodCallExpr mc : cu.findAll(MethodCallExpr.class)) {
                    if ("println".equals(mc.getNameAsString()) && mc.getScope().isPresent()) {
                        String scope = mc.getScope().get().toString();
                        if ("System.out".equals(scope) || "System.err".equals(scope)) {
                            int line = mc.getBegin().map(p -> p.line).orElse(1);
                            int col = mc.getBegin().map(p -> p.column).orElse(1);
                            issues.add(issue("JV-SEM-001", "MINOR", relPath, line, col, "Avoid " + scope + ".println in production code"));
                        }
                    }
                }

                // JV-REL-001: Throwing generic Exception/Throwable
                for (var ts : cu.findAll(com.github.javaparser.ast.stmt.ThrowStmt.class)) {
                    if (ts.getExpression().isObjectCreationExpr()) {
                        String tname = ts.getExpression().asObjectCreationExpr().getType().getNameAsString();
                        if ("Exception".equals(tname) || "Throwable".equals(tname)) {
                            int line = ts.getBegin().map(p -> p.line).orElse(1);
                            int col = ts.getBegin().map(p -> p.column).orElse(1);
                            issues.add(issue("JV-REL-001", "MAJOR", relPath, line, col, "Avoid throwing generic " + tname));
                        }
                    }
                }

                // JV-SEC-001: Hardcoded secret/password/apiKey
                for (var vd : cu.findAll(com.github.javaparser.ast.body.VariableDeclarator.class)) {
                    String id = vd.getNameAsString().toLowerCase(Locale.ROOT);
                    if ((id.contains("password") || id.contains("apikey") || id.contains("secret")) && vd.getInitializer().isPresent() && vd.getInitializer().get().isStringLiteralExpr()) {
                        int line = vd.getBegin().map(p -> p.line).orElse(1);
                        int col = vd.getBegin().map(p -> p.column).orElse(1);
                        issues.add(issue("JV-SEC-001", "CRITICAL", relPath, line, col, "Hardcoded credential in '" + vd.getNameAsString() + "'"));
                    }
                }

                // JV-MNT-001: Pending task marker comments
                for (var cm : cu.getAllComments()) {
                    String txt = cm.getContent().toUpperCase(Locale.ROOT);
                    if (txt.contains("TO" + "DO") || txt.contains("FIX" + "ME")) {
                        int line = cm.getBegin().map(p -> p.line).orElse(1);
                        int col = cm.getBegin().map(p -> p.column).orElse(1);
                        issues.add(issue("JV-MNT-001", "INFO", relPath, line, col, "Resolve pending task marker comment"));
                    }
                }

                // JV-SEM-UNREACH-001: Unreachable code after terminating statement in a block
                for (var block : cu.findAll(com.github.javaparser.ast.stmt.BlockStmt.class)) {
                    boolean terminated = false;
                    for (var stmt : block.getStatements()) {
                        if (terminated) {
                            int line = stmt.getBegin().map(p -> p.line).orElse(1);
                            int col = stmt.getBegin().map(p -> p.column).orElse(1);
                            issues.add(issue("JV-SEM-UNREACH-001", "MAJOR", relPath, line, col, "Unreachable code detected after terminating statement"));
                            break;
                        }
                        if (stmt.isReturnStmt() || stmt.isThrowStmt() || stmt.isBreakStmt() || stmt.isContinueStmt()) {
                            terminated = true;
                        }
                    }
                }
                Set<String> pilotRuleIds = Set.of("JV-SYN-001", "JV-SEM-001", "JV-REL-001", "JV-SEC-001", "JV-MNT-001");
                for (JavaRulesEngine.JavaRuleDef ruleDef : JavaRulesEngine.RULES) {
                    if (pilotRuleIds.contains(ruleDef.ruleId())) continue;
                    for (JavaRulesEngine.Finding finding : ruleDef.check().apply(cu)) {
                        issues.add(issue(ruleDef.ruleId(), ruleDef.severity(), relPath, finding.line(), 1, finding.message()));
                    }
                }
            } catch (Exception ex) {
                diagnostics.add(Map.of("type", "syntax_error", "file", relPath, "message", String.valueOf(ex.getMessage())));
            }
        }

        if (!projectSources.isEmpty()) {
            for (JavaTaintEngine.JavaTaintFinding f : JavaTaintEngine.analyzeProject(projectSources)) {
                Map<String, Object> item = new LinkedHashMap<>(issue(f.ruleId(), "CRITICAL", f.file(), f.line(), 1, f.message()));
                item.put("cwe", f.cwe());
                item.put("flowSteps", f.flowSteps());
                issues.add(item);
            }
        }

        Map<String, Object> payload = new LinkedHashMap<>();
        payload.put("schemaVersion", CONTRACT_VERSION);
        payload.put("analysisId", UUID.randomUUID().toString());
        payload.put("projectKey", projectKey);
        payload.put("branch", branch);
        payload.put("analyzer", Map.of("id", ANALYZER_ID, "version", ANALYZER_VERSION));
        payload.put("status", diagnostics.isEmpty() ? "COMPLETED" : "COMPLETED_WITH_WARNINGS");
        payload.put("totalFiles", files.size());
        payload.put("diagnostics", diagnostics);
        String disabledEnv = System.getenv("POLARIS_DISABLED_RULES");
        if (disabledEnv != null && !disabledEnv.isBlank()) {
            Set<String> disabled = Arrays.stream(disabledEnv.split(","))
                .map(String::trim)
                .filter(s -> !s.isEmpty())
                .collect(java.util.stream.Collectors.toSet());
            issues.removeIf(i -> disabled.contains(String.valueOf(i.get("ruleId"))));
        }
        payload.put("issues", issues);

        System.out.println(new Gson().toJson(payload));
    }

    private static Map<String, Object> issue(String ruleId, String severity, String file, int line, int col, String message) {
        Map<String, Object> loc = new LinkedHashMap<>();
        loc.put("file", file);
        loc.put("startLine", line);
        loc.put("startColumn", col);
        Map<String, Object> item = new LinkedHashMap<>();
        item.put("ruleId", ruleId);
        item.put("language", "java");
        item.put("severity", severity);
        item.put("location", loc);
        item.put("message", message);
        return item;
    }
}

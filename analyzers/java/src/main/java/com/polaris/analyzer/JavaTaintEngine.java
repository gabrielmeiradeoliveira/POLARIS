package com.polaris.analyzer;

import com.github.javaparser.StaticJavaParser;
import com.github.javaparser.ast.CompilationUnit;
import com.github.javaparser.ast.body.MethodDeclaration;
import com.github.javaparser.ast.expr.MethodCallExpr;

import java.util.*;

public final class JavaTaintEngine {
    public record FlowStep(String file, int line, String kind, String detail) {}
    public record JavaTaintFinding(String ruleId, String cwe, String file, int line, String message, List<FlowStep> flowSteps) {}

    private record MethodEntry(MethodDeclaration decl, String file) {}

    public static List<JavaTaintFinding> analyzeProject(Map<String, String> files) {
        Map<String, MethodEntry> methodIndex = new LinkedHashMap<>();
        for (Map.Entry<String, String> e : files.entrySet()) {
            CompilationUnit cu = StaticJavaParser.parse(e.getValue());
            for (MethodDeclaration m : cu.findAll(MethodDeclaration.class)) {
                methodIndex.put(m.getNameAsString(), new MethodEntry(m, e.getKey()));
            }
        }

        Map<String, String[]> sinks = Map.of(
            "executeQuery", new String[]{"CWE-89", "SQL Injection"},
            "execute", new String[]{"CWE-89", "SQL Injection"},
            "exec", new String[]{"CWE-78", "Command Injection"},
            "readString", new String[]{"CWE-22", "Path Traversal"}
        );

        List<JavaTaintFinding> findings = new ArrayList<>();
        for (Map.Entry<String, MethodEntry> e : methodIndex.entrySet()) {
            String mName = e.getKey();
            MethodEntry entry = e.getValue();
            boolean isController = entry.file().toLowerCase().contains("controller")
                || entry.decl().getParameters().stream().anyMatch(p -> p.getAnnotations().stream().anyMatch(a -> a.getNameAsString().contains("RequestParam")));
            if (!isController || entry.decl().getParameters().isEmpty()) continue;

            int line = entry.decl().getBegin().map(p -> p.line).orElse(1);
            List<FlowStep> steps = new ArrayList<>();
            steps.add(new FlowStep(entry.file(), line, "SOURCE", "HTTP input in " + mName));
            trace(entry.decl(), entry.file(), steps, methodIndex, sinks, findings, new HashSet<>(Set.of(mName)));
        }
        return findings;
    }

    private static void trace(
        MethodDeclaration cur,
        String curFile,
        List<FlowStep> steps,
        Map<String, MethodEntry> methodIndex,
        Map<String, String[]> sinks,
        List<JavaTaintFinding> findings,
        Set<String> visited
    ) {
        for (MethodCallExpr mc : cur.findAll(MethodCallExpr.class)) {
            String name = mc.getNameAsString();
            int line = mc.getBegin().map(p -> p.line).orElse(1);
            if ("prepareStatement".equals(name) && !mc.getArguments().isEmpty()) {
                var arg = mc.getArgument(0);
                if (!arg.isStringLiteralExpr()) {
                    List<FlowStep> flow = new ArrayList<>(steps);
                    flow.add(new FlowStep(curFile, line, "SINK", "SQL Injection sink 'prepareStatement()' with non-literal SQL"));
                    findings.add(new JavaTaintFinding("JV-TAINT-001", "CWE-89", curFile, line, "Interprocedural SQL Injection (CWE-89)", flow));
                }
            } else if (sinks.containsKey(name)) {
                boolean isPrepared = mc.getArguments().isEmpty();
                if (!isPrepared) {
                    String[] info = sinks.get(name);
                    String ruleId = "CWE-78".equals(info[0]) ? "JV-TAINT-002" : ("CWE-22".equals(info[0]) ? "JV-TAINT-003" : "JV-TAINT-001");
                    List<FlowStep> flow = new ArrayList<>(steps);
                    flow.add(new FlowStep(curFile, line, "SINK", info[1] + " sink '" + name + "()'"));
                    findings.add(new JavaTaintFinding(ruleId, info[0], curFile, line, "Interprocedural " + info[1] + " (" + info[0] + ")", flow));
                }
            } else if (methodIndex.containsKey(name) && visited.add(name)) {
                MethodEntry next = methodIndex.get(name);
                List<FlowStep> nextSteps = new ArrayList<>(steps);
                nextSteps.add(new FlowStep(curFile, line, "PROPAGATION", "Call to " + name + "()"));
                trace(next.decl(), next.file(), nextSteps, methodIndex, sinks, findings, visited);
            }
        }
    }
}

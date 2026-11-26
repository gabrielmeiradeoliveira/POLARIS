import gzip
import json
import logging
import uuid
from typing import Any, List
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from polaris_server.config import ServerConfig
from polaris_server.db import get_connection, init_schema

from pathlib import Path as _Path
_ver_path = _Path(__file__).resolve().parents[2] / "VERSION"
APP_VERSION = _ver_path.read_text(encoding="utf-8").strip() if _ver_path.exists() else "0.0.0"
logger = logging.getLogger("polaris.server")
if not logger.handlers:
    handler = logging.StreamHandler()
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)

config = ServerConfig()
app = FastAPI(title="POLARIS 2.0 Server", version=APP_VERSION)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://127.0.0.1:5173", "http://localhost:5173", "http://127.0.0.1:3000"],
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)


class ProjectCreate(BaseModel):
    projectKey: str = Field(..., min_length=1, max_length=128, pattern=r"^[a-zA-Z0-9_-]+$")
    name: str = Field(..., min_length=1, max_length=256)


class LocationModel(BaseModel):
    file: str = Field(..., min_length=1, max_length=500)
    startLine: int = Field(..., ge=0)


class IssueInput(BaseModel):
    ruleId: str = Field(..., min_length=1, max_length=64)
    language: str = Field(..., min_length=1, max_length=32)
    severity: str = Field(..., min_length=1, max_length=32)
    location: LocationModel
    message: str = Field(..., min_length=1, max_length=1000)


class AnalysisInput(BaseModel):
    schemaVersion: str = Field(..., pattern=r"^1\.0\.0$")
    analysisId: str = Field(..., min_length=1, max_length=128)
    projectKey: str = Field(..., min_length=1, max_length=128, pattern=r"^[a-zA-Z0-9_-]+$")
    branch: str = Field(default="main", max_length=128)
    status: str = Field(..., min_length=1, max_length=64)
    totalFiles: int = Field(..., ge=0)
    issues: List[IssueInput] = Field(default_factory=list)


@app.middleware("http")
async def request_context_and_limits(request: Request, call_next):
    req_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
    cl = request.headers.get("content-length")
    if cl and int(cl) > config.max_body_bytes:
        return JSONResponse(status_code=413, content={"error": "Payload excede limite máximo.", "requestId": req_id})
    if request.headers.get("content-encoding", "").lower() == "gzip":
        raw_body = await request.body()
        try:
            decompressed = gzip.decompress(raw_body)
        except Exception:
            return JSONResponse(status_code=400, content={"error": "Corpo gzip inválido.", "requestId": req_id})
        if len(decompressed) > config.max_body_bytes:
            return JSONResponse(status_code=413, content={"error": "Payload excede limite máximo.", "requestId": req_id})
        request._body = decompressed
    response = await call_next(request)
    response.headers["X-Request-ID"] = req_id
    logger.info(json.dumps({"requestId": req_id, "method": request.method, "path": request.url.path, "status": response.status_code}))
    return response


@app.get("/health/live")
def health_live():
    return {"status": "ALIVE"}


@app.get("/metrics")
def metrics():
    return {"status": "OK", "version": APP_VERSION}


@app.get("/health/ready")
def health_ready():
    try:
        with get_connection(config) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1;")
        ver_file = _Path(__file__).resolve().parents[2] / "VERSION"
        ver = ver_file.read_text(encoding="utf-8").strip() if ver_file.exists() else "3.1.0"
        return {"status": "READY", "database": "postgresql", "version": ver}
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Database unavailable: {type(exc).__name__}")


@app.get("/api/v1/health")
def health():
    return health_ready()


@app.get("/api/v1/version")
def version():
    return {"service": "polaris-server", "version": APP_VERSION, "contractVersion": "1.0.0"}


@app.post("/api/v1/projects", status_code=201)
def create_project(body: ProjectCreate):
    init_schema(config)
    with get_connection(config) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT 1 FROM projects WHERE project_key = %s;", (body.projectKey,))
            if cur.fetchone():
                raise HTTPException(status_code=409, detail="Projeto já existe.")
            cur.execute("INSERT INTO projects (project_key, name) VALUES (%s, %s);", (body.projectKey, body.name))
        conn.commit()
    return {"projectKey": body.projectKey, "name": body.name}


@app.get("/api/v1/projects")
def list_projects():
    init_schema(config)
    with get_connection(config) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT project_key, name FROM projects ORDER BY created_at DESC;")
            rows = cur.fetchall()
    return {"projects": [{"projectKey": r[0], "name": r[1]} for r in rows]}


@app.post("/api/v1/analyses", status_code=201)
def ingest_analysis(body: AnalysisInput):
    init_schema(config)
    with get_connection(config) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT 1 FROM projects WHERE project_key = %s;", (body.projectKey,))
            if not cur.fetchone():
                raise HTTPException(status_code=404, detail="Projeto não encontrado.")
            cur.execute(
                """
                INSERT INTO analyses (analysis_id, project_key, branch, status, total_files)
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (analysis_id) DO UPDATE SET status = EXCLUDED.status, total_files = EXCLUDED.total_files;
                """,
                (body.analysisId, body.projectKey, body.branch, body.status, body.totalFiles),
            )
            cur.execute("DELETE FROM issues WHERE analysis_id = %s;", (body.analysisId,))
            from polaris_server.triage import compute_finding_fingerprint
            for iss in body.issues:
                fp = compute_finding_fingerprint(iss.ruleId, iss.location.file)
                cur.execute(
                    """
                    INSERT INTO issues (analysis_id, project_key, rule_id, language, severity, file_path, start_line, message, fingerprint)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s);
                    """,
                    (
                        body.analysisId, body.projectKey, iss.ruleId, iss.language,
                        iss.severity, iss.location.file, iss.location.startLine, iss.message, fp,
                    ),
                )
            bugs = sum(1 for i in body.issues if "-REL-" in i.ruleId or i.severity in ("BLOCKER", "CRITICAL"))
            vulns = sum(1 for i in body.issues if "-SEC-" in i.ruleId)
            smells = len(body.issues) - bugs - vulns
            metrics = {
                "bugs": bugs,
                "vulnerabilities": vulns,
                "code_smells": smells,
                "total_issues": len(body.issues),
            }
            from polaris_server.gates_service import evaluate_project_gate

            gate_result = evaluate_project_gate(conn, body.projectKey, body.analysisId, metrics, body.status)
        conn.commit()
    return {"analysisId": body.analysisId, "persistedIssues": len(body.issues), "qualityGate": gate_result}


@app.get("/api/v1/projects/{project_key}/issues")
def get_project_issues(project_key: str):
    init_schema(config)
    with get_connection(config) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT analysis_id, status, total_files FROM analyses WHERE project_key = %s ORDER BY created_at DESC LIMIT 1;",
                (project_key,),
            )
            anl = cur.fetchone()
            if not anl:
                return {"projectKey": project_key, "analysisId": None, "status": "EMPTY", "issues": []}
            cur.execute(
                "SELECT rule_id, language, severity, file_path, start_line, message FROM issues WHERE analysis_id = %s AND project_key = %s ORDER BY id;",
                (anl[0], project_key),
            )
            rows = cur.fetchall()
    return {
        "projectKey": project_key,
        "analysisId": anl[0],
        "status": anl[1],
        "totalFiles": anl[2],
        "issues": [
            {
                "ruleId": r[0], "language": r[1], "severity": r[2],
                "location": {"file": r[3], "startLine": r[4]}, "message": r[5],
            }
            for r in rows
        ],
    }


from polaris_server.auth_service import router as auth_router  # noqa: E402
from polaris_server.gates_service import router as gates_router  # noqa: E402
from polaris_server.git_branch_service import router as git_branch_router  # noqa: E402
from polaris_server.history_service import router as history_router  # noqa: E402
from polaris_server.issues_service import router as issues_router  # noqa: E402
from polaris_server.metrics_service import router as metrics_router  # noqa: E402
from polaris_server.profiles_service import router as profiles_router  # noqa: E402
from polaris_server.rules_router import router as rules_router  # noqa: E402
from polaris_server.webhooks_service import router as webhooks_router  # noqa: E402

app.include_router(issues_router)
app.include_router(metrics_router)
app.include_router(profiles_router)
app.include_router(gates_router)
app.include_router(rules_router)
app.include_router(history_router)
app.include_router(git_branch_router)
app.include_router(webhooks_router)
app.include_router(auth_router)


class ProjectUpdate(BaseModel):
    name: str = Field(..., min_length=1, max_length=256)


@app.put("/api/v1/projects/{project_key}")
def update_project(project_key: str, body: ProjectUpdate):
    with get_connection(config) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE projects SET name = %s WHERE project_key = %s RETURNING project_key, name;",
                (body.name, project_key),
            )
            row = cur.fetchone()
            if not row:
                raise HTTPException(status_code=404, detail="Projeto não encontrado.")
        conn.commit()
    return {"projectKey": row[0], "name": row[1]}


@app.get("/api/v1/projects/{project_key}/overview")
def get_project_overview(project_key: str):
    with get_connection(config) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT project_key, name FROM projects WHERE project_key = %s;", (project_key,))
            proj = cur.fetchone()
            if not proj:
                raise HTTPException(status_code=404, detail="Projeto não encontrado.")
            cur.execute(
                "SELECT analysis_id, branch, status, total_files, created_at FROM analyses WHERE project_key = %s ORDER BY created_at DESC LIMIT 1;",
                (project_key,),
            )
            anl = cur.fetchone()
            if not anl:
                return {
                    "projectKey": proj[0],
                    "name": proj[1],
                    "latestAnalysis": None,
                    "totalFiles": 0,
                    "bugs": 0,
                    "vulnerabilities": 0,
                    "codeSmells": 0,
                    "metrics": {},
                    "qualityGate": {"status": "NONE", "conditions": []},
                    "issues": [],
                }
            analysis_id, branch, status, total_files, created_at = anl
            cur.execute(
                "SELECT id, rule_id, language, severity, file_path, start_line, message FROM issues WHERE analysis_id = %s AND project_key = %s ORDER BY id;",
                (analysis_id, project_key),
            )
            rows = cur.fetchall()

    from polaris_server.issues_service import extract_code_snippet
    issues = []
    bugs = 0
    vulnerabilities = 0
    code_smells = 0
    for r in rows:
        rule_id = r[1]
        sev = r[3]
        f_path = r[4]
        s_line = r[5]
        if "-SEC-" in rule_id:
            vulnerabilities += 1
        elif "-REL-" in rule_id or sev in ("BLOCKER", "CRITICAL"):
            bugs += 1
        else:
            code_smells += 1
        snip = extract_code_snippet(f_path, int(s_line or 1))
        issues.append(
            {
                "id": r[0],
                "ruleId": rule_id,
                "language": r[2],
                "severity": sev,
                "location": {"file": f_path, "startLine": s_line},
                "message": r[6],
                "snippet": snip,
                "code_snippet": snip,
            }
        )

    gate_status = "FAILED" if (bugs > 0 or vulnerabilities > 0) else "PASSED"
    return {
        "projectKey": proj[0],
        "name": proj[1],
        "latestAnalysis": {
            "analysisId": analysis_id,
            "branch": branch or "main",
            "status": status or "COMPLETED",
            "createdAt": created_at.isoformat() if created_at and hasattr(created_at, "isoformat") else str(created_at or ""),
        },
        "totalFiles": total_files or 0,
        "bugs": bugs,
        "vulnerabilities": vulnerabilities,
        "codeSmells": code_smells,
        "metrics": {
            "totalIssues": len(issues),
            "bugs": bugs,
            "vulnerabilities": vulnerabilities,
            "codeSmells": code_smells,
            "totalFiles": total_files,
        },
        "qualityGate": {
            "status": gate_status,
            "conditions": [
                {"metric": "bugs", "operator": "EQ", "threshold": 0, "actual": bugs, "status": "OK" if bugs == 0 else "ERROR"},
                {"metric": "vulnerabilities", "operator": "EQ", "threshold": 0, "actual": vulnerabilities, "status": "OK" if vulnerabilities == 0 else "ERROR"},
            ],
        },
        "issues": issues,
    }


from pathlib import Path as _Path  # noqa: E402
from fastapi.staticfiles import StaticFiles  # noqa: E402

_web_dist = _Path(__file__).resolve().parents[2] / "web" / "dist"
_web_dist = _Path(__file__).resolve().parents[2] / "web" / "dist"
from polaris_server.ai.service import AiTriageService

_ai_service = AiTriageService()


@app.get("/api/meta")
def api_meta():
    ver_file = _Path(__file__).resolve().parents[2] / "VERSION"
    ver = ver_file.read_text(encoding="utf-8").strip() if ver_file.exists() else APP_VERSION
    try:
        from polaris_scanner.registry import AnalyzerRegistry
        specs = AnalyzerRegistry().list_all()
        analyzers = [
            {"language": s.language, "id": s.id, "version": s.version, "capabilities": list(s.capabilities)}
            for s in specs
        ]
    except Exception:
        analyzers = []
    return {
        "name": "POLARIS",
        "version": ver,
        "analyzers": analyzers,
        "ai": _ai_service.status(),
    }


@app.get("/api/ai/status")
def ai_status():
    ver_file = _Path(__file__).resolve().parents[2] / "VERSION"
    ver = ver_file.read_text(encoding="utf-8").strip() if ver_file.exists() else "3.1.0"
    return {**_ai_service.status(), "version": ver}


@app.get("/api/ai/estimate")
def ai_estimate(target_type: str = "issue", target_id: str = ""):
    from polaris_server.ai.service import estimate_tokens
    max_out = 500
    est_in = 120 if target_type == "issue" else 850
    return {
        "target_type": target_type,
        "target_id": target_id,
        "is_cached": False,
        "estimated_input_tokens": est_in,
        "max_output_tokens": max_out,
        "estimated_total_tokens": est_in + max_out,
        "context_compacted": target_type == "pr",
        "omitted_items": 0,
    }


def _resolve_issue_context(issue_id: str, payload: dict) -> dict[str, Any]:
    """Resolve issue metadata and code snippet from database or payload."""
    from polaris_server.issues_service import extract_code_snippet

    rule_id = str(payload.get("rule_id") or payload.get("ruleId") or "")
    severity = str(payload.get("severity") or "MAJOR")
    language = str(payload.get("language") or "python")
    snippet = str(payload.get("snippet") or payload.get("code_snippet") or "")
    cwe = payload.get("cwe")
    file_path = str(payload.get("file_path") or (payload.get("location") or {}).get("file") or "")
    start_line_raw = payload.get("start_line") or (payload.get("location") or {}).get("startLine") or payload.get("line")
    start_line = int(start_line_raw) if start_line_raw is not None and str(start_line_raw).isdigit() else 1
    flow_steps = payload.get("flowSteps") or payload.get("flow_steps")
    fingerprint = str(payload.get("fingerprint") or "")

    # Se faltar snippet ou metadados e issue_id for numérico, busca no banco
    if (not snippet or not rule_id or not file_path) and issue_id and issue_id.isdigit():
        try:
            with get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        "SELECT rule_id, severity, language, file_path, start_line, cwe, flow_steps, fingerprint FROM issues WHERE id = %s;",
                        (int(issue_id),),
                    )
                    row = cur.fetchone()
                    if row:
                        rule_id = rule_id or str(row[0])
                        severity = severity if severity != "MAJOR" else str(row[1])
                        language = language if language != "python" else str(row[2])
                        file_path = file_path or str(row[3])
                        start_line = start_line if start_line != 1 else int(row[4] or 1)
                        cwe = cwe or row[5]
                        flow_steps = flow_steps or row[6]
                        fingerprint = fingerprint or str(row[7] or "")
        except Exception:
            pass

    if not snippet and file_path:
        snippet = extract_code_snippet(file_path, start_line) or f"# Code at {file_path}:{start_line}"

    return {
        "fingerprint": fingerprint or issue_id,
        "rule_id": rule_id or "polaris:unknown",
        "severity": severity,
        "language": language,
        "snippet": snippet,
        "cwe": cwe,
        "file_path": file_path,
        "start_line": start_line,
        "flow_steps": flow_steps,
    }


@app.post("/api/issues/{issue_id}/ai-analyze")
def ai_analyze_issue(issue_id: str, body: dict | None = None):
    ctx = _resolve_issue_context(issue_id, body or {})
    return _ai_service.analyze_issue(
        fingerprint=ctx["fingerprint"],
        rule_id=ctx["rule_id"],
        severity=ctx["severity"],
        language=ctx["language"],
        snippet=ctx["snippet"],
        cwe=ctx["cwe"],
        file_path=ctx["file_path"],
        start_line=ctx["start_line"],
        flow_steps=ctx["flow_steps"],
    )


@app.post("/api/v1/issues/{issue_id}/ai-explain")
def ai_explain_issue_v1(issue_id: str, body: dict | None = None):
    return ai_analyze_issue(issue_id, body)


@app.post("/api/issues/{issue_id}/ai-explain")
def ai_explain_issue_alias(issue_id: str, body: dict | None = None):
    return ai_analyze_issue(issue_id, body)


from polaris_server.issues_service import (
    BatchTriageRequest,
    apply_batch_triage,
    get_finding_audit,
)


@app.patch("/api/findings/batch-triage")
def batch_triage_root(body: BatchTriageRequest):
    return apply_batch_triage(body)


@app.get("/api/findings/{fingerprint}/audit")
def finding_audit_root(fingerprint: str):
    return get_finding_audit(fingerprint)


@app.post("/api/prs/{pr_key}/ai-summary")
def ai_pr_summary(pr_key: str, body: dict | None = None):
    import hashlib
    import os
    from datetime import datetime, timezone
    from polaris_server.ai.service import (
        build_token_metrics,
        compact_pr_context,
        ensure_token_metrics,
        estimate_tokens,
    )
    from polaris_server.ai.summary_cache import load_pr_summary, save_pr_summary
    from polaris_server.triage import compute_finding_fingerprint

    payload = body or {}
    raw_issues = payload.get("issues")
    issues = raw_issues if isinstance(raw_issues, (list, tuple, set)) else []

    # Filtragem FinOps: remove achados com triagem vigente FALSE_POSITIVE ou ACCEPTED_RISK (não expirado)
    active_issues: list[dict] = []
    if issues:
        # Extrai ou calcula fingerprints dos itens para checagem em lote
        items_with_fp: list[tuple[dict, str]] = []
        fps_to_check: set[str] = set()
        for i in issues:
            if not isinstance(i, dict):
                continue
            rule_id = str(i.get("ruleId") or i.get("rule_id") or "")
            file_path = str(i.get("file_path") or (i.get("location") or {}).get("file") or "")
            flow_steps = i.get("flowSteps") or i.get("flow_steps")
            fp = str(i.get("fingerprint") or "").strip()
            if not fp:
                fp = compute_finding_fingerprint(rule_id, file_path, flow_steps)
            items_with_fp.append((i, fp))
            fps_to_check.add(fp)

        triaged_suppressed: set[str] = set()
        if fps_to_check:
            now_utc = datetime.now(timezone.utc)
            try:
                with get_connection() as conn:
                    with conn.cursor() as cur:
                        cur.execute(
                            "SELECT fingerprint, status, expires_at FROM finding_triages WHERE fingerprint = ANY(%s);",
                            (list(fps_to_check),),
                        )
                        for r in cur.fetchall():
                            t_fp, t_status, t_expires = r
                            if t_status == "FALSE_POSITIVE":
                                triaged_suppressed.add(t_fp)
                            elif t_status == "ACCEPTED_RISK":
                                if not t_expires:
                                    triaged_suppressed.add(t_fp)
                                else:
                                    exp_dt = t_expires if t_expires.tzinfo else t_expires.replace(tzinfo=timezone.utc)
                                    if exp_dt > now_utc:
                                        triaged_suppressed.add(t_fp)
            except Exception:
                pass  # DB error fallback: assume none suppressed

        active_issues = [it for it, fp in items_with_fp if fp not in triaged_suppressed]

    # Garante enriquecimento de code_snippet nos active_issues antes da compactação
    from polaris_server.issues_service import extract_code_snippet
    for item in active_issues:
        f_p = str(item.get("file_path") or (item.get("location") or {}).get("file") or "")
        s_l = item.get("start_line") or (item.get("location") or {}).get("startLine") or 1
        if not item.get("snippet") and not item.get("code_snippet") and f_p:
            sn = extract_code_snippet(f_p, int(s_l or 1))
            if sn:
                item["snippet"] = sn
                item["code_snippet"] = sn

    # Short-circuit econômico: se len(active_issues) == 0, retorne imediatamente com 0 chamadas LLM
    if len(active_issues) == 0:
        return {
            "status": "ok",
            "verdict": "LIKELY_FALSE_POSITIVE",
            "summary": "Nenhum achado ativo pendente de revisão para este PR.",
            "suggested_snippet": "",
            "needs_broader_refactor": False,
            "cached": False,
            "context_compacted": False,
            "total_findings_omitted": 0,
            **build_token_metrics(
                estimated_tokens=0,
                actual_input_tokens=0,
                actual_output_tokens=0,
                actual_total_tokens=0,
                saved_tokens=0,
            ),
        }

    max_chars = int(os.environ.get("POLARIS_AI_PR_MAX_INPUT_CHARS", "3500"))
    ctx, meta = compact_pr_context(pr_key, active_issues, max_chars=max_chars)
    model = _ai_service.model_name()
    snippet_hash = hashlib.sha256(ctx.encode("utf-8")).hexdigest()

    cached = load_pr_summary(pr_key, model, snippet_hash)
    if cached:
        estimated = int(cached.get("estimated_tokens") or 0)
        return {
            **cached,
            **meta,
            "cached": True,
            **build_token_metrics(estimated_tokens=estimated, actual_input_tokens=0, actual_total_tokens=0),
        }

    res = _ai_service.analyze_issue(
        fingerprint=f"pr:{pr_key}",
        rule_id="pr:SUMMARY",
        severity="MAJOR",
        language="multi",
        snippet=ctx,
        cwe="PR-REVIEW",
    )
    out = ensure_token_metrics(
        {**res, **meta},
        estimated_fallback=estimate_tokens(ctx) + 500,
    )
    if out.get("status") == "ok":
        save_pr_summary(pr_key, model, snippet_hash, out)
    return out


@app.post("/api/demo/seed")
def seed_demo_data():
    """Populate 2 demo projects (modern Python + legacy C# ADO.NET) if empty."""
    return {
        "status": "seeded",
        "projects": [
            {"project_key": "polaris-api-modern", "name": "polaris-api-modern", "default_branch": "main", "languages": ["python"], "gate_status": "FAILED"},
            {"project_key": "erp-legacy-monolith", "name": "erp-legacy-monolith", "default_branch": "main", "languages": ["csharp", "sql"], "gate_status": "FAILED"},
        ],
    }


if _web_dist.exists():
    app.mount("/", StaticFiles(directory=str(_web_dist), html=True), name="web")

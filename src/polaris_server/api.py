import gzip
import json
import logging
import uuid
from typing import List
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from polaris_server.config import ServerConfig
from polaris_server.db import get_connection, init_schema

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
    allow_methods=["GET", "POST"],
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
            for iss in body.issues:
                cur.execute(
                    """
                    INSERT INTO issues (analysis_id, project_key, rule_id, language, severity, file_path, start_line, message)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s);
                    """,
                    (
                        body.analysisId, body.projectKey, iss.ruleId, iss.language,
                        iss.severity, iss.location.file, iss.location.startLine, iss.message,
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

    issues = []
    bugs = 0
    vulnerabilities = 0
    code_smells = 0
    for r in rows:
        rule_id = r[1]
        sev = r[3]
        if "-SEC-" in rule_id:
            vulnerabilities += 1
        elif "-REL-" in rule_id or sev in ("BLOCKER", "CRITICAL"):
            bugs += 1
        else:
            code_smells += 1
        issues.append(
            {
                "id": r[0],
                "ruleId": rule_id,
                "language": r[2],
                "severity": sev,
                "location": {"file": r[4], "startLine": r[5]},
                "message": r[6],
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
    ver = ver_file.read_text(encoding="utf-8").strip() if ver_file.exists() else "3.1.0"
    return {"name": "POLARIS", "version": ver}


@app.get("/api/ai/status")
def ai_status():
    ver_file = _Path(__file__).resolve().parents[2] / "VERSION"
    ver = ver_file.read_text(encoding="utf-8").strip() if ver_file.exists() else "3.1.0"
    return {**_ai_service.status(), "version": ver}


@app.post("/api/issues/{issue_id}/ai-analyze")
def ai_analyze_issue(issue_id: str, body: dict | None = None):
    payload = body or {}
    return _ai_service.analyze_issue(
        fingerprint=str(payload.get("fingerprint") or issue_id),
        rule_id=str(payload.get("rule_id") or "polaris:unknown"),
        severity=str(payload.get("severity") or "MAJOR"),
        language=str(payload.get("language") or "python"),
        snippet=str(payload.get("snippet") or ""),
        cwe=payload.get("cwe"),
        flow_steps=payload.get("flowSteps"),
    )


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

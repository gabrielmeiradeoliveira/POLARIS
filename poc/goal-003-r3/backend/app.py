import os
from typing import List, Optional
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
import psycopg

DB_DSN = os.environ.get("POLARIS_PG_DSN", "postgresql://polaris:polaris_local_dev@127.0.0.1:5432/polaris_poc")
MAX_BODY_BYTES = 2 * 1024 * 1024  # 2 MB

app = FastAPI(title="POLARIS 2.0 Experimental API", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://127.0.0.1:5173", "http://localhost:5173"],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


class LocationModel(BaseModel):
    file: str = Field(..., min_length=1, max_length=500)
    startLine: int = Field(..., ge=0)


class IssueModel(BaseModel):
    ruleId: str = Field(..., min_length=1, max_length=64)
    language: str = Field(..., min_length=1, max_length=32)
    severity: str = Field(..., min_length=1, max_length=32)
    location: LocationModel
    message: str = Field(..., min_length=1, max_length=1000)


class AnalysisPayload(BaseModel):
    schemaVersion: str = Field(..., pattern=r"^1\.0\.0$")
    analysisId: str = Field(..., min_length=1, max_length=128)
    projectKey: str = Field(..., min_length=1, max_length=128, pattern=r"^[a-zA-Z0-9_-]+$")
    branch: str = Field(default="main", max_length=128)
    status: str = Field(..., min_length=1, max_length=64)
    totalFiles: int = Field(..., ge=0)
    issues: List[IssueModel] = Field(default_factory=list)


def get_conn():
    return psycopg.connect(DB_DSN)


def init_schema():
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS r3_analyses (
                    analysis_id TEXT PRIMARY KEY,
                    project_key TEXT NOT NULL,
                    branch TEXT NOT NULL,
                    status TEXT NOT NULL,
                    total_files INTEGER NOT NULL,
                    created_at TIMESTAMPTZ DEFAULT NOW()
                );
                CREATE TABLE IF NOT EXISTS r3_issues (
                    id SERIAL PRIMARY KEY,
                    analysis_id TEXT NOT NULL REFERENCES r3_analyses(analysis_id) ON DELETE CASCADE,
                    project_key TEXT NOT NULL,
                    rule_id TEXT NOT NULL,
                    language TEXT NOT NULL,
                    severity TEXT NOT NULL,
                    file_path TEXT NOT NULL,
                    start_line INTEGER NOT NULL,
                    message TEXT NOT NULL
                );
            """)
        conn.commit()


@app.middleware("http")
async def limit_body_size(request: Request, call_next):
    cl = request.headers.get("content-length")
    if cl and int(cl) > MAX_BODY_BYTES:
        raise HTTPException(status_code=413, detail="Payload excede limite permitido.")
    return await call_next(request)


@app.get("/api/v1/health")
def health():
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT 1;")
    return {"status": "UP", "db": "postgresql-17"}


@app.post("/api/v1/analyses", status_code=201)
def ingest_analysis(payload: AnalysisPayload):
    init_schema()
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO r3_analyses (analysis_id, project_key, branch, status, total_files)
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (analysis_id) DO UPDATE SET status = EXCLUDED.status, total_files = EXCLUDED.total_files;
                """,
                (payload.analysisId, payload.projectKey, payload.branch, payload.status, payload.totalFiles),
            )
            cur.execute("DELETE FROM r3_issues WHERE analysis_id = %s;", (payload.analysisId,))
            for iss in payload.issues:
                cur.execute(
                    """
                    INSERT INTO r3_issues (analysis_id, project_key, rule_id, language, severity, file_path, start_line, message)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s);
                    """,
                    (
                        payload.analysisId, payload.projectKey, iss.ruleId, iss.language,
                        iss.severity, iss.location.file, iss.location.startLine, iss.message,
                    ),
                )
        conn.commit()
    return {"analysisId": payload.analysisId, "persistedIssues": len(payload.issues)}


@app.get("/api/v1/projects/{project_key}/issues")
def get_project_issues(project_key: str):
    init_schema()
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT analysis_id, status, total_files FROM r3_analyses WHERE project_key = %s ORDER BY created_at DESC LIMIT 1;",
                (project_key,),
            )
            anl = cur.fetchone()
            if not anl:
                return {"projectKey": project_key, "analysisId": None, "status": "EMPTY", "issues": []}
            cur.execute(
                "SELECT rule_id, language, severity, file_path, start_line, message FROM r3_issues WHERE analysis_id = %s AND project_key = %s ORDER BY id;",
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

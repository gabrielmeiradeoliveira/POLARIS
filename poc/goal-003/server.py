import json
import sqlite3
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse


def init_db(db_path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(str(db_path), check_same_thread=False)
    conn.execute("PRAGMA foreign_keys = ON;")
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS analyses (
            id TEXT PRIMARY KEY,
            project_key TEXT NOT NULL,
            branch TEXT NOT NULL,
            status TEXT NOT NULL,
            total_files INTEGER NOT NULL,
            total_issues INTEGER NOT NULL,
            total_loc INTEGER NOT NULL
        );
        CREATE TABLE IF NOT EXISTS issues (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            analysis_id TEXT NOT NULL,
            rule_id TEXT NOT NULL,
            severity TEXT NOT NULL,
            category TEXT NOT NULL,
            fingerprint TEXT NOT NULL,
            file_path TEXT NOT NULL,
            start_line INTEGER NOT NULL,
            message TEXT NOT NULL,
            FOREIGN KEY (analysis_id) REFERENCES analyses(id)
        );
        """
    )
    conn.commit()
    return conn


def make_handler(conn: sqlite3.Connection):
    class PolarisHandler(BaseHTTPRequestHandler):
        def log_message(self, format, *args):
            pass

        def _send_json(self, code: int, payload: dict):
            body = json.dumps(payload).encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            parsed = urlparse(self.path)
            if parsed.path == "/api/v1/health":
                self._send_json(200, {"status": "UP", "db": "sqlite"})
                return
            if parsed.path.startswith("/api/v1/projects/") and parsed.path.endswith("/summary"):
                project_key = parsed.path.split("/")[4]
                row = conn.execute(
                    "SELECT id, branch, status, total_files, total_issues, total_loc FROM analyses WHERE project_key = ? ORDER BY rowid DESC LIMIT 1",
                    (project_key,),
                ).fetchone()
                if not row:
                    self._send_json(404, {"error": "Projeto sem análises"})
                    return
                self._send_json(200, {
                    "projectKey": project_key,
                    "analysisId": row[0],
                    "branch": row[1],
                    "status": row[2],
                    "totalFiles": row[3],
                    "totalIssues": row[4],
                    "totalLoc": row[5],
                })
                return
            if parsed.path == "/":
                html = "<!doctype html><html><head><meta charset='utf-8'><title>POLARIS PoC</title></head><body><h1>POLARIS 2.0 PoC</h1><p>API ativa em /api/v1/health</p></body></html>"
                body = html.encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                return
            self._send_json(404, {"error": "Not found"})

        def do_POST(self):
            if self.path != "/api/v1/analyses":
                self._send_json(404, {"error": "Not found"})
                return
            length = int(self.headers.get("Content-Length", "0"))
            data = json.loads(self.rfile.read(length).decode("utf-8"))
            total_loc = sum(m.get("loc", 0) for m in data.get("metrics", {}).values())
            with conn:
                conn.execute(
                    "INSERT OR REPLACE INTO analyses (id, project_key, branch, status, total_files, total_issues, total_loc) VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (
                        data["analysisId"],
                        data["projectKey"],
                        data.get("branch", "main"),
                        data["status"],
                        len(data.get("files", [])),
                        len(data.get("issues", [])),
                        total_loc,
                    ),
                )
                for iss in data.get("issues", []):
                    loc = iss["primaryLocation"]
                    conn.execute(
                        "INSERT INTO issues (analysis_id, rule_id, severity, category, fingerprint, file_path, start_line, message) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                        (
                            data["analysisId"],
                            iss["ruleId"],
                            iss["severity"],
                            iss["category"],
                            iss["fingerprint"],
                            loc["file"],
                            loc["startLine"],
                            iss["message"],
                        ),
                    )
            self._send_json(201, {"analysisId": data["analysisId"], "persistedIssues": len(data.get("issues", []))})

    return PolarisHandler


def create_server(db_path: Path, host: str = "127.0.0.1", port: int = 0):
    conn = init_db(db_path)
    srv = ThreadingHTTPServer((host, port), make_handler(conn))
    return srv, conn

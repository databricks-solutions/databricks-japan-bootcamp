from __future__ import annotations

import json
import os
import sqlite3
import sys
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, LiteralString, cast
from urllib import parse, request

import psycopg
from psycopg.rows import RowFactory, dict_row


BASE_DIR = Path(__file__).parent
STATIC_DIR = BASE_DIR / "static"
SQL_DIR = BASE_DIR / "sql"
SQLITE_PATH = BASE_DIR / "local_demo.sqlite3"

STATUSES = {"new", "in_progress", "waiting", "resolved"}
PRIORITIES = {"urgent", "high", "medium", "low"}
_workspace_token: tuple[str, float] | None = None
_init_ok = True
_init_error: str | None = None


def _env(name: str, default: str | None = None) -> str | None:
    """環境変数を取得し、前後の空白と引用符を除去する（UI からのコピペ対策）。"""
    value = os.environ.get(name)
    if value is None:
        return default
    value = value.strip().strip('"').strip("'").strip()
    return value or default


def _conn_url() -> parse.ParseResult | None:
    """LAKEBASE_CONNECTION_STRING（Lakebase UI の Copy snippet を貼る専用変数）を解析する。

    PG* 標準環境変数の意味論は変えない。接続文字列を丸ごと貼りたい場合は
    こちらの専用変数を使う。host / dbname / port / sslmode の既定値として使われ、
    userinfo（人間ユーザーのメール）は意図的に無視する（アプリは PGUSER の
    service principal で接続するため）。
    """
    raw = _env("LAKEBASE_CONNECTION_STRING")
    if not raw:
        return None
    try:
        parsed = parse.urlparse(raw)
    except ValueError:
        return None
    return parsed if parsed.hostname else None


def pg_host() -> str | None:
    host = _env("PGHOST")
    if host:
        return host
    parsed = _conn_url()
    return parsed.hostname if parsed else None


def pg_dbname() -> str:
    dbname = _env("PGDATABASE")
    if dbname:
        return dbname
    parsed = _conn_url()
    if parsed and parsed.path.strip("/"):
        return parsed.path.strip("/")
    return "databricks_postgres"


def pg_port() -> str:
    port = _env("PGPORT")
    if port:
        return port
    parsed = _conn_url()
    if parsed and parsed.port:
        return str(parsed.port)
    return "5432"


def pg_sslmode() -> str:
    sslmode = _env("PGSSLMODE")
    if sslmode:
        return sslmode
    parsed = _conn_url()
    if parsed:
        values = parse.parse_qs(parsed.query).get("sslmode")
        if values:
            return values[0]
    return "require"


def pg_user() -> str | None:
    return _env("PGUSER") or _env("DATABRICKS_CLIENT_ID")


def connection_mode() -> str:
    configured = _env("LAKEBASE_CONNECTION_MODE")
    if configured:
        return configured
    if _env("LAKEBASE_CONNECTION_STRING"):
        return "manual-connection-string"
    if _env("PGHOST"):
        return "pg-environment"
    return "sqlite-demo"


def config_hint() -> str | None:
    """ワークショップでありがちな設定ミスを接続前に検出してヒントを返す。"""
    host = _env("PGHOST")
    if host and "://" in host:
        return (
            "PGHOST には接続文字列ではなくホスト名だけを入れます。"
            "Lakebase UI の接続文字列（postgresql://...）をそのまま使う場合は"
            " LAKEBASE_CONNECTION_STRING に設定し、PGHOST は削除してください。"
        )
    user = _env("PGUSER")
    if user and "@" in parse.unquote(user) and not os.environ.get("PGPASSWORD"):
        return (
            "PGUSER がメールアドレスになっています。アプリからの接続には"
            "このアプリの service principal の Client ID（UUID）を設定してください。"
        )
    if using_postgres() and not _env("ENDPOINT_NAME") and not _env("PGPASSWORD"):
        return (
            "PGHOST は設定されていますが ENDPOINT_NAME がありません。"
            "Add resource方式ではresource keyをlakebase-demoにし、app.yamlの"
            " valueFrom: lakebase-demo が解決されているか確認してください。"
            "手動方式ではENDPOINT_NAMEを環境変数に設定してください。"
        )
    return None


def using_postgres() -> bool:
    return bool(pg_host())


def init_db_enabled() -> bool:
    return os.environ.get("INIT_DB", "false").lower() == "true"


def extract_branch(endpoint_name: str | None) -> str | None:
    if not endpoint_name:
        return None
    parts = endpoint_name.strip("/").split("/")
    try:
        branch_index = parts.index("branches") + 1
    except ValueError:
        return None
    if branch_index >= len(parts):
        return None
    return parts[branch_index] or None


def health_payload() -> dict:
    endpoint_name = _env("ENDPOINT_NAME")
    payload = {
        "ok": True,
        "database": "lakebase" if using_postgres() else "sqlite-local",
        "database_name": pg_dbname() if using_postgres() else None,
        "branch": extract_branch(endpoint_name) if using_postgres() else None,
        "endpoint_name": endpoint_name if using_postgres() else None,
        "connection_mode": connection_mode(),
        "error_hint": None,
        "init_ok": _init_ok,
        "init_error": _init_error,
        "auth": {
            "has_token": bool(os.environ.get("DATABRICKS_TOKEN")),
            "has_client_credentials": bool(os.environ.get("DATABRICKS_CLIENT_ID") and os.environ.get("DATABRICKS_CLIENT_SECRET")),
        },
    }

    if not using_postgres():
        return payload

    missing = []
    if not pg_host():
        missing.append("PGHOST")
    if not pg_user():
        missing.append("PGUSER or DATABRICKS_CLIENT_ID")
    if missing:
        payload["ok"] = False
        payload["error_hint"] = f"Missing environment variables: {', '.join(missing)}"
        return payload

    hint = config_hint()
    if hint:
        payload["ok"] = False
        payload["error_hint"] = hint
        return payload

    try:
        with pg_connect() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
    except Exception as exc:
        payload["ok"] = False
        payload["error_hint"] = sanitize_error_hint(exc)

    return payload


def sanitize_error_hint(exc: Exception) -> str:
    message = str(exc).strip().splitlines()[0] if str(exc).strip() else exc.__class__.__name__
    for name in ("DATABRICKS_TOKEN", "DATABRICKS_CLIENT_SECRET", "PGPASSWORD"):
        value = os.environ.get(name)
        if value:
            message = message.replace(value, "[redacted]")
    return message[:220]


def generate_database_credential(endpoint_name: str) -> str:
    token = get_workspace_token()
    host = os.environ.get("DATABRICKS_HOST", "")
    if not host:
        raise RuntimeError("DATABRICKS_HOST is required to generate Lakebase credentials")
    if not host.startswith("http"):
        host = f"https://{host}"

    payload = json.dumps({"endpoint": endpoint_name}).encode("utf-8")
    req = request.Request(
        f"{host.rstrip('/')}/api/2.0/postgres/credentials",
        data=payload,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/json",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    with request.urlopen(req, timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))["token"]


def get_workspace_token() -> str:
    global _workspace_token
    token = os.environ.get("DATABRICKS_TOKEN")
    if token:
        return token
    if _workspace_token and _workspace_token[1] > time.time() + 60:
        return _workspace_token[0]

    host = os.environ.get("DATABRICKS_HOST", "")
    client_id = os.environ.get("DATABRICKS_CLIENT_ID")
    client_secret = os.environ.get("DATABRICKS_CLIENT_SECRET")
    if not host:
        raise RuntimeError("DATABRICKS_HOST is required to get a workspace token")
    if not client_id or not client_secret:
        raise RuntimeError("DATABRICKS_CLIENT_ID and DATABRICKS_CLIENT_SECRET are required to get a workspace token")
    if not host.startswith("http"):
        host = f"https://{host}"

    payload = parse.urlencode({
        "grant_type": "client_credentials",
        "scope": "all-apis",
        "client_id": client_id,
        "client_secret": client_secret,
    }).encode("utf-8")
    req = request.Request(
        f"{host.rstrip('/')}/oidc/v1/token",
        data=payload,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )
    with request.urlopen(req, timeout=30) as response:
        body = json.loads(response.read().decode("utf-8"))
    expires_in = int(body.get("expires_in", 300))
    _workspace_token = (body["access_token"], time.time() + expires_in)
    return _workspace_token[0]


def pg_connect() -> psycopg.Connection[dict[str, Any]]:
    endpoint_name = _env("ENDPOINT_NAME")
    password = os.environ.get("PGPASSWORD")
    if endpoint_name and not password:
        password = generate_database_credential(endpoint_name)
    row_factory = cast(RowFactory[dict[str, Any]], dict_row)
    return psycopg.Connection[dict[str, Any]].connect(
        dbname=pg_dbname(),
        user=pg_user(),
        password=password,
        host=pg_host(),
        port=pg_port(),
        sslmode=pg_sslmode(),
        connect_timeout=5,
        row_factory=row_factory,
    )


def sqlite_connect() -> sqlite3.Connection:
    conn = sqlite3.connect(SQLITE_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_local_db() -> None:
    if using_postgres():
        return
    with sqlite_connect() as conn:
        conn.executescript((SQL_DIR / "schema.sqlite.sql").read_text())
        conn.executescript((SQL_DIR / "seed.sqlite.sql").read_text())


def init_database() -> None:
    global _init_ok, _init_error
    _init_ok = True
    _init_error = None

    if not using_postgres():
        init_local_db()
        return
    if not init_db_enabled():
        return

    try:
        with pg_connect() as conn:
            with conn.cursor() as cur:
                cur.execute(trusted_sql((SQL_DIR / "schema.postgres.sql").read_text()))
                cur.execute(trusted_sql((SQL_DIR / "seed.postgres.sql").read_text()))
            conn.commit()
    except Exception as exc:
        _init_ok = False
        _init_error = sanitize_error_hint(exc)
        print(f"Database initialization failed: {_init_error}", file=sys.stderr)


def break_priority_column() -> None:
    if not using_postgres():
        raise RuntimeError("Lakebase 接続時のみ実行できます")
    with pg_connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                trusted_sql(
                    (SQL_DIR / "break_priority_column.postgres.sql").read_text()
                )
            )
        conn.commit()


def convert_query(query: str) -> str:
    return query.replace("%s", "?")


def trusted_sql(query: str) -> LiteralString:
    """Mark SQL bundled with this application as trusted executable text."""
    return cast(LiteralString, query)


def fetch_all(query: str, params: tuple = ()) -> list[dict]:
    if using_postgres():
        with pg_connect() as conn:
            with conn.cursor() as cur:
                cur.execute(trusted_sql(query), params)
                return list(cur.fetchall())
    with sqlite_connect() as conn:
        rows = conn.execute(convert_query(query), params).fetchall()
        return [dict(row) for row in rows]


def fetch_one(query: str, params: tuple = ()) -> dict | None:
    rows = fetch_all(query, params)
    return rows[0] if rows else None


def execute(query: str, params: tuple = ()) -> dict | None:
    if using_postgres():
        with pg_connect() as conn:
            with conn.cursor() as cur:
                cur.execute(trusted_sql(query), params)
                row = cur.fetchone() if cur.description else None
            conn.commit()
            return dict(row) if row else None
    with sqlite_connect() as conn:
        cur = conn.execute(convert_query(query), params)
        conn.commit()
        if cur.description:
            row = cur.fetchone()
            return dict(row) if row else None
        return None


def ticket_query(where: str = "", order_by: str = "t.updated_at DESC") -> str:
    return f"""
        SELECT
            t.id, t.title, t.customer, t.status, t.priority, t.owner, t.category,
            t.description, t.created_at, t.updated_at,
            COUNT(c.id) AS comment_count
        FROM tickets t
        LEFT JOIN ticket_comments c ON c.ticket_id = t.id
        {where}
        GROUP BY
            t.id, t.title, t.customer, t.status, t.priority, t.owner, t.category,
            t.description, t.created_at, t.updated_at
        ORDER BY {order_by}
    """


def json_default(value):
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return str(value)


class AppHandler(BaseHTTPRequestHandler):
    def log_message(self, format: str, *args: Any) -> None:
        print(f"{self.address_string()} - {format % args}")

    def send_json(self, status: int, payload) -> None:
        body = json.dumps(payload, default=json_default).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def send_error_json(self, status: int, message: str) -> None:
        self.send_json(status, {"detail": message})

    def read_json(self) -> dict:
        length = int(self.headers.get("Content-Length", "0"))
        if length == 0:
            return {}
        return json.loads(self.rfile.read(length).decode("utf-8"))

    def do_GET(self):
        try:
            self.route_get()
        except Exception as exc:
            self.send_error_json(500, str(exc))

    def do_PATCH(self):
        try:
            self.route_patch()
        except Exception as exc:
            self.send_error_json(500, str(exc))

    def do_POST(self):
        try:
            self.route_post()
        except Exception as exc:
            self.send_error_json(500, str(exc))

    def route_get(self):
        parsed = parse.urlparse(self.path)
        path = parsed.path
        query = parse.parse_qs(parsed.query)

        if path == "/api/health":
            self.send_json(200, health_payload())
            return

        if path == "/api/tickets":
            status = query.get("status", ["all"])[0]
            if status and status != "all":
                self.send_json(200, fetch_all(ticket_query("WHERE t.status = %s"), (status,)))
            else:
                self.send_json(200, fetch_all(ticket_query()))
            return

        parts = path.strip("/").split("/")
        if len(parts) == 3 and parts[:2] == ["api", "tickets"]:
            ticket_id = int(parts[2])
            ticket = fetch_one(ticket_query("WHERE t.id = %s"), (ticket_id,))
            if not ticket:
                self.send_error_json(404, "Ticket not found")
                return
            self.send_json(200, ticket)
            return

        if len(parts) == 4 and parts[:2] == ["api", "tickets"] and parts[3] == "comments":
            ticket_id = int(parts[2])
            self.send_json(200, fetch_all(
                """
                SELECT id, ticket_id, author, body, created_at
                  FROM ticket_comments
                 WHERE ticket_id = %s
                 ORDER BY created_at ASC, id ASC
                """,
                (ticket_id,),
            ))
            return

        self.serve_static(path)

    def route_patch(self):
        parts = parse.urlparse(self.path).path.strip("/").split("/")
        if len(parts) != 3 or parts[:2] != ["api", "tickets"]:
            self.send_error_json(404, "Not found")
            return
        ticket_id = int(parts[2])
        payload = self.read_json()
        status = payload.get("status")
        priority = payload.get("priority")
        owner = str(payload.get("owner", "")).strip()
        if status not in STATUSES or priority not in PRIORITIES or not owner:
            self.send_error_json(400, "Invalid ticket update")
            return

        if using_postgres():
            updated = execute(
                """
                UPDATE tickets
                   SET status = %s, priority = %s, owner = %s, updated_at = NOW()
                 WHERE id = %s
                RETURNING id
                """,
                (status, priority, owner, ticket_id),
            )
        else:
            execute(
                """
                UPDATE tickets
                   SET status = %s, priority = %s, owner = %s, updated_at = CURRENT_TIMESTAMP
                 WHERE id = %s
                """,
                (status, priority, owner, ticket_id),
            )
            updated = fetch_one("SELECT id FROM tickets WHERE id = %s", (ticket_id,))
        if not updated:
            self.send_error_json(404, "Ticket not found")
            return
        self.send_json(200, fetch_one(ticket_query("WHERE t.id = %s"), (ticket_id,)))

    def route_post(self):
        parts = parse.urlparse(self.path).path.strip("/").split("/")
        if parts == ["api", "admin", "break-priority"]:
            if not using_postgres():
                self.send_error_json(409, "デモモードでは実行できません。Lakebase 接続後に実行してください。")
                return
            break_priority_column()
            self.send_json(200, {
                "ok": True,
                "message": "priority column dropped",
                "database_name": pg_dbname(),
                "branch": extract_branch(_env("ENDPOINT_NAME")),
            })
            return

        if len(parts) != 4 or parts[:2] != ["api", "tickets"] or parts[3] != "comments":
            self.send_error_json(404, "Not found")
            return
        ticket_id = int(parts[2])
        payload = self.read_json()
        body = str(payload.get("body", "")).strip()
        author = str(payload.get("author", "workshop participant")).strip() or "workshop participant"
        if not body:
            self.send_error_json(400, "Comment body is required")
            return
        if not fetch_one("SELECT id FROM tickets WHERE id = %s", (ticket_id,)):
            self.send_error_json(404, "Ticket not found")
            return

        if using_postgres():
            comment = execute(
                """
                INSERT INTO ticket_comments (ticket_id, author, body)
                VALUES (%s, %s, %s)
                RETURNING id, ticket_id, author, body, created_at
                """,
                (ticket_id, author, body),
            )
        else:
            execute(
                "INSERT INTO ticket_comments (ticket_id, author, body) VALUES (%s, %s, %s)",
                (ticket_id, author, body),
            )
            comment = fetch_one(
                """
                SELECT id, ticket_id, author, body, created_at
                  FROM ticket_comments
                 WHERE ticket_id = %s
                 ORDER BY id DESC
                 LIMIT 1
                """,
                (ticket_id,),
            )
        execute("UPDATE tickets SET updated_at = CURRENT_TIMESTAMP WHERE id = %s", (ticket_id,))
        self.send_json(200, comment)

    def serve_static(self, path: str):
        if path in {"", "/"}:
            target = STATIC_DIR / "index.html"
        elif path.startswith("/assets/"):
            target = STATIC_DIR / path.removeprefix("/assets/")
        else:
            target = STATIC_DIR / "index.html"

        if not target.exists() or not target.is_file():
            self.send_error_json(404, "Not found")
            return

        content_type = "text/html; charset=utf-8"
        if target.suffix == ".css":
            content_type = "text/css; charset=utf-8"
        elif target.suffix == ".js":
            content_type = "application/javascript; charset=utf-8"

        body = target.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def main() -> None:
    init_database()
    port = int(os.environ.get("DATABRICKS_APP_PORT", os.environ.get("PORT", "8000")))
    server = ThreadingHTTPServer(("0.0.0.0", port), AppHandler)
    print(f"Serving on 0.0.0.0:{port}")
    server.serve_forever()


if __name__ == "__main__":
    main()

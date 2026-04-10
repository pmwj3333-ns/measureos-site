import json
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text

from app.database import SessionLocal, engine
from app import models
from app.routers import settings, v2 as v2_routes, test_control, work


def _sqlite_migrate():
    with engine.begin() as conn:
        def cols(table: str):
            r = conn.execute(text(f"PRAGMA table_info({table})"))
            return {row[1] for row in r.fetchall()}

        try:
            cs = cols("company_settings")
            if "field_users" not in cs:
                conn.execute(
                    text("ALTER TABLE company_settings ADD COLUMN field_users VARCHAR DEFAULT ''")
                )
            if "input_mode" not in cs:
                conn.execute(
                    text(
                        "ALTER TABLE company_settings ADD COLUMN input_mode VARCHAR DEFAULT 'manufacturing'"
                    )
                )
            if "company_name" not in cs:
                conn.execute(
                    text("ALTER TABLE company_settings ADD COLUMN company_name VARCHAR DEFAULT ''")
                )
            if "phase2_enabled" not in cs:
                conn.execute(
                    text(
                        "ALTER TABLE company_settings ADD COLUMN phase2_enabled BOOLEAN DEFAULT 0"
                    )
                )
        except Exception:
            pass
        try:
            wu = cols("work_unit")
            if "is_unregistered_user" not in wu:
                conn.execute(
                    text(
                        "ALTER TABLE work_unit ADD COLUMN is_unregistered_user BOOLEAN DEFAULT 0"
                    )
                )
            if "user_source" not in wu:
                conn.execute(
                    text("ALTER TABLE work_unit ADD COLUMN user_source VARCHAR DEFAULT 'master'")
                )
            if "planned_lines_json" not in wu:
                conn.execute(
                    text("ALTER TABLE work_unit ADD COLUMN planned_lines_json VARCHAR")
                )
            if "actual_lines_json" not in wu:
                conn.execute(
                    text("ALTER TABLE work_unit ADD COLUMN actual_lines_json VARCHAR")
                )
            if "created_at" not in wu:
                conn.execute(text("ALTER TABLE work_unit ADD COLUMN created_at DATETIME"))
            if "business_date_source" not in wu:
                conn.execute(
                    text("ALTER TABLE work_unit ADD COLUMN business_date_source VARCHAR")
                )
            if "business_date_debug_json" not in wu:
                conn.execute(
                    text("ALTER TABLE work_unit ADD COLUMN business_date_debug_json VARCHAR")
                )
            if "updated_at" not in wu:
                conn.execute(text("ALTER TABLE work_unit ADD COLUMN updated_at DATETIME"))
            for col, typ in (
                ("planned_work_type", "VARCHAR"),
                ("planned_work_label", "VARCHAR"),
                ("planned_item_name", "VARCHAR"),
                ("actual_work_type", "VARCHAR"),
                ("actual_work_label", "VARCHAR"),
                ("actual_item_name", "VARCHAR"),
                ("pattern_a", "BOOLEAN"),
                ("pattern_b", "BOOLEAN"),
                ("status", "VARCHAR DEFAULT 'normal'"),
                ("system_pattern", "VARCHAR"),
                ("user_pattern", "VARCHAR"),
                ("planned_at", "DATETIME"),
                ("input_source", "VARCHAR"),
                ("anomaly_started_at", "DATETIME"),
            ):
                if col not in wu:
                    conn.execute(text(f"ALTER TABLE work_unit ADD COLUMN {col} {typ}"))
        except Exception:
            pass
        # work_unit_status_history: models.WorkUnitStatusHistory と同一 DDL（create_all 後の冪等救済）
        try:
            conn.execute(
                text(
                    """
                    CREATE TABLE IF NOT EXISTS work_unit_status_history (
                        id INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
                        work_unit_id INTEGER NOT NULL,
                        from_status VARCHAR,
                        to_status VARCHAR NOT NULL,
                        changed_at DATETIME NOT NULL,
                        trigger_type VARCHAR,
                        FOREIGN KEY(work_unit_id) REFERENCES work_unit (id)
                    )
                    """
                )
            )
            conn.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS ix_work_unit_status_history_work_unit_id "
                    "ON work_unit_status_history (work_unit_id)"
                )
            )
            conn.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS ix_work_unit_status_history_changed_at "
                    "ON work_unit_status_history (changed_at)"
                )
            )
            conn.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS ix_work_unit_status_history_unit_changed "
                    "ON work_unit_status_history (work_unit_id, changed_at)"
                )
            )
        except Exception:
            pass


# テーブルを自動作成（既存テーブルはスキップ）
models.Base.metadata.create_all(bind=engine)
_sqlite_migrate()

app = FastAPI(title="MEASURE OS", version="2.0")

app.include_router(settings.router)
app.include_router(work.router)
app.include_router(v2_routes.router)
app.include_router(work.router, prefix="/v2", tags=["v2-作業"])
app.include_router(test_control.router, prefix="/v2")

# uvicorn の cwd に依存しない（/static/debug.html 等）
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_FRONTEND_DIR = _PROJECT_ROOT / "frontend"

_NO_CACHE = {
    "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
    "Pragma": "no-cache",
}


def _file_response_or_404(name: str) -> FileResponse:
    path = _FRONTEND_DIR / name
    if not path.is_file():
        raise HTTPException(
            status_code=404,
            detail=f"frontend に {name} がありません（期待パス: {path}）",
        )
    return FileResponse(path, headers=_NO_CACHE)


def _field_html():
    return _file_response_or_404("field.html")


def _field_users_raw_for_company(company_id: str) -> str:
    db = SessionLocal()
    try:
        row = db.query(models.CompanySettings).filter_by(company_id=company_id).first()
        return (row.field_users or "").strip() if row else ""
    finally:
        db.close()


def _field_v2_html_response(request: Request) -> HTMLResponse:
    """班長 raw を </head> 直前に埋め込む（?company= 時）。HTMLコメント・overlay 文言に依存しない。"""
    path = _FRONTEND_DIR / "field_v2.html"
    if not path.is_file():
        raise HTTPException(
            status_code=404,
            detail=f"frontend に field_v2.html がありません（期待パス: {path}）",
        )
    html = path.read_text(encoding="utf-8")
    company = (
        request.query_params.get("company") or request.query_params.get("company_id") or ""
    ).strip()
    raw = _field_users_raw_for_company(company) if company else ""
    if company:
        inject = (
            "<script>"
            f"window.__MO_FIELD_USERS_RAW__={json.dumps(raw)};"
            f"window.__MO_BOOTSTRAP_COMPANY__={json.dumps(company)};"
            "</script>\n"
        )
        lowered = html.lower()
        head_i = lowered.find("</head>")
        if head_i != -1:
            html = html[:head_i] + inject + html[head_i:]
        else:
            body_i = lowered.find("<body")
            if body_i != -1:
                gt = html.find(">", body_i)
                if gt != -1:
                    gt += 1
                    html = html[:gt] + inject + html[gt:]
                else:
                    html = inject + html
            else:
                html = inject + html
    return HTMLResponse(content=html, headers=_NO_CACHE)


# --- 画面ルートは /static マウントより先に登録（404 の取り違え防止） ---
@app.get("/field")
def field_screen():
    return _field_html()


@app.get("/field/v2", summary="現場 v2（第5条フェーズ1・最小）")
def field_v2_screen(request: Request):
    return _field_v2_html_response(request)


@app.get("/現場")
def field_screen_ja():
    """従来どおり日本語パス（エディタプレビュー・ブックマーク互換）"""
    return _field_html()


@app.get("/現場/v2", summary="現場 v2 日本語パス")
def field_v2_screen_ja(request: Request):
    return _field_v2_html_response(request)


@app.get("/genba/v2", summary="現場 v2（ASCII 別名・日本語パスが通らない環境用）")
def field_v2_screen_ascii_alias(request: Request):
    return _field_v2_html_response(request)


@app.get("/sr/v2", summary="社労士 v2（班長マスタ・フェーズ1 専用）")
def sr_v2_screen():
    return _file_response_or_404("sr_v2.html")


@app.get("/debug")
def debug_screen():
    return _file_response_or_404("debug.html")


@app.get("/debug/v2", summary="debug v2（DB 参照のみ・ field_v2 用）")
def debug_v2_screen():
    return _file_response_or_404("debug_v2.html")


@app.get("/office/v2", summary="事務 v2（blue/red 確認・完了）")
def office_v2_screen():
    return _file_response_or_404("office_v2.html")


@app.get("/dev")
def debug_screen_alias():
    """旧ログ画面パス互換"""
    return _file_response_or_404("debug.html")


app.mount("/static", StaticFiles(directory=str(_FRONTEND_DIR)), name="static")

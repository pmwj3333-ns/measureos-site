import json
import os
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text
from starlette.middleware.sessions import SessionMiddleware

from app.database import SessionLocal, engine
from app.services.company_validator import normalize_company_id
from app.services.return_to import build_office_login_url
from app import models
from app.routers import (
    admin_companies,
    office_session,
    priority,
    product_master,
    settings,
    shipment,
    sr_observe,
    sr_monthly,
    stock,
    v2 as v2_routes,
    test_control,
    work,
    working_calendar,
)


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
            if "package_code" not in cs:
                conn.execute(
                    text(
                        "ALTER TABLE company_settings ADD COLUMN package_code VARCHAR DEFAULT 'A'"
                    )
                )
                conn.execute(
                    text(
                        "UPDATE company_settings SET package_code = 'A' WHERE package_code IS NULL OR TRIM(package_code) = ''"
                    )
                )
            if "order_cutoff_time" not in cs:
                conn.execute(
                    text("ALTER TABLE company_settings ADD COLUMN order_cutoff_time TIME")
                )
            if "default_working_weekdays" not in cs:
                conn.execute(
                    text(
                        "ALTER TABLE company_settings ADD COLUMN default_working_weekdays VARCHAR"
                    )
                )
        except Exception:
            pass
        try:
            wc = cols("working_calendar")
            if not wc:
                conn.execute(
                    text(
                        """
                        CREATE TABLE IF NOT EXISTS working_calendar (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            company_id VARCHAR NOT NULL,
                            target_date DATE NOT NULL,
                            is_working_day BOOLEAN NOT NULL,
                            created_at DATETIME,
                            UNIQUE(company_id, target_date)
                        )
                        """
                    )
                )
                conn.execute(
                    text(
                        "CREATE INDEX IF NOT EXISTS ix_working_calendar_company_id "
                        "ON working_calendar (company_id)"
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
            if "is_deviation" not in wu:
                conn.execute(
                    text("ALTER TABLE work_unit ADD COLUMN is_deviation BOOLEAN DEFAULT 0")
                )
            if "deviation_reason" not in wu:
                conn.execute(
                    text("ALTER TABLE work_unit ADD COLUMN deviation_reason VARCHAR")
                )
            if "is_article7_deviation" not in wu:
                conn.execute(
                    text(
                        "ALTER TABLE work_unit ADD COLUMN is_article7_deviation BOOLEAN DEFAULT 0"
                    )
                )
                conn.execute(
                    text(
                        "UPDATE work_unit SET is_article7_deviation = 1 WHERE is_deviation = 1"
                    )
                )
            if "reflection_status" not in wu:
                conn.execute(
                    text(
                        "ALTER TABLE work_unit ADD COLUMN reflection_status VARCHAR DEFAULT 'pending'"
                    )
                )
            if "reflection_reject_reason_code" not in wu:
                conn.execute(
                    text(
                        "ALTER TABLE work_unit ADD COLUMN reflection_reject_reason_code VARCHAR"
                    )
                )
            if "reflection_reject_reason_detail" not in wu:
                conn.execute(
                    text(
                        "ALTER TABLE work_unit ADD COLUMN reflection_reject_reason_detail VARCHAR"
                    )
                )
            if "actual_memo" not in wu:
                conn.execute(text("ALTER TABLE work_unit ADD COLUMN actual_memo VARCHAR"))
            if "used_materials_json" not in wu:
                conn.execute(
                    text("ALTER TABLE work_unit ADD COLUMN used_materials_json VARCHAR")
                )
            if "anomaly_classification_json" not in wu:
                conn.execute(
                    text(
                        "ALTER TABLE work_unit ADD COLUMN anomaly_classification_json VARCHAR"
                    )
                )
            conn.execute(
                text(
                    "UPDATE work_unit SET reflection_status = 'pending' "
                    "WHERE reflection_status IS NULL OR TRIM(reflection_status) = ''"
                )
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
            wu_pr = cols("work_unit")
            if wu_pr is not None and "planned_registered_at" not in wu_pr:
                conn.execute(
                    text("ALTER TABLE work_unit ADD COLUMN planned_registered_at DATETIME")
                )
                conn.execute(
                    text(
                        "UPDATE work_unit SET planned_registered_at = planned_at "
                        "WHERE planned_registered_at IS NULL AND planned_at IS NOT NULL"
                    )
                )
                conn.execute(
                    text(
                        "UPDATE work_unit SET planned_registered_at = COALESCE(created_at, updated_at) "
                        "WHERE planned_registered_at IS NULL AND planned_at IS NULL "
                        "AND planned_lines_json IS NOT NULL "
                        "AND TRIM(planned_lines_json) != '' "
                        "AND TRIM(planned_lines_json) != '[]'"
                    )
                )
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
        # priority_item: value → ship_value / prod_value（既存 DB 互換）
        try:
            pi = cols("priority_item")
            if pi:
                if "ship_value" not in pi:
                    conn.execute(text("ALTER TABLE priority_item ADD COLUMN ship_value FLOAT"))
                if "prod_value" not in pi:
                    conn.execute(text("ALTER TABLE priority_item ADD COLUMN prod_value FLOAT"))
                pi2 = cols("priority_item")
                if "value" in pi2:
                    conn.execute(
                        text(
                            "UPDATE priority_item SET ship_value = value "
                            "WHERE ship_value IS NULL"
                        )
                    )
                    conn.execute(
                        text(
                            "UPDATE priority_item SET prod_value = value "
                            "WHERE prod_value IS NULL"
                        )
                    )
                conn.execute(
                    text("UPDATE priority_item SET ship_value = 0 WHERE ship_value IS NULL")
                )
                conn.execute(
                    text("UPDATE priority_item SET prod_value = 0 WHERE prod_value IS NULL")
                )
                if "product_code" not in pi2:
                    conn.execute(
                        text(
                            "ALTER TABLE priority_item ADD COLUMN product_code VARCHAR DEFAULT ''"
                        )
                    )
                    conn.execute(
                        text(
                            "UPDATE priority_item SET product_code = '' WHERE product_code IS NULL"
                        )
                    )
                pi3 = cols("priority_item")
                if pi3 and "stock_qty" not in pi3:
                    conn.execute(
                        text("ALTER TABLE priority_item ADD COLUMN stock_qty FLOAT")
                    )
                    conn.execute(
                        text(
                            "UPDATE priority_item SET stock_qty = "
                            "MAX(0, COALESCE(ship_value, 0) - COALESCE(prod_value, 0)) "
                            "WHERE stock_qty IS NULL"
                        )
                    )
                pi4 = cols("priority_item")
                if pi4 and "stock_qty" in pi4:
                    conn.execute(
                        text(
                            "UPDATE priority_item SET stock_qty = 0 "
                            "WHERE stock_qty IS NULL"
                        )
                    )
                pi5 = cols("priority_item")
                if pi5 and "status" not in pi5:
                    conn.execute(
                        text(
                            "ALTER TABLE priority_item ADD COLUMN status VARCHAR DEFAULT 'open'"
                        )
                    )
                    conn.execute(
                        text(
                            "UPDATE priority_item SET status = 'open' "
                            "WHERE status IS NULL OR TRIM(COALESCE(status, '')) = ''"
                        )
                    )
                pi6 = cols("priority_item")
                if pi6 and "is_after_cutoff" not in pi6:
                    conn.execute(
                        text(
                            "ALTER TABLE priority_item ADD COLUMN is_after_cutoff BOOLEAN DEFAULT 0"
                        )
                    )
                    conn.execute(
                        text(
                            "UPDATE priority_item SET is_after_cutoff = 0 "
                            "WHERE is_after_cutoff IS NULL"
                        )
                    )
        except Exception:
            pass
        try:
            conn.execute(
                text(
                    """
                    CREATE TABLE IF NOT EXISTS product_master (
                        id INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
                        company_id VARCHAR NOT NULL,
                        product_code VARCHAR,
                        label VARCHAR NOT NULL,
                        is_active BOOLEAN NOT NULL DEFAULT 1,
                        created_at DATETIME,
                        updated_at DATETIME,
                        CONSTRAINT uq_product_master_company_label UNIQUE (company_id, label)
                    )
                    """
                )
            )
            conn.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS ix_product_master_company_id "
                    "ON product_master (company_id)"
                )
            )
            pm_cols = cols("product_master")
            if pm_cols is not None and "safety_stock_value" not in pm_cols:
                conn.execute(
                    text(
                        "ALTER TABLE product_master ADD COLUMN safety_stock_value INTEGER"
                    )
                )
            if pm_cols is not None and "production_mode" not in pm_cols:
                conn.execute(
                    text(
                        "ALTER TABLE product_master ADD COLUMN production_mode VARCHAR "
                        "NOT NULL DEFAULT 'manufacture'"
                    )
                )
                conn.execute(
                    text(
                        "UPDATE product_master SET production_mode = 'manufacture' "
                        "WHERE production_mode IS NULL OR TRIM(production_mode) = ''"
                    )
                )
        except Exception:
            pass
        try:
            conn.execute(
                text(
                    """
                    CREATE TABLE IF NOT EXISTS company_master (
                        id INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
                        company_id VARCHAR NOT NULL,
                        company_name VARCHAR NOT NULL,
                        is_active BOOLEAN NOT NULL DEFAULT 1,
                        created_at DATETIME,
                        updated_at DATETIME,
                        CONSTRAINT uq_company_master_company_id UNIQUE (company_id)
                    )
                    """
                )
            )
        except Exception:
            pass
        try:
            conn.execute(
                text(
                    "ALTER TABLE company_master ADD COLUMN company_password_hash TEXT"
                )
            )
        except Exception:
            pass
        try:
            conn.execute(
                text(
                    """
                    CREATE TABLE IF NOT EXISTS monthly_reports (
                        id INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
                        company_id VARCHAR NOT NULL,
                        target_month VARCHAR NOT NULL,
                        generated_summary VARCHAR NOT NULL DEFAULT '',
                        consultant_comment VARCHAR,
                        created_at DATETIME NOT NULL,
                        CONSTRAINT uq_monthly_reports_company_month UNIQUE (company_id, target_month)
                    )
                    """
                )
            )
            conn.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS ix_monthly_reports_company_id ON monthly_reports (company_id)"
                )
            )
        except Exception:
            pass
models.Base.metadata.create_all(bind=engine)
_sqlite_migrate()

try:
    from app.services.company_validator import backfill_company_master_from_legacy

    _bf_db = SessionLocal()
    try:
        backfill_company_master_from_legacy(_bf_db)
    finally:
        _bf_db.close()
except Exception:
    pass

app = FastAPI(title="MEASURE OS", version="2.0")

app.add_middleware(
    SessionMiddleware,
    secret_key=os.environ.get(
        "MEASUREOS_SESSION_SECRET",
        "dev-measureos-session-secret-do-not-use-in-production",
    ),
)

app.include_router(settings.router)
app.include_router(work.router)
app.include_router(v2_routes.router)
app.include_router(office_session.router)
app.include_router(work.router, prefix="/v2", tags=["v2-作業"])
app.include_router(priority.router)
app.include_router(stock.router)
app.include_router(product_master.router)
app.include_router(shipment.router)
app.include_router(test_control.router, prefix="/v2")
app.include_router(admin_companies.router)
app.include_router(sr_observe.router)
app.include_router(sr_monthly.router)
app.include_router(working_calendar.router)

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


def _unauthenticated_login_redirect(request: Request) -> RedirectResponse:
    return RedirectResponse(
        url=build_office_login_url(str(request.url.path)),
        status_code=307,
        headers={
            **_NO_CACHE,
            "Vary": "Cookie",
        },
    )


def _inject_script_into_html(html: str, script_body: str) -> str:
    inject = f"<script>{script_body}</script>\n"
    lowered = html.lower()
    head_i = lowered.find("</head>")
    if head_i != -1:
        return html[:head_i] + inject + html[head_i:]
    body_i = lowered.find("<body")
    if body_i != -1:
        gt = html.find(">", body_i)
        if gt != -1:
            return html[: gt + 1] + inject + html[gt + 1 :]
    return inject + html



def _session_bootstrap_html_response(request: Request, html_name: str):
    """session company を注入。未ログイン時は office_v2 へ return_to 付き redirect。"""
    company = normalize_company_id(request.session.get("company_id"))
    if not company:
        return _unauthenticated_login_redirect(request)

    path = _FRONTEND_DIR / html_name
    if not path.is_file():
        raise HTTPException(
            status_code=404,
            detail=f"frontend に {html_name} がありません（期待パス: {path}）",
        )
    html = path.read_text(encoding="utf-8")
    script = f"window.__MO_BOOTSTRAP_COMPANY__={json.dumps(company)};"
    html = _inject_script_into_html(html, script)
    return HTMLResponse(content=html, headers=_NO_CACHE)


def _priority_v2_html_response(request: Request):
    return _session_bootstrap_html_response(request, "priority_view.html")


def _field_v2_html_response(request: Request):
    """session company を注入。未ログイン時は office_v2 へ return_to 付き redirect。"""
    company = normalize_company_id(request.session.get("company_id"))
    if not company:
        return _unauthenticated_login_redirect(request)

    path = _FRONTEND_DIR / "field_v2.html"
    if not path.is_file():
        raise HTTPException(
            status_code=404,
            detail=f"frontend に field_v2.html がありません（期待パス: {path}）",
        )
    html = path.read_text(encoding="utf-8")
    raw = _field_users_raw_for_company(company)
    script = (
        f"window.__MO_FIELD_USERS_RAW__={json.dumps(raw)};"
        f"window.__MO_BOOTSTRAP_COMPANY__={json.dumps(company)};"
    )
    html = _inject_script_into_html(html, script)
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


@app.get("/sr/v2/ops", summary="運営ダッシュボード（/sr/v2?tab=ops へ統合）")
def sr_v2_ops_screen():
    return RedirectResponse(url="/sr/v2?tab=ops", status_code=307)


@app.get("/sr/v2", summary="社労士 v2（班長マスタ・フェーズ1 専用）")
def sr_v2_screen():
    return _file_response_or_404("sr_v2.html")


@app.get("/sr/monthly", summary="社労士 月報作成")
def sr_monthly_screen():
    return _file_response_or_404("sr_monthly.html")


@app.get("/debug")
def debug_screen():
    return _file_response_or_404("debug.html")


@app.get("/debug/v2", summary="debug v2（DB 参照のみ・ field_v2 用）")
def debug_v2_screen():
    return _file_response_or_404("debug_v2.html")


@app.get("/office/v2", summary="事務 v2（blue/red 確認・完了）")
def office_v2_screen():
    return _file_response_or_404("office_v2.html")


@app.get("/priority/v2", summary="第7条・事務の優先指示一覧（表示のみ・現場は変更しない）")
def priority_v2_screen(request: Request):
    return _priority_v2_html_response(request)


@app.get(
    "/priority/input/v2",
    summary="第7条・優先指示の入力（事務・営業・CSV/API）",
)
def priority_input_v2_screen():
    return _file_response_or_404("priority_input_v2.html")


@app.get(
    "/stock/import/v2",
    summary="在庫CSV取り込み（第7条ステップ①・投入のみ）",
)
def stock_import_v2_screen(request: Request):
    return _session_bootstrap_html_response(request, "stock_import_v2.html")


@app.get(
    "/shipment/import/v2",
    summary="出荷予定CSV取り込み（第7条ステップ②・投入のみ）",
)
def shipment_import_v2_screen(request: Request):
    return _session_bootstrap_html_response(request, "shipment_import_v2.html")


@app.get(
    "/product/master/v2",
    summary="商品マスタ（第5条・product_code 補完・事務向け）",
)
def product_master_v2_screen(request: Request):
    return _session_bootstrap_html_response(request, "product_master_v2.html")


@app.get("/admin/companies/ui", summary="会社マスタ管理（簡易画面）")
def admin_companies_ui_screen():
    return _file_response_or_404("admin_companies.html")


@app.get("/dev")
def debug_screen_alias():
    """旧ログ画面パス互換"""
    return _file_response_or_404("debug.html")


app.mount("/static", StaticFiles(directory=str(_FRONTEND_DIR)), name="static")

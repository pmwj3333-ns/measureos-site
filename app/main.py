from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text

from app.database import engine
from app import models
from app.routers import settings, work


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
            ):
                if col not in wu:
                    conn.execute(text(f"ALTER TABLE work_unit ADD COLUMN {col} {typ}"))
        except Exception:
            pass


# テーブルを自動作成（既存テーブルはスキップ）
models.Base.metadata.create_all(bind=engine)
_sqlite_migrate()

app = FastAPI(title="MEASURE OS", version="2.0")

app.include_router(settings.router)
app.include_router(work.router)

app.mount("/static", StaticFiles(directory="frontend"), name="static")


_NO_CACHE = {
    "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
    "Pragma": "no-cache",
}


def _field_html():
    return FileResponse("frontend/field.html", headers=_NO_CACHE)


@app.get("/field")
def field_screen():
    return _field_html()


@app.get("/現場")
def field_screen_ja():
    """従来どおり日本語パス（エディタプレビュー・ブックマーク互換）"""
    return _field_html()


@app.get("/debug")
def debug_screen():
    return FileResponse("frontend/debug.html", headers=_NO_CACHE)


@app.get("/dev")
def debug_screen_alias():
    """旧ログ画面パス互換"""
    return FileResponse("frontend/debug.html", headers=_NO_CACHE)

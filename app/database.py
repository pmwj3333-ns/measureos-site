import logging
import os
from pathlib import Path

from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, Session as SASession, sessionmaker

# 起動時のカレントディレクトリに依存させない（別の measure_os.db を見て「一向に変わらない」原因になる）
_DB_FILE = (Path(__file__).resolve().parent.parent / "measure_os.db").resolve()
_sql_override = os.environ.get("MEASUREOS_SQLITE_URL", "").strip()
if _sql_override:
    # pytest など: sqlite:///… のフル URL、またはファイルパスをそのまま指定
    DATABASE_URL = (
        _sql_override
        if _sql_override.startswith("sqlite:")
        else f"sqlite:///{Path(_sql_override).expanduser().resolve().as_posix()}"
    )
else:
    DATABASE_URL = f"sqlite:///{_DB_FILE.as_posix()}"

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

_pattern_debug_log = logging.getLogger("measureos.pattern_debug")


@event.listens_for(SASession, "before_commit")
def _pattern_debug_before_commit(session: SASession) -> None:
    """commit 直前のセッション内 WorkUnit の system_pattern（SQL 送出直前の値）。"""
    try:
        from app import models
    except Exception:
        return
    ids: list[int] = []
    seen: set[int] = set()
    for obj in set(session.dirty).union(session.new):
        if not isinstance(obj, models.WorkUnit):
            continue
        uid = getattr(obj, "id", None)
        sp = getattr(obj, "system_pattern", None)
        st = getattr(obj, "status", None)
        in_dirty = obj in session.dirty
        msg = (
            f"[measureos.pattern_debug] before_commit unit_id={uid} "
            f"system_pattern={sp!r} status={st!r} in_dirty={in_dirty}"
        )
        print(msg, flush=True)
        _pattern_debug_log.warning(msg)
        if uid is not None and uid not in seen:
            seen.add(uid)
            ids.append(uid)
    session.info["_pattern_debug_work_unit_ids"] = ids


@event.listens_for(SASession, "after_commit")
def _pattern_debug_after_commit(session: SASession) -> None:
    """commit 後に別セッションで SELECT し、DB に載った system_pattern を表示。"""
    ids = session.info.pop("_pattern_debug_work_unit_ids", None) or []
    if not ids:
        return
    try:
        from app import models
    except Exception:
        return
    read_sess = SessionLocal()
    try:
        for uid in ids:
            row = read_sess.get(models.WorkUnit, uid)
            if row is None:
                msg = f"[measureos.pattern_debug] after_commit_db_read unit_id={uid} row=MISSING"
            else:
                msg = (
                    f"[measureos.pattern_debug] after_commit_db_read unit_id={uid} "
                    f"system_pattern={row.system_pattern!r} status={row.status!r}"
                )
            print(msg, flush=True)
            _pattern_debug_log.warning(msg)
    finally:
        read_sess.close()


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

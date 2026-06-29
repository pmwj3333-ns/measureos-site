"""CSV 取込メタ（ヘッダースキーマ配信）。"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request

from app.services.csv_header_normalizer import IMPORT_SCHEMAS, export_schema_for_client
from app.services.office_session_scope import require_authenticated_session

router = APIRouter(prefix="/v2/csv", tags=["v2-CSV取込"])


@router.get(
    "/import-schemas/{schema_name}",
    summary="CSV取込ヘッダースキーマ（別名辞書・必須列）",
)
def get_csv_import_schema(schema_name: str, request: Request):
    require_authenticated_session(request)
    """
    在庫・出荷など取込種別ごとの canonical key とヘッダー別名を返す。
    将来 company_id クエリで会社別 override をマージする拡張点。
    """
    key = (schema_name or "").strip().lower()
    if key not in IMPORT_SCHEMAS:
        raise HTTPException(
            status_code=404,
            detail=f"未知のスキーマです: {schema_name!r}（利用可能: {', '.join(sorted(IMPORT_SCHEMAS))}）",
        )
    return export_schema_for_client(key)

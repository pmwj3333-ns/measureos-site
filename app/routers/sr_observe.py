"""Package A: 管理者向け現場観測 API（/sr/v2 ダッシュボード用・読取専用）。"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas import PackageAObserveDashboardOut, PackageAObservePortfolioOut
from app.services.package_a_observe import build_observe_portfolio, build_package_a_dashboard

router = APIRouter(prefix="/v2/sr", tags=["v2-PackageA観測"])


@router.get(
    "/observe-dashboard",
    response_model=PackageAObserveDashboardOut,
    summary="Package A 現場観測ダッシュボード（読取専用）",
)
def observe_dashboard(
    company_id: str = Query(..., description="company_id"),
    db: Session = Depends(get_db),
):
    cid = (company_id or "").strip()
    if not cid:
        raise HTTPException(status_code=422, detail="company_id が空です")
    return build_package_a_dashboard(cid, db)


@router.get(
    "/observe-portfolio",
    response_model=PackageAObservePortfolioOut,
    summary="Package A 運営ダッシュボード（全社一覧・読取専用）",
)
def observe_portfolio(
    active_only: bool = Query(True, description="true のとき is_active のみ"),
    db: Session = Depends(get_db),
):
    return build_observe_portfolio(db, active_only=active_only)

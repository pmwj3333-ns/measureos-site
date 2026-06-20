"""社労士向け月報 API（/sr/monthly）。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas import MonthlyReportAggregateOut, MonthlyReportSaveIn, MonthlyReportSaveOut
from app.services.monthly_report import (
    build_monthly_report_aggregate,
    parse_target_month,
    save_monthly_report,
)

router = APIRouter(prefix="/v2/sr", tags=["v2-月報"])


def _render_print_html(payload: dict) -> str:
    m = payload.get("metrics") or {}
    company_name = payload.get("company_name") or payload.get("company_id") or ""
    month_label = payload.get("target_month_label") or payload.get("target_month") or ""
    summary = payload.get("generated_summary") or ""
    comment = payload.get("consultant_comment") or ""

    def rows(items):
        if not items:
            return "<tr><td colspan=\"2\">該当なし</td></tr>"
        return "".join(
            f"<tr><td>{r.get('label', '')}</td><td>{int(r.get('count') or 0)}</td></tr>"
            for r in items
        )

    metrics_rows = [
        ("総作業数", m.get("total_work_count", 0)),
        ("実績入力済み", m.get("completed_count", 0)),
        ("実績未入力", m.get("incomplete_count", 0)),
    ]
    metrics_html = "".join(
        f"<tr><td>{label}</td><td>{value}</td></tr>" for label, value in metrics_rows
    )
    breakdown_rows = m.get("anomaly_breakdown") or []
    breakdown_html = "".join(
        f"<tr><td>{r.get('label', '')}</td><td>{int(r.get('count') or 0)}</td></tr>"
        for r in breakdown_rows
    ) or "<tr><td colspan=\"2\">該当なし</td></tr>"
    breakdown_note = m.get("anomaly_breakdown_note") or ""
    audit_target = int(m.get("audit_target_count") or 0)
    audit_rows = m.get("audit_breakdown") or []
    audit_html = "".join(
        f"<tr><td>{r.get('label', '')}</td><td>{int(r.get('count') or 0)}</td></tr>"
        for r in audit_rows
    ) or "<tr><td colspan=\"2\">該当なし</td></tr>"
    audit_note = m.get("audit_breakdown_note") or ""
    audit_rate = m.get("audit_response_rate", 0.0)
    fc = m.get("field_classification_breakdown") or {}
    fc_note = fc.get("note") or ""
    fc_heading = (
        "②-b 現場分類（自動判定）"
        if fc.get("display_mode") == "auto"
        else "②-b 現場分類（任意入力）"
    )

    def field_classification_list(items):
        if not items:
            return "<li>該当なし</li>"
        return "".join(
            f"<li><span>{r.get('label', '')}</span><span>{int(r.get('count') or 0)}件</span></li>"
            for r in items
        )

    fc_process_items = list(fc.get("process") or [])
    if fc.get("auto_process") and int(fc["auto_process"].get("count") or 0) > 0:
        fc_process_items.append(fc["auto_process"])
    fc_result_items = list(fc.get("result") or [])
    if fc.get("auto_result") and int(fc["auto_result"].get("count") or 0) > 0:
        fc_result_items.append(fc["auto_result"])

    fc_process_html = field_classification_list(fc_process_items)
    fc_result_html = field_classification_list(fc_result_items)

    return f"""<!DOCTYPE html>
<html lang="ja">
<head>
  <meta charset="UTF-8" />
  <title>月報 {company_name} {month_label}</title>
  <style>
    body {{ font-family: "Hiragino Sans", "Meiryo", sans-serif; margin: 24px; color: #111; }}
    h1 {{ font-size: 1.25rem; margin-bottom: 4px; }}
    h2 {{ font-size: 1rem; margin: 20px 0 8px; border-bottom: 1px solid #ccc; padding-bottom: 4px; }}
    table {{ width: 100%; border-collapse: collapse; margin-bottom: 12px; }}
    th, td {{ border: 1px solid #ddd; padding: 6px 8px; text-align: left; }}
    th {{ background: #f5f5f5; }}
    .summary, .comment, .note {{ white-space: pre-wrap; line-height: 1.6; padding: 10px; background: #fafafa; border: 1px solid #eee; }}
    .note {{ font-size: 0.85rem; color: #555; margin-bottom: 8px; }}
    .fc-box {{ padding: 10px; background: #f8fafc; border: 1px solid #e5e7eb; margin-bottom: 12px; }}
    .fc-box h3 {{ font-size: 0.9rem; margin: 10px 0 6px; }}
    .fc-box h3:first-child {{ margin-top: 0; }}
    .fc-list {{ list-style: none; margin: 0; padding: 0; }}
    .fc-list li {{ display: flex; justify-content: space-between; padding: 4px 0; border-bottom: 1px dashed #ddd; }}
    .fc-list li:last-child {{ border-bottom: none; }}
    @media print {{ body {{ margin: 12mm; }} }}
  </style>
</head>
<body>
  <h1>MEASURE OS 月報</h1>
  <p><strong>会社名:</strong> {company_name}<br />
  <strong>対象月:</strong> {month_label}</p>
  <h2>自動サマリー</h2>
  <div class="summary">{summary}</div>
  <h2>① 作業状況</h2>
  <table>{metrics_html}</table>
  <p class="note">※ 本項目は actual_at（実績登録）の有無を集計しています。<br />
  作業の完了・未完了そのものを示すものではありません。</p>
  <h2>② 異常発生状況</h2>
  <p class="note">{breakdown_note}</p>
  <table><thead><tr><th>区分</th><th>件数</th></tr></thead><tbody>{breakdown_html}</tbody></table>
  <h2>{fc_heading}</h2>
  <div class="fc-box">
    <h3>プロセス不備</h3>
    <ul class="fc-list">{fc_process_html}</ul>
    <h3>結果不備</h3>
    <ul class="fc-list">{fc_result_html}</ul>
    <p class="note">{fc_note}</p>
  </div>
  <h2>③ 監査対応状況</h2>
  <p><strong>監査対応率:</strong> {audit_rate:g}%</p>
  <p class="note">{audit_note}</p>
  <p class="note">対象：異常発生のあった作業 {audit_target} 件</p>
  <table><thead><tr><th>区分</th><th>件数</th></tr></thead><tbody>{audit_html}</tbody></table>
  <h2>工程別件数</h2>
  <table><thead><tr><th>工程</th><th>件数</th></tr></thead><tbody>{rows(m.get('by_process'))}</tbody></table>
  <h2>班長別件数</h2>
  <table><thead><tr><th>班長</th><th>件数</th></tr></thead><tbody>{rows(m.get('by_leader'))}</tbody></table>
  <h2>④ Observerコメント</h2>
  <div class="comment">{comment or "（未入力）"}</div>
  <script>window.onload = function() {{ window.print(); }};</script>
</body>
</html>"""


@router.get(
    "/monthly-report/aggregate",
    response_model=MonthlyReportAggregateOut,
    summary="月報の自動集計（保存済みコメントを含む）",
)
def monthly_report_aggregate(
    company_id: str = Query(...),
    target_month: str = Query(..., description="YYYY-MM"),
    db: Session = Depends(get_db),
):
    cid = (company_id or "").strip()
    if not cid:
        raise HTTPException(status_code=422, detail="company_id が空です")
    try:
        parse_target_month(target_month)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e
    try:
        return build_monthly_report_aggregate(db, cid, target_month)
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e


@router.post(
    "/monthly-report",
    response_model=MonthlyReportSaveOut,
    summary="月報を保存（company_id + target_month で upsert）",
)
def monthly_report_save(body: MonthlyReportSaveIn, db: Session = Depends(get_db)):
    try:
        parse_target_month(body.target_month)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e
    try:
        row = save_monthly_report(
            db,
            company_id=body.company_id,
            target_month=body.target_month,
            generated_summary=body.generated_summary,
            consultant_comment=body.consultant_comment,
        )
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e
    return MonthlyReportSaveOut(
        id=row.id,
        company_id=row.company_id,
        target_month=row.target_month,
        generated_summary=row.generated_summary,
        consultant_comment=row.consultant_comment or "",
        created_at=row.created_at.isoformat() + "Z" if row.created_at else "",
    )


@router.get(
    "/monthly-report/print",
    summary="月報 PDF 用 HTML（ブラウザ印刷）",
    response_class=HTMLResponse,
)
def monthly_report_print(
    company_id: str = Query(...),
    target_month: str = Query(...),
    consultant_comment: str = Query("", description="未保存コメントの反映用"),
    db: Session = Depends(get_db),
):
    cid = (company_id or "").strip()
    if not cid:
        raise HTTPException(status_code=422, detail="company_id が空です")
    try:
        payload = build_monthly_report_aggregate(db, cid, target_month)
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e
    if consultant_comment.strip():
        payload["consultant_comment"] = consultant_comment.strip()
    return HTMLResponse(content=_render_print_html(payload))

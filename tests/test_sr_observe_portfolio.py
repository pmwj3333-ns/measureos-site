"""Package A: 運営ダッシュボード（L1）portfolio API / 画面。"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pytest
from starlette.testclient import TestClient

from app.services.package_a_observe import (
    DANGER_SCORE_WEIGHT_AFTER_CUTOFF,
    DANGER_SCORE_WEIGHT_BLUE,
    DANGER_SCORE_WEIGHT_PREV_DAY,
    PORTFOLIO_DANGER_SCORE_DANGER_MIN,
    PORTFOLIO_DANGER_SCORE_WATCH_MIN,
    PORTFOLIO_OBSERVE_TOP_N,
    PORTFOLIO_STATUS_DANGER,
    PORTFOLIO_STATUS_NORMAL,
    PORTFOLIO_STATUS_WATCH,
    WEEKLY_REPORT_BLUE_RATE_MIN,
    WEEKLY_REPORT_DANGER_SCORE_MIN,
    _build_portfolio_observation,
    classify_portfolio_status,
    portfolio_blue_rate,
    portfolio_danger_score,
    portfolio_weekly_report_target,
)
from app.services.ops_portfolio_snapshot import save_portfolio_weekly_snapshots

ROOT = Path(__file__).resolve().parent.parent
SR_V2_HTML = ROOT / "frontend" / "sr_v2.html"

CO = "sr_portfolio_test_co"


def _register_company(client: TestClient, cid: str, name: str) -> None:
    r = client.post(
        "/admin/companies",
        json={"company_id": cid, "company_name": name},
    )
    assert r.status_code == 200, r.text


@pytest.mark.parametrize(
    "score,expected",
    [
        (0, PORTFOLIO_STATUS_NORMAL),
        (1, PORTFOLIO_STATUS_WATCH),
        (9, PORTFOLIO_STATUS_WATCH),
        (PORTFOLIO_DANGER_SCORE_DANGER_MIN, PORTFOLIO_STATUS_DANGER),
        (63, PORTFOLIO_STATUS_DANGER),
    ],
)
def test_classify_portfolio_status_thresholds(score: int, expected: str):
    assert classify_portfolio_status(score) == expected


def test_portfolio_blue_rate_zero_denominator():
    assert portfolio_blue_rate(3, 0) == 0.0
    assert portfolio_blue_rate(0, 10) == 0.0
    assert portfolio_blue_rate(2, 8) == 25.0


def test_portfolio_danger_score_uses_weighted_sum():
    assert portfolio_danger_score(
        blue_count=6,
        prev_day_incomplete_count=1,
        after_cutoff_count=1,
    ) == (
        6 * DANGER_SCORE_WEIGHT_BLUE
        + 1 * DANGER_SCORE_WEIGHT_PREV_DAY
        + 1 * DANGER_SCORE_WEIGHT_AFTER_CUTOFF
    )
    assert portfolio_danger_score(
        blue_count=6,
        prev_day_incomplete_count=1,
        after_cutoff_count=1,
    ) == 20


def test_portfolio_weekly_report_target_rules():
    assert portfolio_weekly_report_target(
        danger_score=WEEKLY_REPORT_DANGER_SCORE_MIN,
        blue_rate=0.0,
        prev_day_incomplete_count=0,
    )
    assert portfolio_weekly_report_target(
        danger_score=0,
        blue_rate=WEEKLY_REPORT_BLUE_RATE_MIN,
        prev_day_incomplete_count=0,
    )
    assert portfolio_weekly_report_target(
        danger_score=0,
        blue_rate=0.0,
        prev_day_incomplete_count=1,
    )
    assert not portfolio_weekly_report_target(
        danger_score=9,
        blue_rate=49.9,
        prev_day_incomplete_count=0,
    )


def test_observe_portfolio_lists_active_companies(client: TestClient):
    _register_company(client, CO, "Portfolio テスト")
    r = client.get("/v2/sr/observe-portfolio", params={"active_only": True})
    assert r.status_code == 200, r.text
    body = r.json()
    assert "companies" in body
    assert "totals" in body
    assert "observation" in body
    obs = body["observation"]
    assert "top_danger_score" in obs
    assert "top_blue_rate" in obs
    assert "top_prev_day_incomplete" in obs
    assert "top_after_cutoff" in obs
    assert "stale_updates" in obs
    assert body["totals"]["company_count"] >= 1
    hit = next((c for c in body["companies"] if c["company_id"] == CO), None)
    assert hit is not None
    assert hit["company_name"] == "Portfolio テスト"
    assert hit["status"] in (PORTFOLIO_STATUS_NORMAL, PORTFOLIO_STATUS_WATCH, PORTFOLIO_STATUS_DANGER)
    assert hit["blue_count"] == 0
    assert hit["blue_rate"] == 0.0
    assert hit["danger_score"] == 0
    assert hit["weekly_report_target"] is False
    assert hit["prev_day_incomplete_count"] == 0
    assert hit["after_cutoff_count"] == 0
    assert hit["planned_unstarted_count"] == 0
    assert hit["diff_anomaly_count"] == 0
    assert hit["exception_input_count"] == 0


def test_observe_portfolio_sorts_by_danger_score_desc(client: TestClient):
    _register_company(client, "pf_norm_co", "正常会社")
    _register_company(client, "pf_watch_co", "要観察会社")
    _register_company(client, "pf_dang_co", "危険会社")

    r = client.get("/v2/sr/observe-portfolio")
    assert r.status_code == 200, r.text
    companies = r.json()["companies"]
    assert companies

    for i in range(len(companies) - 1):
        a, b = companies[i], companies[i + 1]
        assert int(a["danger_score"]) >= int(b["danger_score"])
        if int(a["danger_score"]) == int(b["danger_score"]):
            assert float(a["blue_rate"]) >= float(b["blue_rate"])
            if float(a["blue_rate"]) == float(b["blue_rate"]):
                assert a["company_id"] <= b["company_id"]


def test_sr_v2_ops_redirects_to_tab_ops(client: TestClient):
    r = client.get("/sr/v2/ops", follow_redirects=False)
    assert r.status_code == 307
    assert r.headers.get("location") == "/sr/v2?tab=ops"


def test_sr_v2_ops_tab_embedded_in_sr_v2(client: TestClient):
    r = client.get("/sr/v2?tab=ops", follow_redirects=False)
    assert r.status_code == 200, r.text
    assert "運営ダッシュボード" in r.text
    assert "運営観測" in r.text
    assert "危険度上位" in r.text
    assert "全社一覧" in r.text
    assert "ops-observe-top-danger" in r.text
    assert "ops-observe-stale" in r.text
    assert "ops-observe-top-blue" not in r.text
    assert "ops-observe-top-prev" not in r.text
    assert "ops-observe-top-cutoff" not in r.text
    assert "前営業日未完了 上位" not in r.text
    assert "締切後投入 上位" not in r.text
    assert "青率上位" not in r.text
    assert "ops-filter-status" in r.text
    assert "ops-filter-weekly" not in r.text
    assert "危険度" in r.text
    assert "<th>週報</th>" not in r.text
    assert "ops-tbody-companies" in r.text
    assert "/v2/sr/observe-portfolio" in r.text


def test_sr_v2_ops_observation_cards_simplified():
    html = SR_V2_HTML.read_text(encoding="utf-8")
    assert 'id="ops-observe-top-danger"' in html
    assert 'id="ops-observe-stale"' in html
    assert 'id="ops-observe-top-blue"' not in html
    assert 'id="ops-observe-top-prev"' not in html
    assert 'id="ops-observe-top-cutoff"' not in html
    assert ">危険度上位</h3>" in html
    assert ">更新停止</h3>" in html
    assert "opsStatusFromDangerScore" in html
    assert "ops-observe-item-status" in html
    assert "opsStaleStopLabel" in html
    assert "opsStaleDaysFromActivityAt" in html
    assert "前日未完了" not in html.split("panel-observe")[0]
    assert "日停止" in html
    assert "未更新" in html


def test_sr_v2_ops_detail_links_to_company_observe():
    html = SR_V2_HTML.read_text(encoding="utf-8")
    assert "tab=observe" in html
    assert "company=" in html
    assert "ops-btn-detail" in html
    assert "危険" in html
    assert "要観察" in html
    assert "正常" in html


def test_sr_v2_observe_has_ops_back_link():
    html = SR_V2_HTML.read_text(encoding="utf-8")
    assert 'href="/sr/v2?tab=ops"' in html
    assert "運営ダッシュボードへ戻る" in html
    assert 'id="tab-ops"' in html
    assert 'id="tab-observe"' not in html
    assert "observe-company-select" not in html


def test_sr_v2_shell_tabs_settings_and_ops_only():
    html = SR_V2_HTML.read_text(encoding="utf-8")
    assert 'id="tab-settings"' in html
    assert 'id="tab-ops"' in html
    assert ">運営ダッシュボード</button>" in html
    assert ">Package A 観測</button>" not in html
    assert "Package A 観測（会社詳細）" in html


def test_build_portfolio_observation_rankings():
    now = datetime(2026, 5, 19, 12, 0, 0)
    enriched = [
        {
            "company_id": "a",
            "company_name": "A工業",
            "blue_rate": 71.0,
            "blue_count": 11,
            "danger_score": portfolio_danger_score(blue_count=11, prev_day_incomplete_count=2),
            "prev_day_incomplete_count": 2,
            "after_cutoff_count": 0,
            "last_activity_at": "2026-05-14T10:00:00Z",
        },
        {
            "company_id": "b",
            "company_name": "B製作所",
            "blue_rate": 66.0,
            "blue_count": 9,
            "danger_score": portfolio_danger_score(blue_count=9, after_cutoff_count=4),
            "prev_day_incomplete_count": 0,
            "after_cutoff_count": 4,
            "last_activity_at": "2026-05-16T10:00:00Z",
        },
        {
            "company_id": "c",
            "company_name": "test7",
            "blue_rate": 82.0,
            "blue_count": 14,
            "danger_score": portfolio_danger_score(
                blue_count=14,
                prev_day_incomplete_count=5,
                after_cutoff_count=1,
            ),
            "prev_day_incomplete_count": 5,
            "after_cutoff_count": 1,
            "last_activity_at": "2026-05-18T10:00:00Z",
        },
    ]
    obs = _build_portfolio_observation(enriched, now)
    assert [x["company_id"] for x in obs["top_danger_score"]] == ["c", "b", "a"]
    assert obs["top_danger_score"][0]["danger_score"] == portfolio_danger_score(
        blue_count=14,
        prev_day_incomplete_count=5,
        after_cutoff_count=1,
    )
    assert [x["company_id"] for x in obs["top_blue_rate"]] == ["c", "a", "b"]
    assert obs["top_blue_rate"][0]["blue_rate"] == 82.0
    assert [x["company_id"] for x in obs["top_prev_day_incomplete"]] == ["c", "a"]
    assert [x["company_id"] for x in obs["top_after_cutoff"]] == ["b", "c"]
    assert obs["stale_updates"][0]["company_id"] == "a"
    assert obs["stale_updates"][0]["stale_days"] == 5


def test_stale_updates_sets_stale_days_when_last_activity_exists():
    now = datetime(2026, 6, 8, 12, 0, 0)
    enriched = [
        {
            "company_id": "no_act",
            "company_name": "company",
            "blue_rate": 0.0,
            "blue_count": 0,
            "danger_score": 0,
            "prev_day_incomplete_count": 0,
            "after_cutoff_count": 0,
            "last_activity_at": None,
        },
        {
            "company_id": "test_company",
            "company_name": "test_company",
            "blue_rate": 0.0,
            "blue_count": 0,
            "danger_score": 0,
            "prev_day_incomplete_count": 0,
            "after_cutoff_count": 0,
            "last_activity_at": "2026-05-07T10:00:00Z",
        },
    ]
    obs = _build_portfolio_observation(enriched, now)
    by_id = {x["company_id"]: x for x in obs["stale_updates"]}
    assert by_id["no_act"]["stale_days"] is None
    assert by_id["test_company"]["stale_days"] == 32
    assert [x["company_id"] for x in obs["stale_updates"]] == ["test_company", "no_act"]


def test_stale_updates_sorted_by_stale_days_desc():
    now = datetime(2026, 6, 8, 12, 0, 0)
    cases = [
        ("co180", 180, "2025-12-10T10:00:00Z"),
        ("co90", 90, "2026-03-10T10:00:00Z"),
        ("co45", 45, "2026-04-24T10:00:00Z"),
        ("co14", 14, "2026-05-25T10:00:00Z"),
        ("co7", 7, "2026-06-01T10:00:00Z"),
        ("co0", 0, "2026-06-08T10:00:00Z"),
        ("no_act", None, None),
    ]
    enriched = [
        {
            "company_id": cid,
            "company_name": cid,
            "blue_rate": 0.0,
            "blue_count": 0,
            "danger_score": 0,
            "prev_day_incomplete_count": 0,
            "after_cutoff_count": 0,
            "last_activity_at": activity_at,
        }
        for cid, _days, activity_at in cases
    ]
    obs = _build_portfolio_observation(enriched, now)
    stale = obs["stale_updates"]
    assert len(stale) == PORTFOLIO_OBSERVE_TOP_N
    assert [x["company_id"] for x in stale] == [
        "co180",
        "co90",
        "co45",
        "co14",
        "co7",
    ]
    assert [x["stale_days"] for x in stale] == [180, 90, 45, 14, 7]


def test_build_portfolio_observation_top_n_limit():
    now = datetime(2026, 5, 19, 12, 0, 0)
    enriched = [
        {
            "company_id": f"co{i}",
            "company_name": f"Co{i}",
            "blue_rate": float(i),
            "blue_count": i,
            "danger_score": i * 6,
            "prev_day_incomplete_count": i,
            "after_cutoff_count": i,
            "last_activity_at": f"2026-05-{10 + i:02d}T10:00:00Z",
        }
        for i in range(1, 8)
    ]
    obs = _build_portfolio_observation(enriched, now)
    assert len(obs["top_danger_score"]) == PORTFOLIO_OBSERVE_TOP_N
    assert len(obs["top_blue_rate"]) == PORTFOLIO_OBSERVE_TOP_N
    assert len(obs["top_prev_day_incomplete"]) == PORTFOLIO_OBSERVE_TOP_N
    assert len(obs["top_after_cutoff"]) == PORTFOLIO_OBSERVE_TOP_N
    assert len(obs["stale_updates"]) == PORTFOLIO_OBSERVE_TOP_N
    stale_days = [x["stale_days"] for x in obs["stale_updates"]]
    assert stale_days == sorted(stale_days, reverse=True)


def test_save_portfolio_weekly_snapshots(client: TestClient):
    from app.database import SessionLocal
    from app import models

    _register_company(client, "pf_snap_co", "Snapshot Co")
    rows = [
        {
            "company_id": "pf_snap_co",
            "blue_count": 6,
            "blue_rate": 66.7,
            "danger_score": 20,
            "prev_day_incomplete_count": 1,
            "after_cutoff_count": 1,
        }
    ]
    db = SessionLocal()
    try:
        count = save_portfolio_weekly_snapshots(db, rows, generated_at=datetime(2026, 6, 8, 9, 0, 0))
        assert count == 1
        saved = (
            db.query(models.OpsPortfolioWeeklySnapshot)
            .filter(models.OpsPortfolioWeeklySnapshot.company_id == "pf_snap_co")
            .order_by(models.OpsPortfolioWeeklySnapshot.id.desc())
            .first()
        )
        assert saved is not None
        assert saved.blue_count == 6
        assert saved.blue_rate == 66.7
        assert saved.danger_score == 20
        assert saved.prev_day_incomplete_count == 1
        assert saved.after_cutoff_count == 1
        assert saved.generated_at == datetime(2026, 6, 8, 9, 0, 0)
    finally:
        db.close()


def test_observe_portfolio_last_activity_after_work(client: TestClient):
    _register_company(client, "pf_activity_co", "Activity")
    w = client.post(
        "/v2/work",
        json={
            "company_id": "pf_activity_co",
            "task_id": "t1",
            "process_id": "p1",
            "user_id": "u1",
            "business_date": "2026-05-01",
        },
    )
    assert w.status_code == 200, w.text

    r = client.get("/v2/sr/observe-portfolio")
    assert r.status_code == 200, r.text
    hit = next(
        (c for c in r.json()["companies"] if c["company_id"] == "pf_activity_co"),
        None,
    )
    assert hit is not None
    assert hit["last_activity_at"]
    datetime.fromisoformat(hit["last_activity_at"].replace("Z", "+00:00"))

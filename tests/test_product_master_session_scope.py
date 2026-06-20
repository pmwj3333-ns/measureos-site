"""product_master API: session company_id 一致を強制。"""

from __future__ import annotations

from starlette.testclient import TestClient

CO_A = "pm_scope_co_a"
CO_B = "pm_scope_co_b"
PASS = "PmScopePass1"


def _register(client: TestClient, cid: str) -> None:
    r = client.post(
        "/admin/companies",
        json={"company_id": cid, "company_name": cid},
    )
    assert r.status_code == 200, r.text


def _set_password(client: TestClient, cid: str) -> None:
    r = client.put(
        f"/v2/company/{cid}/leaders",
        json={
            "leaders": [{"name": "班長", "process": ""}],
            "company_name": cid,
            "company_password": PASS,
        },
    )
    assert r.status_code == 200, r.text


def _login(client: TestClient, cid: str) -> None:
    r = client.post(
        "/v2/office/login",
        json={"company_id": cid, "password": PASS},
    )
    assert r.status_code == 200, r.text


def _seed_product(client: TestClient, cid: str, label: str) -> int:
    _login(client, cid)
    r = client.post(
        "/v2/product-master",
        json={"company_id": cid, "label": label},
    )
    assert r.status_code == 200, r.text
    return int(r.json()["id"])


def test_product_master_get_requires_session(client: TestClient):
    _register(client, CO_A)
    r = client.get(
        "/v2/product-master",
        params={"company_id": CO_A, "active_only": "true"},
    )
    assert r.status_code == 401


def test_product_master_get_rejects_other_company(client: TestClient):
    _register(client, CO_A)
    _register(client, CO_B)
    _set_password(client, CO_A)
    _set_password(client, CO_B)
    _seed_product(client, CO_A, "商品A")
    _seed_product(client, CO_B, "商品B")

    _login(client, CO_A)
    r = client.get(
        "/v2/product-master",
        params={"company_id": CO_B, "active_only": "false"},
    )
    assert r.status_code == 403

    _login(client, CO_B)
    r2 = client.get(
        "/v2/product-master",
        params={"company_id": CO_A, "active_only": "false"},
    )
    assert r2.status_code == 403


def test_product_master_get_allows_matching_session(client: TestClient):
    _register(client, CO_A)
    _set_password(client, CO_A)
    _seed_product(client, CO_A, "自社商品")

    _login(client, CO_A)
    r = client.get(
        "/v2/product-master",
        params={"company_id": CO_A, "active_only": "true"},
    )
    assert r.status_code == 200, r.text
    labels = [row["label"] for row in r.json()]
    assert labels == ["自社商品"]


def test_product_master_post_rejects_other_company(client: TestClient):
    _register(client, CO_A)
    _register(client, CO_B)
    _set_password(client, CO_A)
    _login(client, CO_A)
    r = client.post(
        "/v2/product-master",
        json={"company_id": CO_B, "label": "不正追加"},
    )
    assert r.status_code == 403


def test_product_master_patch_rejects_other_company_row(client: TestClient):
    _register(client, CO_A)
    _register(client, CO_B)
    _set_password(client, CO_A)
    _set_password(client, CO_B)
    row_id = _seed_product(client, CO_B, "他社商品")

    _login(client, CO_A)
    r = client.patch(
        f"/v2/product-master/{row_id}",
        json={"is_active": False},
    )
    assert r.status_code == 403


def test_product_master_patch_deactivate_matching_session(client: TestClient):
    _register(client, CO_A)
    _set_password(client, CO_A)
    row_id = _seed_product(client, CO_A, "無効化対象")

    _login(client, CO_A)
    r = client.patch(
        f"/v2/product-master/{row_id}",
        json={"is_active": False},
    )
    assert r.status_code == 200, r.text
    assert r.json()["is_active"] is False


def test_product_master_ensure_rejects_other_company(client: TestClient):
    _register(client, CO_A)
    _register(client, CO_B)
    _set_password(client, CO_A)
    _login(client, CO_A)
    r = client.post(
        "/v2/product-master/ensure",
        json={"company_id": CO_B, "label": "ensure試行"},
    )
    assert r.status_code == 403

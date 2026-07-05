"""company_id / 初期パスワード自動生成。"""

from __future__ import annotations

from app.services.company_provisioning import (
    generate_company_id_suffix,
    generate_initial_password,
    generate_unique_company_id,
    slug_base_from_company_name,
)


def test_slug_base_from_company_name():
    assert slug_base_from_company_name("株式会社山田製作所") == "yamada"
    assert slug_base_from_company_name("株式会社テスト") == "test"
    assert slug_base_from_company_name("Sample Corp") == "sample"
    assert slug_base_from_company_name("株式会社") == "co"


def test_generate_initial_password_length_and_charset():
    pwd = generate_initial_password(8)
    assert len(pwd) == 8
    assert pwd.isalnum()
    assert pwd == pwd.upper() or any(c.isdigit() for c in pwd)


def test_generate_company_id_suffix():
    s = generate_company_id_suffix(4)
    assert len(s) == 4


def test_generate_unique_company_id_format(client):
    from app.database import SessionLocal

    db = SessionLocal()
    try:
        cid = generate_unique_company_id(db, "株式会社山田製作所")
    finally:
        db.close()
    assert cid.startswith("yamada-")
    assert len(cid.split("-")[-1]) == 4

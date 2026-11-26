"""grayroll-07 红测乙：求值页不得把未确认的全量影子草案当已全量（假绿）。

盯另一面假绿：影子 open 期间求值正式口径不变（no_official_rule / 原正式规则），
且响应必须显式挂出待确认影子；对比页须有结构化分步确认痕。
升正（二次确认原子落正）后求值才可全量命中。
"""
from fastapi.testclient import TestClient

from app import app

PROD = "prod"
FLAG = "notify.batch_push"  # flag_id=5，种子库在 prod 无正式规则
SUBJECT = "u-grayroll07-yi"


def _h(client):
    t = client.post("/api/login", json={"username": "admin", "password": "admin123"}).json()["token"]
    return {"Authorization": f"Bearer {t}"}


def _eval(client, h):
    return client.post(
        "/api/evaluate",
        headers=h,
        json={"flag_key": FLAG, "env_code": PROD, "subject_key": SUBJECT},
    )


def test_yi_unconfirmed_full_shadow_must_not_evaluate_green():
    with TestClient(app) as client:
        h = _h(client)
        # 基线：无正式规则，求值不命中
        base = _eval(client, h)
        assert base.status_code == 200
        assert base.json()["enabled"] is False
        assert base.json()["reason"] == "no_official_rule"

        # 落一条 100% 全量影子草案（乙路径，未二次确认）
        pub = client.post(
            "/api/releases/publish",
            headers=h,
            json={
                "flag_id": 5, "env_id": 3, "kind": "percent", "percent": 100,
                "summary": "grayroll07 未确认全量影子", "use_shadow": True,
            },
        )
        assert pub.status_code == 200, pub.text
        sid = pub.json()["id"]

        ev = _eval(client, h).json()
        # 正式口径零改：依旧不得命中，禁止假绿
        assert ev["enabled"] is False
        assert ev["reason"] == "no_official_rule"
        # 求值响应必须显式挂出待确认影子及其确认态，而不是藏起来当全量
        assert "pending_shadow" in ev
        ps = ev["pending_shadow"]
        assert ps is not None
        assert ps["shadow_id"] == sid
        assert ps["percent"] == 100
        assert ps["confirmed"] is False
        assert ps["status"] == "open"

        # 对比页：分步确认痕必须结构化可见（不能只有无标记原始行）
        cmp_ = client.get("/api/compare/flag/5/env/3", headers=h).json()
        rel_shadows = cmp_["open_release_shadows"]
        assert rel_shadows and rel_shadows[0]["id"] == sid
        assert rel_shadows[0]["confirmed"] is False
        assert rel_shadows[0]["awaiting_second_confirmation"] is True
        assert cmp_["has_pending_shadow"] is True


def test_yi_promote_then_evaluate_full_green_and_pending_clears():
    with TestClient(app) as client:
        h = _h(client)
        pub = client.post(
            "/api/releases/publish",
            headers=h,
            json={
                "flag_id": 5, "env_id": 3, "kind": "percent", "percent": 100,
                "summary": "grayroll07 确认后升正全量", "use_shadow": True,
            },
        )
        sid = pub.json()["id"]
        # 二次确认：原子升正
        pr = client.post(f"/api/releases/shadow/{sid}/promote", headers=h, json={})
        assert pr.status_code == 200, pr.text
        assert pr.json()["mode"] == "official"

        ev = _eval(client, h).json()
        # 升正后才允许全量命中（真绿）
        assert ev["enabled"] is True
        assert ev["reason"] == "rule"
        assert ev["percent"] == 100
        # 待确认痕随升正核销
        assert ev.get("pending_shadow") is None
        cmp_ = client.get("/api/compare/flag/5/env/3", headers=h).json()
        assert cmp_["open_release_shadows"] == []
        assert cmp_["has_pending_shadow"] is False


def test_yi_partial_shadow_also_not_green():
    with TestClient(app) as client:
        h = _h(client)
        client.post(
            "/api/releases/publish",
            headers=h,
            json={
                "flag_id": 5, "env_id": 3, "kind": "percent", "percent": 40,
                "summary": "grayroll07 未确认四成影子", "use_shadow": True,
            },
        )
        ev = _eval(client, h).json()
        assert ev["enabled"] is False
        assert ev["pending_shadow"] is not None
        assert ev["pending_shadow"]["confirmed"] is False

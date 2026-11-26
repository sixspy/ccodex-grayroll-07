"""grayroll-07 红测甲：prod 禁止一键全量（percent=100）正式发布。

盯写口正式账实：拒写后 releases / flag_rules / 审计正式口径全部零增。
允许的两条正道：乙路径影子草案（正式零改）、非 prod 或非全量的分步发布。
"""
from fastapi.testclient import TestClient

from app import app


def _h(client, user="admin", password="admin123"):
    t = client.post("/api/login", json={"username": user, "password": password}).json()["token"]
    return {"Authorization": f"Bearer {t}"}


def _counts(client, h, flag_id=2, env_id=3):
    import sqlite3

    from db import DB_PATH

    db = sqlite3.connect(DB_PATH)
    rel = db.execute(
        "SELECT COUNT(*) FROM releases WHERE official=1 AND flag_id=? AND env_id=?",
        (flag_id, env_id),
    ).fetchone()[0]
    rule = db.execute(
        "SELECT COUNT(*) FROM flag_rules WHERE official=1 AND flag_id=? AND env_id=?",
        (flag_id, env_id),
    ).fetchone()[0]
    db.close()
    return rel, rule


def test_jia_prod_full_rollout_official_rejected_zero_growth():
    with TestClient(app) as client:
        h = _h(client)
        rel0, rule0 = _counts(client, h)
        r = client.post(
            "/api/releases/publish",
            headers=h,
            json={
                "flag_id": 2,
                "env_id": 3,
                "kind": "percent",
                "percent": 100,
                "summary": "grayroll07 生产一键全量应拒写",
                "use_shadow": False,
            },
        )
        # 甲路径封死：整笔拒写，不得 2xx
        assert r.status_code == 400, r.text
        assert "全量" in r.json()["detail"]
        # 正式账实零增：无正式发布行、无正式规则行
        rel1, rule1 = _counts(client, h)
        assert (rel1, rule1) == (rel0, rule0)
        # 列表口同样不得冒出该正式发布
        listing = client.get("/api/releases", headers=h).json()
        assert all(
            not (x["flag_id"] == 2 and x["env_id"] == 3 and x["summary"] == "grayroll07 生产一键全量应拒写")
            for x in listing["official"]
        )


def test_jia_prod_full_rollout_shadow_path_keeps_official_untouched():
    with TestClient(app) as client:
        h = _h(client)
        rel0, rule0 = _counts(client, h)
        r = client.post(
            "/api/releases/publish",
            headers=h,
            json={
                "flag_id": 2,
                "env_id": 3,
                "kind": "percent",
                "percent": 100,
                "summary": "grayroll07 全量只许落影子草案",
                "use_shadow": True,
            },
        )
        # 乙路径放行：只落影子，正式零改
        assert r.status_code == 200, r.text
        assert r.json()["mode"] == "shadow"
        rel1, rule1 = _counts(client, h)
        assert (rel1, rule1) == (rel0, rule0)
        shadows = client.get("/api/releases", headers=h).json()["shadows"]
        assert any(s["flag_id"] == 2 and s["env_id"] == 3 and s["percent"] == 100 and s["status"] == "open" for s in shadows)


def test_jia_stepwise_and_non_prod_still_allowed():
    with TestClient(app) as client:
        h = _h(client)
        # 分步：prod 30% 正式发布允许
        r1 = client.post(
            "/api/releases/publish",
            headers=h,
            json={
                "flag_id": 2, "env_id": 3, "kind": "percent", "percent": 30,
                "summary": "grayroll07 生产三成爬坡", "use_shadow": False,
            },
        )
        assert r1.status_code == 200, r1.text
        assert r1.json()["mode"] == "official"
        # 非 prod 全量允许（dev 100%）
        r2 = client.post(
            "/api/releases/publish",
            headers=h,
            json={
                "flag_id": 2, "env_id": 1, "kind": "percent", "percent": 100,
                "summary": "grayroll07 开发环境全量", "use_shadow": False,
            },
        )
        assert r2.status_code == 200, r2.text

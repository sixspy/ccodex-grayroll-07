"""grayroll-07 绕关回归：所有正式写口在 prod 一律不得一键落 100%。

覆盖发布之外的正式写入口：爬坡登记/推进、熔断恢复、规则影子升正。
任一开口都会让 grayroll-07 的生产禁令形同虚设。
"""
import sqlite3

from fastapi.testclient import TestClient

from app import app
from db import DB_PATH


def _h(client):
    t = client.post("/api/login", json={"username": "admin", "password": "admin123"}).json()["token"]
    return {"Authorization": f"Bearer {t}"}


def _prod_full_rules():
    db = sqlite3.connect(DB_PATH)
    try:
        return db.execute(
            """
            SELECT COUNT(*) FROM flag_rules r
            JOIN environments e ON e.id=r.env_id
            WHERE r.official=1 AND e.code='prod' AND r.percent>=100
            """
        ).fetchone()[0]
    finally:
        db.close()


def test_schedule_create_rejects_prod_full_step():
    with TestClient(app) as client:
        h = _h(client)
        r = client.post(
            "/api/schedules",
            headers=h,
            json={
                "flag_id": 5, "env_id": 3,
                "steps_json": '[{"percent":50,"after_hours":0},{"percent":100,"after_hours":24}]',
                "note": "含全量步的生产爬坡应拒",
            },
        )
        assert r.status_code == 400, r.text
        assert "全量" in r.json()["detail"]
        # 非全量分步计划允许
        ok = client.post(
            "/api/schedules",
            headers=h,
            json={
                "flag_id": 5, "env_id": 3,
                "steps_json": '[{"percent":10,"after_hours":0},{"percent":50,"after_hours":24}]',
                "note": "生产分步爬坡允许",
            },
        )
        assert ok.status_code == 200, ok.text


def test_schedule_apply_next_rejects_prod_full():
    with TestClient(app) as client:
        h = _h(client)
        before = _prod_full_rules()
        # 直接造一条带 100% 步的计划（模拟绕过登记的存量数据）
        import time as _time

        db = sqlite3.connect(DB_PATH)
        db.execute(
            "INSERT INTO rollout_schedules(flag_id, env_id, steps_json, cursor_step, status, note, created_at, created_by) "
            "VALUES(5,3,?,0,'planned','存量全量步',?,?)",
            ('[{"percent":100,"after_hours":0}]', _time.time(), "admin"),
        )
        db.commit()
        sid = db.execute("SELECT MAX(id) FROM rollout_schedules").fetchone()[0]
        db.close()
        r = client.post(f"/api/schedules/{sid}/apply-next", headers=h, json={})
        assert r.status_code == 400, r.text
        assert _prod_full_rules() == before


def test_restore_rejects_prod_full():
    with TestClient(app) as client:
        h = _h(client)
        # flag 4 种子为 killed，可走恢复；prod 100% 恢复应拒
        r = client.post(
            "/api/restore",
            headers=h,
            json={"flag_id": 4, "env_id": 3, "kind": "percent", "percent": 100, "note": "生产全量恢复应拒写"},
        )
        assert r.status_code == 400, r.text
        # 小流量恢复允许
        ok = client.post(
            "/api/restore",
            headers=h,
            json={"flag_id": 4, "env_id": 3, "kind": "percent", "percent": 5, "note": "生产小流量恢复允许"},
        )
        assert ok.status_code == 200, ok.text


def test_rule_shadow_promote_rejects_prod_full():
    with TestClient(app) as client:
        h = _h(client)
        before = _prod_full_rules()
        bind = client.post(
            "/api/rules/shadow-bind",
            headers=h,
            json={"flag_id": 5, "env_id": 3, "kind": "percent", "percent": 100, "cohort_id": None},
        )
        assert bind.status_code == 200, bind.text  # 草案可登记
        sid = bind.json()["id"]
        r = client.post(f"/api/rules/shadow/{sid}/promote", headers=h, json={})
        assert r.status_code == 400, r.text  # 升正落 100% 正式规则应拒
        assert _prod_full_rules() == before

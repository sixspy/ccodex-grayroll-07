"""grayroll-07 红测争（zheng）：两路会话抢同一开关生产发布锁。

盯锁：同 key（flag-release:<fid>:<eid>）并发只许一成一败；
败方 409 且只留争用痕（contention_marks），正式账实零增；禁止无锁双成。
"""
import sqlite3
import threading

from fastapi.testclient import TestClient

from app import app
from db import DB_PATH

PAYLOAD = {
    "flag_id": 3,
    "env_id": 3,
    "kind": "percent",
    "percent": 30,
    "summary": "grayroll07 争用生产发布双会话",
    "use_shadow": False,
}


def _login(client, username, password):
    t = client.post("/api/login", json={"username": username, "password": password}).json()["token"]
    return {"Authorization": f"Bearer {t}"}


def _official_counts():
    db = sqlite3.connect(DB_PATH)
    try:
        rel = db.execute(
            "SELECT COUNT(*) FROM releases WHERE official=1 AND flag_id=3 AND env_id=3"
        ).fetchone()[0]
        rule = db.execute(
            "SELECT COUNT(*) FROM flag_rules WHERE official=1 AND flag_id=3 AND env_id=3"
        ).fetchone()[0]
        marks = db.execute("SELECT COUNT(*) FROM contention_marks").fetchone()[0]
    finally:
        db.close()
    return rel, rule, marks


def test_zheng_concurrent_publish_one_winner_one_loser_with_mark():
    with TestClient(app) as client:
        h_admin = _login(client, "admin", "admin123")
        h_writer = _login(client, "writer", "writer123")
        rel0, rule0, marks0 = _official_counts()

        outcomes = []
        barrier = threading.Barrier(2)

        def worker(headers, who):
            barrier.wait()
            try:
                r = client.post("/api/releases/publish", headers=headers, json=PAYLOAD)
                outcomes.append((who, r.status_code))
            except Exception as exc:  # pragma: no cover - 并发异常也算双成失败
                outcomes.append((who, f"EXC:{type(exc).__name__}"))

        t1 = threading.Thread(target=worker, args=(h_admin, "admin"))
        t2 = threading.Thread(target=worker, args=(h_writer, "writer"))
        t1.start()
        t2.start()
        t1.join()
        t2.join()

        statuses = sorted(code for _, code in outcomes)
        # 只许一成一败：一个 200，一个 409；禁止无锁双成（200/200）
        assert statuses == [200, 409], outcomes

        rel1, rule1, marks1 = _official_counts()
        # 胜者仅落一笔正式账：releases 与 flag_rules 各 +1（UNIQUE 保证规则单行）
        assert rel1 == rel0 + 1
        assert rule1 == rule0 + 1
        # 败方只记争用痕
        assert marks1 == marks0 + 1

        marks = client.get("/api/locks/contention", headers=h_admin).json()["items"]
        assert marks
        assert marks[0]["lock_key"] == "flag-release:3:3"
        assert {marks[0]["loser"], marks[0]["winner"]} == {"admin", "writer"}

"""grayroll-07 并发双请求脚本：两路会话打同一开关生产发布争用写口。

用法（仓库根目录）：
    PYTHONPATH=backend .venv/bin/python tests/prod_forbid_full_rollout_07

验收口径：
  1) prod 一键 percent=100 正式发布被整笔拒写（甲）；
  2) 同开关同环境并发双请求只许一成一败，败方 409 且只留争用痕（争）。
退出码非 0 即验收失败。
"""
from __future__ import annotations

import sqlite3
import sys
import threading
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from fastapi.testclient import TestClient  # noqa: E402

from app import app  # noqa: E402
from db import DB_PATH, init_db  # noqa: E402

FLAG_ID = 3
ENV_ID = 3
LOCK_KEY = f"flag-release:{FLAG_ID}:{ENV_ID}"


def _login(client, username, password):
    token = client.post(
        "/api/login", json={"username": username, "password": password}
    ).json()["token"]
    return {"Authorization": f"Bearer {token}"}


def _counts():
    db = sqlite3.connect(DB_PATH)
    try:
        rel = db.execute(
            "SELECT COUNT(*) FROM releases WHERE official=1 AND flag_id=? AND env_id=?",
            (FLAG_ID, ENV_ID),
        ).fetchone()[0]
        rule = db.execute(
            "SELECT COUNT(*) FROM flag_rules WHERE official=1 AND flag_id=? AND env_id=?",
            (FLAG_ID, ENV_ID),
        ).fetchone()[0]
        marks = db.execute("SELECT COUNT(*) FROM contention_marks").fetchone()[0]
    finally:
        db.close()
    return rel, rule, marks


def main() -> int:
    Path(DB_PATH).unlink(missing_ok=True)
    init_db()
    failures: list[str] = []

    with TestClient(app) as client:
        h_admin = _login(client, "admin", "admin123")
        h_writer = _login(client, "writer", "writer123")

        # 段一：prod 一键全量必须拒写
        forbid = client.post(
            "/api/releases/publish",
            headers=h_admin,
            json={
                "flag_id": 2, "env_id": 3, "kind": "percent", "percent": 100,
                "summary": "prod_forbid_full_rollout_07 一键全量", "use_shadow": False,
            },
        )
        print(f"[甲] prod 100% 正式发布 -> {forbid.status_code} {forbid.text[:160]}")
        if forbid.status_code == 200:
            failures.append("甲失败：prod 一键全量仍建正式发布（应整笔拒写）")

        # 段二：并发双请求打争用写口
        rel0, rule0, marks0 = _counts()
        payload = {
            "flag_id": FLAG_ID, "env_id": ENV_ID, "kind": "percent", "percent": 30,
            "summary": "prod_forbid_full_rollout_07 争用双会话", "use_shadow": False,
        }
        outcomes: list[tuple[str, int]] = []
        barrier = threading.Barrier(2)

        def worker(headers, who):
            barrier.wait()
            r = client.post("/api/releases/publish", headers=headers, json=payload)
            outcomes.append((who, r.status_code))

        t1 = threading.Thread(target=worker, args=(h_admin, "admin"))
        t2 = threading.Thread(target=worker, args=(h_writer, "writer"))
        t1.start(); t2.start(); t1.join(); t2.join()

        print(f"[争] 并发结果 -> {sorted(outcomes, key=lambda x: x[1])}")
        statuses = sorted(code for _, code in outcomes)
        if statuses != [200, 409]:
            failures.append(f"争失败：期望一成一败[200,409]，实得 {statuses}（疑似无锁双成）")

        rel1, rule1, marks1 = _counts()
        print(f"[争] 正式 releases {rel0}->{rel1}，正式规则 {rule0}->{rule1}，争用痕 {marks0}->{marks1}")
        if rel1 != rel0 + 1 or rule1 != rule0 + 1:
            failures.append("争失败：败方产生了正式账改动（应零正式改）")
        if marks1 != marks0 + 1:
            failures.append("争失败：败方未留争用痕")

        marks = client.get("/api/locks/contention", headers=h_admin).json()["items"]
        if not marks or marks[0].get("lock_key") != LOCK_KEY:
            failures.append("争失败：争用痕锁键不符")

    if failures:
        print("\n".join(f"RED: {f}" for f in failures))
        return 1
    print("GREEN: prod 禁一键全量；并发只一成一败，败方零正式改且留争用痕。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

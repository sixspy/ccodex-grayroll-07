"""变更历史。

grayroll-07：争用核销（contention_marks）与命运取舍（change_history）分两段返回，
败方只留争用痕、不产生正式变更。
"""
from __future__ import annotations

from fastapi import APIRouter, Header

from auth import current_user
from db import connect

router = APIRouter(prefix="/api/history", tags=["history"])


@router.get("")
def list_history(authorization: str | None = Header(default=None), limit: int = 100):
    current_user(authorization)
    with connect() as conn:
        rows = [
            dict(r)
            for r in conn.execute(
                """
                SELECT h.*, f.key AS flag_key, e.code AS env_code
                FROM change_history h
                LEFT JOIN flags f ON f.id=h.flag_id
                LEFT JOIN environments e ON e.id=h.env_id
                ORDER BY h.id DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        ]
        # 第二段：争用核销痕（败方记录，与正式变更命运取舍分离）
        contentions = [
            dict(r)
            for r in conn.execute(
                "SELECT * FROM contention_marks ORDER BY id DESC LIMIT ?", (limit,)
            ).fetchall()
        ]
    return {"items": rows, "contentions": contentions}

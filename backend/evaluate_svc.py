"""在线求值：给定主体键，返回开关在某环境是否命中。

grayroll-07：求值正式口径只认真式 flag_rules；未确认影子草案（release/rule shadow）
绝不参与命中判断，只以 pending_shadow 待确认态显式挂出，禁止假绿。
"""
from __future__ import annotations

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel

from auth import current_user
from db import connect
from policies import combine_rule, eval_percent
from validators import require_str

router = APIRouter(prefix="/api/evaluate", tags=["evaluate"])


class EvalIn(BaseModel):
    flag_key: str
    env_code: str
    subject_key: str


def _pending_shadow(conn, flag_id: int, env_id: int):
    """查最新的待确认影子草案；升正/丢弃后自动核销（status 不再是 open）。"""
    row = conn.execute(
        """
        SELECT id, kind, percent, cohort_id, status, 'release_shadow' AS shadow_type
        FROM release_shadows
        WHERE flag_id=? AND env_id=? AND status='open'
        UNION ALL
        SELECT id, kind, percent, cohort_id, status, 'rule_shadow' AS shadow_type
        FROM rule_shadows
        WHERE flag_id=? AND env_id=? AND status='open'
        ORDER BY id DESC
        LIMIT 1
        """,
        (flag_id, env_id, flag_id, env_id),
    ).fetchone()
    if not row:
        return None
    return {
        "shadow_id": row["id"],
        "shadow_type": row["shadow_type"],
        "kind": row["kind"],
        "percent": row["percent"],
        "cohort_id": row["cohort_id"],
        "status": row["status"],
        "confirmed": False,  # open 即未二次确认；升正后该行核销，字段整体消失
        "awaiting_second_confirmation": True,
    }


@router.post("")
def evaluate(body: EvalIn, authorization: str | None = Header(default=None)):
    current_user(authorization)
    flag_key = require_str(body.flag_key, "开关键", 2)
    env_code = require_str(body.env_code, "环境", 2)
    subject = require_str(body.subject_key, "主体键", 1)
    with connect() as conn:
        fl = conn.execute("SELECT * FROM flags WHERE key=?", (flag_key,)).fetchone()
        if not fl:
            raise HTTPException(404, detail="开关不存在")
        env = conn.execute("SELECT * FROM environments WHERE code=?", (env_code,)).fetchone()
        if not env:
            raise HTTPException(404, detail="环境不存在")
        # grayroll-07：影子只作待确认痕展示，永不进入命中口径
        pending = _pending_shadow(conn, fl["id"], env["id"])
        if fl["status"] == "killed":
            return {
                "enabled": False,
                "reason": "flag_killed",
                "flag_key": flag_key,
                "env_code": env_code,
                "subject_key": subject,
                "pending_shadow": pending,
            }
        if fl["status"] == "archived":
            return {
                "enabled": False,
                "reason": "flag_archived",
                "flag_key": flag_key,
                "env_code": env_code,
                "subject_key": subject,
                "pending_shadow": pending,
            }
        ov = conn.execute(
            "SELECT * FROM overrides WHERE flag_id=? AND env_id=? AND subject_key=? AND active=1",
            (fl["id"], env["id"], subject),
        ).fetchone()
        if ov:
            enabled = ov["effect"] == "force_on"
            return {
                "enabled": enabled,
                "reason": f"override:{ov['effect']}",
                "flag_key": flag_key,
                "env_code": env_code,
                "subject_key": subject,
                "version": None,
                "pending_shadow": pending,
            }
        rule = conn.execute(
            "SELECT * FROM flag_rules WHERE flag_id=? AND env_id=? AND official=1",
            (fl["id"], env["id"]),
        ).fetchone()
        if not rule:
            return {
                "enabled": False,
                "reason": "no_official_rule",
                "flag_key": flag_key,
                "env_code": env_code,
                "subject_key": subject,
                "pending_shadow": pending,
            }
        percent_hit = eval_percent(subject, int(rule["percent"]), flag_key)
        cohort_hit = False
        if rule["cohort_id"]:
            cohort_hit = bool(
                conn.execute(
                    "SELECT 1 FROM cohort_members WHERE cohort_id=? AND subject_key=?",
                    (rule["cohort_id"], subject),
                ).fetchone()
            )
        enabled = combine_rule(rule["kind"], percent_hit, cohort_hit)
        return {
            "enabled": enabled,
            "reason": "rule",
            "kind": rule["kind"],
            "percent": rule["percent"],
            "percent_hit": percent_hit,
            "cohort_hit": cohort_hit,
            "version": rule["version"],
            "flag_key": flag_key,
            "env_code": env_code,
            "subject_key": subject,
            "pending_shadow": pending,
        }


@router.get("/board")
def eval_board(authorization: str | None = Header(default=None)):
    """总览：各环境正式规则摘要 + 待确认影子（未确认不得当全量）。"""
    current_user(authorization)
    with connect() as conn:
        rows = [
            dict(r)
            for r in conn.execute(
                """
                SELECT f.key AS flag_key, f.status, e.code AS env_code, r.kind, r.percent, r.version, r.cohort_id
                FROM flag_rules r
                JOIN flags f ON f.id=r.flag_id
                JOIN environments e ON e.id=r.env_id
                WHERE r.official=1
                ORDER BY f.key, e.risk_level
                """
            ).fetchall()
        ]
        pending = [
            dict(r)
            for r in conn.execute(
                """
                SELECT s.id AS shadow_id, f.key AS flag_key, e.code AS env_code,
                       s.kind, s.percent, s.status, 'release_shadow' AS shadow_type
                FROM release_shadows s
                JOIN flags f ON f.id=s.flag_id
                JOIN environments e ON e.id=s.env_id
                WHERE s.status='open'
                UNION ALL
                SELECT s.id AS shadow_id, f.key AS flag_key, e.code AS env_code,
                       s.kind, s.percent, s.status, 'rule_shadow' AS shadow_type
                FROM rule_shadows s
                JOIN flags f ON f.id=s.flag_id
                JOIN environments e ON e.id=s.env_id
                WHERE s.status='open'
                ORDER BY shadow_id DESC
                """
            ).fetchall()
        ]
        by_status = [
            dict(x)
            for x in conn.execute("SELECT status, COUNT(*) c FROM flags GROUP BY status").fetchall()
        ]
    return {
        "rules": rows,
        "pending_shadows": [
            {**p, "confirmed": False, "awaiting_second_confirmation": True} for p in pending
        ],
        "by_status": by_status,
    }

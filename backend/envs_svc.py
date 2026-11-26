"""环境目录与生产风险联查（grayroll-07：生产全量与环境风险跨表口径）。"""
from __future__ import annotations

from fastapi import APIRouter, Header, HTTPException

from auth import current_user
from db import connect

router = APIRouter(prefix="/api/envs", tags=["envs"])

# grayroll-07 封死口径：生产环境一键全量只许走影子草案，正式发布整笔拒写
PROD_CODE = "prod"
FULL_ROLLOUT_PERCENT = 100


def get_env(conn, env_id: int):
    return conn.execute("SELECT * FROM environments WHERE id=?", (env_id,)).fetchone()


def is_prod_env(conn, env_id: int) -> bool:
    """跨表：以 environments 表风险目录为准，禁止调用方硬编码 env_id。"""
    env = get_env(conn, env_id)
    return bool(env and env["code"] == PROD_CODE)


def assert_not_prod_full_rollout(conn, env_id: int, percent: int) -> None:
    """甲路径闸口：prod 且 percent=100 的正式写入整笔拒写（正式零增）。"""
    if percent >= FULL_ROLLOUT_PERCENT and is_prod_env(conn, env_id):
        raise HTTPException(
            400,
            detail="生产环境禁止一键全量（100%）正式发布：请改走分步爬坡，或落影子草案经二次确认后升正",
        )


def _prod_risk_rows(conn):
    """生产全量与环境风险联查跨表：正式规则/待确认影子 + 环境风险等级。"""
    official_full = [
        dict(r)
        for r in conn.execute(
            """
            SELECT r.flag_id, f.key AS flag_key, e.id AS env_id, e.code AS env_code,
                   e.risk_level, r.percent, r.version, 'official_rule' AS source
            FROM flag_rules r
            JOIN flags f ON f.id = r.flag_id
            JOIN environments e ON e.id = r.env_id
            WHERE r.official = 1 AND e.code = ? AND r.percent >= ?
            ORDER BY r.id
            """,
            (PROD_CODE, FULL_ROLLOUT_PERCENT),
        ).fetchall()
    ]
    pending_full = [
        dict(r)
        for r in conn.execute(
            """
            SELECT s.flag_id, f.key AS flag_key, e.id AS env_id, e.code AS env_code,
                   e.risk_level, s.percent, s.status, s.id AS shadow_id, 'release_shadow' AS source
            FROM release_shadows s
            JOIN flags f ON f.id = s.flag_id
            JOIN environments e ON e.id = s.env_id
            WHERE e.code = ? AND s.percent >= ? AND s.status = 'open'
            ORDER BY s.id
            """,
            (PROD_CODE, FULL_ROLLOUT_PERCENT),
        ).fetchall()
    ]
    return official_full, pending_full


@router.get("")
def list_envs(authorization: str | None = Header(default=None)):
    current_user(authorization)
    with connect() as conn:
        rows = [dict(r) for r in conn.execute("SELECT * FROM environments ORDER BY risk_level, id").fetchall()]
        official_full, pending_full = _prod_risk_rows(conn)
    return {
        "items": rows,
        "prod_full_rollout_guard": {
            "env_code": PROD_CODE,
            "forbid_official_full": True,
            "full_rollout_percent": FULL_ROLLOUT_PERCENT,
            "official_full_rows": official_full,
            "pending_full_shadows": pending_full,
        },
    }


@router.get("/{env_id}")
def get_env_detail(env_id: int, authorization: str | None = Header(default=None)):
    current_user(authorization)
    with connect() as conn:
        row = conn.execute("SELECT * FROM environments WHERE id=?", (env_id,)).fetchone()
        if not row:
            raise HTTPException(404, detail="环境不存在")
        data = dict(row)
        if data["code"] == PROD_CODE:
            official_full, pending_full = _prod_risk_rows(conn)
            data["prod_full_rollout_guard"] = {
                "forbid_official_full": True,
                "full_rollout_percent": FULL_ROLLOUT_PERCENT,
                "official_full_rows": official_full,
                "pending_full_shadows": pending_full,
            }
    return data

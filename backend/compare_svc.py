"""正式规则 vs 影子草案对比。

grayroll-07：影子行带结构化分步确认痕（confirmed / awaiting_second_confirmation），
未确认全量影子与正式规则的差异必须显式可见，禁止在对比页无痕混同。
"""
from __future__ import annotations

from fastapi import APIRouter, Header, HTTPException

from auth import current_user
from db import connect
from validators import require_int

router = APIRouter(prefix="/api/compare", tags=["compare"])


def _mark_pending(rows):
    """给 open 影子行统一盖待确认章：确认态与正式零改口径同源。"""
    out = []
    for r in rows:
        item = dict(r)
        item["confirmed"] = False
        item["awaiting_second_confirmation"] = True
        item["official_changed"] = False
        out.append(item)
    return out


@router.get("/flag/{flag_id}/env/{env_id}")
def compare_flag_env(flag_id: int, env_id: int, authorization: str | None = Header(default=None)):
    current_user(authorization)
    fid = require_int(flag_id, "开关", 1)
    eid = require_int(env_id, "环境", 1)
    with connect() as conn:
        fl = conn.execute("SELECT id, key, title, status FROM flags WHERE id=?", (fid,)).fetchone()
        env = conn.execute("SELECT id, code, title, risk_level FROM environments WHERE id=?", (eid,)).fetchone()
        if not fl or not env:
            raise HTTPException(404, detail="开关或环境不存在")
        official = conn.execute(
            "SELECT * FROM flag_rules WHERE flag_id=? AND env_id=? AND official=1", (fid, eid)
        ).fetchone()
        rule_shadows = _mark_pending(
            conn.execute(
                "SELECT * FROM rule_shadows WHERE flag_id=? AND env_id=? AND status='open' ORDER BY id DESC",
                (fid, eid),
            ).fetchall()
        )
        release_shadows = _mark_pending(
            conn.execute(
                "SELECT * FROM release_shadows WHERE flag_id=? AND env_id=? AND status='open' ORDER BY id DESC",
                (fid, eid),
            ).fetchall()
        )
        kill_shadows = _mark_pending(
            conn.execute(
                "SELECT * FROM kill_shadows WHERE flag_id=? AND env_id=? AND status='open' ORDER BY id DESC",
                (fid, eid),
            ).fetchall()
        )
        recent_releases = [
            dict(r)
            for r in conn.execute(
                "SELECT * FROM releases WHERE flag_id=? AND env_id=? AND official=1 ORDER BY id DESC LIMIT 5",
                (fid, eid),
            ).fetchall()
        ]
    diffs = []
    if official and release_shadows:
        sh = release_shadows[0]
        for field in ("kind", "percent", "cohort_id"):
            if official[field] != sh.get(field):
                diffs.append({
                    "field": field,
                    "official": official[field],
                    "shadow": sh.get(field),
                    "shadow_confirmed": False,
                    "note": "影子未二次确认，正式口径仍以 official 为准",
                })
    elif not official and release_shadows:
        # 无正式规则却挂影子：明确这是待确认草案而非已生效全量
        for sh in release_shadows:
            diffs.append({
                "field": "official_rule",
                "official": None,
                "shadow": {"percent": sh.get("percent"), "kind": sh.get("kind")},
                "shadow_confirmed": False,
                "note": "正式规则不存在；影子草案未确认，求值不得命中",
            })
    return {
        "flag": dict(fl),
        "env": dict(env),
        "official_rule": dict(official) if official else None,
        "open_rule_shadows": rule_shadows,
        "open_release_shadows": release_shadows,
        "open_kill_shadows": kill_shadows,
        "recent_releases": recent_releases,
        "diffs": diffs,
        "has_pending_shadow": bool(rule_shadows or release_shadows or kill_shadows),
        "confirmation": {
            "shadow_confirmed": False,
            "awaiting_second_confirmation": bool(rule_shadows or release_shadows or kill_shadows),
            "official_zero_change_before_promote": bool(rule_shadows or release_shadows or kill_shadows),
        },
    }


@router.get("/matrix")
def compare_matrix(authorization: str | None = Header(default=None)):
    current_user(authorization)
    with connect() as conn:
        flags = [dict(r) for r in conn.execute("SELECT id, key, status FROM flags ORDER BY id").fetchall()]
        envs = [dict(r) for r in conn.execute("SELECT id, code FROM environments ORDER BY risk_level").fetchall()]
        rules = {
            (r["flag_id"], r["env_id"]): dict(r)
            for r in conn.execute("SELECT * FROM flag_rules WHERE official=1").fetchall()
        }
        matrix = []
        for f in flags:
            row = {"flag_id": f["id"], "flag_key": f["key"], "status": f["status"], "cells": []}
            for e in envs:
                rule = rules.get((f["id"], e["id"]))
                row["cells"].append(
                    {
                        "env_id": e["id"],
                        "env_code": e["code"],
                        "has_rule": rule is not None,
                        "percent": rule["percent"] if rule else None,
                        "version": rule["version"] if rule else None,
                        "kind": rule["kind"] if rule else None,
                    }
                )
            matrix.append(row)
    return {"envs": envs, "matrix": matrix}

from __future__ import annotations

import json
from datetime import datetime, timezone

from services import db

VALID_RISKS = {"low", "medium", "high"}


def create_js_proposal(
    *,
    title: str,
    summary: str,
    code: str,
    page_context: dict | None = None,
    risk_level: str = "medium",
    expected_effects: list[str] | None = None,
    task_id: str | None = None,
) -> dict:
    """Persist a browser-side JavaScript proposal for user review."""
    risk = risk_level if risk_level in VALID_RISKS else "medium"
    proposal = db.create_agent_proposal(
        title=title.strip() or "JS 操作提案",
        summary=summary.strip() or "Agent 生成了一个需要确认的页面操作。",
        code=code.strip(),
        kind="js",
        page_context=page_context or {},
        risk_level=risk,
        expected_effects=expected_effects or [],
        task_id=task_id,
    )
    db.add_evolution_log(
        "proposal_created",
        f"Agent 创建 JS 提案：{proposal['title']}",
        task_id=task_id,
        after={
            "proposal_id": proposal["id"],
            "risk_level": proposal["risk_level"],
            "expected_effects": proposal.get("expected_effects", []),
        },
        artifact_type="proposal",
        artifact_id=proposal["id"],
    )
    return proposal


def approve(proposal_id: str) -> dict:
    proposal = db.get_agent_proposal(proposal_id)
    if not proposal:
        return {"ok": False, "error": "proposal not found"}
    if proposal["status"] not in {"pending", "failed"}:
        return {"ok": False, "error": f"proposal is {proposal['status']}"}
    updated = db.update_agent_proposal(
        proposal_id,
        status="approved",
        approved_at=datetime.now(timezone.utc).isoformat(),
        error=None,
    )
    db.add_evolution_log(
        "proposal_approved",
        f"用户批准 JS 提案：{proposal['title']}",
        artifact_type="proposal",
        artifact_id=proposal_id,
    )
    return {"ok": True, "proposal": updated}


def reject(proposal_id: str) -> dict:
    proposal = db.get_agent_proposal(proposal_id)
    if not proposal:
        return {"ok": False, "error": "proposal not found"}
    updated = db.update_agent_proposal(proposal_id, status="rejected")
    db.add_evolution_log(
        "proposal_rejected",
        f"用户拒绝 JS 提案：{proposal['title']}",
        artifact_type="proposal",
        artifact_id=proposal_id,
    )
    return {"ok": True, "proposal": updated}


def record_result(proposal_id: str, ok: bool, result: dict | None = None, error: str | None = None) -> dict:
    proposal = db.get_agent_proposal(proposal_id)
    if not proposal:
        return {"ok": False, "error": "proposal not found"}
    status = "executed" if ok else "failed"
    updated = db.update_agent_proposal(
        proposal_id,
        status=status,
        result_json=json.dumps(result or {}, ensure_ascii=False),
        error=error,
        executed_at=datetime.now(timezone.utc).isoformat(),
    )
    db.add_evolution_log(
        "proposal_executed" if ok else "proposal_failed",
        f"JS 提案{'执行完成' if ok else '执行失败'}：{proposal['title']}" + (f"。原因：{error}" if error else ""),
        after=result or {},
        artifact_type="proposal",
        artifact_id=proposal_id,
    )
    return {"ok": True, "proposal": updated}

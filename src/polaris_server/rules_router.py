from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException

from polaris_server.rules_catalog import load_production_inventory

router = APIRouter(prefix="/api/v1/rules", tags=["rules"])


@router.get("")
def list_rules(
    language: str | None = None,
    category: str | None = None,
    severity: str | None = None,
    q: str | None = None,
    limit: int = 250,
    offset: int = 0,
) -> dict[str, Any]:
    items = load_production_inventory()
    if language:
        items = [r for r in items if r["language"] == language]
    if category:
        items = [r for r in items if r["category"] == category]
    if severity:
        items = [r for r in items if r["severity"] == severity]
    if q:
        ql = q.lower()
        items = [
            r
            for r in items
            if ql in r["name"].lower() or ql in r["description"].lower() or ql in r["ruleId"].lower()
        ]
    total = len(items)
    page = items[offset : offset + limit]
    return {"total": total, "items": page}


@router.get("/{rule_id}")
def get_rule(rule_id: str) -> dict[str, Any]:
    for r in load_production_inventory():
        if r["ruleId"] == rule_id:
            return r
    raise HTTPException(status_code=404, detail="Regra não encontrada")

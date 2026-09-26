"""闸口通行业务规则：状态流转、字段校验与筛选口径都收在这里。"""
from __future__ import annotations

from typing import Any

from app.store import store
from app.services.gate_policy import (
    REVIEWED_STATUS,
    REVIEW_LOCK_HINT,
    evaluate_release,
    with_release_verdict,
)

MODULE = "gate"
# 登记仍需保留通行编号作为业务主键
REQUIRED_FIELDS = ["通行编号", "车牌号码", "关联箱号"]
# 登记时可随单补录的通行要素；放行判据只认车牌号码与关联箱号
OPTIONAL_FIELDS = ["进出方向", "通行时间", "道口编号", "值守人员"]
STATUS_ORDER = ["待放行", "已放行", "已拦截", "已复核"]
ACTION_RULES = {"确认放行": "已放行", "拦截车辆": "已拦截", "复核通行": "已复核"}
NEGATIVE_ACTIONS = []


class GateService:
    def list_entries(
        self,
        *,
        keyword: str | None = None,
        status: str | None = None,
        page: int = 1,
        size: int = 20,
    ) -> tuple[list[dict[str, Any]], int]:
        rows = store.rows(MODULE)
        if keyword:
            rows = [row for row in rows if keyword in str(row.get("通行编号", ""))]
        if status:
            rows = [row for row in rows if row.get("status") == status]
        total = len(rows)
        start = max(page - 1, 0) * size
        page_rows = [with_release_verdict(row) for row in rows[start:start + size]]
        return page_rows, total

    def get_entry(self, entry_id: int) -> dict[str, Any] | None:
        entry = store.find(MODULE, entry_id)
        if entry is None:
            return None
        return with_release_verdict(entry)

    def create_entry(self, values: dict[str, Any]) -> tuple[dict[str, Any] | None, list[str]]:
        missing = [field for field in REQUIRED_FIELDS if not str(values.get(field) or "").strip()]
        if missing:
            return None, missing
        rows = store.rows(MODULE)
        entry = {"id": max((int(row.get("id", 0)) for row in rows), default=0) + 1}
        entry.update({field: values.get(field) for field in REQUIRED_FIELDS})
        for field in OPTIONAL_FIELDS:
            value = str(values.get(field) or "").strip()
            if value:
                entry[field] = value
        entry["status"] = STATUS_ORDER[0]
        entry["pending"] = True
        entry["abnormal"] = False
        rows.append(entry)
        return with_release_verdict(entry), []

    def run_action(self, entry_id: int, action: str) -> tuple[dict[str, Any] | None, str]:
        entry = store.find(MODULE, entry_id)
        if entry is None:
            return None, f"通行记录 {entry_id} 不存在或已归档"
        if action not in ACTION_RULES:
            return None, f"动作「{action}」不属于闸口通行可执行范围"
        target = ACTION_RULES[action]
        if target not in STATUS_ORDER:
            return None, f"目标状态「{target}」不在允许的状态序列里"

        reviewed = entry.get("status") == REVIEWED_STATUS
        if reviewed and action != "复核通行":
            # 已复核是终态：任何把它拉回待放行/其它队列的尝试都拒绝
            return None, REVIEW_LOCK_HINT

        if action == "复核通行":
            if "复核结果" not in entry:
                # 复核结论同样取自唯一判据，且只落一条，重复复核不产生新结果
                entry["复核结果"] = evaluate_release(entry)["放行结果"]
            entry["status"] = REVIEWED_STATUS
            entry["pending"] = False
            entry["abnormal"] = action in NEGATIVE_ACTIONS
            return with_release_verdict(entry), "通行记录已复核，复核结论以唯一放行判据为准"

        if action == "确认放行":
            verdict = evaluate_release(entry)
            if verdict["放行结果"] != "准予放行":
                # 判据不通过时不改状态，直接回传同一份判据的说明
                return None, f"{verdict['放行说明']}，暂不允许确认放行"

        entry["status"] = target
        entry["pending"] = target != STATUS_ORDER[-1]
        entry["abnormal"] = action in NEGATIVE_ACTIONS
        return with_release_verdict(entry), f"通行记录已{action}"

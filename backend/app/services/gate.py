"""闸口通行业务规则：状态流转、字段校验与筛选口径都收在这里。"""
from __future__ import annotations

from typing import Any

from app.store import store

MODULE = "gate"
REQUIRED_FIELDS = ["通行编号"]
STATUS_ORDER = ["待放行", "已放行", "已拦截", "已复核"]
ACTION_RULES = {"确认放行": "已放行", "拦截车辆": "已拦截", "复核通行": "已复核"}
NEGATIVE_ACTIONS = []

# 放行判据只维护这一份：登记、放行确认、复核都调用 evaluate_release，结论自然一致。
RELEASE_CHECK_FIELDS = ["车牌号码", "关联箱号"]
RELEASE_PASS_MESSAGE = "车牌号码与关联箱号齐全，允许放行"
RELEASE_BLOCK_MESSAGE = "车牌号码或关联箱号缺失，暂不能放行"

FINAL_STATUS = "已复核"
# 既有道口动作照旧；已复核是定案状态，任何动作都不能把它拉回待放行。
ALLOWED_TRANSITIONS = {
    "待放行": {"已放行", "已拦截", "已复核"},
    "已放行": {"已放行", "已拦截", "已复核"},
    "已拦截": {"已放行", "已拦截", "已复核"},
    "已复核": {"已放行", "已拦截", "已复核"},
}


def evaluate_release(entry: dict[str, Any]) -> dict[str, Any]:
    """共用放行判据：车牌号码与关联箱号齐全才允许放行，缺失时各入口用同一段话说明。"""
    missing = [field for field in RELEASE_CHECK_FIELDS if not str(entry.get(field) or "").strip()]
    if missing:
        return {"ok": False, "message": RELEASE_BLOCK_MESSAGE, "missing": missing}
    return {"ok": True, "message": RELEASE_PASS_MESSAGE, "missing": []}


class GateService:
    def _present(self, entry: dict[str, Any]) -> dict[str, Any]:
        """列表、详情与动作回执统一走这里，刷新后放行结果始终取自同一份判据。"""
        row = dict(entry)
        verdict = evaluate_release(row)
        row["放行结论"] = "允许放行" if verdict["ok"] else "暂不能放行"
        row["放行说明"] = verdict["message"]
        row["缺失字段"] = verdict["missing"]
        return row

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
        return [self._present(row) for row in rows[start:start + size]], total

    def get_entry(self, entry_id: int) -> dict[str, Any] | None:
        entry = store.find(MODULE, entry_id)
        if entry is None:
            return None
        return self._present(entry)

    def create_entry(self, values: dict[str, Any]) -> tuple[dict[str, Any] | None, list[str]]:
        missing = [field for field in REQUIRED_FIELDS if not str(values.get(field) or "").strip()]
        if missing:
            return None, missing
        rows = store.rows(MODULE)
        entry = {"id": max((int(row.get("id", 0)) for row in rows), default=0) + 1}
        entry["通行编号"] = values.get("通行编号")
        # 车牌号码、关联箱号缺失不拦登记，由共用判据给出"暂不能放行"结论。
        for field in RELEASE_CHECK_FIELDS:
            entry[field] = values.get(field)
        entry["status"] = STATUS_ORDER[0]
        entry["pending"] = True
        entry["abnormal"] = False
        rows.append(entry)
        return self._present(entry), []

    def run_action(self, entry_id: int, action: str) -> tuple[dict[str, Any] | None, str]:
        entry = store.find(MODULE, entry_id)
        if entry is None:
            return None, f"通行记录 {entry_id} 不存在或已归档"
        if action not in ACTION_RULES:
            return None, f"动作「{action}」不属于闸口通行可执行范围"
        target = ACTION_RULES[action]

        if action == "复核通行" and entry.get("status") == FINAL_STATUS and entry.get("复核结果"):
            # 重复复核只留一条结果，不再覆盖既有结论。
            return self._present(entry), "通行记录已复核，复核结果保持唯一，不再重复登记"

        if action == "确认放行":
            verdict = evaluate_release(entry)
            if not verdict["ok"]:
                return None, verdict["message"]

        current = str(entry.get("status") or STATUS_ORDER[0])
        if target not in ALLOWED_TRANSITIONS.get(current, set()):
            if current == FINAL_STATUS and target == STATUS_ORDER[0]:
                return None, "通行记录已复核定案，不能再拉回待放行"
            return None, f"通行记录当前状态「{current}」不允许流转到「{target}」"

        if action == "复核通行":
            verdict = evaluate_release(entry)
            entry["复核结果"] = {
                "结论": "复核通过" if verdict["ok"] else "复核不通过",
                "说明": verdict["message"],
            }

        entry["status"] = target
        entry["pending"] = target != STATUS_ORDER[-1]
        entry["abnormal"] = action in NEGATIVE_ACTIONS
        return self._present(entry), f"通行记录已{action}"

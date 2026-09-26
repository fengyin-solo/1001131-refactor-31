"""闸口放行判据：登记、放行确认、复核三处共用同一份口径。

任何入口都不允许自己另写一套判定逻辑，需要结论时统一调用 evaluate_release，
保证同一张通行证在列表、详情与各动作之间得到一致的放行结果。
"""
from __future__ import annotations

from typing import Any

# 放行判据依赖的字段，缺一不可；顺序即缺失提示的拼接顺序
RELEASE_FIELDS = ["车牌号码", "关联箱号"]

PASS_RESULT = "准予放行"
HOLD_RESULT = "暂不予放行"
# 车牌号码与关联箱号缺失时，所有入口都使用这同一段说明
MISSING_HINT = "车牌号码或关联箱号缺失，无法判定放行，请补齐后再核对"

REVIEWED_STATUS = "已复核"
# 已复核记录的终态锁定说明
REVIEW_LOCK_HINT = "通行记录已复核，结论锁定，不能再拉回待放行"


def _filled(entry: dict[str, Any], field: str) -> bool:
    return bool(str(entry.get(field) or "").strip())


def evaluate_release(entry: dict[str, Any]) -> dict[str, str]:
    """按唯一判据给出放行结论：车牌号码与关联箱号齐备才准予放行。

    返回 {"放行结果", "放行说明"}，纯函数、不落库；读列表/详情时现算，
    保证刷新后各入口结论始终取自同一份判据。
    """
    missing = [field for field in RELEASE_FIELDS if not _filled(entry, field)]
    if missing:
        return {"放行结果": HOLD_RESULT, "放行说明": MISSING_HINT}
    return {"放行结果": PASS_RESULT, "放行说明": "车牌号码与关联箱号核对一致，准予放行"}


def with_release_verdict(entry: dict[str, Any]) -> dict[str, Any]:
    """返回附加了放行结论的记录副本，列表与详情共用。"""
    result = dict(entry)
    result.update(evaluate_release(entry))
    return result

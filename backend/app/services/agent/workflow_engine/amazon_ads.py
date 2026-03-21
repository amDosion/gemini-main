"""
Amazon Ads analysis helpers extracted from WorkflowEngine.
"""

from __future__ import annotations

import math
import re
import time
from typing import Any, Dict, List, Optional, Tuple

try:
    import pandas as pd  # type: ignore
except Exception:  # pragma: no cover - optional dependency
    pd = None  # type: ignore


def normalize_header_token(engine: Any, value: Any) -> str:
    _ = engine
    text = str(value or "").strip().lower()
    if not text:
        return ""
    return re.sub(r"[\s\-_:/\\()（）\[\]{}.,，。%$#@!+*|]+", "", text)


def resolve_column_by_alias(engine: Any, columns: List[str], aliases: List[str]) -> Optional[str]:
    if not columns or not aliases:
        return None

    normalized_map: Dict[str, str] = {}
    ordered_pairs: List[Tuple[str, str]] = []
    for column in columns:
        normalized = engine._normalize_header_token(column)
        if not normalized:
            continue
        normalized_map.setdefault(normalized, column)
        ordered_pairs.append((normalized, column))

    normalized_aliases = [engine._normalize_header_token(alias) for alias in aliases if engine._normalize_header_token(alias)]
    for alias in normalized_aliases:
        if alias in normalized_map:
            return normalized_map[alias]

    for alias in normalized_aliases:
        for normalized, column in ordered_pairs:
            if alias in normalized:
                return column
    return None


def parse_numeric_value(engine: Any, value: Any) -> Optional[float]:
    _ = engine
    if value is None:
        return None
    if isinstance(value, bool):
        return 1.0 if value else 0.0
    if isinstance(value, (int, float)):
        parsed = float(value)
        return parsed if math.isfinite(parsed) else None

    text = str(value).strip()
    if not text:
        return None
    lowered = text.lower()
    if lowered in {"nan", "none", "null", "-", "--", "n/a", "na"}:
        return None

    compact = (
        text.replace(",", "")
        .replace("，", "")
        .replace("$", "")
        .replace("￥", "")
        .replace("元", "")
        .replace(" ", "")
    )
    percentage = compact.endswith("%")
    if percentage:
        compact = compact[:-1]

    try:
        parsed = float(compact)
    except Exception:
        matched = re.search(r"-?\d+(?:\.\d+)?", compact)
        if not matched:
            return None
        try:
            parsed = float(matched.group(0))
        except Exception:
            return None

    if not math.isfinite(parsed):
        return None
    if percentage:
        return parsed / 100.0
    return parsed


def normalize_text_value(engine: Any, value: Any) -> str:
    _ = engine
    if value is None:
        return ""
    if isinstance(value, float):
        if not math.isfinite(value):
            return ""
    text = str(value).strip()
    if not text:
        return ""
    if text.lower() in {"nan", "none", "null", "-", "--", "n/a", "na"}:
        return ""
    return text


def parse_ratio_value(engine: Any, value: Any) -> Optional[float]:
    parsed = engine._parse_numeric_value(value)
    if parsed is None:
        return None
    if parsed > 1.0:
        parsed = parsed / 100.0
    if parsed < 0:
        return None
    return parsed


def parse_boolean_value(engine: Any, value: Any) -> bool:
    _ = engine
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return float(value) != 0
    text = str(value or "").strip().lower()
    if not text:
        return False
    if text in {"1", "true", "yes", "y", "on", "是", "true/yes"}:
        return True
    if any(token in text for token in ("negative", "否定", "已否定")):
        return True
    return False


def safe_ratio(engine: Any, numerator: float, denominator: float) -> Optional[float]:
    _ = engine
    if denominator <= 0:
        return None
    value = numerator / denominator
    if not math.isfinite(value) or value < 0:
        return None
    return value


def format_money(engine: Any, value: Optional[float]) -> str:
    _ = engine
    if value is None:
        return "-"
    return f"${value:.2f}"


def format_ratio(engine: Any, value: Optional[float]) -> str:
    _ = engine
    if value is None:
        return "-"
    return f"{value * 100:.2f}%"


def match_amazon_ads_columns(engine: Any, columns: List[str]) -> Dict[str, Optional[str]]:
    alias_map: Dict[str, List[str]] = {
        "search_term": [
            "用户搜索词", "搜索词", "search term", "customer search term", "search query", "query",
        ],
        "keyword": [
            "关键词", "keyword", "target keyword", "targeting", "投放词",
        ],
        "campaign": [
            "广告活动", "campaign", "campaign name",
        ],
        "ad_group": [
            "广告组", "ad group", "ad group name",
        ],
        "match_type": [
            "关键词匹配方式", "匹配方式", "match type", "keyword match type",
        ],
        "negative_keyword_flag": [
            "关键词是否否定", "negative keyword", "is negative keyword",
        ],
        "negative_search_term_flag": [
            "用户搜索词是否否定", "search term is negative", "is negative search term",
        ],
        "impressions": [
            "曝光量", "展示量", "impressions", "impr",
        ],
        "clicks": [
            "点击", "clicks", "click",
        ],
        "ctr": [
            "ctr", "点击百分比", "点击率", "click through rate",
        ],
        "cpc": [
            "cpc", "平均点击花费", "平均每次点击费用", "cost per click",
        ],
        "spend": [
            "花费", "spend", "cost", "ad spend",
        ],
        "sales": [
            "销售额", "销售", "sales", "attributed sales", "ad sales",
        ],
        "orders": [
            "广告订单", "订单", "orders", "attributed conversions", "conversions",
        ],
        "acos": [
            "acos", "a cos", "acoss", "aCoS",
        ],
        "cvr": [
            "cvr", "转化率", "conversion rate",
        ],
        "bid": [
            "竞价($)", "竞价", "bid", "max bid", "default bid",
        ],
        "search_rank": [
            "搜索词展示量排名", "展示排名", "impression rank",
        ],
        "search_share": [
            "搜索词展示份额", "展示份额", "impression share",
        ],
    }

    matched: Dict[str, Optional[str]] = {}
    for canonical, aliases in alias_map.items():
        matched[canonical] = engine._resolve_column_by_alias(columns, aliases)
    return matched


def build_amazon_ads_decision_board(
    engine: Any,
    *,
    negative_candidates: List[Dict[str, Any]],
    scale_candidates: List[Dict[str, Any]],
    watchlist: List[Dict[str, Any]],
) -> Dict[str, Any]:
    _ = engine

    def _action_rows(items: List[Dict[str, Any]], action_type: str, top_n: int = 20) -> List[Dict[str, Any]]:
        rows: List[Dict[str, Any]] = []
        for item in items[:top_n]:
            rows.append({
                "term": str(item.get("term") or "").strip(),
                "actionType": action_type,
                "reason": str(item.get("reason") or "").strip(),
                "campaigns": item.get("campaigns") or [],
                "adGroups": item.get("adGroups") or [],
                "matchTypes": item.get("matchTypes") or [],
                "impressions": int(item.get("impressions") or 0),
                "clicks": int(item.get("clicks") or 0),
                "orders": int(item.get("orders") or 0),
                "spend": float(item.get("spend") or 0.0),
                "sales": float(item.get("sales") or 0.0),
                "acos": item.get("acos"),
                "ctr": item.get("ctr"),
                "cvr": item.get("cvr"),
                "suggestedBidIncreasePct": item.get("suggestedBidIncreasePct"),
                "suggestedBudgetMultiplier": item.get("suggestedBudgetMultiplier"),
                "recommendedNegativeType": item.get("recommendedNegativeType"),
                "rule": item.get("rule"),
            })
        return rows

    decision_rows: List[Dict[str, Any]] = []
    decision_rows.extend(_action_rows(negative_candidates, "add_negative"))
    decision_rows.extend(_action_rows(scale_candidates, "scale_up"))
    decision_rows.extend(_action_rows(watchlist, "watch"))
    return {
        "rows": decision_rows,
        "counts": {
            "negative": len(negative_candidates),
            "scaleUp": len(scale_candidates),
            "watch": len(watchlist),
            "total": len(decision_rows),
        },
    }


def build_amazon_ads_validation_summary(
    engine: Any,
    *,
    column_map: Dict[str, Optional[str]],
    negative_candidates: List[Dict[str, Any]],
    scale_candidates: List[Dict[str, Any]],
    watchlist: List[Dict[str, Any]],
    total_orders: int,
    overall_acos: Optional[float],
    target_acos: float,
) -> Dict[str, Any]:
    _ = engine
    issues: List[Dict[str, Any]] = []
    required_fields = ("search_term", "keyword", "impressions", "clicks", "spend", "sales", "orders")
    missing_fields = [field for field in required_fields if not column_map.get(field)]
    if len(missing_fields) >= 3:
        issues.append({
            "code": "missing_critical_columns",
            "severity": "high",
            "message": f"关键字段缺失较多：{', '.join(missing_fields)}",
        })

    negative_terms = {
        str(item.get("term") or "").strip().lower()
        for item in negative_candidates
        if str(item.get("term") or "").strip()
    }
    scale_terms = {
        str(item.get("term") or "").strip().lower()
        for item in scale_candidates
        if str(item.get("term") or "").strip()
    }
    overlap_terms = sorted(term for term in negative_terms & scale_terms if term)
    if overlap_terms:
        issues.append({
            "code": "negative_scale_conflict",
            "severity": "high",
            "message": f"存在 {len(overlap_terms)} 个词同时进入否定与扩量候选，需人工确认。",
            "terms": overlap_terms[:15],
        })

    if total_orders <= 0 and scale_candidates:
        issues.append({
            "code": "scale_without_orders",
            "severity": "medium",
            "message": "当前订单为 0，但出现扩量建议，请复核口径。",
        })

    if overall_acos is not None and overall_acos > target_acos * 2.5 and len(scale_candidates) > len(negative_candidates):
        issues.append({
            "code": "acos_risk_bias",
            "severity": "medium",
            "message": "整体 ACoS 显著高于目标，但扩量建议数量偏多，建议复核阈值。",
        })

    risk_flags: List[str] = []
    if watchlist and len(watchlist) >= max(len(scale_candidates) * 2, 20):
        risk_flags.append("watchlist_heavy")
    if len(negative_candidates) == 0 and len(scale_candidates) == 0:
        risk_flags.append("low_signal_data")
    if overall_acos is not None and overall_acos > target_acos * 1.4:
        risk_flags.append("overall_acos_high")

    confidence = 95
    confidence -= min(len(issues) * 16, 48)
    confidence -= min(len(risk_flags) * 7, 21)
    confidence = max(30, min(98, confidence))

    if any(str(item.get("severity") or "").lower() == "high" for item in issues):
        status = "fail"
    elif issues:
        status = "pass_with_warnings"
    else:
        status = "pass"

    return {
        "status": status,
        "confidence": confidence,
        "issues": issues,
        "riskFlags": risk_flags,
        "checkedAt": int(time.time() * 1000),
    }


async def run_amazon_ads_keyword_optimize_tool(
    engine: Any,
    tool_args: Dict[str, Any],
    latest_input: Any,
) -> Dict[str, Any]:
    if pd is None:
        return {
            "tool": "amazon_ads_keyword_optimize",
            "status": "invalid_input",
            "summary": "缺少 pandas 依赖，无法解析 Excel 数据。",
            "text": "缺少 pandas 依赖，无法解析 Excel 数据，请先安装 pandas/openpyxl。",
        }

    table_payload = (
        engine._get_tool_arg(tool_args, "table", "file_url", "fileUrl", "csv", "content")
        or latest_input
    )
    business_goal = (
        engine._get_tool_arg(tool_args, "query", "question", "goal", "task")
        or engine._extract_text_from_value(latest_input)
        or ""
    ).strip()

    try:
        frame, source_type = engine._table_payload_to_dataframe(table_payload)
    except Exception as exc:
        return {
            "tool": "amazon_ads_keyword_optimize",
            "status": "invalid_input",
            "summary": f"广告报表读取失败：{exc}",
            "text": f"广告报表读取失败：{exc}",
        }

    if frame is None or len(frame.columns) == 0:
        return {
            "tool": "amazon_ads_keyword_optimize",
            "status": "no_data",
            "summary": "未检测到有效表格列，请上传广告报表（Excel/CSV）。",
            "text": "未检测到有效表格列，请上传广告报表（Excel/CSV）。",
        }

    df = engine._normalize_dataframe(frame)
    if len(df.index) == 0:
        return {
            "tool": "amazon_ads_keyword_optimize",
            "status": "no_data",
            "summary": "数据为空，无法生成优化建议。",
            "text": "数据为空，无法生成优化建议。",
        }

    column_map = engine._match_amazon_ads_columns([str(col) for col in df.columns])
    if not column_map.get("search_term") and not column_map.get("keyword"):
        return {
            "tool": "amazon_ads_keyword_optimize",
            "status": "invalid_input",
            "summary": "缺少“搜索词/关键词”字段，无法输出否定词和加投词。",
            "detectedColumns": [str(col) for col in df.columns],
            "text": "缺少“搜索词/关键词”字段，无法输出否定词和加投词。",
        }

    target_acos = engine._to_float(
        engine._get_tool_arg(tool_args, "target_acos", "targetAcos", "acos_target"),
        default=0.35,
        minimum=0.01,
        maximum=200.0,
    ) or 0.35
    if target_acos > 1.0:
        target_acos /= 100.0

    negative_min_clicks_no_order = engine._to_int(
        engine._get_tool_arg(tool_args, "negative_min_clicks_no_order", "negativeMinClicksNoOrder"),
        default=8,
        minimum=1,
        maximum=200,
    ) or 8
    negative_min_spend_no_order = engine._to_float(
        engine._get_tool_arg(tool_args, "negative_min_spend_no_order", "negativeMinSpendNoOrder"),
        default=8.0,
        minimum=0.0,
        maximum=999999.0,
    ) or 8.0
    negative_high_acos = engine._to_float(
        engine._get_tool_arg(tool_args, "negative_high_acos", "negativeHighAcos"),
        default=max(target_acos * 1.6, 0.55),
        minimum=0.05,
        maximum=500.0,
    ) or max(target_acos * 1.6, 0.55)
    if negative_high_acos > 1.0:
        negative_high_acos /= 100.0
    negative_min_clicks_high_acos = engine._to_int(
        engine._get_tool_arg(tool_args, "negative_min_clicks_high_acos", "negativeMinClicksHighAcos"),
        default=10,
        minimum=1,
        maximum=300,
    ) or 10

    scale_min_orders = engine._to_int(
        engine._get_tool_arg(tool_args, "scale_min_orders", "scaleMinOrders"),
        default=2,
        minimum=1,
        maximum=500,
    ) or 2
    scale_min_clicks = engine._to_int(
        engine._get_tool_arg(tool_args, "scale_min_clicks", "scaleMinClicks"),
        default=8,
        minimum=1,
        maximum=300,
    ) or 8
    scale_min_cvr = engine._to_float(
        engine._get_tool_arg(tool_args, "scale_min_cvr", "scaleMinCvr"),
        default=0.08,
        minimum=0.0,
        maximum=100.0,
    ) or 0.08
    if scale_min_cvr > 1.0:
        scale_min_cvr /= 100.0

    watch_min_impressions = engine._to_int(
        engine._get_tool_arg(tool_args, "watch_min_impressions", "watchMinImpressions"),
        default=1200,
        minimum=1,
        maximum=99999999,
    ) or 1200
    watch_max_ctr = engine._to_float(
        engine._get_tool_arg(tool_args, "watch_max_ctr", "watchMaxCtr"),
        default=0.0025,
        minimum=0.0,
        maximum=100.0,
    ) or 0.0025
    if watch_max_ctr > 1.0:
        watch_max_ctr /= 100.0

    top_n = engine._to_int(
        engine._get_tool_arg(tool_args, "top_n", "topN", "limit"),
        default=30,
        minimum=5,
        maximum=100,
    ) or 30

    search_term_col = column_map.get("search_term")
    keyword_col = column_map.get("keyword")
    campaign_col = column_map.get("campaign")
    ad_group_col = column_map.get("ad_group")
    match_type_col = column_map.get("match_type")
    neg_keyword_col = column_map.get("negative_keyword_flag")
    neg_search_col = column_map.get("negative_search_term_flag")

    impressions_col = column_map.get("impressions")
    clicks_col = column_map.get("clicks")
    ctr_col = column_map.get("ctr")
    cpc_col = column_map.get("cpc")
    spend_col = column_map.get("spend")
    sales_col = column_map.get("sales")
    orders_col = column_map.get("orders")
    acos_col = column_map.get("acos")
    cvr_col = column_map.get("cvr")
    bid_col = column_map.get("bid")

    buckets: Dict[str, Dict[str, Any]] = {}
    for _, row in df.iterrows():
        raw_search_term = engine._normalize_text_value(row.get(search_term_col) if search_term_col else "")
        raw_keyword = engine._normalize_text_value(row.get(keyword_col) if keyword_col else "")
        term = raw_search_term or raw_keyword
        term = term.strip()
        if not term:
            continue

        key = term.lower()
        impressions = engine._to_int(engine._parse_numeric_value(row.get(impressions_col)) if impressions_col else 0, default=0, minimum=0) or 0
        clicks = engine._to_int(engine._parse_numeric_value(row.get(clicks_col)) if clicks_col else 0, default=0, minimum=0) or 0
        spend = engine._to_float(engine._parse_numeric_value(row.get(spend_col)) if spend_col else 0.0, default=0.0, minimum=0.0) or 0.0
        sales = engine._to_float(engine._parse_numeric_value(row.get(sales_col)) if sales_col else 0.0, default=0.0, minimum=0.0) or 0.0
        orders = engine._to_int(engine._parse_numeric_value(row.get(orders_col)) if orders_col else 0, default=0, minimum=0) or 0
        ctr = engine._parse_ratio_value(row.get(ctr_col)) if ctr_col else None
        cpc = engine._to_float(engine._parse_numeric_value(row.get(cpc_col)) if cpc_col else None, default=None, minimum=0.0)
        cvr = engine._parse_ratio_value(row.get(cvr_col)) if cvr_col else None
        acos = engine._parse_ratio_value(row.get(acos_col)) if acos_col else None
        bid = engine._to_float(engine._parse_numeric_value(row.get(bid_col)) if bid_col else None, default=None, minimum=0.0)

        if cpc is None:
            cpc = engine._safe_ratio(spend, max(clicks, 1))
        if cvr is None:
            cvr = engine._safe_ratio(float(orders), max(clicks, 1))
        if ctr is None:
            ctr = engine._safe_ratio(float(clicks), max(impressions, 1))
        if acos is None:
            acos = engine._safe_ratio(spend, sales) if sales > 0 else None

        is_negative = engine._parse_boolean_value(row.get(neg_keyword_col)) if neg_keyword_col else False
        if neg_search_col:
            is_negative = is_negative or engine._parse_boolean_value(row.get(neg_search_col))

        current = buckets.get(key)
        if not current:
            current = {
                "term": term,
                "keyword": raw_keyword,
                "campaigns": set(),
                "adGroups": set(),
                "matchTypes": set(),
                "impressions": 0,
                "clicks": 0,
                "spend": 0.0,
                "sales": 0.0,
                "orders": 0,
                "bidValues": [],
                "isNegative": False,
            }
            buckets[key] = current

        if campaign_col:
            campaign_name = engine._normalize_text_value(row.get(campaign_col))
            if campaign_name:
                current["campaigns"].add(campaign_name)
        if ad_group_col:
            ad_group_name = engine._normalize_text_value(row.get(ad_group_col))
            if ad_group_name:
                current["adGroups"].add(ad_group_name)
        if match_type_col:
            match_type_value = engine._normalize_text_value(row.get(match_type_col))
            if match_type_value:
                current["matchTypes"].add(match_type_value)

        current["impressions"] += impressions
        current["clicks"] += clicks
        current["spend"] += spend
        current["sales"] += sales
        current["orders"] += orders
        current["isNegative"] = bool(current["isNegative"] or is_negative)
        if bid is not None:
            current["bidValues"].append(bid)

    if not buckets:
        return {
            "tool": "amazon_ads_keyword_optimize",
            "status": "no_data",
            "summary": "无法提取有效搜索词记录，请检查报表字段与内容。",
            "text": "无法提取有效搜索词记录，请检查报表字段与内容。",
        }

    records: List[Dict[str, Any]] = []
    for item in buckets.values():
        impressions = int(item["impressions"])
        clicks = int(item["clicks"])
        spend = float(item["spend"])
        sales = float(item["sales"])
        orders = int(item["orders"])
        avg_bid = (
            sum(item["bidValues"]) / len(item["bidValues"])
            if item["bidValues"] else None
        )
        ctr = engine._safe_ratio(float(clicks), max(impressions, 1))
        cvr = engine._safe_ratio(float(orders), max(clicks, 1))
        cpc = engine._safe_ratio(spend, max(clicks, 1))
        acos = engine._safe_ratio(spend, sales) if sales > 0 else None

        records.append({
            "term": item["term"],
            "keyword": item["keyword"],
            "campaigns": sorted(item["campaigns"]),
            "adGroups": sorted(item["adGroups"]),
            "matchTypes": sorted(item["matchTypes"]),
            "impressions": impressions,
            "clicks": clicks,
            "spend": spend,
            "sales": sales,
            "orders": orders,
            "ctr": ctr,
            "cvr": cvr,
            "cpc": cpc,
            "acos": acos,
            "avgBid": avg_bid,
            "isNegative": bool(item["isNegative"]),
        })

    active_records = [item for item in records if not item["isNegative"]]
    if not active_records:
        active_records = records

    negative_candidates: List[Dict[str, Any]] = []
    scale_candidates: List[Dict[str, Any]] = []
    watchlist: List[Dict[str, Any]] = []

    for item in active_records:
        impressions = int(item["impressions"])
        clicks = int(item["clicks"])
        spend = float(item["spend"])
        sales = float(item["sales"])
        orders = int(item["orders"])
        ctr = item.get("ctr")
        cvr = item.get("cvr")
        acos = item.get("acos")

        if (
            clicks >= negative_min_clicks_no_order
            and orders == 0
            and spend >= negative_min_spend_no_order
        ):
            negative_candidates.append({
                **item,
                "rule": "high_click_no_order",
                "reason": f"点击 {clicks} 次且花费 {engine._format_money(spend)}，但无订单",
                "recommendedNegativeType": "phrase" if len(str(item['term']).split()) >= 2 else "exact",
            })
            continue

        if (
            orders > 0
            and acos is not None
            and acos >= negative_high_acos
            and clicks >= negative_min_clicks_high_acos
            and spend >= negative_min_spend_no_order
        ):
            negative_candidates.append({
                **item,
                "rule": "high_acos",
                "reason": f"ACoS {engine._format_ratio(acos)} 超过阈值 {engine._format_ratio(negative_high_acos)}",
                "recommendedNegativeType": "phrase",
            })
            continue

        if (
            orders >= scale_min_orders
            and clicks >= scale_min_clicks
            and sales > 0
            and acos is not None
            and acos <= target_acos
            and (cvr is None or cvr >= scale_min_cvr)
        ):
            bid_change = 0.08
            if acos <= target_acos * 0.6:
                bid_change = 0.20
            elif acos <= target_acos * 0.8:
                bid_change = 0.12
            scale_candidates.append({
                **item,
                "rule": "high_efficiency",
                "reason": f"订单 {orders}，ACoS {engine._format_ratio(acos)}，建议扩量",
                "suggestedBidIncreasePct": bid_change,
                "suggestedBudgetMultiplier": 1.3 if bid_change >= 0.12 else 1.15,
            })
            continue

        if impressions >= watch_min_impressions and (ctr or 0.0) <= watch_max_ctr and orders == 0:
            watchlist.append({
                **item,
                "rule": "high_impression_low_ctr",
                "reason": f"曝光 {impressions} 但 CTR 仅 {engine._format_ratio(ctr)}，建议优化匹配与文案",
            })
            continue

        if clicks > 0 and orders == 0 and spend > 0:
            watchlist.append({
                **item,
                "rule": "click_no_order_watch",
                "reason": f"已有点击 {clicks} 次、花费 {engine._format_money(spend)}，建议继续观察 2-3 天",
            })

    negative_candidates.sort(key=lambda item: (item.get("spend", 0.0), item.get("clicks", 0)), reverse=True)
    scale_candidates.sort(key=lambda item: (item.get("orders", 0), item.get("sales", 0.0)), reverse=True)
    watchlist.sort(key=lambda item: (item.get("impressions", 0), item.get("spend", 0.0)), reverse=True)

    negative_candidates = negative_candidates[:top_n]
    scale_candidates = scale_candidates[:top_n]
    watchlist = watchlist[:top_n]

    total_impressions = sum(int(item.get("impressions") or 0) for item in active_records)
    total_clicks = sum(int(item.get("clicks") or 0) for item in active_records)
    total_spend = sum(float(item.get("spend") or 0.0) for item in active_records)
    total_sales = sum(float(item.get("sales") or 0.0) for item in active_records)
    total_orders = sum(int(item.get("orders") or 0) for item in active_records)
    overall_ctr = engine._safe_ratio(float(total_clicks), max(total_impressions, 1))
    overall_cvr = engine._safe_ratio(float(total_orders), max(total_clicks, 1))
    overall_acos = engine._safe_ratio(total_spend, total_sales) if total_sales > 0 else None

    action_items: List[str] = []
    if negative_candidates:
        top_terms = "、".join(item["term"] for item in negative_candidates[:5])
        action_items.append(f"P0：优先添加否定词（{len(negative_candidates)} 个），首批建议：{top_terms}。")
    if scale_candidates:
        top_scale_terms = "、".join(item["term"] for item in scale_candidates[:5])
        action_items.append(f"P0：对高效词加价扩量（{len(scale_candidates)} 个），首批建议：{top_scale_terms}。")
    if watchlist:
        action_items.append(f"P1：观察词池 {len(watchlist)} 个，重点优化高曝光低点击搜索词。")
    if not action_items:
        action_items.append("当前暂无强烈调整信号，建议保持投放并继续累积数据。")

    decision_board = engine._build_amazon_ads_decision_board(
        negative_candidates=negative_candidates,
        scale_candidates=scale_candidates,
        watchlist=watchlist,
    )
    validation = engine._build_amazon_ads_validation_summary(
        column_map=column_map,
        negative_candidates=negative_candidates,
        scale_candidates=scale_candidates,
        watchlist=watchlist,
        total_orders=total_orders,
        overall_acos=overall_acos,
        target_acos=target_acos,
    )

    lines: List[str] = []
    lines.append("## Amazon 广告搜索词优化报告")
    lines.append("")
    if business_goal:
        lines.append(f"- 业务目标: {business_goal}")
    lines.append(f"- 数据来源: {source_type}")
    lines.append(f"- 原始行数: {len(df.index)}")
    lines.append(f"- 聚合词条数: {len(active_records)}（已排除已否定词）")
    lines.append(f"- 总曝光: {total_impressions:,}")
    lines.append(f"- 总点击: {total_clicks:,}（CTR {engine._format_ratio(overall_ctr)}）")
    lines.append(f"- 总花费: {engine._format_money(total_spend)}")
    lines.append(f"- 总销售额: {engine._format_money(total_sales)}")
    lines.append(f"- 总订单: {total_orders}（CVR {engine._format_ratio(overall_cvr)}）")
    lines.append(f"- 当前 ACoS: {engine._format_ratio(overall_acos)}，目标 ACoS: {engine._format_ratio(target_acos)}")
    lines.append(f"- 校验状态: {validation.get('status')}（置信度 {int(validation.get('confidence') or 0)}）")
    lines.append("")

    lines.append("### 建议加入否定词")
    if negative_candidates:
        for item in negative_candidates[:20]:
            lines.append(
                f"- `{item['term']}` | 花费 {engine._format_money(item.get('spend'))} | 点击 {item.get('clicks')} | "
                f"订单 {item.get('orders')} | ACoS {engine._format_ratio(item.get('acos'))} | 原因: {item.get('reason')}"
            )
    else:
        lines.append("- 暂无明确否定词候选。")
    lines.append("")

    lines.append("### 建议加大投入")
    if scale_candidates:
        for item in scale_candidates[:20]:
            bid_pct = float(item.get("suggestedBidIncreasePct") or 0.0)
            lines.append(
                f"- `{item['term']}` | 销售 {engine._format_money(item.get('sales'))} | 订单 {item.get('orders')} | "
                f"ACoS {engine._format_ratio(item.get('acos'))} | 建议加价 {bid_pct * 100:.0f}%"
            )
    else:
        lines.append("- 暂无满足扩量条件的词。")
    lines.append("")

    lines.append("### 观察池")
    if watchlist:
        for item in watchlist[:20]:
            lines.append(
                f"- `{item['term']}` | 曝光 {item.get('impressions')} | CTR {engine._format_ratio(item.get('ctr'))} | "
                f"花费 {engine._format_money(item.get('spend'))} | 原因: {item.get('reason')}"
            )
    else:
        lines.append("- 暂无观察词。")
    lines.append("")

    lines.append("### 执行动作")
    for action in action_items:
        lines.append(f"- {action}")

    lines.append("")
    lines.append("### 校验结果")
    issues = validation.get("issues") or []
    if issues:
        for issue in issues:
            severity = str(issue.get("severity") or "low").upper()
            message = str(issue.get("message") or "").strip()
            if message:
                lines.append(f"- [{severity}] {message}")
    else:
        lines.append("- 未发现明显冲突，建议按动作清单执行。")

    report_text = "\n".join(lines).strip()

    return {
        "tool": "amazon_ads_keyword_optimize",
        "status": "analyzed",
        "sourceType": source_type,
        "rowCount": int(len(df.index)),
        "aggregatedTermCount": len(active_records),
        "detectedColumns": column_map,
        "thresholds": {
            "targetAcos": target_acos,
            "negativeMinClicksNoOrder": negative_min_clicks_no_order,
            "negativeMinSpendNoOrder": negative_min_spend_no_order,
            "negativeHighAcos": negative_high_acos,
            "negativeMinClicksHighAcos": negative_min_clicks_high_acos,
            "scaleMinOrders": scale_min_orders,
            "scaleMinClicks": scale_min_clicks,
            "scaleMinCvr": scale_min_cvr,
            "watchMinImpressions": watch_min_impressions,
            "watchMaxCtr": watch_max_ctr,
        },
        "summary": {
            "impressions": total_impressions,
            "clicks": total_clicks,
            "spend": total_spend,
            "sales": total_sales,
            "orders": total_orders,
            "ctr": overall_ctr,
            "cvr": overall_cvr,
            "acos": overall_acos,
            "targetAcos": target_acos,
        },
        "negativeKeywords": negative_candidates,
        "scaleUpKeywords": scale_candidates,
        "watchlist": watchlist,
        "decisionBoard": decision_board,
        "validation": validation,
        "actions": action_items,
        "metrics": {
            "negativeKeywordCount": len(negative_candidates),
            "scaleUpKeywordCount": len(scale_candidates),
            "watchCount": len(watchlist),
        },
        "text": report_text,
    }

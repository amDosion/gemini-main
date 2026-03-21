from __future__ import annotations

import json
import re
from typing import Any, Dict, List, Optional


def _truncate(text: str, max_chars: int = 240) -> str:
    value = str(text or "").strip()
    if len(value) <= max_chars:
        return value
    return f"{value[:max_chars]}..."


def _coerce_content_item(item: Any) -> Dict[str, Any]:
    if isinstance(item, dict):
        return {
            "type": str(item.get("type") or "unknown"),
            "text": _truncate(item.get("text") or item.get("content") or ""),
            "annotations": item.get("annotations"),
            "meta": item.get("meta"),
        }

    text = getattr(item, "text", None)
    item_type = getattr(item, "type", None)
    annotations = getattr(item, "annotations", None)
    meta = getattr(item, "meta", None)
    if text is not None or item_type is not None:
        return {
            "type": str(item_type or "unknown"),
            "text": _truncate(text or ""),
            "annotations": annotations,
            "meta": meta,
        }

    return {
        "type": type(item).__name__,
        "text": _truncate(str(item)),
        "annotations": None,
        "meta": None,
    }


def coerce_mcp_content(result: Any) -> List[Dict[str, Any]]:
    if result is None:
        return []
    if isinstance(result, list):
        return [_coerce_content_item(item) for item in result]
    return [_coerce_content_item(result)]


def extract_text_segments(result: Any) -> List[str]:
    segments: List[str] = []
    for item in coerce_mcp_content(result):
        text = str(item.get("text") or "").strip()
        if text:
            segments.append(text)
    return segments


def extract_embedded_json(text: str) -> Any:
    payload = str(text or "").strip()
    if not payload:
        return None

    decoder = json.JSONDecoder()
    for match in re.finditer(r"[\[{]", payload):
        try:
            parsed, _ = decoder.raw_decode(payload[match.start():])
            return parsed
        except Exception:
            continue
    return None


def _to_number(value: Any) -> Any:
    text = str(value or "").strip()
    if not text:
        return value
    compact = text.replace(",", "")
    try:
        if "." in compact:
            return float(compact)
        return int(compact)
    except Exception:
        return value


def _normalize_table_rows(rows: Any, field_map: Dict[str, str]) -> List[Dict[str, Any]]:
    if not isinstance(rows, list):
        return []

    normalized: List[Dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        item: Dict[str, Any] = {}
        for raw_key, target_key in field_map.items():
            if raw_key not in row:
                continue
            item[target_key] = _to_number(row.get(raw_key))
        if item:
            normalized.append(item)
    return normalized


def _parse_product_detail_text(text: str) -> Dict[str, Any]:
    parsed: Dict[str, Any] = {}
    for line in str(text or "").splitlines():
        clean = line.strip()
        if not clean or "：" not in clean:
            continue
        key, _, value = clean.partition("：")
        field = key.strip()
        val = value.strip()
        if not field or not val:
            continue
        parsed[field] = _to_number(val)
    return parsed


def _normalize_keyword_trend(parsed: Any) -> Optional[Dict[str, Any]]:
    if not isinstance(parsed, dict):
        return None

    series: List[Dict[str, Any]] = []
    for raw_key, metric in (
        ("搜索量趋势", "search_volume"),
        ("搜索排名趋势", "search_rank"),
        ("推荐竞价趋势", "recommended_cpc"),
    ):
        raw_series = parsed.get(raw_key)
        if not isinstance(raw_series, list):
            continue
        points: List[Dict[str, Any]] = []
        for entry in raw_series:
            text = str(entry or "").strip()
            if not text:
                continue
            points.append({"label": text})
        if points:
            series.append({"metric": metric, "points": points})

    if not series:
        return None

    return {
        "kind": "time_series",
        "keyword": parsed.get("关键词"),
        "series": series,
    }


def normalize_sorftime_result(tool_name: str, result: Any) -> Dict[str, Any]:
    content = coerce_mcp_content(result)
    text_segments = extract_text_segments(result)
    full_text = "\n".join(text_segments).strip()
    embedded_json = None
    for segment in text_segments:
        embedded_json = extract_embedded_json(segment)
        if embedded_json is not None:
            break

    normalized_name = str(tool_name or "").strip().lower()
    normalized: Optional[Dict[str, Any]] = None

    if normalized_name == "category_name_search" and isinstance(embedded_json, list):
        normalized = {
            "kind": "category_matches",
            "items": _normalize_table_rows(
                embedded_json,
                {
                    "Name": "name",
                    "NodeId": "nodeId",
                },
            ),
        }
    elif normalized_name == "category_report" and isinstance(embedded_json, dict):
        normalized = {
            "kind": "category_report",
            "items": _normalize_table_rows(
                embedded_json.get("Top100产品"),
                {
                    "ASIN": "asin",
                    "标题": "title",
                    "月销量": "monthlySales",
                    "月销额": "monthlyRevenue",
                    "品牌": "brand",
                    "价格": "price",
                    "评论数": "reviewCount",
                    "星级": "rating",
                    "卖家": "seller",
                    "所处类目排名": "categoryRank",
                },
            ),
        }
    elif normalized_name in {"category_keywords", "product_search", "product_traffic_terms", "competitor_product_keywords"} and isinstance(embedded_json, list):
        field_map = {
            "关键词": "keyword",
            "周搜索排名": "weeklySearchRank",
            "周搜索量": "weeklySearchVolume",
            "月搜索量": "monthlySearchVolume",
            "cpc精准竞价": "exactBidCpc",
            "搜索结果数": "searchResultCount",
            "曝光位置": "exposurePosition",
            "最近自然曝光位置": "latestOrganicPosition",
            "最近自然曝光时间": "latestOrganicExposureAt",
            "推荐竞价": "recommendedBid",
            "推荐竞价范围": "recommendedBidRange",
            "产品ASIN码": "asin",
            "主图": "imageUrl",
            "标题": "title",
            "品牌": "brand",
            "价格": "price",
            "月销额": "monthlyRevenue",
            "月销量": "monthlySales",
            "星级": "rating",
            "评论数": "reviewCount",
            "发货方式": "fulfillment",
            "产品潜力指数": "potentialIndex",
        }
        normalized = {
            "kind": "table",
            "items": _normalize_table_rows(embedded_json, field_map),
        }
    elif normalized_name == "keyword_trend":
        normalized = _normalize_keyword_trend(embedded_json)
    elif normalized_name == "product_detail":
        details = _parse_product_detail_text(full_text)
        if details:
            normalized = {
                "kind": "product_detail",
                "details": details,
            }

    summary = ""
    if normalized and normalized.get("kind") == "category_matches":
        items = normalized.get("items") or []
        first = items[0] if items else {}
        summary = f"匹配到 {len(items)} 个类目，首项 {first.get('name') or 'unknown'} ({first.get('nodeId') or '-'})。"
    elif normalized and normalized.get("kind") == "category_report":
        items = normalized.get("items") or []
        first = items[0] if items else {}
        summary = f"返回类目 Top 产品 {len(items)} 条，头部 ASIN {first.get('asin') or '-'}，月销量 {first.get('monthlySales') or '-'}。"
    elif normalized and normalized.get("kind") == "time_series":
        series = normalized.get("series") or []
        point_count = sum(len(item.get("points") or []) for item in series if isinstance(item, dict))
        summary = f"返回关键词趋势序列 {len(series)} 条，共 {point_count} 个时间点。"
    elif normalized and normalized.get("kind") == "product_detail":
        details = normalized.get("details") or {}
        summary = (
            f"产品详情已获取：{details.get('标题') or details.get('标题'.lower()) or details.get('title') or '-'}；"
            f"品牌 {details.get('品牌') or '-'}；价格 {details.get('价格') or '-'}。"
        )
    elif normalized and normalized.get("kind") == "table":
        items = normalized.get("items") or []
        summary = f"返回结构化表格数据 {len(items)} 条。"

    if not summary:
        summary = _truncate(full_text, max_chars=320) or "MCP 工具调用完成。"

    return {
        "content": content,
        "text": summary,
        "rawText": _truncate(full_text, max_chars=4000),
        "parsed": embedded_json,
        "normalized": normalized,
    }


__all__ = [
    "coerce_mcp_content",
    "extract_embedded_json",
    "extract_text_segments",
    "normalize_sorftime_result",
]

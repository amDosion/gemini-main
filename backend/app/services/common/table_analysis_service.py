"""
Table analysis service for CSV/XLSX inputs.
"""

from __future__ import annotations

import base64
import io
import json
import math
from datetime import datetime, timezone
from typing import Any, Literal

SUPPORTED_TABLE_FORMATS = {"csv", "xlsx"}


class TableAnalysisError(Exception):
    """Base exception for table analysis errors."""


class UnsupportedTableFormatError(TableAnalysisError):
    """Raised when the table format is not supported."""


class TableAnalysisDependencyError(TableAnalysisError):
    """Raised when required dependencies are unavailable."""


class InvalidTableInputError(TableAnalysisError):
    """Raised when input data is invalid."""


def _resolve_table_format(file_name: str | None, file_format: str | None) -> Literal["csv", "xlsx"]:
    if file_format:
        normalized = file_format.strip().lower()
    else:
        normalized = ""
        if file_name and "." in file_name:
            normalized = file_name.rsplit(".", 1)[-1].strip().lower()

    if normalized not in SUPPORTED_TABLE_FORMATS:
        raise UnsupportedTableFormatError(
            "Unsupported table format. Only csv and xlsx are supported."
        )
    return normalized  # type: ignore[return-value]


def _ensure_pandas():
    try:
        import pandas as pd  # type: ignore
    except ImportError as exc:
        raise TableAnalysisDependencyError(
            "Table analysis requires pandas dependency. Install with `pip install pandas>=2.0.0`."
        ) from exc
    return pd


def _read_dataframe(
    file_bytes: bytes,
    table_format: Literal["csv", "xlsx"],
    *,
    csv_encoding: str,
    sheet_name: str | int | None,
):
    if not file_bytes:
        raise InvalidTableInputError("Table file is empty.")

    pd = _ensure_pandas()
    file_stream = io.BytesIO(file_bytes)

    if table_format == "csv":
        try:
            return pd.read_csv(file_stream, encoding=csv_encoding), "pandas.read_csv"
        except UnicodeDecodeError as exc:
            raise InvalidTableInputError(
                f"CSV decode failed with encoding '{csv_encoding}'."
            ) from exc
        except Exception as exc:
            raise InvalidTableInputError(f"Invalid CSV content: {exc}") from exc

    try:
        return (
            pd.read_excel(file_stream, sheet_name=sheet_name, engine="openpyxl"),
            "pandas.read_excel(openpyxl)",
        )
    except ImportError as exc:
        raise TableAnalysisDependencyError(
            "XLSX analysis requires optional dependency 'openpyxl'. "
            "Install with `pip install openpyxl>=3.1.0`."
        ) from exc
    except ValueError as exc:
        if "openpyxl" in str(exc).lower():
            raise TableAnalysisDependencyError(
                "XLSX analysis requires optional dependency 'openpyxl'. "
                "Install with `pip install openpyxl>=3.1.0`."
            ) from exc
        raise InvalidTableInputError(f"Invalid XLSX content: {exc}") from exc
    except Exception as exc:
        raise InvalidTableInputError(f"Invalid XLSX content: {exc}") from exc


def _to_json_value(value: Any) -> Any:
    if value is None:
        return None

    if hasattr(value, "item"):
        try:
            value = value.item()
        except Exception:
            pass

    if isinstance(value, float):
        if math.isnan(value) or math.isinf(value):
            return None
        return value

    if isinstance(value, (str, int, bool)):
        return value

    if isinstance(value, (bytes, bytearray)):
        try:
            return value.decode("utf-8")
        except Exception:
            return value.decode("utf-8", errors="replace")

    if hasattr(value, "isoformat"):
        try:
            return value.isoformat()
        except Exception:
            pass

    return str(value)


def _safe_ratio(numerator: int, denominator: int) -> float:
    if denominator <= 0:
        return 0.0
    return round(numerator / denominator, 6)


def _safe_float(value: Any) -> float | None:
    value = _to_json_value(value)
    if value is None:
        return None
    if isinstance(value, (int, float)):
        if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
            return None
        return round(float(value), 6)
    return None


def _build_numeric_summary(dataframe, numeric_columns: list[str]) -> dict[str, dict[str, float | int | None]]:
    if not numeric_columns:
        return {}

    pd = _ensure_pandas()
    numeric_summary: dict[str, dict[str, float | int | None]] = {}

    for column in numeric_columns:
        numeric_series = pd.to_numeric(dataframe[column], errors="coerce").dropna()
        count = int(numeric_series.count())
        if count == 0:
            continue

        numeric_summary[column] = {
            "count": count,
            "mean": _safe_float(numeric_series.mean()),
            "std": _safe_float(numeric_series.std()),
            "min": _safe_float(numeric_series.min()),
            "p25": _safe_float(numeric_series.quantile(0.25)),
            "p50": _safe_float(numeric_series.quantile(0.5)),
            "p75": _safe_float(numeric_series.quantile(0.75)),
            "max": _safe_float(numeric_series.max()),
        }

    return numeric_summary


def _build_categorical_summary(dataframe, numeric_columns: list[str]) -> dict[str, dict[str, Any]]:
    categorical_summary: dict[str, dict[str, Any]] = {}
    numeric_column_set = set(numeric_columns)

    for column in dataframe.columns:
        if str(column) in numeric_column_set:
            continue
        series = dataframe[column]
        non_null = series.dropna()
        non_null_count = int(non_null.count())
        if non_null_count == 0:
            continue

        normalized = non_null.astype(str)
        top_values = normalized.value_counts(dropna=True).head(5)
        categorical_summary[str(column)] = {
            "non_null_count": non_null_count,
            "unique_count": int(non_null.nunique(dropna=True)),
            "top_values": [
                {
                    "value": str(index),
                    "count": int(count),
                    "rate": _safe_ratio(int(count), non_null_count),
                }
                for index, count in top_values.items()
            ],
        }

    return categorical_summary


def _build_datetime_summary(dataframe, numeric_columns: list[str]) -> dict[str, dict[str, Any]]:
    pd = _ensure_pandas()
    datetime_summary: dict[str, dict[str, Any]] = {}
    numeric_column_set = set(numeric_columns)

    for column in dataframe.columns:
        column_name = str(column)
        if column_name in numeric_column_set:
            continue

        series = dataframe[column].dropna()
        source_count = int(series.count())
        if source_count < 2:
            continue

        parsed = pd.to_datetime(series, errors="coerce")
        parsed_non_null = parsed.dropna()
        parsed_count = int(parsed_non_null.count())
        if parsed_count < 2:
            continue
        if _safe_ratio(parsed_count, source_count) < 0.8:
            continue

        min_value = parsed_non_null.min()
        max_value = parsed_non_null.max()
        span_days = None
        try:
            span_days = _safe_float((max_value - min_value).total_seconds() / 86400)
        except Exception:
            span_days = None

        datetime_summary[column_name] = {
            "non_null_count": parsed_count,
            "min": _to_json_value(min_value),
            "max": _to_json_value(max_value),
            "span_days": span_days,
        }

    return datetime_summary


def _build_outlier_summary(dataframe, numeric_columns: list[str]) -> dict[str, dict[str, Any]]:
    pd = _ensure_pandas()
    outlier_summary: dict[str, dict[str, Any]] = {}

    for column in numeric_columns:
        numeric_series = pd.to_numeric(dataframe[column], errors="coerce").dropna()
        count = int(numeric_series.count())
        if count < 4:
            continue

        q1 = numeric_series.quantile(0.25)
        q3 = numeric_series.quantile(0.75)
        iqr = q3 - q1
        if iqr is None or math.isnan(iqr) or iqr == 0:
            continue

        lower = q1 - 1.5 * iqr
        upper = q3 + 1.5 * iqr
        mask = (numeric_series < lower) | (numeric_series > upper)
        outlier_count = int(mask.sum())
        if outlier_count <= 0:
            continue

        outlier_summary[column] = {
            "count": count,
            "outlier_count": outlier_count,
            "outlier_rate": _safe_ratio(outlier_count, count),
            "iqr_lower": _safe_float(lower),
            "iqr_upper": _safe_float(upper),
        }

    return outlier_summary


def _build_correlation_summary(dataframe, numeric_columns: list[str]) -> dict[str, Any]:
    if len(numeric_columns) < 2:
        return {
            "pair_count": 0,
            "strong_pair_count": 0,
            "top_pairs": [],
        }

    pd = _ensure_pandas()
    numeric_frame = dataframe[numeric_columns].apply(pd.to_numeric, errors="coerce")
    correlation_matrix = numeric_frame.corr(numeric_only=True)
    top_pairs: list[dict[str, Any]] = []

    for index, left in enumerate(numeric_columns):
        for right in numeric_columns[index + 1:]:
            try:
                correlation_value = _safe_float(correlation_matrix.at[left, right])
            except Exception:
                correlation_value = None
            if correlation_value is None:
                continue
            top_pairs.append({
                "left": left,
                "right": right,
                "correlation": correlation_value,
                "absolute_correlation": _safe_float(abs(correlation_value)),
                "direction": "positive" if correlation_value >= 0 else "negative",
            })

    top_pairs.sort(
        key=lambda item: float(item.get("absolute_correlation") or 0.0),
        reverse=True,
    )
    strong_pair_count = sum(
        1 for item in top_pairs
        if float(item.get("absolute_correlation") or 0.0) >= 0.7
    )

    return {
        "pair_count": len(top_pairs),
        "strong_pair_count": strong_pair_count,
        "top_pairs": top_pairs[:12],
    }


def _build_sample_rows(dataframe, sample_rows: int) -> tuple[list[dict[str, Any]], list[Any]]:
    sample_size = max(1, min(int(sample_rows), 100))
    sampled = dataframe.head(sample_size)
    sample_records: list[dict[str, Any]] = []
    sample_indices: list[Any] = []

    for index, row in sampled.iterrows():
        sample_indices.append(_to_json_value(index))
        row_payload = {str(col): _to_json_value(row[col]) for col in sampled.columns}
        sample_records.append(row_payload)

    return sample_records, sample_indices


def _build_quality_flags(
    *,
    fields: list[dict[str, Any]],
    row_count: int,
    duplicate_row_count: int,
) -> dict[str, Any]:
    high_missing_fields: list[str] = []
    sparse_fields: list[str] = []
    candidate_key_fields: list[str] = []

    for field in fields:
        if not isinstance(field, dict):
            continue
        name = str(field.get("name") or "").strip()
        if not name:
            continue
        missing_rate = _safe_float(field.get("missing_rate")) or 0.0
        non_null_count = int(field.get("non_null_count") or 0)
        unique_count = int(field.get("unique_count") or 0)

        if missing_rate >= 0.2:
            high_missing_fields.append(name)
        if missing_rate >= 0.5:
            sparse_fields.append(name)
        if row_count > 0 and non_null_count == row_count and unique_count == row_count:
            candidate_key_fields.append(name)

    return {
        "duplicate_row_count": duplicate_row_count,
        "duplicate_row_rate": _safe_ratio(duplicate_row_count, row_count),
        "high_missing_fields": high_missing_fields,
        "sparse_fields": sparse_fields,
        "candidate_key_fields": candidate_key_fields,
    }


def analyze_table_bytes(
    file_bytes: bytes,
    *,
    file_name: str | None = None,
    file_format: str | None = None,
    sample_rows: int = 5,
    csv_encoding: str = "utf-8",
    sheet_name: str | int | None = 0,
) -> dict[str, Any]:
    table_format = _resolve_table_format(file_name, file_format)
    dataframe, parser_name = _read_dataframe(
        file_bytes,
        table_format,
        csv_encoding=csv_encoding,
        sheet_name=sheet_name,
    )

    if getattr(dataframe, "columns", None) is None:
        raise InvalidTableInputError("Table content could not be parsed as rows and columns.")

    dataframe = dataframe.copy()
    dataframe.columns = [str(column) for column in dataframe.columns.tolist()]

    row_count = int(len(dataframe.index))
    column_count = int(len(dataframe.columns))
    missing_cell_count = int(dataframe.isna().sum().sum())
    total_cells = row_count * column_count
    duplicate_row_count = int(dataframe.duplicated().sum()) if row_count > 0 else 0

    fields: list[dict[str, Any]] = []
    for column in dataframe.columns:
        series = dataframe[column]
        missing_count = int(series.isna().sum())
        non_null_count = max(row_count - missing_count, 0)
        field_payload = {
            "name": column,
            "dtype": str(series.dtype),
            "non_null_count": non_null_count,
            "missing_count": missing_count,
            "missing_rate": _safe_ratio(missing_count, row_count),
            "unique_count": int(series.nunique(dropna=True)),
            "sample_values": [_to_json_value(value) for value in series.dropna().head(3).tolist()],
        }
        fields.append(field_payload)

    numeric_columns = [str(column) for column in dataframe.select_dtypes(include=["number"]).columns.tolist()]
    numeric_summary = _build_numeric_summary(dataframe, numeric_columns)
    categorical_summary = _build_categorical_summary(dataframe, numeric_columns)
    datetime_summary = _build_datetime_summary(dataframe, numeric_columns)
    outlier_summary = _build_outlier_summary(dataframe, numeric_columns)
    correlation_summary = _build_correlation_summary(dataframe, numeric_columns)
    sample_records, sample_indices = _build_sample_rows(dataframe, sample_rows)
    quality_flags = _build_quality_flags(
        fields=fields,
        row_count=row_count,
        duplicate_row_count=duplicate_row_count,
    )

    return {
        "summary": {
            "row_count": row_count,
            "column_count": column_count,
            "missing_cell_count": missing_cell_count,
            "missing_cell_rate": _safe_ratio(missing_cell_count, total_cells),
            "numeric_column_count": len(numeric_columns),
            "categorical_column_count": len(categorical_summary),
            "datetime_column_count": len(datetime_summary),
            "duplicate_row_count": duplicate_row_count,
            "duplicate_row_rate": _safe_ratio(duplicate_row_count, row_count),
            "correlation_pair_count": int(correlation_summary.get("pair_count") or 0),
            "strong_correlation_pair_count": int(correlation_summary.get("strong_pair_count") or 0),
        },
        "fields": fields,
        "numeric_summary": numeric_summary,
        "categorical_summary": categorical_summary,
        "datetime_summary": datetime_summary,
        "outlier_summary": outlier_summary,
        "correlation_summary": correlation_summary,
        "quality_flags": quality_flags,
        "column_groups": {
            "numeric": numeric_columns,
            "categorical": sorted(categorical_summary.keys()),
            "datetime": sorted(datetime_summary.keys()),
        },
        "sample_rows": sample_records,
        "evidence": {
            "source": {
                "filename": file_name or "inline_input",
                "format": table_format,
                "size_bytes": len(file_bytes),
            },
            "parser": {
                "name": parser_name,
                "sheet_name": sheet_name if table_format == "xlsx" else None,
                "csv_encoding": csv_encoding if table_format == "csv" else None,
            },
            "sampling": {
                "sample_row_count": len(sample_records),
                "sample_row_indices": sample_indices,
            },
            "generated_at": datetime.now(timezone.utc).isoformat(),
        },
    }


def analyze_inline_table_content(
    *,
    file_name: str,
    content: str,
    file_format: str | None = None,
    content_encoding: Literal["plain", "base64"] = "plain",
    sample_rows: int = 5,
    csv_encoding: str = "utf-8",
    sheet_name: str | int | None = 0,
) -> dict[str, Any]:
    table_format = _resolve_table_format(file_name, file_format)

    if content_encoding == "base64":
        try:
            file_bytes = base64.b64decode(content, validate=True)
        except Exception as exc:
            raise InvalidTableInputError("Invalid base64 content for table input.") from exc
    else:
        if table_format == "xlsx":
            raise InvalidTableInputError("XLSX inline content must use base64 encoding.")
        file_bytes = content.encode(csv_encoding)

    return analyze_table_bytes(
        file_bytes,
        file_name=file_name,
        file_format=table_format,
        sample_rows=sample_rows,
        csv_encoding=csv_encoding,
        sheet_name=sheet_name,
    )


def _stringify_list(values: list[Any]) -> str:
    normalized = [str(value) for value in values if value is not None]
    return ", ".join(normalized[:5])


def render_table_analysis_markdown(analysis: dict[str, Any]) -> str:
    summary = analysis.get("summary")
    if not isinstance(summary, dict):
        raise InvalidTableInputError("Invalid analysis payload: missing summary.")

    fields = analysis.get("fields")
    if not isinstance(fields, list):
        raise InvalidTableInputError("Invalid analysis payload: missing fields.")

    numeric_summary = analysis.get("numeric_summary")
    if not isinstance(numeric_summary, dict):
        raise InvalidTableInputError("Invalid analysis payload: missing numeric_summary.")

    categorical_summary = analysis.get("categorical_summary")
    if categorical_summary is None:
        categorical_summary = {}
    if not isinstance(categorical_summary, dict):
        raise InvalidTableInputError("Invalid analysis payload: missing categorical_summary.")

    datetime_summary = analysis.get("datetime_summary")
    if datetime_summary is None:
        datetime_summary = {}
    if not isinstance(datetime_summary, dict):
        raise InvalidTableInputError("Invalid analysis payload: missing datetime_summary.")

    outlier_summary = analysis.get("outlier_summary")
    if outlier_summary is None:
        outlier_summary = {}
    if not isinstance(outlier_summary, dict):
        raise InvalidTableInputError("Invalid analysis payload: missing outlier_summary.")

    correlation_summary = analysis.get("correlation_summary")
    if correlation_summary is None:
        correlation_summary = {}
    if not isinstance(correlation_summary, dict):
        raise InvalidTableInputError("Invalid analysis payload: missing correlation_summary.")

    quality_flags = analysis.get("quality_flags")
    if quality_flags is None:
        quality_flags = {}
    if not isinstance(quality_flags, dict):
        raise InvalidTableInputError("Invalid analysis payload: missing quality_flags.")

    sample_rows = analysis.get("sample_rows")
    if not isinstance(sample_rows, list):
        raise InvalidTableInputError("Invalid analysis payload: missing sample_rows.")

    evidence = analysis.get("evidence")
    if not isinstance(evidence, dict):
        raise InvalidTableInputError("Invalid analysis payload: missing evidence.")

    lines: list[str] = [
        "# Table Analysis Report",
        "",
        "## Summary",
        f"- Rows: {summary.get('row_count', 0)}",
        f"- Columns: {summary.get('column_count', 0)}",
        f"- Missing Cells: {summary.get('missing_cell_count', 0)}",
        f"- Missing Cell Rate: {summary.get('missing_cell_rate', 0)}",
        f"- Duplicate Rows: {summary.get('duplicate_row_count', 0)}",
        f"- Numeric Columns: {summary.get('numeric_column_count', 0)}",
        f"- Categorical Columns: {summary.get('categorical_column_count', 0)}",
        f"- Datetime Columns: {summary.get('datetime_column_count', 0)}",
        f"- Correlation Pairs: {summary.get('correlation_pair_count', 0)}",
        f"- Strong Correlation Pairs: {summary.get('strong_correlation_pair_count', 0)}",
        "",
        "## Field Summary",
        "| Field | Type | Missing Rate | Missing Count | Non-null Count | Unique Count | Samples |",
        "| --- | --- | ---: | ---: | ---: | ---: | --- |",
    ]

    for field in fields:
        if not isinstance(field, dict):
            continue
        lines.append(
            "| {name} | {dtype} | {missing_rate} | {missing_count} | {non_null_count} | {unique_count} | {samples} |".format(
                name=field.get("name", ""),
                dtype=field.get("dtype", ""),
                missing_rate=field.get("missing_rate", 0),
                missing_count=field.get("missing_count", 0),
                non_null_count=field.get("non_null_count", 0),
                unique_count=field.get("unique_count", 0),
                samples=_stringify_list(field.get("sample_values", [])),
            )
        )

    lines.extend(["", "## Numeric Summary"])
    if numeric_summary:
        lines.extend(
            [
                "| Field | Count | Mean | Std | Min | P25 | P50 | P75 | Max |",
                "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
            ]
        )
        for field_name, stats in numeric_summary.items():
            if not isinstance(stats, dict):
                continue
            lines.append(
                "| {field} | {count} | {mean} | {std} | {minv} | {p25} | {p50} | {p75} | {maxv} |".format(
                    field=field_name,
                    count=stats.get("count", 0),
                    mean=stats.get("mean", ""),
                    std=stats.get("std", ""),
                    minv=stats.get("min", ""),
                    p25=stats.get("p25", ""),
                    p50=stats.get("p50", ""),
                    p75=stats.get("p75", ""),
                    maxv=stats.get("max", ""),
                )
            )
    else:
        lines.append("No numeric columns detected.")

    lines.extend(["", "## Categorical Summary"])
    if categorical_summary:
        lines.extend(
            [
                "| Field | Non-null Count | Unique Count | Top Values |",
                "| --- | ---: | ---: | --- |",
            ]
        )
        for field_name, stats in categorical_summary.items():
            if not isinstance(stats, dict):
                continue
            top_values = stats.get("top_values")
            top_value_text = ""
            if isinstance(top_values, list):
                top_value_text = "; ".join(
                    [
                        f"{item.get('value', '')} ({item.get('count', 0)})"
                        for item in top_values
                        if isinstance(item, dict)
                    ]
                )
            lines.append(
                "| {field} | {non_null_count} | {unique_count} | {top_values} |".format(
                    field=field_name,
                    non_null_count=stats.get("non_null_count", 0),
                    unique_count=stats.get("unique_count", 0),
                    top_values=top_value_text or "-",
                )
            )
    else:
        lines.append("No categorical columns detected.")

    lines.extend(["", "## Datetime Summary"])
    if datetime_summary:
        lines.extend(
            [
                "| Field | Non-null Count | Min | Max | Span Days |",
                "| --- | ---: | --- | --- | ---: |",
            ]
        )
        for field_name, stats in datetime_summary.items():
            if not isinstance(stats, dict):
                continue
            lines.append(
                "| {field} | {non_null_count} | {minv} | {maxv} | {span_days} |".format(
                    field=field_name,
                    non_null_count=stats.get("non_null_count", 0),
                    minv=stats.get("min", ""),
                    maxv=stats.get("max", ""),
                    span_days=stats.get("span_days", ""),
                )
            )
    else:
        lines.append("No datetime-like columns detected.")

    lines.extend(["", "## Outlier Summary"])
    if outlier_summary:
        lines.extend(
            [
                "| Field | Count | Outliers | Outlier Rate | Lower Bound | Upper Bound |",
                "| --- | ---: | ---: | ---: | ---: | ---: |",
            ]
        )
        for field_name, stats in outlier_summary.items():
            if not isinstance(stats, dict):
                continue
            lines.append(
                "| {field} | {count} | {outlier_count} | {outlier_rate} | {lower} | {upper} |".format(
                    field=field_name,
                    count=stats.get("count", 0),
                    outlier_count=stats.get("outlier_count", 0),
                    outlier_rate=stats.get("outlier_rate", 0),
                    lower=stats.get("iqr_lower", ""),
                    upper=stats.get("iqr_upper", ""),
                )
            )
    else:
        lines.append("No numeric outliers detected by IQR rule.")

    lines.extend(["", "## Correlation Summary"])
    top_pairs = correlation_summary.get("top_pairs") if isinstance(correlation_summary, dict) else None
    if isinstance(top_pairs, list) and top_pairs:
        lines.extend(
            [
                "| Left Field | Right Field | Correlation | Direction |",
                "| --- | --- | ---: | --- |",
            ]
        )
        for pair in top_pairs:
            if not isinstance(pair, dict):
                continue
            lines.append(
                "| {left} | {right} | {correlation} | {direction} |".format(
                    left=pair.get("left", ""),
                    right=pair.get("right", ""),
                    correlation=pair.get("correlation", ""),
                    direction=pair.get("direction", ""),
                )
            )
    else:
        lines.append("No numeric correlation pairs detected.")

    lines.extend(["", "## Quality Flags"])
    lines.append(f"- Duplicate Rows: {quality_flags.get('duplicate_row_count', 0)}")
    lines.append(f"- High Missing Fields: {_stringify_list(quality_flags.get('high_missing_fields', [])) or 'None'}")
    lines.append(f"- Sparse Fields: {_stringify_list(quality_flags.get('sparse_fields', [])) or 'None'}")
    lines.append(f"- Candidate Key Fields: {_stringify_list(quality_flags.get('candidate_key_fields', [])) or 'None'}")

    lines.extend(
        [
            "",
            "## Sample Rows",
            "```json",
            json.dumps(sample_rows, ensure_ascii=False, indent=2),
            "```",
            "",
            "## Evidence",
            "```json",
            json.dumps(evidence, ensure_ascii=False, indent=2),
            "```",
        ]
    )

    return "\n".join(lines)


def export_table_analysis(
    analysis: dict[str, Any],
    export_format: Literal["json", "markdown"],
) -> dict[str, Any] | str:
    if export_format == "json":
        return analysis
    if export_format == "markdown":
        return render_table_analysis_markdown(analysis)
    raise InvalidTableInputError("Unsupported export format. Use json or markdown.")

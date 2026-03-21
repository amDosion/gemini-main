"""
Excel Tools - Excel 分析工具

提供：
- read_excel_file: 读取 Excel 文件
- clean_dataframe: 清理数据框
- analyze_dataframe: 分析数据框
- generate_chart: 生成图表
"""

import logging
from typing import Dict, Any, Optional, List
import io
import base64
import os
from pathlib import Path

logger = logging.getLogger(__name__)

# 延迟导入 pandas（如果未安装则使用占位实现）
try:
    import pandas as pd
    import numpy as np
    PANDAS_AVAILABLE = True
except ImportError:
    PANDAS_AVAILABLE = False
    logger.warning("[ExcelTools] pandas not available, using placeholder implementation")

# 延迟导入 matplotlib（如果未安装则使用占位实现）
try:
    import matplotlib
    matplotlib.use('Agg')  # 非交互式后端
    import matplotlib.pyplot as plt
    MATPLOTLIB_AVAILABLE = True
except ImportError:
    MATPLOTLIB_AVAILABLE = False
    logger.warning("[ExcelTools] matplotlib not available, chart generation disabled")


ALLOWED_TABLE_SUFFIXES = {".xlsx", ".xls", ".csv", ".tsv"}
ALLOWED_TABLE_ROOTS_ENV = "EXCEL_WORKFLOW_ALLOWED_ROOTS"


def _resolve_allowed_table_roots() -> List[Path]:
    raw = str(os.getenv(ALLOWED_TABLE_ROOTS_ENV, "") or "").strip()
    roots: List[Path] = []
    if raw:
        for item in raw.split(","):
            text = str(item or "").strip()
            if not text:
                continue
            try:
                roots.append(Path(text).expanduser().resolve())
            except Exception:
                continue
    if roots:
        return roots

    cwd = Path.cwd().resolve()
    default_roots = [cwd, (cwd / "tmp").resolve(), Path("/tmp"), Path("/private/tmp")]
    unique_roots: List[Path] = []
    seen: set[str] = set()
    for root in default_roots:
        marker = str(root)
        if marker in seen:
            continue
        seen.add(marker)
        unique_roots.append(root)
    return unique_roots


def _is_path_in_roots(candidate: Path, roots: List[Path]) -> bool:
    for root in roots:
        if candidate == root or root in candidate.parents:
            return True
    return False


def _resolve_table_path(file_path: str) -> Path:
    raw_path = str(file_path or "").strip()
    if not raw_path:
        raise ValueError("file_path is required")

    candidate = Path(raw_path).expanduser()
    if not candidate.is_absolute():
        candidate = (Path.cwd() / candidate).resolve()
    else:
        candidate = candidate.resolve()

    if not candidate.exists() or not candidate.is_file():
        raise FileNotFoundError(f"File not found: {candidate}")

    if candidate.suffix.lower() not in ALLOWED_TABLE_SUFFIXES:
        raise ValueError(
            f"Unsupported file type: {candidate.suffix}. Supported: {sorted(ALLOWED_TABLE_SUFFIXES)}"
        )

    allowed_roots = _resolve_allowed_table_roots()
    if not _is_path_in_roots(candidate, allowed_roots):
        raise PermissionError(
            f"Path is outside allowed roots: {candidate}. "
            f"Configure {ALLOWED_TABLE_ROOTS_ENV} for trusted directories."
        )

    return candidate


def _sanitize_dataframe_for_json(df):
    if not PANDAS_AVAILABLE:
        return df
    return df.where(pd.notna(df), None)


def _build_dataframe_from_payload(df_data: Dict[str, Any]):
    if isinstance(df_data, dict) and "cleaned_data" in df_data:
        return pd.DataFrame(df_data["cleaned_data"])
    if isinstance(df_data, dict) and "records" in df_data:
        return pd.DataFrame(df_data["records"])
    if isinstance(df_data, dict) and "sample_data" in df_data:
        return pd.DataFrame(df_data["sample_data"])
    return pd.DataFrame(df_data)


def _normalize_analysis_type(analysis_type: str) -> str:
    raw = str(analysis_type or "comprehensive").strip().lower()
    aliases = {
        "summary": "statistics",
        "stats": "statistics",
        "statistic": "statistics",
        "trend": "trends",
        "anomaly": "distribution",
        "anomalies": "distribution",
        "all": "comprehensive",
    }
    return aliases.get(raw, raw)


async def read_excel_file(
    file_path: str,
    sheet_name: Optional[str] = None
) -> Dict[str, Any]:
    """
    读取 Excel 文件
    
    Args:
        file_path: Excel 文件路径
        sheet_name: 工作表名称（可选，默认读取第一个工作表）
        
    Returns:
        数据结构信息（列名、数据类型、形状、样本数据等）
    """
    if not PANDAS_AVAILABLE:
        return {
            "error": "pandas not installed. Please install: pip install pandas openpyxl",
            "file_path": file_path
        }
    
    try:
        resolved_path = _resolve_table_path(file_path)
        logger.info(f"[ExcelTools] Reading table file: {resolved_path}")

        # 读取文件（支持 Excel + CSV/TSV）
        suffix = resolved_path.suffix.lower()
        if suffix in {".csv", ".tsv"}:
            sep = "\t" if suffix == ".tsv" else ","
            df = pd.read_csv(resolved_path, sep=sep)
        else:
            df = pd.read_excel(resolved_path, sheet_name=sheet_name, engine='openpyxl')

        max_rows = 5000
        records_df = _sanitize_dataframe_for_json(df.head(max_rows))
        sample_df = records_df.head(5)
        
        # 返回结构化数据
        result = {
            "columns": df.columns.tolist(),
            "dtypes": df.dtypes.astype(str).to_dict(),
            "shape": list(df.shape),
            "sample_data": sample_df.to_dict('records'),
            "records": records_df.to_dict('records'),
            "total_rows": int(df.shape[0]),
            "rows_included": int(records_df.shape[0]),
            "truncated": bool(df.shape[0] > max_rows),
            "null_counts": df.isnull().sum().to_dict(),
            "duplicate_rows": int(df.duplicated().sum()),
            "file_path": str(resolved_path)
        }
        
        logger.info(f"[ExcelTools] Excel file read successfully: {result['shape']}")
        return result
        
    except Exception as e:
        logger.error(f"[ExcelTools] Error reading Excel file: {e}", exc_info=True)
        return {
            "error": str(e),
            "file_path": file_path
        }


async def clean_dataframe(
    df_data: Dict[str, Any],
    cleaning_rules: Dict[str, Any]
) -> Dict[str, Any]:
    """
    清理数据框
    
    Args:
        df_data: 数据框数据（字典格式，包含 'sample_data' 或完整数据）
        cleaning_rules: 清理规则
            - handle_nulls: "drop" | "fill" | "interpolate"
            - fill_value: 填充值（当 handle_nulls="fill" 时使用）
            - remove_outliers: bool（是否移除异常值）
            - standardize: bool（是否标准化）
        
    Returns:
        清理后的数据（字典格式）
    """
    if not PANDAS_AVAILABLE:
        return {
            "error": "pandas not installed",
            "cleaned_data": df_data
        }
    
    try:
        logger.info(f"[ExcelTools] Cleaning dataframe with rules: {cleaning_rules}")
        
        # 从字典重建 DataFrame
        df = _build_dataframe_from_payload(df_data)
        
        cleaning_steps = []
        issues_fixed = []
        
        # 处理缺失值
        if cleaning_rules.get("handle_nulls") == "drop":
            before_count = len(df)
            df = df.dropna()
            after_count = len(df)
            if before_count > after_count:
                cleaning_steps.append(f"删除缺失值: {before_count - after_count} 行")
                issues_fixed.append(f"缺失值: {before_count - after_count} 行")
        elif cleaning_rules.get("handle_nulls") == "fill":
            fill_value = cleaning_rules.get("fill_value", 0)
            df = df.fillna(fill_value)
            cleaning_steps.append(f"填充缺失值: {fill_value}")
            issues_fixed.append("缺失值已填充")
        elif cleaning_rules.get("handle_nulls") == "interpolate":
            numeric_cols = df.select_dtypes(include=['number']).columns
            df[numeric_cols] = df[numeric_cols].interpolate()
            cleaning_steps.append("插值填充缺失值")
            issues_fixed.append("缺失值已插值")
        
        # 处理异常值
        if cleaning_rules.get("remove_outliers"):
            numeric_cols = df.select_dtypes(include=['number']).columns
            before_count = len(df)
            
            for col in numeric_cols:
                Q1 = df[col].quantile(0.25)
                Q3 = df[col].quantile(0.75)
                IQR = Q3 - Q1
                lower_bound = Q1 - 1.5 * IQR
                upper_bound = Q3 + 1.5 * IQR
                df = df[(df[col] >= lower_bound) & (df[col] <= upper_bound)]
            
            after_count = len(df)
            if before_count > after_count:
                cleaning_steps.append(f"移除异常值: {before_count - after_count} 行")
                issues_fixed.append(f"异常值: {before_count - after_count} 行")
        
        # 数据标准化
        if cleaning_rules.get("standardize"):
            numeric_cols = df.select_dtypes(include=['number']).columns
            for col in numeric_cols:
                std = df[col].std()
                if std and not np.isclose(std, 0):
                    df[col] = (df[col] - df[col].mean()) / std
            cleaning_steps.append("数据标准化")
            issues_fixed.append("数据已标准化")
        
        logger.info(f"[ExcelTools] Data cleaning completed: {len(cleaning_steps)} steps")
        sanitized_df = _sanitize_dataframe_for_json(df)
        
        return {
            "cleaning_steps": cleaning_steps,
            "cleaned_data": sanitized_df.to_dict('records'),
            "cleaned_shape": list(df.shape),
            "issues_fixed": issues_fixed,
            "data_quality_improvement": f"数据质量改善: {len(issues_fixed)} 项修复"
        }
        
    except Exception as e:
        logger.error(f"[ExcelTools] Error cleaning dataframe: {e}", exc_info=True)
        return {
            "error": str(e),
            "cleaned_data": df_data
        }


async def analyze_dataframe(
    df_data: Dict[str, Any],
    analysis_type: str = "comprehensive"
) -> Dict[str, Any]:
    """
    分析数据框
    
    Args:
        df_data: 数据框数据（字典格式）
        analysis_type: 分析类型
            - "comprehensive": 全面分析
            - "statistics": 描述性统计
            - "correlation": 相关性分析
            - "trends": 趋势分析
            - "distribution": 分布分析
        
    Returns:
        分析结果
    """
    if not PANDAS_AVAILABLE:
        return {
            "error": "pandas not installed",
            "analysis_type": analysis_type
        }
    
    try:
        normalized_analysis_type = _normalize_analysis_type(analysis_type)
        logger.info(f"[ExcelTools] Analyzing dataframe: requested={analysis_type}, normalized={normalized_analysis_type}")

        allowed_types = {"comprehensive", "statistics", "correlation", "trends", "distribution"}
        if normalized_analysis_type not in allowed_types:
            return {
                "error": f"Unsupported analysis_type: {analysis_type}",
                "analysis_type": normalized_analysis_type,
                "supported_types": sorted(allowed_types),
            }

        # 从字典重建 DataFrame
        df = _build_dataframe_from_payload(df_data)
        
        result = {}
        numeric_cols = df.select_dtypes(include=['number']).columns.tolist()
        
        # 描述性统计
        if normalized_analysis_type in ["comprehensive", "statistics"]:
            result["descriptive_stats"] = df.describe().to_dict()
            result["basic_stats"] = {
                "mean": df[numeric_cols].mean().to_dict() if numeric_cols else {},
                "median": df[numeric_cols].median().to_dict() if numeric_cols else {},
                "std": df[numeric_cols].std().to_dict() if numeric_cols else {}
            }
        
        # 相关性分析
        if normalized_analysis_type in ["comprehensive", "correlation"] and len(numeric_cols) > 1:
            result["correlations"] = df[numeric_cols].corr().to_dict()
        
        # 分布分析
        if normalized_analysis_type in ["comprehensive", "distribution"] and numeric_cols:
            result["distributions"] = {}
            for col in numeric_cols:
                result["distributions"][col] = {
                    "mean": float(df[col].mean()),
                    "median": float(df[col].median()),
                    "std": float(df[col].std()),
                    "min": float(df[col].min()),
                    "max": float(df[col].max()),
                    "skew": float(df[col].skew()) if len(df) > 0 else 0.0,
                    "kurtosis": float(df[col].kurtosis()) if len(df) > 0 else 0.0
                }
        
        # 趋势分析（简化实现）
        if normalized_analysis_type in ["comprehensive", "trends"] and numeric_cols:
            result["trends"] = {}
            for col in numeric_cols:
                if len(df) > 1:
                    # 简单的线性趋势
                    x = np.arange(len(df))
                    y = df[col].values
                    slope = np.polyfit(x, y, 1)[0] if len(y) > 1 else 0
                    result["trends"][col] = {
                        "slope": float(slope),
                        "trend": "increasing" if slope > 0 else "decreasing" if slope < 0 else "stable"
                    }
        
        # 数据洞察（基于分析结果）
        insights = []
        if "correlations" in result:
            # 找出强相关性
            for col1, corr_dict in result["correlations"].items():
                for col2, corr_value in corr_dict.items():
                    if col1 != col2 and abs(corr_value) > 0.7:
                        insights.append(f"{col1} 与 {col2} 有强相关性 ({corr_value:.2f})")
        
        if "trends" in result:
            for col, trend_info in result["trends"].items():
                if trend_info["slope"] != 0:
                    insights.append(f"{col} 呈现{trend_info['trend']}趋势")
        
        result["insights"] = insights if insights else ["数据无明显趋势或相关性"]
        
        logger.info(f"[ExcelTools] Data analysis completed: {len(result)} analysis types")
        result["analysis_type"] = normalized_analysis_type
        return result
        
    except Exception as e:
        logger.error(f"[ExcelTools] Error analyzing dataframe: {e}", exc_info=True)
        return {
            "error": str(e),
            "analysis_type": _normalize_analysis_type(analysis_type)
        }


async def generate_chart(
    df_data: Dict[str, Any],
    chart_type: str,
    x_column: str,
    y_column: Optional[str] = None,
    title: Optional[str] = None
) -> str:
    """
    生成图表（返回 Base64 编码的图片）
    
    Args:
        df_data: 数据框数据（字典格式）
        chart_type: 图表类型（bar, line, scatter, histogram, pie）
        x_column: X 轴列名
        y_column: Y 轴列名（可选，用于 line/scatter）
        title: 图表标题（可选）
        
    Returns:
        Base64 编码的图片（data:image/png;base64,...）
    """
    if not PANDAS_AVAILABLE or not MATPLOTLIB_AVAILABLE:
        return ""
    
    try:
        logger.info(f"[ExcelTools] Generating {chart_type} chart: {x_column} vs {y_column}")
        
        # 从字典重建 DataFrame
        df = _build_dataframe_from_payload(df_data)
        
        # 创建图表
        plt.figure(figsize=(10, 6))
        
        if chart_type == "bar":
            if y_column:
                df.plot(x=x_column, y=y_column, kind='bar')
            else:
                df[x_column].value_counts().plot(kind='bar')
        elif chart_type == "line" and y_column:
            df.plot(x=x_column, y=y_column, kind='line', marker='o')
        elif chart_type == "scatter" and y_column:
            df.plot(x=x_column, y=y_column, kind='scatter')
        elif chart_type == "histogram":
            df[x_column].hist(bins=20)
        elif chart_type == "pie":
            if y_column:
                df.set_index(x_column)[y_column].plot(kind='pie', autopct='%1.1f%%')
            else:
                df[x_column].value_counts().plot(kind='pie', autopct='%1.1f%%')
        else:
            logger.warning(f"[ExcelTools] Unsupported chart type: {chart_type}")
            plt.close()
            return ""
        
        chart_title = title or f"{chart_type.title()} Chart: {x_column}" + (f" vs {y_column}" if y_column else "")
        plt.title(chart_title)
        plt.tight_layout()
        
        # 转换为 Base64
        buffer = io.BytesIO()
        plt.savefig(buffer, format='png', dpi=150, bbox_inches='tight')
        buffer.seek(0)
        chart_base64 = base64.b64encode(buffer.read()).decode()
        plt.close()
        
        logger.info(f"[ExcelTools] Chart generated successfully")
        return f"data:image/png;base64,{chart_base64}"
        
    except Exception as e:
        logger.error(f"[ExcelTools] Error generating chart: {e}", exc_info=True)
        if MATPLOTLIB_AVAILABLE:
            plt.close()
        return ""

"""
Workflow Templates - 工作流模板模块

提供：
- 图像编辑工作流
- Excel 分析工作流
"""

from .image_edit_workflow import ImageEditWorkflow
from .excel_analysis_workflow import ExcelAnalysisWorkflow

__all__ = [
    "ImageEditWorkflow",
    "ExcelAnalysisWorkflow"
]

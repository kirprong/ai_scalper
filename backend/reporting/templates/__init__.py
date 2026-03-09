"""
Report Templates Module

Provides template configurations for PDF report generation.
"""

from backend.reporting.templates.report_template import (
    ReportTemplate,
    DailyReportTemplate,
    WeeklyReportTemplate,
    MonthlyReportTemplate,
)

__all__ = [
    "ReportTemplate",
    "DailyReportTemplate",
    "WeeklyReportTemplate",
    "MonthlyReportTemplate",
]

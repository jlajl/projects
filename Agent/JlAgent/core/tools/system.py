from datetime import datetime
from pathlib import Path

from .base import Tool

NO_PARAMS = {"type": "object", "properties": {}}


def is_leap_year(year: int) -> bool:
    """公历闰年规则：能被 4 整除，且整百年必须能被 400 整除。"""
    return year % 4 == 0 and (year % 100 != 0 or year % 400 == 0)


def _leap_year(year: object) -> str:
    try:
        value = int(year)  # 允许模型把年份写成字符串 "2024"
    except (TypeError, ValueError):
        return f"错误：year 必须是整数，收到 {year!r}"
    if not 1 <= value <= 9999:
        return "错误：year 必须在 1-9999 之间"
    if is_leap_year(value):
        return f"{value} 年是闰年（2 月 29 天，全年 366 天）"
    return f"{value} 年不是闰年（2 月 28 天，全年 365 天）"


def build_tools(workspace: Path) -> list[Tool]:
    return [
        Tool(
            "getDate",
            "获取当前电脑的日期和时间",
            NO_PARAMS,
            lambda: datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        ),
        Tool(
            "getCwd",
            "获取当前工作目录",
            NO_PARAMS,
            lambda: str(workspace),
        ),
        Tool(
            "isLeapYear",
            "判断指定年份是否为闰年。规则：能被 4 整除，且整百年（如 1900）"
            "必须能被 400 整除。返回该年的天数说明。",
            {
                "type": "object",
                "properties": {
                    "year": {
                        "type": "integer",
                        "description": "待判断的年份，公历纪年，范围 1-9999",
                        "minimum": 1,
                        "maximum": 9999,
                    }
                },
                "required": ["year"],
            },
            _leap_year,
        ),
    ]

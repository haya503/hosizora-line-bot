# src/message_parser.py
from __future__ import annotations
import re
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from typing import Literal

JST = timezone(timedelta(hours=9))

ERROR_MESSAGE = """\
❌ 形式が正しくありません。
以下の形式でメンションしてください：

@Bot [日付] [時間] [場所]

例：
・@Bot 明日 夜 東京
・@Bot 今日 21時 阿蘇山
・@Bot 5月20日 午後9時 新宿区"""


@dataclass
class ParsedRequest:
    target_date: date
    time_type: Literal["night", "hour"]
    hour: int | None
    location: str


class ParseError(Exception):
    pass


_MENTION_RE = re.compile(r"@\S+")
# 今夜/今日の夜/明日の夜/明後日の夜 → 日付+夜を同時に確定
_COMPOUND_RE = re.compile(r"今夜|今日の夜|明日の夜|明後日の夜")
# 単独日付トークン
_DATE_RE = re.compile(r"今日|明日|明後日|(\d{1,2})月(\d{1,2})日|(\d{1,2})/(\d{1,2})")
# 時間：午後Xh / 夜Xh / 夜のXh → +12, 午前Xh, Xh
_HOUR_RE = re.compile(r"(午後|夜の?|)(\d{1,2})時|(午前)(\d{1,2})時")
# スタンドアロン「夜」（前後が空白または文字列境界）
_NIGHT_RE = re.compile(r"(?:^|\s)夜(?:\s|$)")


def parse_mention_text(text: str, today: date | None = None) -> ParsedRequest:
    if today is None:
        today = datetime.now(JST).date()

    clean = _MENTION_RE.sub("", text).strip()

    target_date: date | None = None
    time_type: Literal["night", "hour"] | None = None
    hour: int | None = None

    def sub_compound(m: re.Match) -> str:
        nonlocal target_date, time_type
        w = m.group(0)
        if w in ("今夜", "今日の夜"):
            target_date = today
        elif w == "明日の夜":
            target_date = today + timedelta(days=1)
        elif w == "明後日の夜":
            target_date = today + timedelta(days=2)
        time_type = "night"
        return " "

    loc = _COMPOUND_RE.sub(sub_compound, clean)

    def sub_date(m: re.Match) -> str:
        nonlocal target_date
        if target_date is not None:
            return " "
        w = m.group(0)
        if w == "今日":
            target_date = today
        elif w == "明日":
            target_date = today + timedelta(days=1)
        elif w == "明後日":
            target_date = today + timedelta(days=2)
        elif m.group(1):  # X月Y日
            target_date = _resolve_date(today, int(m.group(1)), int(m.group(2)))
        elif m.group(3):  # X/Y
            target_date = _resolve_date(today, int(m.group(3)), int(m.group(4)))
        return " "

    loc = _DATE_RE.sub(sub_date, loc)

    def sub_hour(m: re.Match) -> str:
        nonlocal time_type, hour
        if time_type is not None:
            return " "
        if m.group(3):  # 午前Xh
            h = int(m.group(4))
            hour = 0 if h == 12 else h
        else:
            prefix = m.group(1)  # "午後", "夜", "夜の", or ""
            h = int(m.group(2))
            if prefix in ("午後", "夜", "夜の"):
                h = h + 12 if h <= 11 else h
            hour = h
        time_type = "hour"
        return " "

    loc = _HOUR_RE.sub(sub_hour, loc)

    # スタンドアロン「夜」
    if time_type is None and _NIGHT_RE.search(loc):
        time_type = "night"
        loc = _NIGHT_RE.sub(" ", loc)

    if target_date is None or time_type is None:
        raise ParseError(ERROR_MESSAGE)

    location = loc.strip()
    if not location:
        raise ParseError(ERROR_MESSAGE)

    return ParsedRequest(
        target_date=target_date,
        time_type=time_type,
        hour=hour if time_type == "hour" else None,
        location=location,
    )


def _resolve_date(today: date, month: int, day: int) -> date:
    try:
        d = date(today.year, month, day)
    except ValueError:
        raise ParseError(ERROR_MESSAGE)
    if d < today:
        try:
            return date(today.year + 1, month, day)
        except ValueError:
            raise ParseError(ERROR_MESSAGE)
    return d

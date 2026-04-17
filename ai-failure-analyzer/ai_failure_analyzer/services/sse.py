"""SSE 文本帧格式化。"""

import json
from typing import Any


def format_sse(event: str, data: Any) -> str:
    """返回一条 SSE 消息（含结尾空行）。"""
    if isinstance(data, (dict, list)):
        payload = json.dumps(data, ensure_ascii=False)
    else:
        payload = str(data)
    return f"event: {event}\ndata: {payload}\n\n"

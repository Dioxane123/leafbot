from typing import Any
from melobot.protocols.onebot.v11 import Adapter

_RawData = dict[str, Any]

async def patch_event_anonymous_missing(raw_dict: _RawData, _: Exception):
    """
    使用NapCat v4.9.8 时接收群消息时会返回KeyError: 'anonymous'
    """
    if raw_dict.get("message_type") == "group" and "anonymous" not in raw_dict:
        raw_dict["anonymous"] = None

def patch_all(adapter: Adapter):
    adapter.when_validate_error(validate_type="event")(patch_event_anonymous_missing)
    return adapter
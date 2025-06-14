from melobot import Bot, PluginPlanner, on_full_match, send_text, on_start_match
from melobot.protocols.onebot.v11 import ForwardWebSocketIO, OneBotV11Protocol, MessageEvent, on_message, Adapter, MsgChecker
from melobot.protocols.onebot.v11 import NodeSegment, ImageSegment, TextSegment, LevelRole
from melobot.utils.parse import CmdParser, CmdArgs

from datetime import datetime
from zoneinfo import ZoneInfo

from utils.image import img_to_b64

import os
from dotenv import load_dotenv
load_dotenv()

OWNER_ID = os.getenv("OWNER")

@on_start_match(".sayhi")
async def echo_hi(e: MessageEvent) -> None:
    if e.sender.user_id != OWNER_ID:
        await send_text("你好")
    else:
        time = datetime.now(ZoneInfo("Asia/Shanghai")).strftime("%H:%M:%S")
        await send_text(f"你好，主人！现在时间是 {time}")

@on_full_match("meow")
async def meow(e: MessageEvent, adaptor: Adapter) -> None:
    node1 = NodeSegment(content=[TextSegment("我是猫娘喵")], name="卡拉彼丘量产型猫娘", uin=e.user_id, use_std=True)
    node2 = NodeSegment(content=[ImageSegment(file=img_to_b64("image.png"))],
                        name="卡拉彼丘量产型猫娘", uin=e.user_id, use_std=True)
    # await adaptor.send_forward_custom([node1, node2], group_id=662805726)
    await adaptor.send_forward_custom([node1, node2], user_id=e.user_id)

HelloPlugin = PluginPlanner(version="0.0.1", flows=[echo_hi, meow])
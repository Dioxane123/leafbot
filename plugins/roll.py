from melobot import Bot, PluginPlanner, on_contain_match, send_text, on_start_match
from melobot.protocols.onebot.v11 import ForwardWebSocketIO, OneBotV11Protocol, MessageEvent, on_message, Adapter, MsgChecker
from melobot.protocols.onebot.v11 import NodeSegment, ImageSegment, TextSegment, LevelRole
from melobot.utils.parse import CmdParser, CmdArgs

import random
@on_message(parser=CmdParser(cmd_start='.',cmd_sep=' ', targets='roll'))
async def roll(args: CmdArgs, e: MessageEvent) -> None:
    assert args.name == 'roll'
    if len(args.vals) == 0:
        await send_text("请指定一个整数")
        return
    try:
        i = int(args.vals[0])
        if i < 1:
            await send_text("请指定一个大于等于 1 的整数")
        else:
            await send_text(f"你掷出了 {random.randint(1, int(args.vals[0]))} 点")
    except ValueError:
        await send_text("请输入一个有效的整数")

RollPlugin = PluginPlanner(version="1.0.0", flows=[roll])
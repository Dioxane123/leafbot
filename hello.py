from melobot import Bot, PluginPlanner, on_contain_match, send_text, on_start_match
from melobot.protocols.onebot.v11 import ForwardWebSocketIO, OneBotV11Protocol, MessageEvent, on_message, Adapter, MsgChecker
from melobot.protocols.onebot.v11 import NodeSegment, ImageSegment, TextSegment, LevelRole
from melobot.utils.parse import CmdParser, CmdArgs
from datetime import datetime
from zoneinfo import ZoneInfo
from utils.image import img_to_b64
import random

OWNER_ID = 1204876262

# img = ImageSegment(file=img_to_b64("image.png"))
@on_start_match(".sayhi")
async def echo_hi(e: MessageEvent) -> None:
    if e.sender.user_id != OWNER_ID:
        await send_text("你好")
    else:
        time = datetime.now(ZoneInfo("Asia/Shanghai")).strftime("%H:%M:%S")
        await send_text(f"你好，主人！现在时间是 {time}")

@on_contain_match("meow")
async def meow(e: MessageEvent, adaptor: Adapter) -> None:
    node1 = NodeSegment(content=[TextSegment("我是猫娘喵")], name="卡拉彼丘量产型猫娘", uin=e.user_id, use_std=True)
    node2 = NodeSegment(content=[ImageSegment(file=img_to_b64("image.png"))],
                        name="卡拉彼丘量产型猫娘", uin=e.user_id, use_std=True)
    await adaptor.send_forward_custom([node1, node2], group_id=662805726)
    # await adaptor.send(img)

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
    

hello_plugin = PluginPlanner(version="1.0.0", flows=[echo_hi, roll, meow])
# meow_plugin = PluginPlanner(version="1.0.0", flows=[meow])

if __name__ == "__main__":
    bot = Bot(__name__)
    bot.add_protocol(OneBotV11Protocol(ForwardWebSocketIO("ws://parodydeepseek.news:28275")))
    bot.load_plugin(hello_plugin)
    bot.run()
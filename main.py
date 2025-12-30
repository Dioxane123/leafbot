from melobot import Bot, PluginPlanner, on_contain_match, send_text, on_start_match
from melobot.protocols.onebot.v11 import ForwardWebSocketIO, OneBotV11Protocol, MessageEvent, on_message, Adapter, MsgChecker
from melobot.protocols.onebot.v11 import NodeSegment, ImageSegment, TextSegment, LevelRole
from melobot.utils.parse import CmdParser, CmdArgs

from plugins.chat import ChatPlugin
from plugins.hello import HelloPlugin
from plugins.roll import RollPlugin
from plugins.OneMore import OneMorePlugin
from plugins.rss import RssPlugin
from plugins.timer import TimerPlugin

from plugins.ob11adaptor_patches import patch_all

from dotenv import load_dotenv
load_dotenv()
import os
SOCKET_URL = os.getenv("SOCKET_URL", "ws://localhost:8080")
SOCKET_TOKEN = os.getenv("SOCKET_TOKEN", "")

if __name__ == "__main__":
    bot = (
        Bot("leafbot")
        .add_adapter(patch_all(Adapter()))
        .add_io(ForwardWebSocketIO(url=SOCKET_URL, access_token=SOCKET_TOKEN))
    )
    # bot = Bot(__name__).add_adapter(patch_all(Adapter()))
    # bot.add_io(ForwardWebSocketIO(url=SOCKET_URL, access_token=SOCKET_TOKEN))
    bot.load_plugin(HelloPlugin)
    bot.load_plugin(ChatPlugin)
    bot.load_plugin(RollPlugin)
    bot.load_plugin(OneMorePlugin)
    bot.load_plugin(RssPlugin)
    bot.load_plugin(TimerPlugin)
    bot.run()
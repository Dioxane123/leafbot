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

from dotenv import load_dotenv
load_dotenv()
import os
SOCKET_URL = os.getenv("SOCKET_URL", "ws://localhost:8080")

if __name__ == "__main__":
    bot = Bot(__name__)
    bot.add_protocol(OneBotV11Protocol(ForwardWebSocketIO(SOCKET_URL)))
    bot.load_plugin(HelloPlugin)
    bot.load_plugin(ChatPlugin)
    bot.load_plugin(RollPlugin)
    bot.load_plugin(OneMorePlugin)
    bot.load_plugin(RssPlugin)
    bot.load_plugin(TimerPlugin)
    bot.run()
from melobot import Bot, PluginPlanner, on_contain_match, send_text, on_start_match
from melobot.protocols.onebot.v11 import ForwardWebSocketIO, OneBotV11Protocol, MessageEvent, on_message, Adapter, MsgChecker
from melobot.protocols.onebot.v11 import NodeSegment, ImageSegment, TextSegment, LevelRole
from melobot.utils.parse import CmdParser, CmdArgs

from plugins.chat import ChatPlugin
from plugins.hello import HelloPlugin
from plugins.roll import RollPlugin

OWNER_ID = 1204876262


if __name__ == "__main__":
    bot = Bot(__name__)
    bot.add_protocol(OneBotV11Protocol(ForwardWebSocketIO("ws://parodydeepseek.news:28275")))
    bot.load_plugin(HelloPlugin)
    bot.load_plugin(ChatPlugin)
    bot.load_plugin(RollPlugin)
    bot.run()
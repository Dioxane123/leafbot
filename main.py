from melobot import Bot, PluginPlanner, on_contain_match, send_text, on_start_match
from melobot.protocols.onebot.v11 import ForwardWebSocketIO, OneBotV11Protocol, MessageEvent, on_message, Adapter, MsgChecker
from melobot.protocols.onebot.v11 import NodeSegment, ImageSegment, TextSegment, LevelRole
from melobot.utils.parse import CmdParser, CmdArgs

from plugins.chat import ChatPlugin
from plugins.hello import HelloPlugin
from plugins.roll import RollPlugin
from plugins.OneMore import OneMorePlugin

from dotenv import load_dotenv
load_dotenv()
import os
SOCKET_URL = os.getenv("SOCKET_URL", "ws://localhost:8080")

from datetime import datetime

OWNER_ID = 1204876262

@on_start_match(target=".test")
async def on_start_test(event: MessageEvent):
    await send_text(f"""self_id: {event.self_id}, user_id: {event.user_id}, timestamp: {event.time}, 
                    time1:{datetime.fromtimestamp(event.time)}, 
                    time2: {datetime.fromtimestamp(event.time).strftime("%Y-%m-%d %H:%M:%S")},"""
                    )
TestPlugin = PluginPlanner(version="0.0.1", flows=[on_start_test])

if __name__ == "__main__":
    bot = Bot(__name__)
    bot.add_protocol(OneBotV11Protocol(ForwardWebSocketIO(SOCKET_URL)))
    bot.load_plugin(HelloPlugin)
    bot.load_plugin(ChatPlugin)
    bot.load_plugin(RollPlugin)
    bot.load_plugin(OneMorePlugin)
    bot.run()
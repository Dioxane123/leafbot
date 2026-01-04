import os

from dotenv import load_dotenv
from melobot.bot.base import Bot
from melobot.protocols.onebot.v11 import Adapter, ForwardWebSocketIO

from plugins.chat import ChatPlugin
from plugins.hello import HelloPlugin
from plugins.ob11adaptor_patches import patch_all
from plugins.OneMore import OneMorePlugin
from plugins.roll import RollPlugin
from plugins.rss import RssPlugin
from plugins.timer import TimerPlugin

load_dotenv()
SOCKET_URL = os.getenv("SOCKET_URL", "ws://localhost:8080")
SOCKET_TOKEN = os.getenv("SOCKET_TOKEN", "")

if __name__ == "__main__":
    bot = (
        Bot("leafbot")
        .add_adapter(patch_all(Adapter()))
        .add_io(ForwardWebSocketIO(url=SOCKET_URL, access_token=SOCKET_TOKEN))
    )
    bot.load_plugin(HelloPlugin)
    bot.load_plugin(ChatPlugin)
    bot.load_plugin(RollPlugin)
    bot.load_plugin(OneMorePlugin)
    bot.load_plugin(RssPlugin)
    bot.load_plugin(TimerPlugin)
    bot.run()

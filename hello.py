from melobot import Bot, PluginPlanner, on_start_match, send_text
from melobot.protocols.onebot.v11 import ForwardWebSocketIO, OneBotV11Protocol

@on_start_match(".sayhi")
async def echo_hi() -> None:
    await send_text("Hello, melobot!")

test_plugin = PluginPlanner(version="1.0.0", flows=[echo_hi])

if __name__ == "__main__":
    bot = Bot(__name__)
    bot.add_protocol(OneBotV11Protocol(ForwardWebSocketIO("ws://parodydeepseek.news:28275/onebot/v11/ws")))
    bot.load_plugin(test_plugin)
    bot.run()
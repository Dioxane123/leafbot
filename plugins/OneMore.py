from melobot.protocols.onebot.v11 import ImageSegment, MessageEvent, Adapter

from melobot import on_start_match, PluginPlanner

@on_start_match(".onemore")
async def onemore(event: MessageEvent, adaptor: Adapter) -> None:
    img = ImageSegment(file="https://api.anosu.top/img/")
    await adaptor.send([img])
                       
OneMorePlugin = PluginPlanner(version="0.0.1", flows=[onemore])
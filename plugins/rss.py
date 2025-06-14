from bypy import ByPy
BaiduPan = ByPy()
import json
import os
from pathlib import Path
from dotenv import load_dotenv
load_dotenv()
OWNER = int(os.getenv("OWNER"))

from melobot.protocols.onebot.v11 import MessageEvent, Adapter, on_message, MsgChecker, LevelRole
from melobot.utils.parse import CmdParser, CmdArgs
from melobot import on_start_match, PluginPlanner

from utils.bangumi import run as bangumi_update


@on_start_match(target=".rssupdate", checker=MsgChecker(role=LevelRole.OWNER, owner=OWNER))
async def rss_update(event: MessageEvent, adaptor: Adapter) -> None:
    """处理 .rssupdate 命令，更新 RSS 订阅"""
    await adaptor.send("正在为主人更新 RSS 订阅...")
    try:
        result = bangumi_update()
        text1 = f"本次已更新 {len(result)} 条 RSS 订阅:\n"
        text2 = '\n'.join(result)
        await adaptor.send_reply(text1 + text2)
    except Exception as e:
        await adaptor.send_reply(f"更新失败: {e}")
    BaiduPan.syncup(localdir='/home/ecs-user/bangumi')
    await adaptor.send("已为主人将BT种子同步至百度网盘。")

@on_message(parser=CmdParser(cmd_start="..",
                             cmd_sep=" ",
                             targets="rsslink"), checker=MsgChecker(role=LevelRole.OWNER, owner=OWNER))
async def rss_link(event: MessageEvent, args: CmdArgs, adaptor: Adapter) -> None:
    """处理 .rsslink 命令，添加 RSS 订阅链接"""
    if len(args.vals) < 1 or args.vals[0] == "help":
        await adaptor.send_reply("添加RSS订阅链接。\n格式：\n.rsslink <url> <title> <enable> <savedir> [rule]")
        return
    if len(args.vals) < 4:
        await adaptor.send_reply("参数不足，请提供完整的链接信息。")
        await adaptor.send_reply("格式：\n.rsslink <url> <title> <enable> <savedir> [rule]")
        await adaptor.send_reply("\n".join(args.vals))
        return
    
    add_link = {
        "url": args.vals[0],
        "title": args.vals[1],
        "enable": args.vals[2],
        "savedir": args.vals[3],
        "rule": args.vals[4] if len(args.vals) > 4 else ""
    }

    if env_config_path := os.getenv("MTA_CONFIGPATH"):
        config_path = Path(env_config_path)
    else:
        config_path = Path(".cache/bangumi_config/config.json")
    config_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with open(config_path, 'r', encoding='utf8') as f:
            config = json.load(f)
        config.get('mikan').append(add_link)
        with open(config_path, 'w', encoding='utf8') as f:
            json.dump(config, f, indent=4, ensure_ascii=False)
        await adaptor.send_reply("添加链接成功！")
    except Exception as e:
        await adaptor.send_reply(f"添加链接失败: {e}")
    return

RssPlugin = PluginPlanner(version="0.0.1", flows=[rss_update, rss_link])
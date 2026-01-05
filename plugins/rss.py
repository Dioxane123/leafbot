import json
import os
from pathlib import Path

from bypy import ByPy
from dotenv import load_dotenv
from melobot.handle.register import on_start_match
from melobot.plugin.base import PluginPlanner
from melobot.protocols.onebot.v11 import Adapter, LevelRole, MessageEvent, MsgChecker
from melobot.protocols.onebot.v11.handle import on_message
from melobot.utils.parse.cmd import CmdArgs, CmdParser

from utils.bangumi import run as bangumi_update

load_dotenv()
OWNER = int(os.getenv("OWNER") or "0")
BaiduPan = ByPy()


@on_start_match(
    target=".rssupdate", checker=MsgChecker(role=LevelRole.OWNER, owner=OWNER)
)
async def rss_update(event: MessageEvent, adaptor: Adapter) -> None:
    """处理 .rssupdate 命令，更新 RSS 订阅"""
    await adaptor.send("正在为主人更新 RSS 订阅...")
    try:
        result = bangumi_update()
        text1 = f"本次已更新 {len(result)} 条 RSS 订阅:\n"
        text2 = "\n".join(result)
        await adaptor.send_reply(text1 + text2)
    except Exception as e:
        await adaptor.send_reply(f"更新失败: {e}")
    BaiduPan.syncup(localdir="/home/ecs-user/bangumi")
    await adaptor.send("已将BT种子同步至百度网盘。")


@on_message(
    parser=CmdParser(cmd_start="..", cmd_sep=" ", targets="rsslink"),
    checker=MsgChecker(role=LevelRole.OWNER, owner=OWNER),
)
async def rss_link(event: MessageEvent, args: CmdArgs, adaptor: Adapter) -> None:
    """处理 ..rsslink 命令，添加 RSS 订阅链接"""
    if len(args.vals) < 1 or args.vals[0] == "help":
        await adaptor.send_reply(
            "添加RSS订阅链接。\n格式：\n..rsslink <url> <title> <enable> <savedir> [rule]"
        )
        return
    if len(args.vals) < 4:
        await adaptor.send_reply("参数不足，请提供完整的链接信息。")
        await adaptor.send_reply(
            "格式：\n..rsslink <url> <title> <enable> <savedir> [rule]"
        )
        await adaptor.send_reply("\n".join(args.vals))
        return

    add_link = {
        "url": args.vals[0],
        "title": args.vals[1],
        "enable": args.vals[2],
        "savedir": args.vals[3],
        "rule": args.vals[4] if len(args.vals) > 4 else "",
    }

    if env_config_path := os.getenv("MTA_CONFIGPATH"):
        config_path = Path(env_config_path)
    else:
        config_path = Path(".cache/bangumi_config/config.json")
    config_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with open(config_path, "r", encoding="utf8") as f:
            config = json.load(f)
        config.get("mikan").append(add_link)
        with open(config_path, "w", encoding="utf8") as f:
            json.dump(config, f, indent=4, ensure_ascii=False)
        await adaptor.send_reply("添加链接成功！")
    except Exception as e:
        await adaptor.send_reply(f"添加链接失败: {e}")
    return


@on_message(
    parser=CmdParser(cmd_start="..", cmd_sep=" ", targets="rsslist"),
    checker=MsgChecker(role=LevelRole.OWNER, owner=OWNER),
)
async def rss_list(event: MessageEvent, args: CmdArgs, adaptor: Adapter) -> None:
    """处理 ..rsslist 命令，列出所有 RSS 订阅链接"""
    if len(args.vals) == 1 and args.vals[0] == "help":
        await adaptor.send_reply("列出所有RSS订阅链接。\n格式：\n..rsslist [-r <counts>]")
        return

    if env_config_path := os.getenv("MTA_CONFIGPATH"):
        config_path = Path(env_config_path)
    else:
        config_path = Path(".cache/bangumi_config/config.json")

    try:
        with open(config_path, "r", encoding="utf8") as f:
            config = json.load(f)

        mikan_list = config.get("mikan", [])
        start_index = 0
        if not mikan_list:
            await adaptor.send_reply("当前没有RSS订阅链接。")
            return

        if len(args.vals) > 1 and args.vals[0] == "-r":
            if len(args.vals) < 2:
                await adaptor.send_reply("请提供要显示的项目条数。")
                return
            try:
                count = int(args.vals[1])
            except ValueError:
                await adaptor.send_reply("请输入有效的数字。")
                return
            start_index = max(0, len(mikan_list) - count - 1)
            mikan_list = mikan_list[-count:]

        response = "当前RSS订阅链接：\n"
        for i, item in enumerate(mikan_list, start=start_index):
            status = "启用" if item.get("enable", True) else "禁用"
            rule = item.get("rule", "") or "无过滤规则"
            response += f"[{i}] {item.get('title', '未知标题')} ({status})\n"
            response += f"    目录: {item.get('savedir', '未知目录')}\n"
            response += f"    规则: {rule}\n"
            response += f"    链接: {item.get('url', '未知链接')}\n\n"

        await adaptor.send_reply(response.strip())
    except Exception as e:
        await adaptor.send_reply(f"获取RSS列表失败: {e}")
    return


@on_message(
    parser=CmdParser(cmd_start="..", cmd_sep=" ", targets="rssmodify"),
    checker=MsgChecker(role=LevelRole.OWNER, owner=OWNER),
)
async def rss_modify(event: MessageEvent, args: CmdArgs, adaptor: Adapter) -> None:
    """处理 ..rssmodify 命令，修改已设置的RSS订阅链接"""
    if len(args.vals) < 1 or args.vals[0] == "help":
        await adaptor.send_reply(
            "修改RSS订阅链接。\n格式：\n..rssmodify <索引> <字段> <新值>\n"
            + "字段可选: url, title, enable, savedir, rule\n"
            + "示例: ..rssmodify 0 title 新标题"
        )
        return

    if len(args.vals) < 3:
        await adaptor.send_reply("参数不足，请提供完整的修改信息。")
        await adaptor.send_reply("格式：\n..rssmodify <索引> <字段> <新值>")
        return

    try:
        index = int(args.vals[0])
        field = args.vals[1].lower()
        new_value = args.vals[2]
    except ValueError:
        await adaptor.send_reply("索引必须是数字。请使用 ..rsslist 查看当前索引。")
        return

    if field not in ["url", "title", "enable", "savedir", "rule"]:
        await adaptor.send_reply(
            "字段名错误。可选字段: url, title, enable, savedir, rule"
        )
        return

    if env_config_path := os.getenv("MTA_CONFIGPATH"):
        config_path = Path(env_config_path)
    else:
        config_path = Path(".cache/bangumi_config/config.json")

    try:
        with open(config_path, "r", encoding="utf8") as f:
            config = json.load(f)

        mikan_list = config.get("mikan", [])
        if index < 0 or index >= len(mikan_list):
            await adaptor.send_reply(
                f"索引 {index} 不存在。当前共有 {len(mikan_list)} 个RSS订阅。"
            )
            return

        old_value = mikan_list[index].get(field, "")

        if field == "enable":
            if new_value.lower() in ["true", "1", "yes", "on", "启用"]:
                new_value = True
            elif new_value.lower() in ["false", "0", "no", "off", "禁用"]:
                new_value = False
            else:
                await adaptor.send_reply(
                    "enable字段只能设置为: true/false, 1/0, yes/no, on/off, 启用/禁用"
                )
                return

        mikan_list[index][field] = new_value

        with open(config_path, "w", encoding="utf8") as f:
            json.dump(config, f, indent=4, ensure_ascii=False)

        await adaptor.send_reply(
            "修改成功！\n"
            + f"RSS订阅 [{index}] {mikan_list[index].get('title', '未知标题')}\n"
            + f"字段 {field}: {old_value} -> {new_value}"
        )
    except Exception as e:
        await adaptor.send_reply(f"修改RSS链接失败: {e}")
    return


@on_message(
    parser=CmdParser(cmd_start="..", cmd_sep=" ", targets="rssdelete"),
    checker=MsgChecker(role=LevelRole.OWNER, owner=OWNER),
)
async def rss_delete(event: MessageEvent, args: CmdArgs, adaptor: Adapter) -> None:
    """处理 ..rssdelete 命令，删除指定的RSS订阅链接"""
    if len(args.vals) < 1 or args.vals[0] == "help":
        await adaptor.send_reply(
            "删除RSS订阅链接。\n格式：\n..rssdelete <索引>\n示例: ..rssdelete 0"
        )
        return

    try:
        index = int(args.vals[0])
    except ValueError:
        await adaptor.send_reply("索引必须是数字。请使用 ..rsslist 查看当前索引。")
        return

    if env_config_path := os.getenv("MTA_CONFIGPATH"):
        config_path = Path(env_config_path)
    else:
        config_path = Path(".cache/bangumi_config/config.json")

    try:
        with open(config_path, "r", encoding="utf8") as f:
            config = json.load(f)

        mikan_list = config.get("mikan", [])
        if index < 0 or index >= len(mikan_list):
            await adaptor.send_reply(
                f"索引 {index} 不存在。当前共有 {len(mikan_list)} 个RSS订阅。"
            )
            return

        deleted_item = mikan_list.pop(index)

        with open(config_path, "w", encoding="utf8") as f:
            json.dump(config, f, indent=4, ensure_ascii=False)

        await adaptor.send_reply(
            f"删除成功！\n已删除RSS订阅: {deleted_item.get('title', '未知标题')}"
        )
    except Exception as e:
        await adaptor.send_reply(f"删除RSS链接失败: {e}")
    return


RssPlugin = PluginPlanner(
    version="0.0.1", flows=[rss_update, rss_link, rss_list, rss_modify, rss_delete]
)

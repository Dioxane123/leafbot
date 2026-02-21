"""聊天插件 - 处理与 bot 的自然语言对话"""
from datetime import datetime

from melobot import PluginPlanner
from melobot.protocols.onebot.v11 import (
    MessageEvent, GroupMessageEvent, on_message,
    Adapter, AtSegment, TextSegment,
    PrivateMsgChecker, GroupMsgChecker, LevelRole
)
from melobot.utils.parse.cmd import CmdArgs, CmdParser

import os
from dotenv import load_dotenv

load_dotenv()

from utils.chat_memory import load_memory, save_memory, clear_memory
from utils.chat_llm import analyze_search_intent, call_llm
from utils.web_search import web_search

OWNER_ID = os.getenv("OWNER")
TEST_GROUP = os.getenv("TEST_GROUP")
CST = __import__('zoneinfo').ZoneInfo("Asia/Shanghai")


async def handle_chat(user_message: str, event: MessageEvent, adaptor: Adapter, is_group: bool = False) -> None:
    """处理聊天消息"""
    user_id = event.group_id if is_group else event.sender.user_id

    # 加载记忆
    memory = load_memory(user_id, is_group)

    # 使用 LLM 判断是否需要搜索
    search_result = ""
    search_analysis = analyze_search_intent(user_message, memory)

    if search_analysis.get("need_search"):
        search_query = search_analysis.get("search_query", user_message)
        print(f"需要搜索: {search_query}")
        try:
            search_result = web_search(search_query)
        except Exception as e:
            print(f"网络搜索失败: {e}")

    # 获取当前时间戳
    current_timestamp = datetime.now(CST).timestamp()

    # 调用 LLM 生成回复
    reply = call_llm(user_message, memory, bool(search_result), search_result)

    # 保存记忆（带时间戳）
    memory.append({"role": "user", "content": user_message, "timestamp": current_timestamp})
    memory.append({"role": "assistant", "content": reply, "timestamp": current_timestamp})
    save_memory(user_id, memory, is_group)

    # 发送回复
    await adaptor.send_reply(reply)


@on_message(checker=PrivateMsgChecker(role=LevelRole.OWNER))
async def chat_private(event: MessageEvent, adaptor: Adapter) -> None:
    """处理私聊消息"""
    message = "".join([
        seg.data["text"] for seg in event.get_segments(TextSegment)
    ]).strip()

    if not message or message.startswith(".."):
        return

    await handle_chat(message, event, adaptor, is_group=False)


@on_message(checker=GroupMsgChecker(role=LevelRole.NORMAL, white_groups=[int(os.getenv("TEST_GROUP", "0"))]))
async def chat_group(event: GroupMessageEvent, adaptor: Adapter) -> None:
    """处理群聊消息"""
    message = "".join([
        seg.data["text"] for seg in event.get_segments(TextSegment)
    ]).strip()

    if not message:
        return

    # 检查是否被 @ 或者以小叶开头
    at_segs = event.get_segments(AtSegment)
    is_at_me = any(seg.data.get("qq") == event.self_id for seg in at_segs)
    has_trigger = message[:6].find("小叶") >= 0

    if not (is_at_me or has_trigger):
        return

    # 移除@
    if is_at_me:
        message = message.replace(f"[@{event.self_id}]", "").strip()

    if not message or message.startswith(".."):
        return

    await handle_chat(message, event, adaptor, is_group=True)


@on_message(
    parser=CmdParser(cmd_start="..", cmd_sep=" ", targets="clear"),
    checker=PrivateMsgChecker(role=LevelRole.OWNER)
)
async def clear_memory_private(event: MessageEvent, args: CmdArgs, adaptor: Adapter) -> None:
    """清除私聊记忆"""
    user_id = event.sender.user_id
    clear_memory(user_id, is_group=False)
    await adaptor.send_reply("好哦，主人！我已经把我们的聊天记录都清空了~有什么想聊的吗？")


@on_message(
    parser=CmdParser(cmd_start="..", cmd_sep=" ", targets="clear"),
    checker=GroupMsgChecker(role=LevelRole.NORMAL, white_groups=[int(TEST_GROUP)])
)
async def clear_memory_group(event: GroupMessageEvent, args: CmdArgs, adaptor: Adapter) -> None:
    """清除群聊记忆"""
    user_id = event.group_id
    clear_memory(user_id, is_group=True)
    await adaptor.send_reply("好哦！我已经把这段聊天记忆都清空了~")


# 导出插件
ChatPlugin = PluginPlanner(version="0.0.1", flows=[
    chat_private,
    chat_group,
    clear_memory_private,
    clear_memory_group
])
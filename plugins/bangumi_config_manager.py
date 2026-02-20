import json
import os
import re
from pathlib import Path
from openai import OpenAI
from melobot import PluginPlanner
from melobot.protocols.onebot.v11 import (
    MessageEvent, on_message, Adapter,
    PrivateMsgChecker, GroupMsgChecker, GroupMessageEvent,
    TextSegment, AtSegment, ReplySegment, LevelRole
)
from dotenv import load_dotenv

load_dotenv()

# 获取配置文件路径
workspace = Path(__file__).resolve().parent.parent
CONFIG_PATH = os.getenv("MTA_CONFIGPATH", workspace / ".cache" / "bangumi_config" / "config.json")

# OpenAI 客户端初始化
API_KEY = os.getenv("API_KEY")
client = OpenAI(api_key=API_KEY, base_url="https://api.siliconflow.cn/v1")
MODEL_NAME = "deepseek-ai/DeepSeek-V3"


def load_config() -> dict:
    """加载配置文件"""
    config_path = Path(CONFIG_PATH)
    if config_path.exists() and config_path.is_file():
        with open(config_path, encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_config(config: dict) -> bool:
    """保存配置文件"""
    try:
        config_path = Path(CONFIG_PATH)
        config_path.parent.mkdir(parents=True, exist_ok=True)
        with open(config_path, encoding="utf-8", mode="w") as f:
            json.dump(config, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        print(f"保存配置失败: {e}")
        return False


def parse_config_intent(user_message: str) -> dict:
    """
    使用 LLM 解析用户的配置修改意图（不传递完整配置，节约 token）
    返回: {"action": "add|remove|update|list|query", "details": {...}, "response": "..."}
    """
    prompt = f"""你是配置文件解析助手。用户想要修改 bangumi 番剧订阅配置。

用户的自然语言请求:
{user_message}

请分析用户的意图，并按照以下格式输出 JSON（直接输出 JSON，不要有任何其他内容）:

{{
    "action": "add" | "remove" | "update" | "list" | "query" | "unknown",
    "details": {{
        // add: {{"url": "...", "title": "...", "savedir": "..."}}
        // remove: {{"title": "..."}} 或 {{"index": 0}}
        // update: {{"title": "...", "field": "enable|savedir|rule", "value": "..."}}
        // list: {{}}
        // query: {{"title": "..."}}
    }},
    "response": "你理解的用户意图描述（用于确认）"
}}

注意:
1. 如果用户只是想查看当前配置列表，action 为 "list"
2. 如果用户询问某个番剧的详情，action 为 "query"
3. 如果用户想添加新的订阅，action 为 "add"，需要从用户消息中提取 url, title, savedir
4. 如果用户想删除订阅，action 为 "remove"，需要从用户消息中提取 title 或 index
5. 如果用户想修改某个字段（如启用/禁用），action 为 "update"
6. 如果无法理解用户意图，action 为 "unknown"

输出:"""

    try:
        response = client.chat.completions.create(
            model=MODEL_NAME,
            messages=[{"role": "user", "content": prompt}]
        )
        result_text = response.choices[0].message.content.strip()

        # 尝试提取 JSON
        json_match = re.search(r'\{[\s\S]*\}', result_text)
        if json_match:
            return json.loads(json_match.group())
    except Exception as e:
        print(f"解析意图失败: {e}")

    return {"action": "unknown", "details": {}, "response": "抱歉，我没能理解你的意图呢。请告诉我你想对 bangumi 配置做什么操作？"}


def execute_config_action(action: str, details: dict, config: dict) -> tuple[bool, str]:
    """执行配置修改操作"""
    mikan_list = config.get("mikan", [])

    if action == "list":
        if not mikan_list:
            return True, "当前没有配置任何番剧订阅呢~"

        msg = "当前的番剧订阅列表:\n"
        for i, item in enumerate(mikan_list):
            status = "✅ 启用" if item.get("enable", True) else "❌ 禁用"
            msg += f"{i+1}. {item.get('title', '未命名')} ({status})\n"
            msg += f"   保存目录: {item.get('savedir', '未设置')}\n"
        return True, msg

    elif action == "query":
        title = details.get("title", "")
        for item in mikan_list:
            if title in item.get("title", ""):
                msg = f"番剧 '{item.get('title')}' 的详细信息:\n"
                msg += f"- URL: {item.get('url')}\n"
                msg += f"- 保存目录: {item.get('savedir')}\n"
                msg += f"- 启用状态: {'是' if item.get('enable', True) else '否'}\n"
                msg += f"- 匹配规则: {item.get('rule', '无')}"
                return True, msg
        return False, f"没有找到名为 '{title}' 的番剧订阅"

    elif action == "add":
        url = details.get("url", "")
        title = details.get("title", "")
        savedir = details.get("savedir", title)

        if not url or not title:
            return False, "添加订阅需要提供 url 和 title 哦~"

        # 检查是否已存在（根据 URL 或 title）
        # 如果存在，自动转为更新配置
        for i, item in enumerate(mikan_list):
            if item.get("url") == url:
                # URL 相同，更新 title 和 savedir
                old_title = item.get("title")
                item["title"] = title
                item["savedir"] = savedir
                config["mikan"] = mikan_list
                if save_config(config):
                    return True, f"已更新番剧 '{old_title}' 的配置（URL 已存在）\n新标题: {title}, 保存目录: {savedir}"
                return False, "保存配置失败了orz..."

            if item.get("title") == title:
                # title 相同，更新 URL 和 savedir
                old_url = item.get("url")
                item["url"] = url
                item["savedir"] = savedir
                config["mikan"] = mikan_list
                if save_config(config):
                    return True, f"已更新番剧 '{title}' 的配置（标题已存在）\n新URL: {url}, 保存目录: {savedir}"
                return False, "保存配置失败了orz..."

        # 不存在，新增配置
        new_item = {
            "url": url,
            "title": title,
            "enable": True,
            "rule": "",
            "savedir": savedir
        }
        mikan_list.append(new_item)
        config["mikan"] = mikan_list

        if save_config(config):
            return True, f"已成功添加番剧 '{title}' 到订阅列表！\n保存目录: {savedir}"
        return False, "保存配置失败了orz..."

    elif action == "remove":
        title = details.get("title")
        index = details.get("index")

        if index is not None and 0 <= index < len(mikan_list):
            removed = mikan_list.pop(index)
            config["mikan"] = mikan_list
            if save_config(config):
                return True, f"已删除番剧 '{removed.get('title')}'"
            return False, "保存配置失败了orz..."

        if title:
            for i, item in enumerate(mikan_list):
                if title in item.get("title", ""):
                    removed = mikan_list.pop(i)
                    config["mikan"] = mikan_list
                    if save_config(config):
                        return True, f"已删除番剧 '{removed.get('title')}'"
                    return False, "保存配置失败了orz..."
            return False, f"没有找到名为 '{title}' 的番剧"

        return False, "请告诉我你要删除的番剧名称或编号"

    elif action == "update":
        title = details.get("title")
        field = details.get("field")
        value = details.get("value")

        if not title or not field:
            return False, "更新配置需要提供番剧名称、字段和值"

        for item in mikan_list:
            if title in item.get("title", ""):
                if field == "enable":
                    item["enable"] = bool(value)
                elif field == "savedir":
                    item["savedir"] = str(value)
                elif field == "rule":
                    item["rule"] = str(value)
                else:
                    return False, f"不支持的字段 '{field}'"

                config["mikan"] = mikan_list
                if save_config(config):
                    new_status = "启用" if item.get("enable", True) else "禁用"
                    return True, f"已更新 '{item.get('title')}' 的 {field} 为 {value}"
                return False, "保存配置失败了orz..."

        return False, f"没有找到名为 '{title}' 的番剧"

    return False, "未知的操作"


# 配置修改的触发关键词
CONFIG_TRIGGER = "bangumi"


@on_message(checker=PrivateMsgChecker(role=LevelRole.OWNER))
async def handle_config_private(e: MessageEvent, adaptor: Adapter) -> None:
    message = e.raw_message.strip()

    # 检查是否是配置相关的消息
    if CONFIG_TRIGGER not in message.lower():
        return

    # 移除触发词，获取实际请求
    request = message.replace(CONFIG_TRIGGER, "", 1).strip()

    if not request:
        await adaptor.send_reply("你好呀~ 这是 bangumi 配置管理功能！\n"
                                  "你可以告诉我:\n"
                                  "- 查看当前订阅列表\n"
                                  "- 添加新的番剧订阅 (告诉我URL和名字)\n"
                                  "- 删除某个番剧\n"
                                  "- 禁用/启用某个番剧\n"
                                  "请说出你想做什么吧~")
        return

    # 加载配置
    config = load_config()

    # 解析用户意图
    result = parse_config_intent(request)

    if result.get("action") == "unknown":
        await adaptor.send_reply(result.get("response", "抱歉，我没能理解你的意图呢"))
        return

    # 执行操作
    success, response = execute_config_action(result["action"], result.get("details", {}), config)
    await adaptor.send_reply(response)


@on_message(checker=GroupMsgChecker(role=LevelRole.NORMAL, white_groups=[int(os.getenv("TEST_GROUP", "0"))]))
async def handle_config_group(e: GroupMessageEvent, adaptor: Adapter) -> None:
    message = "".join([seg.data["text"] for seg in e.get_segments(TextSegment)]).strip()

    # 检查是否被 @ 并且包含配置相关关键词
    at_segs = e.get_segments(AtSegment)
    if not any(seg.data.get("qq") == e.self_id for seg in at_segs):
        return

    if CONFIG_TRIGGER not in message.lower():
        return

    # 移除触发词和 @，获取实际请求
    request = message.replace(CONFIG_TRIGGER, "", 1).strip()

    if not request:
        await adaptor.send_reply("这是 bangumi 配置管理功能！\n"
                                  "你可以告诉我:\n"
                                  "- 查看当前订阅列表\n"
                                  "- 添加新的番剧订阅\n"
                                  "- 删除某个番剧\n"
                                  "- 禁用/启用某个番剧")
        return

    # 加载配置
    config = load_config()

    # 解析用户意图
    result = parse_config_intent(request)

    if result.get("action") == "unknown":
        await adaptor.send_reply(result.get("response", "抱歉，我没能理解你的意图呢"))
        return

    # 执行操作
    success, response = execute_config_action(result["action"], result.get("details", {}), config)
    await adaptor.send_reply(response)


BangumiConfigPlugin = PluginPlanner(version="0.0.1", flows=[handle_config_private, handle_config_group])
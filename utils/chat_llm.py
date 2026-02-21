"""LLM 调用和工具函数模块"""
import json
import os
import re
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

# 初始化 OpenAI 客户端
API_KEY = os.getenv("API_KEY")
client = OpenAI(api_key=API_KEY, base_url="https://api.siliconflow.cn/v1")
MODEL_NAME = "deepseek-ai/DeepSeek-V3"

# 中国时区
CST = ZoneInfo("Asia/Shanghai")

# 工作目录
WORKSPACE = Path(__file__).resolve().parent.parent
MEMORY_DIR = WORKSPACE / ".cache" / "chat_memory"

from .chat_prompt import CHARACTER_SYSTEM_PROMPT


def get_current_time_str() -> str:
    """获取当前时间字符串"""
    now = datetime.now(CST)
    weekday_names = ["星期一", "星期二", "星期三", "星期四", "星期五", "星期六", "星期日"]
    return now.strftime('%Y年%m月%d日 %H:%M:%S') + "，" + weekday_names[now.weekday()]


def parse_timestamp(ts: float) -> str:
    """将时间戳转换为可读字符串"""
    dt = datetime.fromtimestamp(ts, CST)
    now = datetime.now(CST)
    diff = now - dt

    if diff < timedelta(minutes=1):
        return "刚刚"
    elif diff < timedelta(hours=1):
        return f"{int(diff.total_seconds() // 60)}分钟前"
    elif diff < timedelta(days=1):
        return f"今天{dt.strftime('%H:%M')}"
    elif diff < timedelta(days=2):
        return f"昨天{dt.strftime('%H:%M')}"
    elif diff < timedelta(days=7):
        return f"{diff.days}天前"
    else:
        return dt.strftime('%Y年%m月%d日 %H:%M')


def analyze_search_intent(user_message: str, memory: list) -> dict:
    """使用 LLM 分析用户消息，判断是否需要搜索"""
    context_info = f"当前时间：{get_current_time_str()}\n"
    if memory:
        context_info += f"对话历史共 {len(memory)//2} 轮\n"
        recent = memory[-8:]
        for msg in recent:
            if msg.get("timestamp"):
                time_str = parse_timestamp(msg["timestamp"])
                context_info += f"[{time_str}] {msg['role']}: {msg['content'][:50]}...\n"

    prompt = f"""{context_info}
用户最新消息：{user_message}

请分析这条消息是否需要网络搜索。

判断标准：
- 需要搜索：天气、新闻、股票、实时热点、精确数值、地理位置、人物百科、最新事件、价格查询
- 不需要搜索：日常闲聊、情感交流、回忆往事、主观意见、创造性内容、已有知识

请直接输出JSON格式（不要有任何其他内容）：
{{
    "need_search": true或false,
    "search_query": "如果需要搜索，给出搜索关键词（简洁明确）",
    "reason": "判断原因（简短）"
}}

输出："""

    try:
        response = client.chat.completions.create(
            model=MODEL_NAME,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            max_tokens=200
        )
        result_text = response.choices[0].message.content.strip()
        json_match = re.search(r'\{[\s\S]*\}', result_text)
        if json_match:
            return json.loads(json_match.group())
    except Exception as e:
        print(f"分析搜索意图失败: {e}")

    return {"need_search": False, "search_query": "", "reason": "分析失败，默认不搜索"}


def call_llm(user_message: str, memory: list, need_search: bool = False, search_result: str = "") -> str:
    """调用 LLM 生成回复"""
    # 延迟导入以避免循环依赖
    from .chat_memory import build_context, truncate_to_token_limit

    current_time = get_current_time_str()

    # 构建上下文：分离最近对话和历史摘要
    recent_msgs, summary, important_points = build_context(memory)

    # 构建消息列表
    messages = [
        {"role": "system", "content": CHARACTER_SYSTEM_PROMPT},
        {"role": "system", "content": f"当前时间：{current_time}"}
    ]

    # 添加历史摘要
    if summary:
        messages.append({
            "role": "system",
            "content": f"【之前对话的摘要】{summary}"
        })

    # 添加重要事项
    if important_points:
        points_text = "\n".join(f"- {p}" for p in important_points)
        messages.append({
            "role": "system",
            "content": f"【需要记住的重要事项】\n{points_text}"
        })

    # 添加最近对话（带时间戳）
    for msg in recent_msgs:
        role = msg.get("role", "user")
        content = msg.get("content", "")
        timestamp = msg.get("timestamp", 0)

        if timestamp:
            time_str = parse_timestamp(timestamp)
            formatted_msg = {
                "role": role,
                "content": f"[{time_str}] {content}"
            }
        else:
            formatted_msg = {"role": role, "content": content}
        messages.append(formatted_msg)

    # token 限制检查
    messages = truncate_to_token_limit(messages)

    # 添加搜索结果
    if need_search and search_result:
        search_context = f"\n\n【网络搜索结果】\n{search_result}\n【搜索结果结束】\n\n请根据以上搜索结果回答。如果搜索不到相关信息，请如实说明并基于你已有的知识回答~"
        messages.append({"role": "system", "content": search_context})
    elif need_search:
        messages.append({"role": "system", "content": "你判断需要搜索网络，但搜索功能暂时不可用。请基于已有知识回答，并说明如果有网络就能查到更准确的信息哦~"})

    # 添加用户当前消息
    messages.append({
        "role": "user",
        "content": f"[{current_time}] {user_message}"
    })

    try:
        response = client.chat.completions.create(
            model=MODEL_NAME,
            messages=messages,
            temperature=0.8,
            max_tokens=600
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        print(f"LLM 调用失败: {e}")
        return "抱歉主人，小叶现在脑子有点转不过来了...我们可以换个话题试试看哦~"
"""自然语言定时器插件 - 使用 LLM 理解用户意图"""
from melobot import PluginPlanner, on_start_match, send_text
from melobot.protocols.onebot.v11 import MessageEvent, Adapter, ReplySegment, on_message
from melobot.utils.parse import RawParser

import asyncio
import os
import re
import json
from datetime import datetime, timedelta, date
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

# 初始化 LLM 客户端
API_KEY = os.getenv("API_KEY")
client = OpenAI(api_key=API_KEY, base_url="https://api.siliconflow.cn/v1")
MODEL_NAME = "deepseek-ai/DeepSeek-V3"

OWNER = os.getenv("OWNER")

# 存储活动的定时器
active_natural_timers: dict[str, dict] = {}


def call_llm_intent(text: str) -> dict:
    """调用 LLM 分析用户的定时意图"""
    prompt = f"""你是一个定时器意图分析助手。用户发送了一条消息，你需要判断用户是否想要设置定时提醒、倒计时、查看统计等。

当前时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

用户消息：{text}

请分析用户的意图，输出 JSON 格式：
{{
    "intent": "timer/统计/cancel/query/none",
    "action": "倒计时/提醒/闹钟/查看统计/取消/查询/none",
    "seconds": 时间秒数（整数，如果无法确定则为0）,
    "time_text": "原始时间文本（如'10分钟'、'1小时'等）",
    "message": "提醒内容摘要（如果用户没有明确，则为空字符串）",
    "reason": "判断原因"
}}

判断规则：
- intent="timer": 用户想要设置倒计时、提醒、闹钟
- intent="统计": 用户想要查看时间统计
- intent="cancel": 用户想要取消定时
- intent="query": 用户想要查询当前的定时
- intent="none": 与定时无关，不处理

如果 intent 不是 "none"，请尽量解析出时间值（秒）。

示例：
- "倒计时10分钟" -> {{"intent": "timer", "action": "倒计时", "seconds": 600, "time_text": "10分钟", "message": "倒计时结束", "reason": "用户明确说要倒计时"}}
- "10分钟后提醒我开会" -> {{"intent": "timer", "action": "提醒", "seconds": 600, "time_text": "10分钟后", "message": "开会", "reason": "用户要求提醒"}}
- "查看今天的统计" -> {{"intent": "统计", "action": "查看统计", "seconds": 0, "time_text": "", "message": "今天", "reason": "用户想查看统计"}}
- "取消所有定时" -> {{"intent": "cancel", "action": "取消", "seconds": 0, "time_text": "", "message": "", "reason": "用户要取消定时"}}

输出（只输出JSON，不要其他内容）："""

    try:
        response = client.chat.completions.create(
            model=MODEL_NAME,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            max_tokens=300
        )
        result_text = response.choices[0].message.content.strip()
        # 提取 JSON
        json_match = re.search(r'\{[\s\S]*\}', result_text)
        if json_match:
            return json.loads(json_match.group())
    except Exception as e:
        print(f"LLM 意图分析失败: {e}")

    return {"intent": "none", "action": "none", "seconds": 0, "time_text": "", "message": "", "reason": "LLM调用失败"}


async def natural_timer_task(event: MessageEvent, adaptor: Adapter, timer_id: str, seconds: int, message: str) -> None:
    """自然语言定时器核心逻辑"""
    try:
        timer_info = active_natural_timers[timer_id]
        await adaptor.send_reply(f"已设置定时提醒：{seconds}秒后提醒「{message}」")

        remaining = seconds
        while remaining > 0:
            await asyncio.sleep(1)
            remaining -= 1
            if timer_id in active_natural_timers:
                active_natural_timers[timer_id]["remain"] = remaining

        if timer_id in active_natural_timers:
            await adaptor.send_reply(f"时间到！提醒：{message}")
            # 记录完成的时间
            os.makedirs(".cache/timer", exist_ok=True)
            total_seconds = active_natural_timers[timer_id]["total_time"]
            hours = total_seconds // 3600
            minutes = (total_seconds % 3600) // 60
            secs = total_seconds % 60
            time_str = f"{hours}:{minutes}:{secs}"
            with open(f".cache/timer/{date.today()}.txt", "a+") as f:
                f.write(f"{event.user_id},natural,{time_str}\n")

    except asyncio.CancelledError:
        await adaptor.send_reply(f"定时提醒已取消：{message}")
    finally:
        if timer_id in active_natural_timers:
            del active_natural_timers[timer_id]


def parse_time_text(time_text: str) -> int:
    """解析时间文本为秒数（备用方法，当 LLM 无法解析时使用）"""
    if not time_text:
        return 0

    time_text = time_text.strip()

    # 各种时间格式匹配
    patterns = [
        (r"(\d+)\s*小时\s*(\d+)\s*分\s*(\d+)\s*秒", lambda h, m, s: int(h) * 3600 + int(m) * 60 + int(s)),
        (r"(\d+)\s*小时\s*(\d+)\s*分", lambda h, m: int(h) * 3600 + int(m) * 60),
        (r"(\d+)\s*分\s*(\d+)\s*秒", lambda m, s: int(m) * 60 + int(s)),
        (r"(\d+)\s*小时", lambda h: int(h) * 3600),
        (r"(\d+)\s*分", lambda m: int(m) * 60),
        (r"(\d+)\s*秒", lambda s: int(s)),
        (r"(\d{1,2}):(\d{1,2}):(\d{1,2})", lambda h, m, s: int(h) * 3600 + int(m) * 60 + int(s)),
        (r"(\d{1,2}):(\d{1,2})", lambda h, m: int(h) * 3600 + int(m) * 60),
    ]

    for pattern, converter in patterns:
        match = re.search(pattern, time_text)
        if match:
            return converter(*match.groups())

    return 0


@on_message(parser=RawParser())
async def handle_natural_timer(event: MessageEvent, adaptor: Adapter) -> None:
    """使用 LLM 处理自然语言定时请求"""
    text = event.raw_message.strip()

    # 忽略空消息和命令
    if "timer" not in text.lower() or text.startswith("."):
        return

    # 使用 LLM 分析意图
    intent_result = call_llm_intent(text)

    intent = intent_result.get("intent", "none")

    # 不处理无关意图
    if intent == "none":
        return

    # 处理定时/提醒/闹钟
    if intent == "timer":
        seconds = intent_result.get("seconds", 0)
        time_text = intent_result.get("time_text", "")
        message = intent_result.get("message", "时间到")

        # 如果 LLM 没有解析出时间，尝试备用解析
        if seconds == 0 and time_text:
            seconds = parse_time_text(time_text)

        if seconds <= 0:
            await adaptor.send_reply("抱歉，我没有理解您想要设置的时间。请明确说明要设置多长时间，例如'10分钟后提醒我'或'倒计时5分钟'。")
            return

        timer_id = str(event.message_id)
        task = asyncio.create_task(
            natural_timer_task(event, adaptor, timer_id, seconds, message)
        )
        active_natural_timers[timer_id] = {
            "user": event.user_id,
            "message": message,
            "remain": seconds,
            "total_time": seconds,
            "task": task,
            "start_time": datetime.now()
        }
        return

    # 处理取消
    if intent == "cancel":
        if not active_natural_timers:
            await adaptor.send_reply("当前没有活动的定时提醒。")
            return

        cancelled = []
        for timer_id, info in list(active_natural_timers.items()):
            if info["user"] == event.user_id:
                info["task"].cancel()
                cancelled.append(info["message"])

        if cancelled:
            await adaptor.send_reply(f"已取消 {len(cancelled)} 个定时提醒：{', '.join(cancelled)}")
        else:
            await adaptor.send_reply("当前没有您设置的定时提醒。")
        return

    # 处理查询
    if intent == "query":
        if not active_natural_timers:
            await adaptor.send_reply("当前没有活动的定时提醒。")
            return

        user_timers = [(tid, info) for tid, info in active_natural_timers.items() if info["user"] == event.user_id]
        if not user_timers:
            await adaptor.send_reply("当前没有您设置的定时提醒。")
            return

        response = "当前您设置的定时提醒：\n"
        for timer_id, info in user_timers:
            minutes = info["remain"] // 60
            secs = info["remain"] % 60
            response += f"• {info['message']}，剩余 {minutes}分{secs}秒\n"
        await adaptor.send_reply(response)
        return

    # 处理统计
    if intent == "统计":
        await show_time_statistics(event, adaptor, text, intent_result)
        return


async def show_time_statistics(event: MessageEvent, adaptor: Adapter, text: str, intent_result: dict = None) -> None:
    """显示时间统计信息"""
    target_date = date.today()
    message = intent_result.get("message", "") if intent_result else ""

    # 从 message 中提取日期信息
    if message:
        # 尝试解析日期
        date_match = re.search(r"(\d{4})[年/\-](\d{1,2})[月/\-](\d{1,2})", message)
        if date_match:
            try:
                target_date = date(
                    int(date_match.group(1)),
                    int(date_match.group(2)),
                    int(date_match.group(3))
                )
            except ValueError:
                pass

    date_str = target_date.strftime("%Y-%m-%d")
    file_path = f".cache/timer/{date_str}.txt"

    if not os.path.exists(file_path):
        await adaptor.send_reply(f"{date_str} 没有时间记录。")
        return

    with open(file_path, "r") as f:
        records = f.readlines()

    if not records:
        await adaptor.send_reply(f"{date_str} 没有时间记录。")
        return

    # 统计时间
    total_seconds = 0
    user_totals: dict[str, int] = {}

    for record in records:
        parts = record.strip().split(",")
        if len(parts) >= 3:
            user_id, tag, time_str = parts[0], parts[1], parts[2]
            time_parts = time_str.split(":")
            if len(time_parts) == 3:
                seconds = int(time_parts[0]) * 3600 + int(time_parts[1]) * 60 + int(time_parts[2])
            elif len(time_parts) == 2:
                seconds = int(time_parts[0]) * 60 + int(time_parts[1])
            else:
                continue

            total_seconds += seconds
            user_totals[user_id] = user_totals.get(user_id, 0) + seconds

    # 格式化总时间
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    seconds = total_seconds % 60

    response = f"{date_str} 的时间统计：\n"
    response += f"总时间：{hours}小时{minutes}分钟{seconds}秒\n"

    if str(event.user_id) == OWNER:
        response += "\n各用户统计：\n"
        for user_id, total in user_totals.items():
            h = total // 3600
            m = (total % 3600) // 60
            s = total % 60
            response += f"用户 {user_id}：{h}小时{m}分钟{s}秒\n"
    elif str(event.user_id) in user_totals:
        total = user_totals[str(event.user_id)]
        h = total // 3600
        m = (total % 3600) // 60
        s = total % 60
        response += f"你的时间：{h}小时{m}分钟{s}秒\n"

    await adaptor.send_reply(response)


@on_start_match(".timer help")
async def timer_help(event: MessageEvent, adaptor: Adapter) -> None:
    """显示定时器帮助信息"""
    help_text = """定时器使用方法：

你可以用自然语言描述你想要做的事情，我会自动理解你的意图：

倒计时：
- "倒计时10分钟"
- "倒计时5分钟"

定时提醒：
- "10分钟后提醒我开会"
- "30分钟后叫我喝水"
- "1小时后提醒我休息"

闹钟：
- "设置10分钟闹钟"

查看和取消：
- "查看我设置的定时"
- "取消所有定时"

时间统计：
- "查看今天的学习时间"
- "统计一下今天的时间"

直接发送你的需求即可，我会自动识别！
"""
    await adaptor.send_reply(help_text)


NaturalTimerPlugin = PluginPlanner(
    version="0.0.1",
    flows=[handle_natural_timer, timer_help]
)

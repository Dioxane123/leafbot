"""对话记忆管理模块"""
import json
import re
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from .chat_llm import client, MODEL_NAME

# 记忆配置
RECENT_TURNS = 4  # 保留最近4轮完整对话
MAX_RECENT_TOKENS = 800  # 近似 tokens 限制
SUMMARY_THRESHOLD = 20  # 超过20轮后触发摘要

# 工作目录
WORKSPACE = Path(__file__).resolve().parent.parent
MEMORY_DIR = WORKSPACE / ".cache" / "chat_memory"
MEMORY_DIR.mkdir(parents=True, exist_ok=True)

# 中国时区
CST = ZoneInfo("Asia/Shanghai")


def get_memory_path(user_id: int, is_group: bool = False) -> Path:
    """获取用户/群聊的记忆文件路径"""
    prefix = f"group_{user_id}" if is_group else f"user_{user_id}"
    return MEMORY_DIR / f"{prefix}.json"


def load_memory(user_id: int, is_group: bool = False) -> list:
    """加载对话记忆，支持结构化记忆"""
    memory_path = get_memory_path(user_id, is_group)
    if memory_path.exists():
        try:
            with open(memory_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            # 检查是否是结构化记忆（新格式）
            if isinstance(data, dict) and "recent_messages" in data:
                recent = data.get("recent_messages", [])
                summary = data.get("summary", "")
                important_points = data.get("important_points", [])

                result = []
                if summary:
                    result.append({
                        "role": "system",
                        "content": f"【之前对话的摘要】{summary}",
                        "timestamp": 0
                    })
                if important_points:
                    points_text = "\n".join(f"- {p}" for p in important_points)
                    result.append({
                        "role": "system",
                        "content": f"【需要记住的重要事项】\n{points_text}",
                        "timestamp": 0
                    })
                result.extend(recent)
                return result

            return data
        except Exception:
            return []
    return []


def save_memory(user_id: int, memory: list, is_group: bool = False) -> None:
    """保存对话记忆，支持自动摘要"""
    memory_path = get_memory_path(user_id, is_group)

    user_msgs = [m for m in memory if m.get("role") == "user"]
    total_turns = len(user_msgs)

    # 超过阈值时触发摘要
    if total_turns > SUMMARY_THRESHOLD:
        print(f"对话轮数 {total_turns} > {SUMMARY_THRESHOLD}，生成摘要...")

        older_turns = total_turns - RECENT_TURNS
        older_msgs = []
        recent_msgs = []

        current_turn = 0
        for msg in memory:
            if msg.get("role") == "user":
                current_turn += 1

            if current_turn <= older_turns:
                older_msgs.append(msg)
            else:
                recent_msgs.append(msg)

        if older_msgs:
            summary = _generate_summary(older_msgs)
            important_points = _extract_important_points(older_msgs)

            structured = {
                "summary": summary,
                "important_points": important_points,
                "recent_messages": recent_msgs,
                "last_summary_turn": total_turns
            }

            try:
                with open(memory_path, "w", encoding="utf-8") as f:
                    json.dump(structured, f, ensure_ascii=False, indent=2)
                print(f"摘要已保存，保留最近{RECENT_TURNS}轮对话")
                return
            except Exception as e:
                print(f"保存记忆失败: {e}")

    if len(memory) > 60:
        memory = memory[-60:]

    try:
        with open(memory_path, "w", encoding="utf-8") as f:
            json.dump(memory, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"保存记忆失败: {e}")


def clear_memory(user_id: int, is_group: bool = False) -> None:
    """清除对话记忆"""
    memory_path = get_memory_path(user_id, is_group)
    if memory_path.exists():
        memory_path.unlink()

    summary_path = get_memory_path(user_id, is_group).with_suffix('.summary')
    if summary_path.exists():
        summary_path.unlink()


def _generate_summary(messages: list) -> str:
    """将对话历史压缩成摘要"""
    dialogue = []
    for msg in messages:
        if msg.get("role") in ["user", "assistant"]:
            content = msg.get("content", "")
            content = re.sub(r'^\[\d{4}年\d{2}月\d{2}日.*?\]\s*', '', content)
            dialogue.append(f"{msg['role']}: {content}")

    full_text = "\n".join(dialogue[-30:])

    prompt = f"""请将以下对话压缩成简洁的摘要，保留关键信息（重要事项、承诺、偏好、任务等）。

对话摘要格式：
- 包含的主题和结论
- 用户的重要请求/偏好
- 待办事项或承诺
- 任何需要长期记住的信息

原始对话：
{full_text}

请直接输出摘要（50-150字），不要有额外说明："""

    try:
        response = client.chat.completions.create(
            model=MODEL_NAME,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            max_tokens=200
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        print(f"生成摘要失败: {e}")
        return "（无法生成摘要）"


def _extract_important_points(messages: list) -> list:
    """从历史中提取重要事项"""
    recent = messages[-20:] if len(messages) > 20 else messages

    dialogue = []
    for msg in recent:
        if msg.get("role") == "user":
            content = msg.get("content", "")
            content = re.sub(r'^\[.*?\]\s*', '', content)
            dialogue.append(content)

    if not dialogue:
        return []

    prompt = f"""从以下用户消息中提取需要长期记住的重要事项，每条用一句话概括。

消息列表：
{chr(10).join(f"{i+1}. {d}" for i, d in enumerate(dialogue))}

提取格式（每行一个，用中文）：
- 重要事项或承诺

只提取真正重要的事项，普通聊天内容不需要提取："""

    try:
        response = client.chat.completions.create(
            model=MODEL_NAME,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            max_tokens=200
        )
        result = response.choices[0].message.content.strip()
        points = [line.strip("- ").strip() for line in result.split("\n") if line.strip()]
        return points
    except Exception as e:
        print(f"提取重要事项失败: {e}")
        return []


def build_context(memory: list) -> tuple[list, str, list]:
    """构建上下文：分离最近对话和历史摘要"""
    if not memory:
        return [], "", []

    user_msgs = [m for m in memory if m.get("role") == "user"]
    assistant_msgs = [m for m in memory if m.get("role") == "assistant"]

    total_turns = min(len(user_msgs), len(assistant_msgs))

    if total_turns <= RECENT_TURNS:
        return memory, "", []

    recent_pairs = []
    for i in range(-RECENT_TURNS, 0):
        if i >= -len(user_msgs) and i >= -len(assistant_msgs):
            recent_pairs.append(user_msgs[i])
            recent_pairs.append(assistant_msgs[i])

    older_msgs = []
    for i in range(len(user_msgs) - RECENT_TURNS):
        older_msgs.append(user_msgs[i])
    for i in range(len(assistant_msgs) - RECENT_TURNS):
        older_msgs.append(assistant_msgs[i])

    summary = _generate_summary(older_msgs) if older_msgs else ""
    important_points = _extract_important_points(older_msgs) if older_msgs else []

    return recent_pairs, summary, important_points


def truncate_to_token_limit(messages: list, max_tokens: int = MAX_RECENT_TOKENS) -> list:
    """截断消息以符合 token 限制"""
    total_chars = sum(len(m.get("content", "")) for m in messages)
    max_chars = max_tokens * 2

    if total_chars <= max_chars:
        return messages

    result = []
    current_chars = 0
    for msg in reversed(messages):
        msg_chars = len(msg.get("content", ""))
        if current_chars + msg_chars <= max_chars:
            result.insert(0, msg)
            current_chars += msg_chars
        else:
            break

    return result

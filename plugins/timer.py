from melobot import PluginPlanner, on_start_match
from melobot.protocols.onebot.v11 import MessageEvent, Adapter, ReplySegment, on_message
from melobot.utils.parse import CmdParser, CmdArgs

import asyncio
from datetime import datetime, timedelta

active_timer: dict[str, dict[str, asyncio.Task] | dict[str, datetime] | dict[str, int]] = {}

async def timer(event: MessageEvent, adaptor: Adapter, time_str: str, delay: int) -> None:
    """倒计时核心逻辑"""
    try:
        await adaptor.send_reply(f"倒计时 {time_str} 已经启动，你可以通过最开始设置定时器的消息.check来查看倒计时状态。")
        await asyncio.sleep(delay)
        await adaptor.send_reply(f"时间到！倒计时 {time_str} 结束！")
    except asyncio.CancelledError:
        await adaptor.send_reply(f"倒计时 {time_str} 已被取消。")
    finally:
        del active_timer[str(event.message_id)]
        return

@on_message(parser=CmdParser(cmd_start=".", cmd_sep=" ", targets="timer"))
async def timer_set(event: MessageEvent, args: CmdArgs, adaptor: Adapter) -> None:
    """处理 .timer 命令，设置倒计时"""
    if len(args.vals) < 1 or args.vals[0] == "help":
        await adaptor.send_reply("设置倒计时。\n格式：\n.timer <时间>\n时间格式为 'HH:MM:SS'")
        return

    time_str: str = args.vals[0]

    try:
        if ":" in time_str:
            parts = time_str.split(":")
            if len(parts) == 2:
                minutes, seconds = map(int, parts)
                delay = minutes * 60 + seconds
            elif len(parts) == 3:
                hours, minutes, seconds = map(int, parts)
                delay = hours * 3600 + minutes * 60 + seconds
            else:
                raise ValueError("时间格式错误")
        else:
            raise ValueError("时间格式错误")
    except ValueError:
        await adaptor.send_reply("时间格式错误，请使用 'HH:MM:SS' 格式。")
        return

    task = asyncio.create_task(timer(event, adaptor, time_str, delay))
    active_timer[str(event.message_id)] = {
        "task": task,
        "end_time": datetime.now() + timedelta(seconds=delay),
        "user": event.user_id
    }
    return

@on_start_match(target=".timerlist")
async def timer_list(event: MessageEvent, adaptor: Adapter) -> None:
    """处理 .timerlist 命令，列出所有活动的倒计时"""
    if not active_timer:
        await adaptor.send_reply("当前没有活动的倒计时。")
        return

    response = "当前活动的倒计时：\n"
    for msg_id, timer_info in active_timer.items():
        end_time = timer_info["end_time"]
        user_id = timer_info["user"]
        remaining_time = end_time - datetime.now()
        response += f"倒计时ID: {msg_id}, 倒计时发起者QQ号: {user_id}, 剩余时间: {remaining_time}\n"

    await adaptor.send_reply(response)

@on_start_match(target=".check")
async def check_timer(event: MessageEvent, adaptor: Adapter) -> None:
    """处理 .check 命令，检查当前倒计时状态"""
    if _ := event.get_segments(ReplySegment):
        msg_id = str(_[0].data["id"])
        if msg_id in active_timer:
            timer_info = active_timer[msg_id]
            end_time = timer_info["end_time"]
            remaining_time = end_time - datetime.now()
            await adaptor.send_reply(f"计时器还剩下大约 {remaining_time}。")
        else:
            await adaptor.send_reply("请回复正确的设置倒计时的消息以检查状态。")
    else:
        await adaptor.send_reply("请回复一条倒计时消息以检查状态。")
        return
    
@on_message(parser=CmdParser(cmd_start=".", cmd_sep=" ", targets="timerkill"))
async def timer_kill(event: MessageEvent, args: CmdArgs, adaptor: Adapter) -> None:
    """处理 .timerkill 命令，取消指定的倒计时"""
    if len(args.vals) < 1 or args.vals[0] == "help":
        await adaptor.send_reply("取消指定的倒计时。\n格式：\n.timerkill <倒计时ID>")
        return

    try:
        msg_id = str(args.vals[0])
    except ValueError:
        await adaptor.send_reply("倒计时ID格式错误，请提供一个有效的整数。")
        return

    if msg_id in active_timer:
        task = active_timer[msg_id]["task"]
        task.cancel()
        del active_timer[msg_id]
        await adaptor.send_reply(f"倒计时 {msg_id} 已被取消。")
    else:
        await adaptor.send_reply(f"没有找到 ID 为 {msg_id} 的倒计时。")

TimerPlugin = PluginPlanner(version="0.0.1", flows=[timer_set, timer_list, check_timer, timer_kill])
from melobot import PluginPlanner, on_start_match
from melobot.protocols.onebot.v11 import MessageEvent, Adapter, ReplySegment, on_message
from melobot.utils.parse import CmdParser, CmdArgs

import asyncio
from datetime import datetime, timedelta

active_timer: dict[str, dict[str, datetime]] = {}

@on_message(parser=CmdParser(cmd_start=".", cmd_sep=" ", targets="timer"))
async def timer(event: MessageEvent, args: CmdArgs, adaptor: Adapter) -> None:
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

    try:
        active_timer[event.message_id] = {"end_time": datetime.now() + timedelta(seconds=delay), "user": event.user_id}
        await adaptor.send_reply(f"倒计时 {time_str} 已经启动，你可以通过最开始设置定时器的消息.check来查看倒计时状态。")
        await asyncio.sleep(delay)
        await adaptor.send_reply(f"时间到！倒计时 {time_str} 结束！")
    finally:
        del active_timer[event.message_id]
        return

@on_start_match(target=".timerlist")
async def timer_list(event: MessageEvent, adaptor: Adapter) -> None:
    """处理 .timerlist 命令，列出所有活动的倒计时"""
    if not active_timer:
        await adaptor.send_reply("当前没有活动的倒计时。")
        return

    response = "当前活动的倒计时：\n"
    for _, timer_info in active_timer.items():
        end_time = timer_info["end_time"]
        user_id = timer_info["user"]
        remaining_time = end_time - datetime.now()
        response += f"倒计时发起者 ID {user_id}: 剩余时间 {remaining_time}\n"

    await adaptor.send_reply(response)

@on_start_match(target=".check")
async def check_timer(event: MessageEvent, adaptor: Adapter) -> None:
    """处理 .check 命令，检查当前倒计时状态"""
    if _ := event.get_segments(ReplySegment):
        msg_id = int(_[0].data["id"])
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

TimerPlugin = PluginPlanner(version="0.0.1", flows=[timer, timer_list, check_timer])
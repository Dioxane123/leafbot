from melobot import PluginPlanner, on_start_match, send_text
from melobot.protocols.onebot.v11 import MessageEvent, Adapter, ReplySegment, on_message
from melobot.utils.parse import CmdParser, CmdArgs

import asyncio
from datetime import datetime, timedelta, date
import os
from plugins.chat import conversation_dict

from dotenv import load_dotenv
load_dotenv()
OWNER = os.getenv("OWNER")

active_timer: dict[str, dict[str, asyncio.Task | datetime | int | bool | asyncio.Event]] = {}

async def timer(event: MessageEvent, adaptor: Adapter, time_str: str, delay: int, msg_id: str) -> None:
    """倒计时核心逻辑"""
    try:
        await adaptor.send_reply(f"倒计时 {time_str} 已经启动，你可以通过最开始设置定时器的消息.check来查看倒计时状态。")
        while delay > 0:
            await active_timer[msg_id]["running_event"].wait()  # 等待运行事件
            await asyncio.sleep(1)
            delay -= 1
            active_timer[str(event.message_id)]["remain_time"] = timedelta(seconds=delay)
        await adaptor.send_reply(f"时间到！倒计时 {time_str} 结束！")
        os.makedirs(".cache/timer",exist_ok=True)
        with open(f".cache/timer/{date.today()}.txt", "a+") as f:
            f.write(f"{active_timer[str(event.message_id)]['user']},{active_timer[str(event.message_id)]['tag']},{active_timer[str(event.message_id)]['total_time']}\n")
    except asyncio.CancelledError:
        await adaptor.send_reply(f"倒计时 {time_str} 已被取消。")
    finally:
        del active_timer[str(event.message_id)]
        return

@on_start_match(target=".pause")
async def pause(event: MessageEvent, adaptor: Adapter) -> None:
    """处理 .pause 命令，暂停选中活动的倒计时"""
    if _ := event.get_segments(ReplySegment):
        msg_id = str(_[0].data["id"])
        if msg_id in active_timer:
            timer_info = active_timer[msg_id]
            if timer_info["running"]:
                timer_info["running_event"].clear()  # 清除运行事件，暂停倒计时
                timer_info["running"] = False  # 标记为暂停状态
                await adaptor.send_reply(f"倒计时已暂停。剩余时间{timer_info['remain_time']}。")
            else:
                timer_info["running_event"].set()  # 恢复运行事件，继续倒计时
                timer_info["running"] = True # 标记为运行状态
                await adaptor.send_reply("倒计时已恢复运行。")
        else:
            await adaptor.send_reply("请回复正确的设置倒计时的消息以暂停倒计时。")
    else:
        await adaptor.send_reply("请回复一条倒计时消息以暂停倒计时。")
        return

@on_message(parser=CmdParser(cmd_start=".", cmd_sep=" ", targets="timer"))
async def timer_set(event: MessageEvent, args: CmdArgs, adaptor: Adapter) -> None:
    """处理 .timer 命令，设置倒计时"""
    if len(args.vals) < 1 or args.vals[0] == "help":
        await adaptor.send_reply("设置倒计时。\n格式：\n.timer <时间> [tag]\n时间格式为 'HH:MM:SS'")
        return

    time_str: str = args.vals[0]
    tag: str = args.vals[1] if len(args.vals) > 1 else ""

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

    task = asyncio.create_task(timer(event, adaptor, time_str, delay, str(event.message_id)))
    running_event = asyncio.Event()
    running_event.set()
    active_timer[str(event.message_id)] = {
        "running": True,
        "task": task,
        "remain_time": timedelta(seconds=delay),
        "user": event.user_id,
        "running_event": running_event,
        "tag": tag,
        "total_time": timedelta(seconds=delay)
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
        user_id = timer_info["user"]
        response += f"倒计时ID: {msg_id}, 倒计时发起者QQ号: {user_id}, 剩余时间: {timer_info['remain_time']}\n"

    await adaptor.send_reply(response)

@on_start_match(target=".check")
async def check_timer(event: MessageEvent, adaptor: Adapter) -> None:
    """处理 .check 命令，检查当前倒计时状态"""
    if _ := event.get_segments(ReplySegment):
        msg_id = str(_[0].data["id"])
        if msg_id in active_timer:
            timer_info = active_timer[msg_id]
            await adaptor.send_reply(f"计时器还剩下大约 {timer_info['remain_time']}。")
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

@on_message(parser=CmdParser(cmd_start=".", cmd_sep=" ", targets="todaytimer"))
async def today_timer(event: MessageEvent, args: CmdArgs, adaptor: Adapter) -> None:
    """处理 .todaytimer 命令，查看特定日期的倒计时记录（默认今天）"""
    if len(args.vals) == 1 and args.vals[0] == "help":
        await adaptor.send_reply("查看某天的倒计时记录。\n格式：\n.todaytimer [日期]\n日期格式为 'YYYY-MM-DD'，默认为今天。")
        return
    date_str = args.vals[0] if args.vals else date.today().strftime("%Y-%m-%d")

    os.makedirs(".cache/timer", exist_ok=True)
    file_path = f".cache/timer/{date_str}.txt"
    if not os.path.exists(file_path):
        await adaptor.send_reply(f"{date_str} 没有倒计时记录。")
        return

    with open(file_path, "r") as f:
        records = f.readlines()

    response = f"{date_str}的计时记录：\n"
    total_time: dict[str, timedelta] = {}
    total_user: dict[str, dict[str, timedelta]] = {}
    for user in os.listdir(".cache/timer/prompt"):
        user_id = user.split(".")[0]
        total_user[user_id] = dict()
    for record in records:
        user_id, tag, time = record.strip().split(",")
        hh, mm, ss = map(int, time.split(":"))
        time = hh * 3600 + mm * 60 + ss
        total_time[f"{user_id},{tag}"] = total_time.get(f"{user_id},{tag}", timedelta(0)) + timedelta(seconds=time)
    for key, value in total_time.items():
        user_id, tag = key.split(",")
        if user_id in total_user:
            total_user[user_id][tag] = total_user[user_id].get(tag, timedelta(0)) + value

        if str(event.user_id) == OWNER:
            response += f"用户QQ号: {user_id}, 标签: {tag}, 总时间: {value}\n"
        elif user_id == str(event.user_id):
            response += f"标签: {tag}, 总时间: {value}\n"
    await adaptor.send_reply(response)

    if str(event.user_id) in total_user:
        event_str = "\n".join([f"{key}: {value}" for key, value in total_user[str(event.user_id)].items()])
        with open(f".cache/timer/prompt/{event.user_id}.txt", "r") as f:
            prompt = f.read().strip()
        prompt = prompt.format(event_str=event_str)
        response = conversation_dict[event.user_id].chat(prompt)
        # owner_response = conversation_dict[int(OWNER)].chat(f"""一天5个小时是我的给自己计划的保底学习时间，7个小时是我给自己的标准学习时间。
        #                                                     今天我不同事项的学习时间是：\n{event_str}\n
        #                                                     上面学习时间的格式为HH:MM:SS。
        #                                                     你帮我算算今天我一共学了多久，再安慰或者鼓励我一下吧。
        #                                                     """)
        await send_text(response)

@on_message(parser=CmdParser(cmd_start=".", cmd_sep=" ", targets="todayprompt"))
async def today_prompt(event: MessageEvent, args: CmdArgs, adaptor: Adapter) -> None:
    """处理 .todayprompt 命令，设置对应用户在使用todaytimer时的prompt"""
    if len(args.vals) < 1 or args.vals[0] == "help":
        await adaptor.send_reply("设置todaytimer的prompt。\n格式：\n.todayprompt <prompt>")
        return
    prompt = str(args.vals[0])
    if str(event.user_id) != OWNER:
        os.makedirs(".cache/timer/prompt", exist_ok=True)
        with open(f".cache/timer/prompt/{event.user_id}.txt", "w") as f:
            f.write(prompt)
        await adaptor.send_reply("已成功设置todaytimer的prompt。")
        return
    else:
        user = str(args.vals[1]) if len(args.vals) > 1 else OWNER
        os.makedirs(".cache/timer/prompt", exist_ok=True)
        with open(f".cache/timer/prompt/{user}.txt", "w") as f:
            f.write(prompt)
        await adaptor.send_reply(f"已成功设置用户 {user} 的todaytimer的prompt。")

TimerPlugin = PluginPlanner(version="0.0.1", flows=[timer_set, timer_list, check_timer, timer_kill, pause, today_timer, today_prompt])
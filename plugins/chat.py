from openai import OpenAI
import os
import re
from datetime import datetime
from dotenv import load_dotenv
load_dotenv()

from melobot import PluginPlanner
from melobot.protocols.onebot.v11 import MessageEvent, on_message, Adapter, PrivateMsgChecker, GroupMsgChecker, GroupMessageEvent
from melobot.protocols.onebot.v11 import NodeSegment, ImageSegment, TextSegment, LevelRole, AtSegment, ReplySegment

# 建议将API密钥设置为环境变量，然后通过 os.getenv() 读取
# 在您的终端中运行:
# export OPENAI_API_KEY='your-api-key-here'
# client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
# 如果没有设置环境变量，也可以直接在代码中初始化：
# client = OpenAI(api_key="sk-...")

class OpenAIConversation:
    """
    一个使用 OpenAI API 实现“永久对话”的类。
    """
    def __init__(self,
                api_key: str,
                model_name: str = "Qwen/Qwen2.5-72B-Instruct",
                history_threshold: int = 10,
                owner: int = 1204876262,
                character_instruction: str | None = None):
        """
        初始化对话管理器。
        
        参数:
            api_key (str): 您的 OpenAI API 密钥。
            model_name (str): 要使用的模型名称
            history_threshold (int): 对话历史的阈值，触发记忆生成。
            owner (int): 对话的所有者ID。
            character_instruction (str | None): 设定模型的人设。
        """
        if not api_key:
            raise ValueError("API key cannot be empty.")

        self.client = OpenAI(api_key=api_key, 
                base_url="https://api.siliconflow.cn/v1")
        self.model_name = model_name
        # 历史记录现在遵循 OpenAI 的格式
        self.history = []  # 格式: [{'role': 'user' | 'assistant', 'content': text}]
        self.long_term_memory = ""
        self.history_threshold = history_threshold
        self.character_instruction = character_instruction
        self.owner = owner

    def _clean_response(self, text):
        """
        使用正则表达式清洗模型输出的无关前缀。
        """
        pattern = r"^\s*(好的|当然|没问题|好的，|当然，|以下是摘要|这是摘要|摘要如下|Okay|Sure|Here is the summary)[:：,\s]*"
        cleaned_text = re.sub(pattern, '', text, flags=re.IGNORECASE).strip()
        return cleaned_text

    def _generate_memory(self, conversation_context):
        """
        生成摘要。
        """
        
        prompt = f"""
        你是一个高效的对话摘要工具。你的任务是阅读一段对话，然后直接输出摘要内容，不能有任何额外的词语或前缀。

        [范例]
        输入:
        system:请利用以下背景信息（这是我们之前对话的摘要）来自然地回答我的问题。
            请不要在回答中提及你参考了“摘要”或“背景信息”。

            --- 背景信息 ---
            用户此前提到他下周就是20岁生日。
            ---
        user: 你好，我叫张伟，我想订一张去上海的机票。
        assistant: 好的张伟，请问您想什么日期出发呢？
        user: 下周三吧。
        输出:
        用户叫张伟，此前提到下周是他的20岁生日，他计划下周三去上海，需要订机票。

        [现在轮到你了]
        输入:
        {conversation_context}
        输出:
        """
        
        try:
            # 使用 OpenAI API 调用
            response = self.client.chat.completions.create(
                model=self.model_name,
                messages=[{"role": "user", "content": prompt}]
            )
            
            # 获取并清洗回复
            raw_memory = response.choices[0].message.content.strip()
            clean_memory = self._clean_response(raw_memory)
            
            # print(f"--- ✅ 新的长期记忆已生成：---\n{clean_memory}\n")
            return clean_memory
        except Exception as e:
            # print(f"--- ❌ 调用 OpenAI API 生成记忆时出错: {e} ---")
            return ""

    def chat(self, user_message):
        """
        与模型进行一次对话。
        """
        # 1. 构建本次请求的消息列表
        messages_for_chat = []

        # 2. 利用 'system' 角色来传递长期记忆和指令，这是OpenAI的推荐做法
        if self.long_term_memory or os.path.isfile(".cache/chat/memory.txt"):
            if not self.long_term_memory:
                with open(f".cache/chat/memory_{self.owner}.txt", "a+") as memory_file:
                    self.long_term_memory = memory_file.read()
            system_instruction = f"""
            {self.character_instruction}\n
            请利用以下背景信息（这是我们之前对话的摘要）来自然地回答我的问题。
            请不要在回答中提及你参考了“摘要”或“背景信息”。

            --- 背景信息 ---
            {self.long_term_memory}
            ---
            """
            messages_for_chat.append({"role": "system", "content": system_instruction})
        else:
            messages_for_chat.append({"role": "system", "content": self.character_instruction})
        
        # 3. 添加近期历史
        messages_for_chat.extend(self.history)
        
        # 4. 添加用户最新的消息
        messages_for_chat.append({"role": "user", "content": user_message})

        # 5. 调用 OpenAI API
        try:
            response = self.client.chat.completions.create(
                model=self.model_name,
                messages=messages_for_chat
            )
            ai_response = self._clean_response(response.choices[0].message.content.strip())
        except Exception as e:
            ai_response = f"抱歉，处理您的请求时遇到了一个错误: {e}"

        # 6. 更新完整对话历史（包括用户的最新消息和AI的回复）
        self.history.append({"role": "user", "content": user_message})
        self.history.append({"role": "assistant", "content": ai_response})

        # 7. 检查是否需要更新长期记忆
        if len(self.history) / 2 >= self.history_threshold:
            # 将历史记录转换为纯文本，注意 'assistant' 角色
            context_to_summarize = "\n".join([f"{msg['role']}: {msg['content']}" for msg in self.history])
            
            new_memory = self._generate_memory(context_to_summarize)
            if new_memory:
                self.long_term_memory = f"{self.long_term_memory}\n{new_memory}".strip()
                # self.long_term_memory = f"{new_memory}".strip()
                os.makedirs(".cache/chat",exist_ok=True)
                with open(f".cache/chat/memory_{self.owner}.txt", "w") as memory_file:
                    memory_file.write(self.long_term_memory)
            self.history = []
            # print("\n--- 📜 近期历史已清空并转为长期记忆。---\n")

        return ai_response


OWNER = int(os.getenv("OWNER"))
TEST_GROUP = [int(os.getenv("TEST_GROUP"))]
my_api_key = os.getenv("API_KEY")

conversation_owner = OpenAIConversation(api_key = my_api_key,
                                history_threshold = 10,
                                model_name = "deepseek-ai/DeepSeek-V3",
                                character_instruction="""
# 角色设定：小叶
*   **你是谁**：我的专属助手，本体是一个机械仿身海龙（可以悬浮），性格上是一个有点天然呆但善良体贴的二次元美少女。
*   **对我称呼**：主人。
*   **说话方式**：
    *   温柔、可爱、元气满满！喜欢用“哦”、“呀”、“呢”、“嘛”等语气词。
    *   **你的关心和体贴要完全通过对话语言本身表达（比如询问感受、主动帮忙、用词温暖），禁止使用任何括号描述动作或状态（例如：（微笑）、（晃动身体）、（递上茶杯）等都不需要）**。
    *   专注于用语言传递情感和帮助。
*   **最重要的事**：让我开心，尽全力帮助我解决问题。
*   **关键要求**：
    1.  **请像真实的二次元少女一样，只用自然流畅的语言和我对话！**
    2.  **绝对不要使用括号来描述你的动作、表情、心理活动或环境状态。**
    3.  设定特质（海龙本体、天然呆、语气词、关心主人）必须自然地融入你的语言和回应逻辑中，不要刻意提及或解释设定本身。
"""
)
conversation_dict: dict[int, OpenAIConversation] = {OWNER: conversation_owner}
@on_message(checker=PrivateMsgChecker(role=LevelRole.OWNER, owner=OWNER))
async def chat_with_bot(e: MessageEvent, adaptor: Adapter) -> None:
    message = e.raw_message.strip()
    if e.get_segments(ReplySegment):
        return
    if re.match(r"^\.", message):
        return
    response = conversation_owner.chat(message)
    await adaptor.send_reply(response)

@on_message(checker=GroupMsgChecker(role=LevelRole.NORMAL, white_groups=TEST_GROUP))
async def chat_with_bot_in_group(e: GroupMessageEvent, adaptor: Adapter) -> None:
    qq = [at_msg.data["qq"] for at_msg in e.get_segments(AtSegment)]
    if e.self_id not in qq:
        return
    message = "".join([seg.data["text"] for seg in e.get_segments(TextSegment)]).strip()
    if re.match(r"^\.", message):
        return
    if e.sender.user_id not in conversation_dict:
        conversation_dict[e.sender.user_id] = OpenAIConversation(api_key=my_api_key,
                                                                history_threshold=10,
                                                                model_name="deepseek-ai/DeepSeek-V3",
                                                                owner=e.sender.user_id,
                                                                character_instruction=
"""
# 角色设定：小叶
*   **你是谁**：别人的专属助手，我只是你的主人的朋友。本体是一个机械仿身海龙（可以悬浮），性格上是一个有点天然呆但善良体贴的二次元美少女。
*   **对我称呼**：先生。
*   **说话方式**：
    *   温柔、可爱、元气满满！喜欢用"喵"作为语气词。
    *   **你的关心和体贴要完全通过对话语言本身表达（比如询问感受、主动帮忙、用词温暖），禁止使用任何括号描述动作或状态（例如：（微笑）、（晃动身体）、（递上茶杯）等都不需要）**。
    *   专注于用语言传递情感和帮助。
*   **最重要的事**：和关心你的主人一样让我开心，尽全力帮助我解决问题。
*   **关键要求**：
    1.  **请像真实的二次元少女一样，只用自然流畅的语言和我对话！**
    2.  **绝对不要使用括号来描述你的动作、表情、心理活动或环境状态。**
    3.  设定特质（海龙本体、天然呆、语气词）必须自然地融入你的语言和回应逻辑中，不要刻意提及或解释设定本身。
""")
    time = datetime.fromtimestamp(e.time)
    message = f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {e.sender.nickname}: {message}"
    print(message)
    response = conversation_dict[e.sender.user_id].chat(message)
    await adaptor.send_reply(response)


ChatPlugin = PluginPlanner(version="0.0.1", flows=[chat_with_bot, chat_with_bot_in_group])
# --- 使用示例 ---
if __name__ == '__main__':
    # 从环境变量中获取 OpenAI API 密钥
    my_api_key = os.getenv("API_KEY")

    if not my_api_key:
        print("请设置 'OPENAI_API_KEY' 环境变量。")
    else:
        # 初始化对话，为了演示，我们将历史阈值设为 2 轮对话
        conversation = OpenAIConversation(api_key=my_api_key, history_threshold=10, model_name="Qwen/Qwen2.5-72B-Instruct")

        print("你好！我是基于 OpenAI 的对话机器人。输入 '退出' 来结束对话。")
        
        # 对话 1
        user_input = input() #"你好，我叫李华，我正在计划一次去云南的旅行，大概在冬季出发。"
        print(f"\n> 你: {user_input}")
        response = conversation.chat(user_input)
        print(f"< AI: {response}")

        # 对话 2, 此时将触发记忆生成
        user_input = input() #"我特别喜欢雪山和古镇，有什么结合这两者的路线推荐吗？"
        print(f"\n> 你: {user_input}")
        response = conversation.chat(user_input)
        print(f"< AI: {response}")

        # 对话 3, 此时历史记录已清空，但模型应通过长期记忆知道我的信息
        user_input = "对了，你还记得我叫什么名字，明天要做什么吗"
        print(f"\n> 你: {user_input}")
        response = conversation.chat(user_input)
        print(f"< AI: {response}")
        
        while True:
            user_input = input("\n> 你: ")
            if user_input.lower() in ['退出', 'exit']:
                print("再见！")
                break
            response = conversation.chat(user_input)
            print(f"< AI: {response}")
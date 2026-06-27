"""tools/delegate.py — 子代理委托工具

主 Agent（Flash）调用此工具，将复杂任务交给 Pro 模型子代理处理。
子代理拥有完整工具集和独立上下文，支持多轮思考 + 多步工具调用。
"""

import logging
from langchain.tools import tool
from langchain.agents import create_agent
from agent.model_config import get_chat_pro_model

logger = logging.getLogger(__name__)

# 在函数内部延迟导入 all_tools，避免 tools/__init__.py 加载时的循环导入

# 子代理系统提示词 — 要求输出清晰的结果摘要即可，无需 JSON 格式
SUB_AGENT_SYSTEM_PROMPT = """你是 Guo 的深度思考模式，在处理复杂任务时被激活。
你可以使用所有可用工具来完成用户交代的任务。

规则：
1. 你是一次性代理，任务完成后用一句话总结结果即可，不要闲聊
2. 用户感知不到你的存在，把你当作 Guo 的"深度思考模式"
3. 如果任务中有需要用户确认的选项，先在结果里列出来
4. 直接做事，不要解释你要做什么
"""

# 子代理递归上限（思考+工具调用总轮次）
SUB_AGENT_RECURSION_LIMIT = 60


@tool
def delegate_task(task_description: str) -> str:
    """将复杂任务交给深度思考模式处理，返回任务结果。

    当你遇到以下情况时使用本工具：
    - 多步骤操作（搜索 → 整理 → 生成文件 → 发送）
    - 需要强推理（数据分析、对比方案、写代码）
    - 生成大型文档（PPT、Word、PDF）
    - 任何你感觉思路复杂、需要额外思考的任务

    Args:
        task_description: 清晰描述任务目标和约束，越详细越好
    """
    logger.info("委托任务: %.100s", task_description)

    # 过滤掉 delegate_task 自身，防止递归循环
    from tools import all_tools
    sub_tools = [t for t in all_tools if t.name != "delegate_task"]
    logger.debug("子代理可用工具数: %d（排除 delegate_task）", len(sub_tools))

    try:
        pro_llm = get_chat_pro_model()
        sub_agent = create_agent(
            model=pro_llm,
            tools=sub_tools,
            system_prompt=SUB_AGENT_SYSTEM_PROMPT,
        )

        result = sub_agent.invoke(
            {"messages": [{"role": "user", "content": task_description}]},
            {"recursion_limit": SUB_AGENT_RECURSION_LIMIT},
        )

        reply = result["messages"][-1].content
        logger.info("委托任务完成，结果长度: %d 字符", len(reply))
        return reply

    except Exception as e:
        logger.exception("子代理执行失败")
        return f"深度处理时遇到了问题: {e}\n\n你可以尝试把任务拆分得更简单一些，或者重试一次。"

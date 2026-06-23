import sys; sys.path.insert(0,'.')
from langchain_core.messages import HumanMessage
from agent.agent_core import llm
from tools import all_tools

# 检查工具是否在模型绑定中
wechat_tool = [t for t in all_tools if t.name == 'send_file_to_wechat'][0]
print(f"工具: {wechat_tool.name}")
print(f"参数: {list(wechat_tool.args.keys())}")

# 直接用模型看它会不会调工具
bound = llm.bind_tools([wechat_tool])
msg = [HumanMessage(content="把桌面上的 test.txt 发到我微信")]
result = bound.invoke(msg)

print(f"\n模型返回类型: {type(result).__name__}")
print(f"tool_calls: {getattr(result, 'tool_calls', [])}")
if result.tool_calls:
    for tc in result.tool_calls:
        print(f"  → 调用了 {tc['name']} args={tc['args']}")
else:
    print(f"  → 没有调用工具，仅文字回复")
    print(f"  回复: {result.content[:100]}")

"""Test tool discovery for send_to_wechat"""
import sys, os
sys.stdout.reconfigure(encoding='utf-8')
os.chdir('E:\\File\\Desktop_pet_Engine1\\Desktop_pet_Engine\\Desktop_Pet_Engine')
sys.path.insert(0, '.')

try:
    from tools import discover_tools, all_tools
    tools = discover_tools()
    names = [t.name for t in tools]
    print(f"discover_tools 发现了 {len(tools)} 个工具:")
    for n in names:
        print(f"  - {n}")
    print()
    has_send = "send_file_to_wechat" in names
    print(f"'send_file_to_wechat' 在列表中: {has_send}")
    print(f"all_tools 长度: {len(all_tools)}")
    
    if has_send:
        idx = names.index("send_file_to_wechat")
        t = tools[idx]
        print(f"\n工具详情:")
        print(f"  类型: {type(t)}")
        print(f"  名称: {t.name}")
        print(f"  描述: {t.description[:100]}")
except Exception as e:
    import traceback; traceback.print_exc()

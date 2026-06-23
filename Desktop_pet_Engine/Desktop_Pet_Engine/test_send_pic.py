"""通过后端 API 发送桌面图片到微信"""
import httpx, json

# 直接用 func 调 send_file_to_wechat
# 但因为通道状态只在后端进程内有，需要走 debug 端点
# 但 debug 端点只测自己的 temp 文件
# 所以我直接在 debug 端点里加个 file_path 参数

# 先查一下桌面图片
import os
desktop = os.path.expanduser('~/Desktop')
pics = [f for f in os.listdir(desktop) if f.lower().endswith(('.png', '.jpg', '.jpeg', '.gif'))]
for p in pics:
    print(f'  {p}')

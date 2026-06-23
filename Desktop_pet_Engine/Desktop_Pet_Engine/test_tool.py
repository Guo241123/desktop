"""直接测试 send_file_to_wechat 工具"""
import sys
sys.path.insert(0, '.')

from tools.send_to_wechat import send_file_to_wechat

# 先测试一个不存在的文件，看工具是否正常响应
result = send_file_to_wechat("C:/nonexistent/test.txt")
print(f"不存在文件: {result}")

# 测试一个存在的文件
import tempfile, os
tmp = tempfile.NamedTemporaryFile(suffix='.txt', delete=False, mode='w', encoding='utf-8')
tmp.write("hello")
tmp.close()

result = send_file_to_wechat(tmp.name)
print(f"存在文件: {result}")
os.unlink(tmp.name)

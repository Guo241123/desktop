"""调试：检查微信通道状态和 send_to_wechat 工具"""
import asyncio
import sys
sys.path.insert(0, '.')

async def check():
    from mi import channel_manager
    ch = channel_manager.get('wechat')
    if not ch:
        print('❌ 通道不存在')
        return
    
    print(f'通道运行中: {ch._running}')
    print(f'API实例: {ch._api is not None}')
    if ch._api:
        print(f'base_url: {ch._api.base_url}')
        print(f'bot_token: {"有" if ch._api.bot_token else "空"}')
        if ch._api.bot_token:
            print(f'bot_token前20位: {ch._api.bot_token[:20]}...')
    print(f'last_user_id: "{ch._last_user_id}"')
    print(f'last_context_token: "{ch._last_context_token}"')
    
    # 查看 credentials
    from mi.channels.wechat_api import load_credentials
    creds = load_credentials()
    if creds:
        print(f'\ncredentials 中的 bot_base_url: {creds.get("bot_base_url")}')
        print(f'credentials 中的 bot_token: {"有" if creds.get("bot_token") else "空"}')
        default_url = 'https://ilinkai.weixin.qq.com'
        bu = creds.get('bot_base_url', '')
        if bu and bu != default_url:
            print(f'⚠️ 和默认地址不同! 自定义地址: {bu}')
        else:
            print(f'base_url 和默认地址相同: {default_url}')
    else:
        print('\n⚠️ 没有 credentials 文件')
    
    # 3. 测试 get_send_context
    ctx = ch.get_send_context() if hasattr(ch, 'get_send_context') else None
    if ctx:
        print(f'\nsend_context:')
        print(f'  bot_token: {"有" if ctx.get("bot_token") else "空"}')
        print(f'  bot_base_url: {ctx.get("bot_base_url")}')
        print(f'  to_user_id: {ctx.get("to_user_id")}')
        print(f'  context_token: {ctx.get("context_token")[:20] if ctx.get("context_token") else "空"}...')
    else:
        print(f'\nsend_context: None')

asyncio.run(check())

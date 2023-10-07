# -*- encoding: utf-8 -*-

gHook: dict[str, list] = {
    # 创建一个新的session时调用
    "session.new": [
    ],
    # 删除一个session时调用
    "session.del": [
    ],
    # 发送一条消息到API服务器时调用
    "remote.send": [
    ],
    # 从API服务器接收到一条消息时调用
    "remote.recv": [
    ],
}

def get_hook(hook_name: str):
    """
        获取一个hook的函数列表
    """
    global gHook
    if hook_name not in gHook:
        gHook[hook_name] = []
    return gHook[hook_name]

def add_hook(hook_name: str, func):
    """
        添加一个hook
    """
    global gHook
    if hook_name not in gHook:
        gHook[hook_name] = []
    gHook[hook_name].append(func)

def run_hook(hook_name: str, *args, **kwargs):
    """
        运行一个hook列表
    """
    global gHook
    if hook_name not in gHook:
        return
    for func in gHook[hook_name]:
        func(*args, **kwargs)

def clear_hook(hook_name: str):
    """
        清空一个hook列表
    """
    global gHook
    if hook_name not in gHook:
        return
    gHook[hook_name].clear()

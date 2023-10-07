# -*- encoding: utf-8 -*-
r"""
 ________  ________  ___  ________       ___    ___ ________  ___  ___  ________  ___  ___
|\   __  \|\   __  \|\  \|\   ___  \    |\  \  /  /|\_____  \|\  \|\  \|\   __  \|\  \|\  \
\ \  \|\  \ \  \|\  \ \  \ \  \\ \  \   \ \  \/  / /\|___/  /\ \  \\\  \ \  \|\  \ \  \\\  \
 \ \   _  _\ \   __  \ \  \ \  \\ \  \   \ \    / /     /  / /\ \   __  \ \  \\\  \ \  \\\  \
  \ \  \\  \\ \  \ \  \ \  \ \  \\ \  \   \/  /  /     /  /_/__\ \  \ \  \ \  \\\  \ \  \\\  \
   \ \__\\ _\\ \__\ \__\ \__\ \__\\ \__\__/  / /      |\________\ \__\ \__\ \_______\ \_______\
    \|__|\|__|\|__|\|__|\|__|\|__| \|__|\___/ /        \|_______|\|__|\|__|\|_______|\|_______|
                                       \|___|/

    @Author: RainyZhou
    @Contact: thunderain_zhou@163.com
    @License: AGPLv3
    @Copyright: (C) 2023
    @Description:
        all the utilities for the plugin
        including:
            1. the diagnose logger wrapped from the OlivOS logger
            2. all the exceptions for the plugin

"""

import dataclasses as _dataclasses

import OlivOS

from . import databaseAPI
from typing import Callable as _Callable

gLogProc = None

@_dataclasses.dataclass
class UserInfo:
    """
        the user info
    """
    user_id: str = "0"
    platform: str = "local"

    def __str__(self):
        return f"{self.platform}:{self.user_id}"

    @classmethod
    def from_event(cls, plugin_event):
        """
            get the user info from the OlivOS event
        """
        platform = plugin_event.platform['platform']
        uid = str(plugin_event.data.user_id)
        return cls(uid, platform)
    

class _LogProcWrapper:
    """
        the logger for the plugin
    """
    def __init__(self, proc_log: _Callable|None = None):
        global gLogProc
        if gLogProc is None:
            gLogProc = self
        else:
            raise RuntimeError("LogProcWrapper can only be initialized once")
        if proc_log is None:
            proc_log = print
        self._log = proc_log

    def trace(self, msg, *args, **kwargs):
        self.log(-1, msg, *args, **kwargs)

    def debug(self, msg, *args, **kwargs):
        self.log(0, msg, *args, **kwargs)
    
    def note(self, msg, *args, **kwargs):
        self.log(1, msg, *args, **kwargs)

    def info(self, msg, *args, **kwargs):
        self.log(2, msg, *args, **kwargs)
    
    def warn(self, msg, *args, **kwargs):
        self.log(3, msg, *args, **kwargs)
    
    def error(self, msg, *args, **kwargs):
        self.log(4, msg, *args, **kwargs)
    
    def fatal(self, msg, *args, **kwargs):
        self.log(5, msg, *args, **kwargs)
    
    def log(self, level: int, msg, *args, **kwargs):
        if args or kwargs:
            self._log(level, str(msg).format(*args,**kwargs))
        else:
            self._log(level, str(msg))
 
    def __call__(self, *args, **kwds):
        self._log(*args, **kwds)

def get_logger(proc_log=None) -> _LogProcWrapper:
    """
        get the logger for the plugin
    """
    global gLogProc
    if gLogProc is None:
        gLogProc = _LogProcWrapper(proc_log)
    return gLogProc

def set_logger(proc_log: _Callable):
    """
        set the logger for the plugin
    """
    global gLogProc
    if gLogProc is None:
        gLogProc = _LogProcWrapper(proc_log)
    else:
        raise RuntimeError("LogProcWrapper can only be initialized once")

def format_dict_factory(plugin_event, proc):
    dict_format = {}

    user_info = UserInfo.from_event(plugin_event)

    dict_format["user_id"] = user_info.user_id
    dict_format["platform"] = user_info.platform

    dict_format["bot_id"] = plugin_event.bot_info.id

    if plugin_event.plugin_info['func_type'] == 'group_message':
        dict_format["group_id"] = plugin_event.data.group_id
        dict_format["host_id"] = plugin_event.data.host_id
        dict_format["target_id"] = plugin_event.data.group_id
    elif plugin_event.plugin_info['func_type'] == 'private_message':
        dict_format["group_id"] = None
        dict_format["host_id"] = None
        dict_format["target_id"] = plugin_event.data.user_id
    else:
        dict_format["group_id"] = None
        dict_format["host_id"] = None
        dict_format["target_id"] = None
    
    dict_format["message_raw"] = plugin_event.data.message.data
    return dict_format

@_dataclasses.dataclass
class CommandConfig:
    plugin_event: OlivOS.API.Event
    Proc: OlivOS.pluginAPI.shallow
    message: str
    user_info: UserInfo
    data: databaseAPI.DataAPI
    
    @property
    def dict_format(self):
        return format_dict_factory(self.plugin_event, self.Proc)
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
        this is the configuration API for the plugin
        the configuration file is located at ./plugin/data/OlivaChatGPT/config.json

        when the configuration file is not found, it will be generated automatically
        but if the configuration file is damaged, it will not be overwritten

"""

import json
import os
import dataclasses

from . import utils, exceptions

DATA_PATH_ROOT = "./plugin/data/OlivaChatGPT/"
CONF_README = r"""在 config.json 的配置项对应解释如下：

{
    // 这里填写基本配置
    "basic": {
        // 默认模型的名称（即 models 中的键名）
        "default_model": "MODEL_NAME",

        // 是否输出日志文件
        // 位置为 ./plugin/data/OlivaChatGPT/log/log-{platform}-{user}-{timestamp}.txt
        "log_output": true,

        // 命令前缀 和 命令名称
        // 例如：.gpt start
        "command_prefix": [".", "。", "!", "！"],
        "command_name": "gpt",
    },

    // 这里填写模型配置
    "models": {
        // 模型名称（用于多模型切换的情况下使用）
        "MODEL_NAME": {

            // 具体的 API 服务器地址（可以是 OpenAI 官方 API，也可以是第三方中转站）
            "url": "http://WRITE.URL.BASIC.HERE:PORT/",

            // API 服务器的具体终结点，一般不需要修改
            "endpoint": "v1/chat/completions/",

            // 模型类型 (如 gpt-4-0613, gpt-3.5-turbo)
            "model_type": "gpt-4-0613",

            // API 服务器的 API Key (由对应的 API 服务商提供)
            "api_key": "sk-ThisIsAPIKeyForChatGPTServerAPIOrThirdPartyAPI",

            // HTTP 请求的超时时间 (默认 -1 为无超时)
            "timeout": -1,

            // 在 OlivOS UserConfDB 中存储的权限等级 (默认 `0` 为所有人)
            "auth_level_required": 0,

            // 每个会话的最大上下文长度 (默认 -1 为无限制)
            // 每个来自用户或 API 服务器的消息都将作为一个上下文
            "max_context": -1,
        }
    }
}
"""

DEFAULT_CONFIG = {
    "basic": {
        "default_model": "MODEL_NAME",
        "log_output": True,
        "command_prefix": [".", "。", "!", "！"],
        "command_name": "chat",
    },
    "models": {
        "MODEL_NAME": {
            "url": "http://WRITE.URL.BASIC.HERE:PORT/",                         # the url of the API server
            "endpoint": "v1/chat/completions/",                                 # the endpoint of the API server
            "model_type": "gpt-4-0613",                                         # the model type (default: gpt-4-0613)
            "api_key": "sk-ThisIsAPIKeyForChatGPTServerAPIOrThirdPartyAPI",     # the API key for the API server (OpenAI or Others)
            "timeout": -1,                                                      # the timeout for HTTP request (default: -1 for no timeout)
            "auth_level_required": 0,       # auth level stored in OlivOS UserConfDB (default `0` for everyone)
                                            # namespace: "unity"
                                            # key: "auth_level"
            "max_context": -1,              # the max context length (default: -1 for no limit)
                                            # each message from either the user or the API server will be a context
            "stream": False
        }
    }
}


@dataclasses.dataclass
class ConfigBasic:
    default_model: str
    log_output: bool
    command_prefix: list
    command_name: str

@dataclasses.dataclass()
class ConfigModel:
    model_name: str
    url: str
    endpoint: str
    model_type: str
    api_key: str
    timeout: int
    auth_level_required: int
    max_context: int
    stream: bool

class Config:
    def __init__(self, dict_config: dict):
        basic= ConfigBasic(**dict_config["basic"])
        models = {}
        for key, value in dict_config["models"].items():
            tmp_conf_this = DEFAULT_CONFIG["models"]["MODEL_NAME"].copy()
            tmp_conf_this.update(value)
            models[key] = ConfigModel(model_name=key, **tmp_conf_this)
        self.basic: ConfigBasic = basic
        self.models: dict[str, ConfigModel] = models

gConf = None

def get_config(path_root: str = DATA_PATH_ROOT):
    global gConf
    if gConf is not None:
        return gConf
    path = os.path.join(path_root, "config.json")

    if not os.path.exists(path):
        write_config(path)
        utils.gLogProc.warn(f"配置文件不存在，已自动生成：{path}")
        utils.gLogProc.warn(f"请修改配置文件后重启插件：{path}")
        utils.gLogProc.warn(f"配置文件的详细说明详见：{path_root}/README.md")
        raise exceptions.OlivaChatGPTConfigInvalidError(path)
    try:
        with open(path, "rb") as f:
            conf_dict = json.load(f)
            gConf = Config(conf_dict)
            return gConf
    except json.JSONDecodeError as err:
        utils.gLogProc.error(f"配置文件无法解析：{err}")
        utils.gLogProc.error(f"请检查配置文件：{path}")
        utils.gLogProc.error(f"配置文件的详细说明详见：{path_root}/README.md")
        raise exceptions.OlivaChatGPTConfigInvalidError(path)

def write_readme(path_root: str|None=None):
    if path_root is None:
        path_root = os.path.join(DATA_PATH_ROOT, "README.md")
    os.makedirs(os.path.dirname(path_root), exist_ok=True)
    with open(path_root, "w", encoding="utf-8") as f:
        f.write(CONF_README)

def write_config(path_root: str|None = None):
    if path_root is None:
        path_root = os.path.join(DATA_PATH_ROOT, "config.json")
    os.makedirs(os.path.dirname(path_root), exist_ok=True)
    with open(path_root, "w", encoding="utf-8") as f:
        json.dump(DEFAULT_CONFIG, f, indent=4, ensure_ascii=False)

# def get_default_model_type(path_root: str = DATA_PATH_ROOT):
#     """
#         获取默认模型的类型: gpt-4-0613
#     """
#     config = get_config(path_root)
#     name = config.basic.default_model
#     return config.models[name].model_type

def get_model_type(model_name: str|None = None, path_root: str = DATA_PATH_ROOT):
    """
        获取模型的类型: gpt-4-0613
    """
    config = get_config(path_root)
    if model_name is None:
        model_name = config.basic.default_model
    return config.models[model_name].model_type

def get_model_config(model_name: str|None = None, path_root: str = DATA_PATH_ROOT):
    config = get_config(path_root)
    if model_name is None:
        model_name = config.basic.default_model
    return config.models[model_name]

from .. import utils

FLAG_TIKTOKEN_INSTALLED = False
try:

    import tiktoken as _tiktoken
    FLAG_TIKTOKEN_INSTALLED = True
except ImportError:
    _tiktoken = None
    FLAG_TIKTOKEN_INSTALLED = False

_warn_once = []                         # 对于未知模型，只警告一次

def get_tiktoken():
    """返回 tiktoken 模块，如果未安装则返回 None 并打印警告。"""
    global _warn_once
    if FLAG_TIKTOKEN_INSTALLED:
        return _tiktoken
    else:
        if "tiktoken-not-installed" not in _warn_once:
            _warn_once.append("tiktoken-not-installed")
            log = utils.get_logger()
            log.warn("""第三方库 tiktoken 未安装，无法使用部分功能。请在源码状态下运行 OlivOS 并使用 "pip install tiktoken" 进行安装。""")
        return None

def get_token_from_string(message: str, model="gpt-3.5-turbo-0613") -> "int|None":
    """
        计算单条消息的 token 数量，如果未安装 tiktoken 模块则返回 None。
        需要使用 tiktoken 模块
    """
    global _warn_once
    tiktoken = get_tiktoken()
    log = utils.get_logger()
    if tiktoken is None:
        return None
    try:
        encoding = tiktoken.encoding_for_model(model)
    except KeyError:
        if model not in _warn_once:
            log.warn(f"未知模型 {model}，无法计算 token 数量")
            _warn_once.append(model)
        # encoding = tiktoken.get_encoding("cl100k_base")
        return None
    token = 0
    token += len(encoding.encode(message, disallowed_special=()))
    return token
    

def get_token_from_message_list(messages, model="gpt-3.5-turbo-0613") -> "int|None":
    """
        计算消息列表的 token 数量，如果未安装 tiktoken 模块则返回 None。
        需要使用 tiktoken 模块
        修改自: https://github.com/openai/openai-cookbook/blob/main/examples/How_to_count_tokens_with_tiktoken.ipynb
    """
    global _warn_once
    tiktoken = get_tiktoken()
    log = utils.get_logger()
    if tiktoken is None:
        return None
    try:
        encoding = tiktoken.encoding_for_model(model)
    except KeyError:
        if model not in _warn_once:
            log.warn(f"未知模型 {model}，无法计算 token 数量")
            _warn_once.append(model)
        # encoding = tiktoken.get_encoding("cl100k_base")
        return None
    if model in {
        "gpt-3.5-turbo-0613",
        "gpt-3.5-turbo-16k-0613",
        "gpt-4-0314",
        "gpt-4-32k-0314",
        "gpt-4-0613",
        "gpt-4-32k-0613",
        }:
        tokens_per_message = 3
        tokens_per_name = 1
    elif model == "gpt-3.5-turbo-0301":
        tokens_per_message = 4  # every message follows <|start|>{role/name}\n{content}<|end|>\n
        tokens_per_name = -1  # if there's a name, the role is omitted
    elif "gpt-3.5-turbo" in model:
        if model not in _warn_once:
            _warn_once.append(model)
            log.warn(f"gpt-3.5-turbo 会随时间更新，返回的 token 数量基于 gpt-3.5-turbo-0613 计算")
        return get_token_from_message_list(messages, model="gpt-3.5-turbo-0613")
    elif "gpt-4" in model:
        if model not in _warn_once:
            _warn_once.append(model)
            log.warn(f"gpt-4 会随时间更新，返回的 token 数量基于 gpt-4-0613 计算")
        return get_token_from_message_list(messages, model="gpt-4-0613")
    else:
        raise NotImplementedError(
            f"""num_tokens_from_messages() is not implemented for model {model}. See https://github.com/openai/openai-python/blob/main/chatml.md for information on how messages are converted to tokens."""
        )
    num_tokens = 0
    if isinstance(messages, dict):
        messages = [messages]
    for message in messages:
        num_tokens += tokens_per_message
        for key, value in message.items():
            num_tokens += len(encoding.encode(value))
            if key == "name":
                num_tokens += tokens_per_name
    num_tokens += 3  # every reply is primed with <|start|>assistant<|message|>
    return num_tokens


if __name__ == "__main__":
    example_messages = [
        {
            "role": "system",
            "content": "You are a helpful, pattern-following assistant that translates corporate jargon into plain English.",
        },
        {
            "role": "system",
            "name": "example_user",
            "content": "New synergies will help drive top-line growth.",
        },
        {
            "role": "system",
            "name": "example_assistant",
            "content": "Things working well together will increase revenue.",
        },
        {
            "role": "system",
            "name": "example_user",
            "content": "Let's circle back when we have more bandwidth to touch base on opportunities for increased leverage.",
        },
        {
            "role": "system",
            "name": "example_assistant",
            "content": "Let's talk later when we're less busy about how to do better.",
        },
        {
            "role": "user",
            "content": "This late pivot means we don't have time to boil the ocean for the client deliverable.",
        },
    ]

    for model in [
        "gpt-3.5-turbo-0301",
        "gpt-3.5-turbo-0613",
        "gpt-3.5-turbo",
        "gpt-4-0314",
        "gpt-4-0613",
        "gpt-4",
        ]:
        print(model)
        # example token count from the function defined above
        print(f"{get_token_from_message_list(example_messages, model)} prompt tokens counted by num_tokens_from_messages().")

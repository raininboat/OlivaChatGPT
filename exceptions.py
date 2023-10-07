
class OlivaChatGPTError(Exception):
    """
        the base exception for the plugin
    """
    pass

class OlivOSVersionError(OlivaChatGPTError):
    """
        the exception for the OlivOS version
    """
    def __init__(self, version, msg: str = ""):
        if msg == "":
            import OlivOS
            msg = f"此功能需要更新 OlivOS 版本。当前版本SVN {OlivOS.infoAPI.OlivOS_SVN}，需求版本SVN {version}"
        super().__init__(msg)

class OlivaChatGPTConfigError(OlivaChatGPTError):
    """
        the exception for the plugin config
    """
    pass

class OlivaChatGPTConfigInvalidError(OlivaChatGPTConfigError):
    """
        the exception for the plugin config invalid
    """
    def __init__(self, path: str, msg: str = ""):
        if msg == "":
            msg = f"配置文件 {path} 无法解析"
        super().__init__(msg)

class OlivaChatGPTRuntimeError(OlivaChatGPTError):
    """
        the exception for the plugin runtime
    """
    pass

class OlivaChatGPTDatabseError(OlivaChatGPTRuntimeError):
    """
        the exception for the plugin database
    """
    pass

class OlivaChatGPTHTTPError(OlivaChatGPTRuntimeError):
    """
        the exception for the plugin HTTP request
    """
    pass


class OlivaChatGPTHTTPTimeoutError(OlivaChatGPTHTTPError):
    """
        the exception for the plugin HTTP request timeout
    """
    pass
    def __init__(self, data=None) -> None:
        self.data = data
        super().__init__("HTTP 请求超时")

class OlivaChatGPTHTTPCodeError(OlivaChatGPTHTTPError):
    """
        the exception for HTTP code
    """
    def __init__(self, code: int, content=None, msg: str = ""):
        if msg == "":
            msg = f"HTTP 请求返回了错误的状态码: {code}"
        self.code = code
        self.msg = msg
        self.content = content
        super().__init__(msg)

class OlivaChatGPTHTTPResponseInvalidError(OlivaChatGPTHTTPError):
    """
        the exception for the plugin HTTP response invalid
    """
    def __init__(self, data, msg: str = ""):
        if msg == "":
            msg = f"HTTP 请求返回了无法解析的数据: {data}"
        self.data = data
        self.msg = msg
        super().__init__(msg)

class OlivaChatGPTHookError(OlivaChatGPTRuntimeError):
    """
        the exception for the plugin hook
    """
    pass

class OlivaChatGPTAuditError(OlivaChatGPTHookError):
    """
        the exception for the plugin audit
    """
    pass

class OlivaChatGPTAuditAuthLevelError(OlivaChatGPTAuditError):
    """
        the exception for the plugin audit auth level
    """
    def __init__(self, required, current, msg: str = ""):
        if msg == "":
            msg = f"用户权限不足，需要权限 {required}，当前权限 {current}"
        self.msg = msg
        self.required = required
        self.current = current
        super().__init__(msg)

class OlivaChatGPTSessionNotFoundError(OlivaChatGPTAuditError):
    """
        the exception for the plugin audit session
    """
    def __init__(self, session_id, name, msg: str = ""):
        if msg == "":
            msg = f"会话不存在：{name} - {session_id}"
        self.msg = msg
        self.session_id = session_id
        self.name = name
        super().__init__(msg)

class OlivaChatGPTSessionNotActiveError(OlivaChatGPTAuditError):
    """
        the exception for the plugin audit session
    """
    def __init__(self, msg: str = ""):
        if msg == "":
            msg = f"会话未激活"
        self.msg = msg
        super().__init__(msg)

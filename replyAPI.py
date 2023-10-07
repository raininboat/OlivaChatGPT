
import time
import textwrap
import os

from enum import Enum
from tempfile import NamedTemporaryFile
from typing import Any

import OlivOS.messageAPI as _OlvMsgAPI
from PIL import Image as _PILImage, ImageDraw as _PILImageDraw, ImageFont as _PILImageFont

from OlivaChatGPT import utils, databaseAPI

class PIC_CONFIG:
    """
        the font config for the image message
    """

    FONT_PATH = os.path.abspath("./plugin/data/OlivaChatGPT/data/font/SourceHanSansCN-Regular.otf")
    FONT_STZE = 20
    FONT_SPACING = 4
    MARGIN = 10
    WIDTH = 40
    IMAGE_WIDTH = MARGIN * 2 + WIDTH * FONT_STZE
class _BaseMessage:
    """
        the base class for all the message types
    """
    _template: Any = None
    def to_message(self) -> _OlvMsgAPI.Message_templet:
        raise NotImplementedError

    def __str__(self) -> str:
        raise NotImplementedError


class _baseReply:
    """
        the base class for all the reply types
    """
    class default:
        def __init__(self) -> None:
            # print("init")
            raise NotImplementedError
    def __new__(cls, *args, **kwargs):
        if hasattr(cls, "__init__"):
            return super().__new__(cls)
        elif hasattr(cls, "default"):
            return cls.default(*args, **kwargs)
        else:
            raise NotImplementedError

    @classmethod
    def get_child(cls, name: str) -> Any:
        if hasattr(cls, name):
            return getattr(cls, name)
        else:
            return cls.default


class _Message:
    class SingleTextMessage(_BaseMessage):
        """
            the text message
        """
        def __init__(self, text: str|None=None, data: dict[str, Any]| None = None):
            if data is None:
                data = {}
            if text is not None:
                self._template = text
            self.data = data
        
        def add_data(self, data: dict[str, Any]) -> None:
            self.data.update(data)

        def to_message(self) -> _OlvMsgAPI.Message_templet:
            text_send = self._template.format_map(self.data)
            message_node = _OlvMsgAPI.PARA.text(text_send)
            message_obj = _OlvMsgAPI.Message_templet("olivos_para", [message_node])
            return message_obj

        def __str__(self) -> str:
            return self._template
    
    class TextImageMessage(_BaseMessage):
        """
            the multi-text message
            if the message is too long, it will be wriiten to a file and send as an image
        """
        _MAX_LENGTH = 8000

        def __init__(self, text_list: list[str]| None = None, data: dict[str, Any]| None = None):
            if data is None:
                data = {}
                
            if text_list is not None:
                self.text_list = text_list
            else:
                self.text_list = self._template.copy()
            self.data = data
            self.cache = {}
        
        def add_data(self, data: dict[str, Any]) -> None:
            self.data.update(data)

        def append(self, text: str) -> None:
            self.text_list.append(text)

        def generate_image(self, text: str, file_path: str|None = None):
            """
                generate an image from the text
                return the binary data of the image
                if file_path is None, the file will be deleted after it is closed
            """
            log = utils.get_logger()
            log.debug(f"文本内容转图片：\n{text}")
            text_list = textwrap.wrap(text, width=PIC_CONFIG.WIDTH)
            image_height = max(PIC_CONFIG.MARGIN * 2 + len(text_list) * (PIC_CONFIG.FONT_STZE + PIC_CONFIG.FONT_SPACING), 800)
            text_print = "\n".join(text_list)

            image = _PILImage.new(
                "RGB", (image_height, PIC_CONFIG.IMAGE_WIDTH), (255, 255, 255)
            )
            draw = _PILImageDraw.Draw(image)
            print(PIC_CONFIG.FONT_PATH)
            font = _PILImageFont.truetype(PIC_CONFIG.FONT_PATH, PIC_CONFIG.FONT_STZE)
            draw.text((PIC_CONFIG.MARGIN, PIC_CONFIG.MARGIN), text_print, font=font, fill=(0, 0, 0))
            if file_path is None:
                temp_file = NamedTemporaryFile(suffix=".png", delete=False)
            else:
                temp_file = open(file_path, "w+b")
            image.save(temp_file, "PNG")
            return temp_file

        def to_message(self) -> _OlvMsgAPI.Message_templet:
            send_list = []
            for msg_template in self._template:
                msg_this = msg_template.format(**self.data)
                if self._MAX_LENGTH > 0 and len(msg_this) > self._MAX_LENGTH:
                    img_obj = self.generate_image(msg_this)
                    self.cache[img_obj.name] = img_obj
                    send_list.append(_OlvMsgAPI.PARA.image(f"file:///{img_obj.name}"))
                else:
                    send_list.append(_OlvMsgAPI.PARA.text(msg_this))
            message_obj = _OlvMsgAPI.Message_templet("olivos_para", send_list)
            return message_obj

        def __str__(self) -> str:
            return "\n".join(self._template)

        def close(self):
            for i in self.cache.values():
                if hasattr(i, "close"):
                    i.close()
        
        def __del__(self):
            self.close()

    class ImageMessage(_BaseMessage):
        """
            the image message
        """
        def __init__(self, image_path):
            self.path = image_path

        def to_message(self) -> _OlvMsgAPI.Message_templet:
            message_node = _OlvMsgAPI.PARA.image(self.path)
            message_obj = _OlvMsgAPI.Message_templet("olivos_para", [message_node])
            return message_obj

        def __str__(self) -> str:
            return self.path



class Reply(_baseReply):
    class help(_baseReply):
        class default(_Message.SingleTextMessage):
            """
                the default help message
            """
            _template = """\
OlivaChatGPT help:
.chat help (<command>): 获取某个指令的帮助信息
.chat new (-n, -m, -h): 初始化一个新的聊天会话
.chat start (<name>| -s <session>) 恢复一个会话
.chat stop: 停止当前聊天会话，并将会话数据输出到文件
.chat show: show all the sessions
.chat switch <session id>: 切换到另一个会话
.chat recall: 撤回当前会话中最后一轮的对话

.chat <xxx>: 向API服务器发送消息
.chat send <xxx>: 同上，用于发送含有指令前缀的消息

.chat config: 查看当前配置
"""
        class command(_baseReply):
            class default(_Message.SingleTextMessage):
                _template = """\
chat command <{command}> not found
"""
            class new(_Message.SingleTextMessage):
                _template = """\
初始化一个新的聊天会话，如果指定了模型，则使用指定的模型，否则使用默认模型
指令格式：
.chat new (<model>)
model: 模型名称，可选
当前默认模型为：
{default_model_name}
具体模型名称如下(名称 - 类别)：
{model_dict}
"""
                def format_model_list(self, model_dict: str|dict) -> str:
                    """
                        format model dict to string for the help message
                    """
                    if isinstance(model_dict, str):
                        return model_dict
                    else:
                        model_list = []
                        for key, value in model_dict.items():
                            model_list.append("{} - {}".format(key, value))
                        return "\n".join(model_list)

                def to_message(self) -> _OlvMsgAPI.Message_templet:
                    self.data["model_dict"] = self.format_model_list(self.data["model_dict"])
                    return super().to_message()

    class new(_baseReply):
        class success(_Message.SingleTextMessage):
            _template = """\
初始化聊天会话成功 √
会话名称: {session_name}
当前使用模型: {model_name}
"""
        class fail(_Message.SingleTextMessage):
            _template = """\
初始化新的聊天会话失败 X
会话名称: {session_name}
当前使用模型: {model_name}
失败原因: 
{reason}
"""

    class start(_baseReply):
        class success(_Message.SingleTextMessage):
            _template = """\
已恢复聊天上下文 √
上下文名称: {session_name}
当前使用模型: {model}
"""
        class fail(_Message.SingleTextMessage):
            _template = """\
恢复聊天上下文失败 X
上下文名称: {session_name}
当前使用模型: {model}
失败原因: {reason}
"""
    class stop(_baseReply):
        class success(_Message.SingleTextMessage):
            _template = """\
已停止聊天会话 √
会话名称: {session_name}

会话数据已保存到文件: {file_path}
"""

    class send(_baseReply):
        class success(_Message.SingleTextMessage):
            _template = """\
已发送消息，等待回复中 √
"""
        class fail(_Message.SingleTextMessage):
            _template = """\
发送消息失败 X
失败原因:
{reason}
"""
        class response(_Message.TextImageMessage):
            _template = [
"""\
ChatGPT 回复消息:
""",
"""\
{reply_message}
""",
"""
消耗时间: {time:.2f} s
消耗token数: {token_num}
"""
            ]
            def __init__(self, data: dict[str, Any]| None = None):
                super().__init__(data=data)
                self.time_start = time.time()
                self.data["token_num"] = "N/A"

            def add_data(self, data: dict[str, Any]) -> None:
                super().add_data(data)
            
            def to_message(self) -> _OlvMsgAPI.Message_templet:
                self.data["time"] = time.time() - self.time_start
                return super().to_message()


    class show(_baseReply):
        class default(_Message.SingleTextMessage):
            _template = """\
当前会话如下：
{session_active}

用户会话列表:
{session_list}
"""
            _template_session = "   {sessoin_index}. {session_name}: {model_name}"

            def format_active_session(self, session_active: "databaseAPI.MasterTable") -> str:
                """
                    format active session to string for the help message
                """
                fmt_this = f"""\
    会话名称: {session_active.session_name}
    模型名称: {session_active.model_name}
    会话ID: {session_active.session_id}
    创建时间: {session_active.time_create_time}
    最后使用时间: {session_active.time_last_update}"""
                self.data["session_active"] = fmt_this
                return self.data["session_active"]

            def format_session_list(self, session_list) -> str:
                """
                    format session list to string for the help message
                """
                session_list_fmt = []
                for idx, sess in enumerate(session_list, 1):
                    session_list_fmt.append(self._template_session.format(**sess, **self.data, sessoin_index=idx))
                self.data["session_list"] = "\n".join(session_list_fmt)
                return self.data["session_list"]

        
        class empty(_Message.SingleTextMessage):
            _template = "尚未初始化任何会话，请使用 .chat new 初始化一个新的会话"

    class export(_baseReply):
        class success(_Message.SingleTextMessage):
            _template = """\
已导出会话数据 √
会话名称: {session_name}
文件路径: {file_path}
"""
        class fail(_Message.SingleTextMessage):
            _template = """\
导出会话数据失败 X
会话名称: {session_name}
失败原因: {reason}
"""
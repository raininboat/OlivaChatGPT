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
"""
import io
try:
    FLAG_DOCX = True
    from docx import Document
except ImportError:
    FLAG_DOCX = False

from . import databaseAPI, utils, confAPI

_LOG_TEMPLATE = {
    "txt": """
{role} ({status}) {time}
{message}
"""
}

class LogExport:
    """
        the log export class, init with the message list
    """
    def __init__(self, message_list: list[databaseAPI.SessionTable]) -> None:
        self.message_list = message_list
        self.log = utils.get_logger()
        self.file_data = {}             # all the file objects, key is type "txt" or "docx"

    def _write_line_txt(self, line_data: databaseAPI.SessionTable) -> None:
        """
            write a line to the file
        """
        fmt_string = _LOG_TEMPLATE["txt"].format(
            role=line_data.role,
            status=line_data.status,
            time=line_data.time_record,
            message=line_data.message
        )
        file = self.file_data["txt"]
        file.write(fmt_string)

    def _write_line_docx(self, file, line_data: databaseAPI.SessionTable) -> None:
        """
            write a line to the file
        """
        if not FLAG_DOCX:
            self.log.error("python-docx 库未安装，无法导出docx文件")
            raise ImportError("docx module not found")
        file = self.file_data["docx"]
        raise NotImplementedError
    
    def _init_txt(self, file_name) -> None:
        """
            init the txt file
        """
        self.file_data["txt"] = open(file_name, "w", encoding="utf-8")
    
    def _init_docx(self, file_name):
        """
            init the docx file
        """
        if not FLAG_DOCX:
            self.log.error("python-docx 库未安装，无法导出docx文件")
            raise ImportError("docx module not found")
        
        docx = Document(file_name)
        self.file_data["docx"] = docx
        docx

    def _done_txt(self) -> None:
        """
            close the txt file
        """
        self.file_data["txt"].close()
    
    def _done_docx(self) -> None:
        """
            close the docx file
        """
        if not FLAG_DOCX:
            self.log.error("python-docx 库未安装，无法导出docx文件")
            raise ImportError("docx module not found")
        self.file_data["docx"].save(file_name)

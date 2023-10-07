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
        this is the database API of the plugin

        every time an user send a message / a message is sent to the user, the log handler will be called
        the log handler will record the message and the user's id, 
        and save into different tables in the database according to the session id

        the session id is computed by the user's id and the time when the user send the message
        when a session is over, the log handler will save the session id and the log table into a file

"""

import sqlite3
import threading
import os
import hashlib
import traceback
import gc
import pickle
import uuid
import json
import dataclasses

try:
    import OlivOS
    from . import NAMESPACE
except ImportError:
    NAMESPACE = "OlivaChatGPT"

from typing import List, Dict, Tuple, Union, Callable, Sequence, Any, Literal
from concurrent.futures import ThreadPoolExecutor as PoolExecutor

from . import utils, confAPI, exceptions

DATABASE_SVN = 1
DATABASE_PATH = os.path.join(".","plugin","data", "OlivaChatGPT","dataAll.db")
class _StatusCodeBase:
    _code = None
    _role = ["unknown", "system", "user", "assistant"]
    def __init__(self, message: str = "", code: int | None = None):
        if code is None:
            code = self._code
        self.code = code
        self.message = message

    def __str__(self):
        return f"{self.code} {self.message}"
    
    def __eq__(self, __value: object) -> bool:
        if isinstance(__value, _StatusCodeBase):
            return self.code == __value.code
        else:
            return False
    
    def __hash__(self):
        return hash(self.code)
    
    def __int__(self):
        return self.code
    
    def __repr__(self):
        return f"<StatusCode: {self.code} {self.message}>"

    @property
    def role(self):
        if self.code is None:
            return self._role[0]
        role = self._role[self.code % 10]
        return role

class _HttpStatusCodeBase(_StatusCodeBase):
    _code = 50000
    """
        Remote error
    """
    def __init__(self, http_code: int, message: str = ""):
        """
            http_code: http status code
            message: error message (request body)
        """
        code = self._code + http_code
        super().__init__(message, code)

class StatusCode:
    class Normal(_StatusCodeBase):
        _code = 10000
        def __init__(self, message: str, code: int):
            super().__init__(message, code)

        class System(_StatusCodeBase):
            _code = 10001
            """
                Message send by the system
            """
        
        class User(_StatusCodeBase):
            _code = 10002
            """
                Message send by the user
            """

        class Assistant(_StatusCodeBase):
            _code = 10003
            """
                Message send by the assistant
            """
    
    class Processed(_StatusCodeBase):
        _code = 30000
        """
            Message has been processed
        """

        class Recall(_StatusCodeBase):
            _code = 30010
            """
                Message has been recalled
            """
            class System(_StatusCodeBase):
                _code = 30011
                """
                    Message send by the system
                """
            
            class User(_StatusCodeBase):
                _code = 30012
                """
                    Message send by the user
                """

            class Assistant(_StatusCodeBase):
                _code = 30013
                """
                    Message send by the assistant
                """

    class RemoteError(_HttpStatusCodeBase):
        _code = 50000
        """
            Remote error
        """
        def __init__(self, http_code: int, message: str = ""):
            """
                http_code: http status code
                message: error message (request body)
            """
            code = self._code + http_code
            super().__init__(code, message)
        
        class HttpNotOK(_HttpStatusCodeBase):
            _code = 51000
            """
                Remote error, http status code is not 200
            """
        
        class HttpOK(_HttpStatusCodeBase):
            _code = 52000
            """
                Remote error, when http status code is 200, but the content is not valid

                e.g. when the remote server returns 200 OK, but the content is not a valid json
            """
            def __init__(self, message: str = ""):
                super().__init__(200, message)


    class LocalError(_StatusCodeBase):
        _code = 60000
        """
            Local error
        """

class _SqlScriptBase:
    data_class = None
    def __init__(self, sql: str = "", format: "None | Dict[str, str]"=None, param: "None | Dict[str, Any]"=None, *_, need_return=False, **__):
        self.sql = sql
        self.sql_this = self.sql
        self.format = format
        self.param = param
        self.need_return = need_return
        if format is not None:
            self.sql_this = self.sql.format(**format)

    def __str__(self):
        return str((self.sql_this, self.param))
    
    def __eq__(self, __value: object) -> bool:
        if not isinstance(__value, _SqlScriptBase):
            return False
        return str(self) == str(__value)

    def __hash__(self):
        return hash(str((self.sql_this, self.param)))
    
    def get(self):
        if self.param is None:
            return (self.sql_this, ())
        else:
            return (self.sql_this, self.param)
@dataclasses.dataclass
class _TableDataBase:
    """
    基于 sqlite3.Row 的数据封装，将查询结果的每一个 namedtuple 封装成一个类
    """
    @classmethod
    def init_by_row(cls, data: sqlite3.Row):
        obj = cls(**dict(data))
        return obj
    
    def to_dict(self):
        return dataclasses.asdict(self)


@dataclasses.dataclass
class MasterTable(_TableDataBase):
    session_name: str
    session_id: str
    hash_user_id: str
    model_name: str
    time_create_time: str | None  = None
    time_last_update: str | None  = None

    @property
    def session_model(self):
        return SessionModel(self.session_id, self.model_name, self.session_name)

@dataclasses.dataclass
class SessionTable(_TableDataBase):
    logline: int
    role: str
    message: str
    time_record: str | None  = None
    status: int = 0

@dataclasses.dataclass(frozen=True)
class SessionModel:
    session_id: str
    model: str
    session_name: str
    @property
    def model_name(self):
        return self.model

class SqlAll:
    class CREATE:
        """
        创建数据库的 sql 指令
        """
        class TABLE:
            class MASTER(_SqlScriptBase):
                """
                    创建一个日志总表，记录所有保存日志的表信息
                    session_name 为用户自定义的会话名称，用于显示
                    session_id 为表名，通过 uuid 生成
                    hash_user_id 为用户的 id，基于用户 uid 和 平台 platform 基于 sha1 计算
                    model_name 为模型名称
                    time_create_time 为表创建时间，自动记录
                    time_last_update 为表最后更新时间，自动记录
                """
                def __init__(self, *args, **kwargs):
                    self.sql ="""\
                        CREATE TABLE IF NOT EXISTS table_master(
                            session_name              TEXT,
                            session_id                TEXT      PRIMARY KEY,
                            hash_user_id              TEXT,
                            model_name                TEXT,
                            time_create_time          DATETIME  DEFAULT CURRENT_TIMESTAMP, 
                            time_last_update          DATETIME  DEFAULT CURRENT_TIMESTAMP
                            );
                        """
                    super().__init__(self.sql, *args, **kwargs)

            class SESSION(_SqlScriptBase):
                """
                    创建单个 session 的日志表，用来存储某一次会话的日志内容
                    logline 为日志行号，自增
                    role 为日志角色，分为 user 和 assistant
                    message 为日志内容（消息或错误信息）
                    time_record 为日志记录时间，自动记录
                    status 为日志状态
                    
                        状态码:
                        00000   未设置

                        10xxx   正常消息
                          000   默认正常消息（未设置）
                          001   来自系统本地的消息 (role = system)
                          002   来自用户的消息 (role = user)
                          003   来自远端服务器的消息 (role = assistant)
                         1003   在 Stream Mode 下，如果远端返回时间超过 120 秒，设置为这个状态码

                        30xxx   本地被处理过的消息记录（这些消息不会作为上下文传输）
                          000   默认被处理过的消息（未设置）

                          010   被回溯（撤回）的消息 (默认)
                          011   被回溯（撤回）的消息 (role = system)
                          012   被回溯（撤回）的消息 (role = user)
                          013   被回溯（撤回）的消息 (role = assistant)

                          100   由于错误被忽略的消息 (默认)
                          101   由于错误被忽略的消息 (role = system)
                          102   由于错误被忽略的消息 (role = user)
                          103   由于错误被忽略的消息 (role = assistant)

                        50xxx   远端错误消息（后三位为 Http 状态码）
                         1xxx   http 非 200 OK 时，此处后三位即为 http 状态码
                         2200   如果远端返回 200 OK 但是内容不合法，统一设置为这个状态码

                        60xxx   本地错误消息
                          000   默认错误
                """
                def __init__(self, session_id: str, *args, **kwargs):
                    self.sql ="""\
                        CREATE TABLE IF NOT EXISTS table_log_{session_id}(
                            logline                   INTEGER   PRIMARY KEY AUTOINCREMENT,
                            role                      TEXT,
                            message                   TEXT,
                            time_record               DATETIME  DEFAULT CURRENT_TIMESTAMP,
                            status                    INTEGER   DEFAULT 0
                            );
                        """
                    format = {"session_id": session_id}
                    super().__init__(self.sql, format=format, *args, **kwargs)

        class TRIGGER:
            class SESSION(_SqlScriptBase):
                """
                    创建一个触发器，当某个 session 的日志表被更新时，更新总表的最后更新时间
                """
                def __init__(self, session_id: str, *args, **kwargs):
                    self.sql ="""\
                        CREATE TRIGGER IF NOT EXISTS trigger_{session_id}
                        BEFORE INSERT ON table_log_{session_id}
                        FOR EACH ROW
                        BEGIN
                            UPDATE OR IGNORE table_master
                            SET time_last_update = CURRENT_TIMESTAMP
                            WHERE session_id = "{session_id}";
                        END;
                        """
                    format = {"session_id": session_id}
                    super().__init__(self.sql, format=format, *args, **kwargs)

    class UPDATE:
        class MESSAGE(_SqlScriptBase):
            """
                更新日志的信息
                session_id 为表名，通过 uuid 生成
                linenum 为日志行号，为负数时表示从最后一行开始计数
                role 为日志角色，分为 user 和 assistant
                message 为日志内容
                status 为日志状态
            """
            def __init__(self, session_id: str, linenum: int, role: str|None=None, message: str|None=None, status: int|None=None, line_status_max=None,*args, **kwargs):
                if role is None and message is None and status is None:
                    raise exceptions.OlivaChatGPTDatabseError("No update information")
                self.sql ="""\
                    UPDATE table_log_{session_id}
                    SET {set_str}
                    WHERE {where_str};
                    """
                param = {"linenum": linenum, "role": role, "message": message, "status": status}
                set_str = ", ".join([f"{k} = :{k}" for k in ["role", "message", "status"] if param.get(k, None) is not None])
                
                if linenum >= 0:
                    where_str = "logline = :linenum"
                else:
                    if line_status_max is None:
                        where_str = f"logline = (SELECT MAX(logline) FROM table_log_{session_id}) + :linenum + 1"
                    else:
                        where_str = f"logline = (SELECT MAX(logline) FROM table_log_{session_id} WHERE status < {line_status_max}) + :linenum + 1"
                format = {"session_id": session_id, "set_str": set_str, "where_str": where_str}
                super().__init__(self.sql, format=format, param=param, *args, **kwargs)

    class INSERT:
        class SESSION(_SqlScriptBase):
            """
                插入一条 session 信息，如果 session 已存在则替换
                session_name 为用户自定义的会话名称，用于显示
                session_id 为表名，通过 uuid 生成
                hash_user_id 为用户的 id，基于用户 uid 和 平台 platform 基于 sha1 计算
                model_name 为模型名称
            """
            def __init__(self, session_name: str, session_id: str, hash_user_id: str, model_name:str, *args, **kwargs):
                self.sql ="""\
                    INSERT OR REPLACE INTO table_master(
                        "session_name", "session_id", "hash_user_id", "model_name"
                    )
                    VALUES (:session_name, :session_id, :hash_user_id, :model_name);
                    """
                param = {"session_id": session_id, "hash_user_id": hash_user_id, "model_name": model_name, "session_name": session_name}
                super().__init__(self.sql, param=param, *args, **kwargs)

        class MESSAGE(_SqlScriptBase):
            """
                插入一条日志信息，如果日志已存在则替换
                session_id 为表名，通过 uuid 生成
                role 为日志角色，分为 user 和 assistant
                message 为日志内容
            """
            def __init__(self, session_id: str, role: str, message: str, status: int=10000,*args, **kwargs):
                self.sql ="""\
                    INSERT OR REPLACE INTO table_log_{session_id}(
                        "role", "message", "status"
                    )
                    VALUES (:role, :message, :status);
                    """
                format = {"session_id": session_id}
                param = {"role": role, "message": message, "status": status}
                super().__init__(self.sql, format=format, param=param, *args, **kwargs)

    class DELETE:
        class SESSION(_SqlScriptBase):
            """
                删除 session 信息
                session_id 为表名，通过 uuid 生成
            """
            def __init__(self, session_id: str, *args, **kwargs):
                self.sql ="""\
                    DELETE FROM table_master
                    WHERE session_id = "{session_id}";
                    """
                format = {"session_id": session_id}
                super().__init__(self.sql, format=format, *args, **kwargs)

        class MESSAGE(_SqlScriptBase):
            """
                删除 session 日志表
            """
            def __init__(self, session_id: str, *args, **kwargs):
                self.sql ="""\
                    DROP TABLE IF EXISTS table_log_{session_id};
                    """
                format = {"session_id": session_id}
                super().__init__(self.sql, format=format, *args, **kwargs)

        class TRIGGER(_SqlScriptBase):
            """
                删除 session 触发器
            """
            def __init__(self, session_id: str, *args, **kwargs):
                self.sql ="""\
                    DROP TRIGGER IF EXISTS trigger_{session_id};
                    """
                format = {"session_id": session_id}
                super().__init__(self.sql, format=format, *args, **kwargs)
                
    class SELECT:
        class MASTER(_SqlScriptBase):
            """
                查询某个用户的所有 session 信息
                hash_user_id 为用户的 id，基于用户 uid 和 平台 platform 基于 sha1 计算
            """
            data_class = MasterTable
            def __init__(self, hash_user_id: str, *, need_return=True, **kwargs):
                self.sql ="""\
                    SELECT session_name, session_id, hash_user_id, time_create_time, model_name, time_last_update FROM table_master
                    WHERE hash_user_id = :hash_user_id;
                    """
                param = {"hash_user_id": hash_user_id}
                super().__init__(self.sql, param=param, need_return=need_return, **kwargs)

        class SESSION(_SqlScriptBase):
            """
                查询某个 session 的所有日志信息
                session_id 为表名，通过 uuid 生成
                status_max 为输出日志状态码的最大值
            """
            data_class = SessionTable
            def __init__(self, session_id: str, status_max = 40000, *, need_return=True, **kwargs):
                self.sql ="""\
                    SELECT logline, role, message, status, time_record FROM table_log_{session_id}
                    WHERE status < :status;
                    """
                format = {"session_id": session_id}
                param = {"status": status_max}
                super().__init__(self.sql, format=format, param=param, need_return=need_return, **kwargs)

    class PRAGMA:
        """
            pragma 元数据（数据库自身的版本号）
        """
        class GET:
            class VERSION(_SqlScriptBase):
                """
                获取数据库 user_version 元数据
                """
                def __init__(self, *args, **kwargs):
                    self.sql ="""PRAGMA user_version ;"""
                    super().__init__(self.sql, *args, **kwargs)

        class SET:
            class VERSION(_SqlScriptBase):
                """
                设置数据库 user_version 元数据
                """
                def __init__(self, ver: "int | str", *args, **kwargs):
                    self.sql ="""PRAGMA user_version = {ver} ;"""
                    format = {"ver": str(ver)}
                    super().__init__(self.sql, format=format, *args, **kwargs)

# function
def get_session_id_new(*_, **__):
    """
    生成一个 session id，用于标识一次会话
    """
    return uuid.uuid4().hex

def get_user_hash(platform: "str", user_id: "str|int", *_, **__):
    """
    生成一个用户的哈希值，用于标识一个用户 (基于用户 uid 和 平台 platform 基于 sha1 计算)
    """
    return get_hash("user", platform, str(user_id))

def get_hash(*data):
    """
    生成一个哈希值
    """
    if len(data) == 0 or data[0] == "--NONEED--":
        return "--NONEED--"
    sha1 = hashlib.sha1()
    sha1.update("-".join(map(str, data)).encode("utf-8"))
    return sha1.hexdigest()

class _DataBaseAPI:
    """
    数据库操作的高层次接口，提供了对数据库的基本操作

    本模块基于 OlivOS.userModule.UserConfDB 进行二次开发，自行维护日志数据库和对应连接池    
    默认情况下，数据库连接池中的连接会在插件被卸载时自动关闭，如果需要手动关闭，请调用 stop() 函数

    数据库默认存储在 `plugin/data/OlivaChatGPT/` 目录下，文件名为 `dataAll.db`
    """
    class _sqlscript:
        """
        具体 sql 指令的封装
        """
        def __init__(self, sql: "str", param=None, format=None):
            if format is not None:
                sql = sql.format(**format)
            self.sql = sql
            self.param = param

        def __str__(self):
            return str((self.sql, self.param))

        def get(self):
            if self.param is None:
                return (self.sql, )
            else:
                return (self.sql, self.param)

    class _sqlconn:
        """
        sqlite 上下文管理实现
        
        用于实现 with 语句，自动管理数据库连接
        在退出时自动提交事务，如果发生错误则回滚事务
        """
        def __init__(self, conn: sqlite3.Connection, log=None):
            # print('start')
            self.conn = conn
            self.cur = self.conn.cursor()
            if log is None:
                log = print
            self.log = log

        def __enter__(self):
            return self.cur

        def __exit__(self, exc_type, exc_val, exc_tb):
            if exc_type is not None:
                # 如果sqlite发生错误，打印错误内容并回滚数据库连接
                err_str = traceback.format_exc()
                self.cur.close()
                self.conn.rollback()
                self.log(4, f"OlivaChatGPT DataBaseAPI Error: {err_str}")
                return False
            self.conn.commit()
            self.cur.close()

    def __init__(self, proc_log = None, max_thread: "int | None" = None, timeout: float = 1):
        """
        初始化数据库连接池

        `proc_log`: 日志处理函数，默认为 print
        `max_thread`: 最大线程数，默认为 None，即不限制
        `timeout`: 数据库操作超时时间，默认为 1 秒
        """
        if proc_log is None:
            proc_log = print

        os.makedirs(os.path.dirname(DATABASE_PATH), exist_ok=True)
        self.proc_log = proc_log
        self.timeout = timeout
        self.namespace_list = []
        self._thread_pool = PoolExecutor(max_thread, initializer=self.__init_thread)
        self.__conn_all = {}
        self._init_database()

    def __init_thread(self):
        "线程池中每个线程的初始化过程，进行数据库连接"
        name = threading.current_thread().name
        # 为方便在主线程一并关闭所有连接 check_same_thread 设为 False
        conn= sqlite3.connect(database=DATABASE_PATH, timeout=self.timeout, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        self.__conn_all[name] = conn
        # self.proc_log(0, f"thread init <{name}>")

    def __run_sql_thread(self, script_list: "List[_SqlScriptBase]"):
        "具体的运行函数，传入的是形如 `[_SqlScript, _SqlScript, ]` 的操作指令队列"
        name = threading.current_thread().name
        conn = self.__conn_all[name]
        with self._sqlconn(conn, self.proc_log) as cur:
            res:"Dict[_SqlScriptBase, List[Any]]" = {}
            for data in script_list:
                # self.proc_log(0, str(data))
                cur.execute(*data.get())
                if data.need_return:
                    res[data] = cur.fetchall()
                else:
                    res[data] = []
        return res

    def _init_database(self):
        "对数据库进行总体初始化"
        sql_list = [
            SqlAll.CREATE.TABLE.MASTER(),
            SqlAll.PRAGMA.GET.VERSION(need_return=True),
        ]
        res = self._execmany(sql_list)
        svn: int = res[sql_list[-1]][0][0]

        if svn != DATABASE_SVN:
            if svn == 0:
                # svn 不存在，为新建的sqlite数据库
                self._exec(SqlAll.PRAGMA.SET.VERSION(DATABASE_SVN))
            else:
                self.proc_log(3, "数据库版本不符合，数据库版本为{0}，所需版本为{1}".format(svn, DATABASE_SVN))
                raise exceptions.OlivaChatGPTDatabseError("数据库版本不符合，数据库版本为{0}，所需版本为{1}".format(svn, DATABASE_SVN))
    
    def init_session(self, platform: "str",  user_id: "str| int", session_name: str|None = None, model_name: "str|None"=None, *_, **__) -> SessionModel:
        """
        对一个用户会话进行初始化，创建一个新的 session
        """
        if model_name is None:
            model_name = confAPI.get_model_type()
        session_id = get_session_id_new()
        if session_name is None:
            session_name = session_id
        hash_user_id = get_user_hash(platform, user_id)
        sql_list = [
            SqlAll.CREATE.TABLE.SESSION(session_id),
            SqlAll.CREATE.TRIGGER.SESSION(session_id),
            SqlAll.INSERT.SESSION(session_name, session_id, hash_user_id, model_name),
        ]
        self._execmany(sql_list)
        session_model = SessionModel(session_id, model_name, session_name)
        return session_model

    def save_message(self, session_id: "str|SessionModel", role: "str", message: "str", status: "int"=0,*_, **__):
        """
        保存一条日志信息
        """
        if isinstance(session_id, SessionModel):
            session_id = session_id.session_id
        sql_list = SqlAll.INSERT.MESSAGE(session_id, role, message, status)
        self._exec(sql_list)
        return True
    
    def update_message(self, session_id: "str|SessionModel", linenum: "int", role: "str|None"=None, message: "str|None"=None, status: "int|None"=None, *_, **__):
        """
        更新一条日志信息

            session_id 为表名，通过 uuid 生成
            linenum 为日志行号，为负数时表示从最后一行开始计数
            role 为日志角色
            message 为日志内容
            status 为日志状态
        """
        if isinstance(session_id, SessionModel):
            session_id = session_id.session_id
        sql_list = SqlAll.UPDATE.MESSAGE(session_id, linenum, role, message, status)
        self._exec(sql_list)
        return True
    
    def get_session_list(self, platform: "str",  user_id: "str| int", *_, **__) -> "List[MasterTable]":
        """
        获取一个用户的所有 session 列表
        """
        hash_user_id = get_user_hash(platform, user_id)
        sql_list = SqlAll.SELECT.MASTER(hash_user_id)
        res = self._exec(sql_list)
        data = [MasterTable.init_by_row(i) for i in res]
        return data
    
    def get_session_message(self, session_id: "str|SessionModel", status_max: "int" = 40000, *_, **__) -> "List[SessionTable]":
        """
        获取一个 session 的所有日志信息
        
        输出一个列表, 格式如下:
        [
            {
                "logline": 1,
                "role": "user",
                "message": "你好",
                "time_record": "1970-01-01 00:00:00"
            },
            {
                "logline": 2,
                "role": "assistant",
                "message": "你好",
                "time_record": "1970-01-01 00:00:01"
            },
            ...   
        ]
        """
        if isinstance(session_id, SessionModel):
            session_id = session_id.session_id
        sql_list = SqlAll.SELECT.SESSION(session_id, status_max)
        res = self._exec(sql_list)
        data = [SessionTable.init_by_row(i) for i in res]
        return data
    
    def delete_session(self, session_id: "str|SessionModel", *_, **__):
        """
        删除一个 session
        """
        if isinstance(session_id, SessionModel):
            session_id = session_id.session_id
        sql_list = [
            SqlAll.DELETE.SESSION(session_id),
            SqlAll.DELETE.MESSAGE(session_id),
            SqlAll.DELETE.TRIGGER(session_id),
        ]
        self._execmany(sql_list)
        return True

    def _execmany(self, sql_list: "List[_SqlScriptBase]"):
        """
        低层次接口函数，一次性运行多个 sql 指令
        """
        r = self._thread_pool.submit(self.__run_sql_thread, sql_list)
        return r.result(self.timeout)

    def _exec(self, sql: "_SqlScriptBase"):
        """
        低层次接口函数，直接运行对应的 sql 指令，完成数据库操作
        """
        r = self._thread_pool.submit(self.__run_sql_thread, [sql,])
        return r.result(self.timeout)[sql]

    def stop(self):
        self._thread_pool.shutdown()
        for conn in self.__conn_all.values():
            conn.close()
        self.__conn_all = {}

class DataAPI:
    """
        日志处理类，用于进行日志操作的封装
    """
    def __init__(self, olivos_proc: "OlivOS.pluginAPI.shallow" , max_thread: "int | None" = None, timeout: float = 1):
        """
        初始化日志处理类

        `olivos_proc`: olivos 中的 proc 对象
        `proc_log`: 日志处理函数，默认为 print
        `max_thread`: 最大线程数，默认为 None，即不限制
        `timeout`: 数据库操作超时时间，默认为 1 秒
        """

        global gLogHandler
        if gLogHandler is not None:
            raise exceptions.OlivaChatGPTRuntimeError("logHandler has been initialized")
        gLogHandler = self

        self.proc = olivos_proc
        conf_database = getattr(self.proc, "database", None)
        if conf_database is None or not isinstance(
            conf_database, OlivOS.userModule.UserConfDB.DataBaseAPI
        ):
            raise exceptions.OlivOSVersionError(135)

        self.conf_database = conf_database
        self.log_database = _DataBaseAPI(olivos_proc.log, max_thread, timeout)

    def get_user_session_this(self, platform: "str",  user_id: "str| int", *_, **__) -> "SessionModel | None":
        """
            获取一个用户的当前激活的 session id
            如果当前该用户当前未激活任何会话，则返回 None
        """

        user_session_model:"SessionModel | None" = self.conf_database.get_user_config(      # type: ignore
            namespace=NAMESPACE,                            # type error WILL BE RAISED
            key="pkl_session_model_active",
            platform=platform,
            user_id=user_id,
            default_value=None,
            pkl=True,                                       # we use pickle to store the tuple in sqlite
        )
        return user_session_model

    def init_user_session_this(self, platform: "str",  user_id: "str| int", session_name: str|None = None, model_name: "str|None"=None, *_, **__) -> "SessionModel":
        """
            初始化一个用户的当前激活的 session model
            如果当前该用户当前未激活任何会话，则会自动初始化一个新的 session
        """
        session_model = self.log_database.init_session(platform, user_id, session_name=session_name, model_name=model_name)
        self.set_active_session_model(platform, user_id, session_model=session_model)
        return session_model

    def set_active_session_model(self, platform: "str",  user_id: "str| int", session_model: SessionModel|None, *_, **__) -> None:
        """
            设置一个用户的当前激活的 session model
            请使用 init_user_session_this() 函数进行初始化
        """
        self.conf_database.set_user_config(
            namespace=NAMESPACE,
            key="pkl_session_model_active",
            platform=platform,
            user_id=user_id,
            value=session_model,
            pkl=True,
        )

    def get_user_session(self, platform: "str",  user_id: "str| int", flag_session_model=False, *_, **__) -> "List[MasterTable]|List[SessionModel]":
        """
            获取一个用户的所有 session id
            如果 session_model 为 True，则返回 SessionModel 对象列表，否则返回 MasterTable 对象列表
        """
        master_list= self.log_database.get_session_list(platform, user_id)
        if master_list is None:
            return []
        if flag_session_model:
            session_model_list = [i.session_model for i in master_list]
            return session_model_list
        else:
            return master_list

    def _save_log(self, session_id, role: "str" = "user", message: "str" = "", status: "int" = 0, *_, **__):
        """
            底层操作：保存一条日志信息
        """
        # session_id = self.get_user_session_this(platform, user_id)      # 配置项数据库中自带 cache 功能，不需要再次缓存
        if session_id is None:
            raise exceptions.OlivaChatGPTRuntimeError("session_id is None, please use init_user_session_this() to initialize the session")
        self.log_database.save_message(session_id, role, message, status)
        return True
    
    def save_message(self, session_id, message: "str", role: Literal["unknown", "system", "user", "assistant"] = "unknown", base_status: "int"=10000):
        """
            保存一条消息
        """
        status = base_status
        status += ["unknown", "system", "user", "assistant"].index(role)
        return self._save_log(session_id, role, message, status)
    
    def save_error(self, session_id, error_msg, status):
        """
            保存一条错误信息
        """
        return self._save_log(session_id, "error", error_msg, status)

    def _update_log(self, session_id, linenum: "int" = -1, role: "str|None" = None, message: "str|None" = None, status: "int|None" = None, *_, **__):
        """
            底层操作：更新一条日志信息
        """
        if session_id is None:
            raise exceptions.OlivaChatGPTRuntimeError("session_id is None, please use init_user_session_this() to initialize the session")
        self.log_database.update_message(session_id, linenum, role, message, status)
        return True

    def recall_messages(self, session_id, num: "int" = 1, target_add=20000, status_max=20000, *_, **__):
        """
            撤回最后几条消息
            num 为撤回的消息条数
            status_max 为日志状态码的最大值，只能撤回小于 status_max 的日志 (默认为 20000, 即只能撤回 10000-19999 的日志)
        """
        message_list = self.get_message(session_id, linenum=-num, status_max=status_max)
        for i in message_list:
            self._update_log(session_id, i.logline, status=i.status+target_add)   # 撤回的消息状态码为原状态码 + 20000 (即 30000-39999)
        return True

    def get_message(self, session_id, num: "int" = -1, status_max=20000, *_, **__):
        """
            获取一条消息
            如果 num 为负数，此时 status_max 为日志状态码的最大值，返回倒数 num 条状态小于 status_max 的日志
        """
        if session_id is None:
            raise exceptions.OlivaChatGPTRuntimeError("session_id is None, please use init_user_session_this() to initialize the session")
        session_table = self.log_database.get_session_message(session_id, status_max=status_max)
        if num > 0:
            return session_table[:num+1]
        elif num == 0:
            return session_table
        else:
            return session_table[num:]

    def delete_session(self, platform: "str",  user_id: "str| int", session_model: SessionModel|None=None, *_, **__):
        """
            删除一个 session
            如果 session_model 为 None，则删除当前激活的 session
            如果 session_model 为当前激活的 session，则删除后会自动将当前激活的 session 设置为 None
        """
        flag_is_active = False
        _session_model = self.get_user_session_this(platform, user_id)
        if session_model is None:
            session_model = _session_model
            if session_model is None:
                raise exceptions.OlivaChatGPTRuntimeError("session_id is None, please use init_user_session_this() to initialize the session")
            flag_is_active = True
        elif _session_model is not None and session_model.session_id == _session_model.session_id:
            flag_is_active = True

        self.log_database.delete_session(session_model)
        if flag_is_active:
            self.set_active_session_model(platform, user_id, None)
        return True
    
    def stop(self):
        """
            关闭数据库连接池
        """
        self.log_database.stop()
        global gLogHandler
        gLogHandler = None

    def __del__(self):
        self.stop()
        global gLogHandler
        gLogHandler = None


gLogHandler: DataAPI|None = None

def init_DataAPI(olivos_proc: "OlivOS.pluginAPI.shallow" , max_thread: "int | None" = None, timeout: float = 1) -> DataAPI:
    """
        初始化日志处理类的实例
    """
    global gLogHandler
    if gLogHandler is not None:
        raise exceptions.OlivaChatGPTRuntimeError("logHandler has been initialized")
    gLogHandler = DataAPI(olivos_proc, max_thread, timeout)
    return gLogHandler

def get_DataAPI() -> DataAPI:
    """
        获取日志处理类的实例
    """
    global gLogHandler
    if gLogHandler is None:
        raise exceptions.OlivaChatGPTRuntimeError("logHandler has not been initialized")
    return gLogHandler



if __name__ == "__main__":
    pass


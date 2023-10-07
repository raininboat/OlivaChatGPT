
import OlivOS

from OlivaChatGPT import utils, databaseAPI, replyAPI, confAPI, crossHook, exceptions, remoteAPI, audit


"""
OlivaChatGPT help:
.chat help (<command>): 获取某个指令的帮助信息
.chat new (-n, -m, -h): 初始化一个新的聊天会话
.chat start (<name>| -s <session>) 恢复一个会话
.chat stop: 停止当前聊天会话，并将会话数据输出到文件
.chat show: show all the sessions
.chat switch <session id>: 切换到另一个会话
.chat recall: 撤回当前会话中最后一轮的对话
.chat export [-a|--all]: 导出当前会话的数据到 log 文件夹 (默认只输出状态码 20000 的消息)

.chat <xxx>: 向API服务器发送消息
.chat send <xxx>: 同上，用于发送含有指令前缀的消息

.chat config: 查看当前配置
"""

def cmd_help(config: utils.CommandConfig):
    """
        .chat help (<command>): 获取某个指令的帮助信息
    """
    command_lst = config.message.strip().split(" ")
    fmt_base = config.dict_format
    if len(command_lst) > 0:
        command = command_lst[0]
    else:
        command = ""
    if command == "":
        reply = replyAPI.Reply.help.default()
    else:
        reply = replyAPI.Reply.help.get_child(command)()
    reply.add_data(fmt_base)
    config.plugin_event.reply(reply.to_message())

def cmd_new(config: utils.CommandConfig):
    """
        .chat new (-n, -m): 初始化一个新的聊天会话
    """
    fmt_base = config.dict_format
    
    arg_list = config.message.strip().split(" ")

    name = None
    model = None
    if "-n" in arg_list:
        name = arg_list[arg_list.index("-n") + 1]
    if "-m" in arg_list:
        model = arg_list[arg_list.index("-m") + 1]
    
    model_conf = confAPI.get_model_config(model)
    fmt_base["session_id"] = "N/A"
    fmt_base["session_name"] = "N/A"
    fmt_base["model_name"] = "N/A"
    data_api = databaseAPI.get_DataAPI()
    reply = None
    try:
        # check if the user can create a new session under the given model
        
        crossHook.run_hook("session.new", audit.session_new_check_config(config, name, model))
        # create a new session
        sess = data_api.init_user_session_this(
            platform=config.user_info.platform,
            user_id=config.user_info.user_id,
            session_name=name,
            model_name=model_conf.model_name
        )
    except exceptions.OlivaChatGPTAuditAuthLevelError as err:
        reply = replyAPI.Reply.new.fail()
        reply.add_data(fmt_base)
        reply.add_data({
            "reason": str(err.msg),
            "authlevel_required": err.required,
            "authlevel_current": err.current,
        })
    except exceptions.OlivaChatGPTError as err:
        reply = replyAPI.Reply.new.fail()
        reply.add_data(fmt_base)
        reply.add_data({
            "reason": "OlivaChatGPT 内部错误：\n"+str(err),
        })
    except Exception as err:
        reply = replyAPI.Reply.new.fail()
        reply.add_data(fmt_base)
        reply.add_data({
            "reason": "未知错误：\n"+str(err),
        })
    else:
        fmt_base["session_id"] = sess.session_id
        fmt_base["session_name"] = sess.session_name
        fmt_base["model_name"] = model_conf.model_name
        reply = replyAPI.Reply.new.success()
        reply.add_data(fmt_base)
    log = utils.get_logger()
    log.debug(F"{fmt_base}")
    config.plugin_event.reply(reply.to_message())

def cmd_start(config: utils.CommandConfig):
    """
        .chat start (<name>| -s <session>) 恢复一个会话
    """
    fmt_base = config.dict_format
    
    arg_list = config.message.strip().split(" ")

    name = None
    session = None

    if len(arg_list) == 0:
        # no argument, show help
        reply = replyAPI.Reply.help.command.get_child("start")()
        reply.add_data(fmt_base)
        config.plugin_event.reply(reply.to_message())
        return

    if "-s" in arg_list:
        idx = arg_list.index("-s")
        if idx + 1 < len(arg_list):
            session = arg_list[arg_list.index("-s") + 1]
    elif len(arg_list) == 1:
        name = arg_list[0]
    
    data_api = databaseAPI.get_DataAPI()
    session_model_this = None
    reply = None
    try:
        # get the session list
        sess_list = data_api.get_user_session(
            platform=config.user_info.platform,
            user_id=config.user_info.user_id,
            flag_session_model=True
        )
        for sess in sess_list:
            if name is not None and sess.session_name == name:
                session_model_this = sess
                break
            if session is not None and sess.session_id == session:
                session_model_this = sess
                break

        if session_model_this is None or not isinstance(session_model_this, databaseAPI.SessionModel):
            raise exceptions.OlivaChatGPTSessionNotFoundError(name, session)

        # set the active session
        data_api.set_active_session_model(
            platform=config.user_info.platform,
            user_id=config.user_info.user_id,
            session_name=name,
            session_model=session_model_this
        )
        fmt_base["session_name"] = ""
        fmt_base["model"] = ""
    except exceptions.OlivaChatGPTSessionNotFoundError as err:
        reply = replyAPI.Reply.start.fail()
        reply.add_data(fmt_base)
        reply.add_data({
            "reason": F"该会话不存在，请使用 .chat new -n <name> -m <model> 创建一个新的会话",
            "session_name": err.name if err.name is not None else err.session_id,
            "model": getattr(session_model_this, "model", ""),
        })
    except exceptions.OlivaChatGPTError as err:
        reply = replyAPI.Reply.start.fail()
        reply.add_data(fmt_base)
        reply.add_data({
            "reason": "OlivaChatGPT 内部错误：\n"+str(err),
            "session_name": name if name is not None else session,
            "model": getattr(session_model_this, "model", ""),
        })
    except Exception as err:
        reply = replyAPI.Reply.start.fail()
        reply.add_data(fmt_base)
        reply.add_data({
            "reason": "未知错误：\n"+str(err),
            "session_name": name if name is not None else session,
            "model": getattr(session_model_this, "model", ""),
        })
    else:
        fmt_base["session_name"] = session_model_this.session_name
        fmt_base["model"] = session_model_this.model
        reply = replyAPI.Reply.start.success()
        reply.add_data(fmt_base)
    config.plugin_event.reply(reply.to_message())

def cmd_send(config: utils.CommandConfig):
    """
        .chat send <xxx>: 向API服务器发送消息
    """
    fmt_base = config.dict_format
    data_api = databaseAPI.get_DataAPI()
    try:
        session_model_this = data_api.get_user_session_this(
            platform=config.user_info.platform,
            user_id=config.user_info.user_id
        )
        if session_model_this is None:
            raise exceptions.OlivaChatGPTSessionNotActiveError()
        # check if the user can send message to the active session
        crossHook.run_hook("remote.send.before", config)
        # send the message
        client = remoteAPI.get_remote_client(session_model_this)
        message = config.message
        client.send(config)

    except exceptions.OlivaChatGPTAuditAuthLevelError as err:
        reply = replyAPI.Reply.send.fail()
        reply.add_data(fmt_base)
        reply.add_data({
            "reason": str(err.msg),
            "authlevel_required": err.required,
            "authlevel_current": err.current,
        })
    except exceptions.OlivaChatGPTSessionNotActiveError as err:
        reply = replyAPI.Reply.send.fail()
        reply.add_data(fmt_base)
        reply.add_data({
            "reason": "当前没有活动会话，请使用 .chat start <name> 或 .chat new -n <name> -m <model> 创建一个新的会话",
        })
    except exceptions.OlivaChatGPTError as err:
        reply = replyAPI.Reply.send.fail()
        reply.add_data(fmt_base)
        reply.add_data({
            "reason": "OlivaChatGPT 内部错误：\n"+str(err),
        })
    except Exception as err:
        reply = replyAPI.Reply.send.fail()
        reply.add_data(fmt_base)
        reply.add_data({
            "reason": "未知错误：\n"+str(err),
        })
    else:
        reply = replyAPI.Reply.send.success()
        reply.add_data(fmt_base)
    config.plugin_event.reply(reply.to_message())

def cmd_show(config: utils.CommandConfig):
    """
        .chat show: show all the sessions
    """
    fmt_base = config.dict_format
    data_api = databaseAPI.get_DataAPI()
    # get the session list
    sess_list: list[databaseAPI.MasterTable] = data_api.get_user_session( # type: ignore
        platform=config.user_info.platform,
        user_id=config.user_info.user_id,
        flag_session_model=False
    )
    if len(sess_list) == 0:
        reply = replyAPI.Reply.show.empty()
    else:
        reply = replyAPI.Reply.show.default()
    # format the session list
        sess_list_fmt = []
        active_session_id = getattr(data_api.get_user_session_this(
                platform=config.user_info.platform,
                user_id=config.user_info.user_id
            ), "session_id", None)
        active_session = databaseAPI.MasterTable("N/A", "N/A", "N/A", "N/A", "N/A", "N/A")

        for sess in sess_list:
            dict_sess = sess.to_dict()
            dict_sess["session_model"] = sess.model_name
            sess_list_fmt.append(dict_sess)
            if sess.session_id == active_session_id:
                active_session = sess
        
        reply.format_active_session(active_session)
        reply.format_session_list(sess_list_fmt)

    reply.add_data(fmt_base)
    config.plugin_event.reply(reply.to_message())

def cmd_export(config: utils.CommandConfig):
    command_list = config.message.strip().split(" ")
    flag_all = False
    if "-a" in command_list or "--all" in command_list:
        flag_all = True
    data_api = databaseAPI.get_DataAPI()
    session_model_this = data_api.get_user_session_this(
        platform=config.user_info.platform,
        user_id=config.user_info.user_id
    )
    if session_model_this is None:
        reply = replyAPI.Reply.export.fail()
        reply.add_data(config.dict_format)
        reply.add_data({
            "reason": "当前没有活动会话，请使用 .chat start <name> 或 .chat new -n <name> -m <model> 创建一个新的会话",
            "session_name": "N/A",
        })
        config.plugin_event.reply(reply.to_message())
        return

    message_list: list[databaseAPI.SessionTable] = []
    if flag_all:
        message_list = data_api.get_message(
            session_id=session_model_this.session_id,
            num=0,
            status_max=100000           # 最大状态码为 99999，故这里选择 100000
        )
    else:
        message_list = data_api.get_message(
            session_id=session_model_this.session_id,
            num=0,
            status=20000
        )
    
    if len(message_list) == 0:
        reply = replyAPI.Reply.export.fail()
        reply.add_data(config.dict_format)
        reply.add_data({
            "reason": "当前会话没有消息，请先使用 .chat send <message> 进行聊天，或使用 .chat export -a 导出所有消息（包括出错信息）",
            "session_name": session_model_this.session_name,
        })
        config.plugin_event.reply(reply.to_message())
        return

    

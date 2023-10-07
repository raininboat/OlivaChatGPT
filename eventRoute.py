# -*- coding: utf-8 -*-
import OlivOS

from . import utils, confAPI, databaseAPI, commandAPI, audit

def init(plugin_event: "OlivOS.API.Event", Proc: "OlivOS.pluginAPI.shallow") -> None:
    """
        the init function for the plugin

        1. initialize logger
        2. load config
        3. load database
        4. load hook
        5. send init message
    """
    utils._LogProcWrapper(Proc.log)
    utils.gLogProc.debug("Initializing plugin...")
    conf = confAPI.get_config()
    databaseAPI.DataAPI(olivos_proc=Proc)
    utils.gLogProc.debug("Loading hooks...")
    audit.init()
    utils.gLogProc.debug("Plugin initialized.")

def msg_run(plugin_event: OlivOS.API.Event, Proc: "OlivOS.pluginAPI.shallow"):
    """
        the main function for the plugin

        1. get the message
        2. check the message
        3. send the message to the API server
        4. send the response to the user
    """

    config = confAPI.get_config()

    message_list: list = plugin_event.data.message.data.copy()      # type: ignore
    if len(message_list) == 0:
        return
    if isinstance(message_list[0], OlivOS.messageAPI.PARA.at):
        at_id = message_list[0].data["id"]
        if at_id != plugin_event.bot_info.id:                       # type: ignore
            return
        message_list.pop(0)
    
    message = ""
    # find the first text message
    for this_message in message_list:
        if isinstance(this_message, OlivOS.messageAPI.PARA.text):
            message: str = this_message.data["text"].strip()        # type: ignore
            break
    # if no text message, return
    if message == "":
        return

    # check the prefix of the message and remove it
    _flag_prefix = False
    for i in config.basic.command_prefix:
        if message.startswith(i):
            message = message[len(i):].lstrip()
            if message.startswith(config.basic.command_name):
                message = message[len(config.basic.command_name):].lstrip()
                _flag_prefix = True
            break
    if not _flag_prefix:
        return
    else:
        # the message is a command, block the plugins after this one
        plugin_event.set_block()

    # check the command
    if message == "":
        message = "help"

    if message.startswith("help"):
        message = message[len("help"):].lstrip()
        commandAPI.cmd_help(
            utils.CommandConfig(
                plugin_event=plugin_event,
                Proc=Proc,
                message=message,
                user_info=utils.UserInfo.from_event(plugin_event),
                data=databaseAPI.get_DataAPI()
            )
        )
    elif message.startswith("new"):
        message = message[len("new"):].lstrip()
        commandAPI.cmd_new(
            utils.CommandConfig(
                plugin_event=plugin_event,
                Proc=Proc,
                message=message,
                user_info=utils.UserInfo.from_event(plugin_event),
                data=databaseAPI.get_DataAPI()
            )
        )
    
    elif message.startswith("start"):
        message = message[len("start"):].lstrip()
        commandAPI.cmd_start(
            utils.CommandConfig(
                plugin_event=plugin_event,
                Proc=Proc,
                message=message,
                user_info=utils.UserInfo.from_event(plugin_event),
                data=databaseAPI.get_DataAPI()
            )
        )
    
    elif message.startswith("switch"):
        message = message[len("switch"):].lstrip()
        commandAPI.cmd_start(
            utils.CommandConfig(
                plugin_event=plugin_event,
                Proc=Proc,
                message=message,
                user_info=utils.UserInfo.from_event(plugin_event),
                data=databaseAPI.get_DataAPI()
            )
        )

    elif message.startswith("show"):
        message = message[len("show"):].lstrip()
        commandAPI.cmd_show(
            utils.CommandConfig(
                plugin_event=plugin_event,
                Proc=Proc,
                message=message,
                user_info=utils.UserInfo.from_event(plugin_event),
                data=databaseAPI.get_DataAPI()
            )
        )



    elif message.startswith("send"):
        message = message[len("send"):].lstrip()
        commandAPI.cmd_send(
            utils.CommandConfig(
                plugin_event=plugin_event,
                Proc=Proc,
                message=message,
                user_info=utils.UserInfo.from_event(plugin_event),
                data=databaseAPI.get_DataAPI()
            )
        )

    else:
        commandAPI.cmd_send(
            utils.CommandConfig(
                plugin_event=plugin_event,
                Proc=Proc,
                message=message,
                user_info=utils.UserInfo.from_event(plugin_event),
                data=databaseAPI.get_DataAPI()
            )
        )

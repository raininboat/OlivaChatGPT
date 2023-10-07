
import OlivOS
import dataclasses
from typing import Any

from OlivaChatGPT import utils, databaseAPI, replyAPI, confAPI, crossHook, exceptions

@dataclasses.dataclass
class session_new_check_config:
    config: utils.CommandConfig
    name: str | None
    model: str | None

@dataclasses.dataclass
class before_send_message_config:
    config: utils.CommandConfig
    message: str
    model_conf: confAPI.ConfigModel


@dataclasses.dataclass
class after_receive_message_config:
    """
        the event when the remote API is done
    """
    session_model: databaseAPI.SessionModel
    cmd: utils.CommandConfig
    flag_stream: bool
    flag_success: bool
    data: Any = None

def session_new_check(config: session_new_check_config):
    """
        check if the user can create a new session under the given model
    """
    model = config.model
    user_info = config.config.user_info
    model_conf = confAPI.get_model_config(model)
    data_api = databaseAPI.get_DataAPI()
    
    auth_level = data_api.conf_database.get_user_config(
        namespace="unity",
        key="auth_level",
        platform=user_info.platform,
        user_id=user_info.user_id,
        default_value=0
    )

    if auth_level is None:
        auth_level = 0
    if auth_level < model_conf.auth_level_required:
        raise exceptions.OlivaChatGPTAuditAuthLevelError(
            required=model_conf.auth_level_required,
            current=auth_level
        )

def before_send_message(config: before_send_message_config):
    """
        check if the user can send a message under the given model
        (autherization system is needed)

        config name of database:
            `namespace`: unity
            `key`: auth_level
    """
    database = databaseAPI.get_DataAPI()
    conf_this = config.config
    model_conf = config.model_conf
    auth_level = database.conf_database.get_user_config(
        namespace="unity",
        key="auth_level",
        platform=conf_this.user_info.platform,
        user_id=conf_this.user_info.user_id,
        default_value=0
    )
    if auth_level is None:
        auth_level = 0
    if auth_level < model_conf.auth_level_required:
        raise exceptions.OlivaChatGPTAuditAuthLevelError(
            required=model_conf.auth_level_required,
            current=auth_level
        )

def eco_after_receive_message(config: after_receive_message_config):
    """
        after a response from Chat GPT is received, calculate the reward and update the database
        (economic system is needed)

        config name of database:
            `namespace`: unity
            `key`: econemy
    """
    pass

def cb_model_count_after_receive_message(config: after_receive_message_config):
    """
        记录用户调用对应模型的次数

        config name of database:
            `namespace`: OlivaChatGPT
            `key`: count_{model_name}

    """
    database = databaseAPI.get_DataAPI()
    user_info = config.cmd.user_info
    session_model = config.session_model
    model_name = session_model.model
    model_count = database.conf_database.get_user_config(
        namespace="OlivaChatGPT",
        key=f"count_{model_name}",
        platform=user_info.platform,
        user_id=user_info.user_id,
        default_value=0
    )
    if model_count is None:
        model_count = 0
    database.conf_database.set_user_config(
        namespace="OlivaChatGPT",
        key=f"count_{model_name}",
        platform=user_info.platform,
        user_id=user_info.user_id,
        value=model_count + 1
    )

def init():
    """
        initialize all the hooks
    """
    crossHook.add_hook("session.new", session_new_check)
    crossHook.add_hook("remote.send", before_send_message)
    crossHook.add_hook("remote.recv", cb_model_count_after_receive_message)

"""
the remote API is used to communicate with the API server of ChatGPT
"""

import requests
import json
import OlivOS
import time
import threading
from urllib.parse import urljoin
import dataclasses

from typing import Literal


from . import databaseAPI, exceptions, replyAPI, utils, confAPI, crossHook
from .audit import after_receive_message_config
from .third_party.get_tocken_num import get_token_from_message_list, get_token_from_string 

STREAM_TIME_OUT = 120


class RemoteClient:
    """
        Remote API Client

       `RemoteClient` is used to communicate with the API server of ChatGPTs
        Usage:
            session_id = "xxx"
            client = RemoteClient(session_id=session_id)
            print(client.send("Hello, world!"))
    """

    def __init__(self, session_model: databaseAPI.SessionModel):
        global gRemoteClient
        if session_model in gRemoteClient:
            raise exceptions.OlivaChatGPTRuntimeError("RemoteClient has been initialized")
        gRemoteClient[session_model] = self
        self.session_model = session_model
        self.database = databaseAPI.get_DataAPI()
        self.conf_all = confAPI.get_config()
        self.model_conf = self.conf_all.models[session_model.model]
        self.cache = {}
        self.cache["cmd"] = None

        self.header = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.model_conf.api_key}",
            'Accept': 'application/json',
        }

        self.url = urljoin(self.model_conf.url, self.model_conf.endpoint)
        # self.model_conf.url + self.model_conf.endpoint
        self.body = {
            "model": self.model_conf.model_type,
            "messages": [],
            "stream": self.model_conf.stream,
        }
        self.get_context()

        self._lock = threading.Lock()
        # self._session = requests.Session()
        # self._session.headers.update(self.header)

    def get_context(self):
        """
            get the context of the session
        """
        history_context = self.database.get_message(
            session_id=self.session_model.session_id, num=0, status_max=20000
        )
        for line in history_context:
            if line.role in ["system", "user", "assistant"]:                    # 已经通过本行确保了 line.role 为 Literal['system', 'user', 'assistant']
                self.add_message(line.role, line.message, record=False)         # type: ignore
        return self.body["messages"]

    def add_message(self, role: "Literal['system', 'user', 'assistant']", message: str, record: bool = True):
        """
            add a message to the body
        """
        self.body["messages"].append({
            "role": role,
            "content": message
        })
        if self.model_conf.max_context > 0 and len(self.body["messages"]) > self.model_conf.max_context:
            self.body["messages"].pop(0)
        if record:
            self._record(role, message)

    def send(self, cmd: utils.CommandConfig|None = None):
        """
            send a message to the API server
        """
        if self.model_conf.timeout > 0:
            lock = self._lock.acquire(blocking=True, timeout=self.model_conf.timeout)
        else:
            lock = self._lock.acquire(blocking=True)
        message = cmd.message if cmd is not None else ""
        if message != "":
            self.add_message("user", message)
        else:
            return
        if lock:
            self.cache["cmd"] = cmd
            threading.Thread(target=self.__send).start()
            self._lock.release()
        else:
            raise exceptions.OlivaChatGPTRuntimeError("RemoteClient is busy")

    def __send(self):
        # self.add_message(message)
        reply = replyAPI.Reply.send.response()

        dict_fmt = {}
        cmd = self.cache["cmd"]
        if cmd is not None:
            dict_fmt = cmd.dict_format
        flag_success = False
        response_data = None
        try:
            # with self._lock:
            log = utils.get_logger()
            log.debug(f"Sending message to {self.url}...")
            log.debug(f"Header: {self.header}")
            log.debug(f"Message: {self.body}")

            if self.model_conf.stream:

                log.debug("using stream mode")
                self.body["stream"] = True
                response = requests.request(
                    method="POST",
                    url=self.url,
                    headers=self.header,
                    json=self.body,
                    stream=True,
                )
                token_send = get_token_from_message_list(self.body["messages"], self.model_conf.model_type)
                data, response_data = self.__get_stream_response(response)
                token_receive = get_token_from_string(data, self.model_conf.model_type)
                if token_send is not None and token_receive is not None:
                    dict_fmt["token_num"] = f"{token_send} + {token_receive} = {token_send + token_receive}\n\tstream mode 下基于 tiktoken 估计 token 数量，请以实际账单为准"
                else:
                    dict_fmt["token_num"] = f"stream mode 下未安装 tiktoken 库或模型不支持，无法计算 token 数量"
            else:
                self.body["stream"] = False
                response = requests.request(
                    method="POST",
                    url=self.url,
                    headers=self.header,
                    json=self.body,
                    # verify=None,
                )
                data, response_data = self.__get_post_response(response)
                dict_fmt["token_num"] = f"""\
{response_data["usage"]["prompt_tokens"]}+{response_data["usage"]["completion_tokens"]} = {response_data["usage"]["total_tokens"]}"""

                log.debug(f"Response: {response_data}")

        except exceptions.OlivaChatGPTHTTPCodeError as err:
            status_code = err.code + 51000
            self.database.save_error(
                session_id=self.session_model.session_id, error_msg=str(err.content), status=status_code
            )
            if cmd is not None:
                dict_fmt["reply_message"] = f"""\
发送消息失败，错误码: {status_code}
错误信息：\n
{err.content}
"""
                reply.add_data(dict_fmt)
        except exceptions.OlivaChatGPTHTTPResponseInvalidError as err:
            self.database.save_error(
                session_id=self.session_model.session_id, error_msg=str(err.data), status=52200
            )
            if cmd is not None:
                dict_fmt["reply_message"] = f"""\
发送消息失败，错误码: 52200
错误信息：\n
{err.data}
"""
                reply.add_data(dict_fmt)
        except exceptions.OlivaChatGPTHTTPTimeoutError as err:
            # 当在 steam mode 下，超过 120s 未接收到结束符时，会抛出此异常
            # 此时， err.data 为已经接收到的数据
            # 此条消息仍然会被记录到数据库中
            message_this = str(err.data)
            self.database.save_message(
                session_id=self.session_model.session_id, message=message_this, role="assistant", base_status=11000
            )
            self.add_message("assistant", message_this, record=False)
            if cmd is not None:
                dict_fmt["reply_message"] = message_this
            flag_success = True
        except Exception as err:
            self.database.save_error(
                session_id=self.session_model.session_id, error_msg=str(err), status=50000
            )
            if cmd is not None:
                dict_fmt["reply_message"] = f"""\
发送消息失败，错误码: 50000
错误信息：\n
{err.__class__.__name__}: {err}
"""
                reply.add_data(dict_fmt)
        else:
            self.add_message("assistant", data)
            if cmd is not None:
                dict_fmt["reply_message"] = f"""\
{data}
"""
                reply.add_data(dict_fmt)
            flag_success = True
        finally:
            if flag_success == False:
                self.database.recall_messages(self.session_model.session_id, -1, target_add=20100)
                self.body["messages"].pop(-1)
            
            event_this = after_receive_message_config(
                self.session_model, cmd, self.model_conf.stream, flag_success, response_data
            )
            try:
                # 用于处理 remote.recv hook，可以用于处理 tocken 数量计算减少等
                crossHook.run_hook("remote.recv", event_this)
            except Exception as err:
                log = utils.get_logger()
                log.error(f"Error in remote.recv hook: {err}")
                reply.append(f"Error in remote.recv hook: {err}")
            if cmd is not None:
                cmd.plugin_event.reply(reply.to_message())
            self.cache["cmd"] = None

    def _record(self, role: "Literal['unknown', 'system', 'user', 'assistant']", content: str):
        """
            record the message to the database
        """
        log = utils.get_logger()
        log.debug(f"Recording message <role: {role}>: \n{content}")
        self.database.save_message(
            session_id=self.session_model.session_id, message=content, role=role
        )

    def __get_post_response(self, response: requests.Response):
        """
            the callback function for the request
        """
        if response.status_code != 200:
            raise exceptions.OlivaChatGPTHTTPCodeError(response.status_code, response.content.decode(encoding="utf-8"))
        response_json = response.json()
        try:
            data = response_json["choices"][0]["message"]["content"]
        except Exception as err:
            raise exceptions.OlivaChatGPTHTTPResponseInvalidError(response_json, str(err))
        return data, response_json

    def __get_stream_response(self, response: requests.Response):
        """
            get the response in stream mode
        """
        # 遍历所有的数据块并打印出来
        log = utils.get_logger()
        completion_text = ""
        event_list = []
        time_start = time.time()
        if (response.status_code == 200):
            err_time = 0
            while time.time() - time_start < STREAM_TIME_OUT:
                tmp_data = b""
                # flag_data_start = False
                try:
                    for chunk in response.iter_lines(chunk_size=1024):
                        if chunk:
                            log.trace(f"chunk: {chunk}")
                            if chunk.startswith(b"data: "):
                                # the chunk is the start of a new chunk
                                chunk = chunk[6:]
                                tmp_data = chunk
                            else:
                                # the chunk is part of the last chunk
                                tmp_data += chunk
                            try:
                                event_this = json.loads(tmp_data)
                                event_list.append(event_this)
                                # tmp_data = tmp_data[end_index + 5:]
                            except json.JSONDecodeError:
                                if tmp_data == "[DONE]":
                                    # break
                                    log.trace("chunk [DONE]")
                                    return completion_text, event_list
                                log.error(f"JSONDecodeError: {chunk}")
                                # tmp_data = tmp_data[end_index + 5:]
                            else:
                                if len(event_this["choices"]) == 0 or "delta" not in event_this["choices"][0]:
                                    # log.debug("an empty chunk")
                                    continue
                                if "content" in event_this["choices"][0]["delta"]:
                                    completion_text += event_this["choices"][0]["delta"]["content"]
                                if event_this["choices"][0]["finish_reason"] is not None:
                                    if event_this["choices"][0]["finish_reason"] == "stop":
                                        log.trace("stopped!")
                                        return completion_text, event_list
                                    else:
                                        log.error(f"gpt returns with stop reason: {event_this['choices'][0]['finish_reason']}")
                except requests.exceptions.StreamConsumedError as err:
                    log.error(f"StreamConsumedError: {err}")
                    err_time += 1
                    if err_time > 5:
                        return completion_text, event_list
                    time.sleep(1)
                time.sleep(0.01)
            raise exceptions.OlivaChatGPTHTTPTimeoutError(completion_text)
        else:
            raise exceptions.OlivaChatGPTHTTPCodeError(response.status_code, response.content.decode(encoding="utf-8"))

gRemoteClient: dict[databaseAPI.SessionModel, RemoteClient] = {}


def get_remote_client(session_model: databaseAPI.SessionModel):
    """
        get the remote client by session_model
    """
    global gRemoteClient
    if session_model in gRemoteClient:
        return gRemoteClient[session_model]
    else:
        return RemoteClient(session_model)

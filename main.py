""" 
    Script Loader - 轻量级插件托盘 for OlivOS
    Copyright (C) 2022  Rainy Zhou

    This program is free software: you can redistribute it and/or modify
    it under the terms of the GNU Affero General Public License as published
    by the Free Software Foundation, either version 3 of the License, or
    (at your option) any later version.

    This program is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU Affero General Public License for more details.

    You should have received a copy of the GNU Affero General Public License
    along with this program.  If not, see <https://www.gnu.org/licenses/>.
"""

import OlivOS
from . import eventRoute

class Event:
    """
    the api interface for the plugin
    """
    @staticmethod
    def init(plugin_event: "OlivOS.API.Event", Proc: "OlivOS.pluginAPI.shallow") -> None:
        # msg_route.script_load()
        eventRoute.init(plugin_event, Proc)

    @staticmethod
    def private_message(plugin_event: "OlivOS.API.Event", Proc: "OlivOS.pluginAPI.shallow"):
        eventRoute.msg_run(plugin_event, Proc)

    @staticmethod
    def group_message(plugin_event: "OlivOS.API.Event", Proc: "OlivOS.pluginAPI.shallow"):
        eventRoute.msg_run(plugin_event, Proc)

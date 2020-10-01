#!/usr/bin/env python3
# -*- coding: UTF-8 -*-
# Copyright 2019 黎慧剑
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

"""
初始化以图搜图服务
@module loader
@file loader.py
"""

import os
import sys
import datetime
import math
from flask import Flask
from flask_cors import CORS
from werkzeug.routing import Rule
from HiveNetLib.simple_log import Logger
from HiveNetLib.base_tools.run_tool import RunTool
# 根据当前文件路径将包路径纳入，在非安装的情况下可以引用到
sys.path.append(os.path.abspath(os.path.join(
    os.path.dirname(__file__), os.path.pardir, os.path.pardir)))
from search_by_image.lib.search import SearchEngine
from search_by_image.lib.pipeline import Pipeline
from search_by_image.lib.restful_api import FlaskTool, SearchServer


__MOUDLE__ = 'loader'  # 模块名
__DESCRIPT__ = u'初始化以图搜图服务'  # 模块描述
__VERSION__ = '0.1.0'  # 版本
__AUTHOR__ = u'黎慧剑'  # 作者
__PUBLISH__ = '2020.07.02'  # 发布日期


class ServerLoader(object):
    """
    以图搜图服务装载器
    """

    def __init__(self, server_config: dict, app: Flask = None, **kwargs):
        """
        以图搜图服务初始化

        @param {dict} server_config - 服务配置字典
        @param {Flask} app=None - 服务
        """
        self.kwargs = kwargs
        self.debug = server_config.get('debug', True)
        self.execute_path = server_config['execute_path']
        RunTool.set_global_var('EXECUTE_PATH', self.execute_path)

        # 日志处理
        self.logger: Logger = None
        if 'logger' in server_config.keys():
            _logger_config = server_config['logger']
            if len(_logger_config['conf_file_name']) > 0 and _logger_config['conf_file_name'][0] == '.':
                # 相对路径
                _logger_config['conf_file_name'] = os.path.join(
                    self.execute_path, _logger_config['conf_file_name']
                )
            if len(_logger_config['logfile_path']) > 0 and _logger_config['logfile_path'][0] == '.':
                # 相对路径
                _logger_config['logfile_path'] = os.path.join(
                    self.execute_path, _logger_config['logfile_path']
                )
            self.logger = Logger.create_logger_by_dict(_logger_config)

        # 加载管道配置
        RunTool.set_global_var(
            'PIPELINE_PROCESSER_PARA', server_config['pipeline']['processer_para']
        )
        RunTool.set_global_var('PIPELINE_ROUTER_PARA', server_config['pipeline']['router_para'])
        _plugins_path_list = server_config['pipeline']['plugins_path'].split(',')
        for _plugins_path in _plugins_path_list:
            Pipeline.load_plugins_by_path(
                os.path.join(self.execute_path, _plugins_path.strip())
            )

        self.server_config = server_config
        self.app = app
        if self.app is None:
            self.app = Flask(__name__)
            CORS(self.app)

        self.app.debug = self.debug
        self.app.send_file_max_age_default = datetime.timedelta(seconds=1)  # 设置文件缓存1秒
        self.app.config['JSON_AS_ASCII'] = False  # 显示中文
        # 上传文件大小限制
        self.app.config['MAX_CONTENT_LENGTH'] = math.floor(
            self.server_config['max_upload_size'] * 1024 * 1024
        )

        # 装载搜索引擎服务
        self.search_engine = SearchEngine(self.server_config, logger=self.logger)

        # 动态加载路由
        self.api_class = [SearchServer, ]

        # 增加客户端demo访问
        if self.server_config['enable_client']:
            # 增加静态路径
            _static_path = self.server_config['static_path']
            if _static_path[0:1] == '.':
                # 相对路径
                _static_path = os.path.realpath(
                    os.path.join(self.execute_path, _static_path)
                )

            self.app.static_folder = _static_path
            self.app.static_url_path = 'static'

            # 加入客户端主页
            self.app.url_map.add(
                Rule('/', endpoint='client', methods=['GET'])
            )
            self.app.view_functions['client'] = self._client_view_function

        FlaskTool.add_route_by_class(self.app, self.api_class)
        self._log_debug(str(self.app.url_map))

    #############################
    # 公共函数
    #############################

    def start_restful_server(self):
        """
        启动Restful Api服务
        """
        self.app.run(**self.server_config['flask'])

    #############################
    # 内部函数
    #############################

    def _client_view_function(self):
        return self.app.send_static_file('index.html')  # index.html在static文件夹下

    def _log_info(self, msg: str, *args, **kwargs):
        """
        输出info日志

        @param {str} msg - 要输出的日志
        """
        if self.logger:
            if 'extra' not in kwargs:
                kwargs['extra'] = {'callFunLevel': 2}

            self.logger.info(msg, *args, **kwargs)

    def _log_debug(self, msg: str, *args, **kwargs):
        """
        输出debug日志

        @param {str} msg - 要输出的日志
        """
        if self.logger:
            if 'extra' not in kwargs:
                kwargs['extra'] = {'callFunLevel': 2}

            self.logger.debug(msg, *args, **kwargs)

    def _log_error(self, msg: str, *args, **kwargs):
        """
        输出error日志

        @param {str} msg - 要输出的日志
        """
        if self.logger:
            if 'extra' not in kwargs:
                kwargs['extra'] = {'callFunLevel': 2}

            self.logger.error(msg, *args, **kwargs)


if __name__ == '__main__':
    # 当程序自己独立运行时执行的操作
    # 打印版本信息
    print(('模块名：%s  -  %s\n'
           '作者：%s\n'
           '发布日期：%s\n'
           '版本：%s' % (__MOUDLE__, __DESCRIPT__, __AUTHOR__, __PUBLISH__, __VERSION__)))

#!/usr/bin/env python3
# -*- coding: UTF-8 -*-
# Copyright 2019 黎慧剑
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

"""
管道处理控制
@module pipeline
@file pipeline.py
"""

import os
import sys
import json
import inspect
import time
import datetime
import threading
import traceback
from HiveNetLib.base_tools.run_tool import RunTool
from HiveNetLib.base_tools.import_tool import ImportTool
from HiveNetLib.base_tools.file_tool import FileTool
# 根据当前文件路径将包路径纳入，在非安装的情况下可以引用到
sys.path.append(os.path.abspath(os.path.join(
    os.path.dirname(__file__), os.path.pardir, os.path.pardir)))


__MOUDLE__ = 'pipeline'  # 模块名
__DESCRIPT__ = u'管道处理控制'  # 模块描述
__VERSION__ = '0.1.0'  # 版本
__AUTHOR__ = u'黎慧剑'  # 作者
__PUBLISH__ = '2020.08.27'  # 发布日期


PIPELINE_PLUGINS_VAR_NAME = 'PIPELINE_PLUGINS'  # 插件装载全局变量名


class Tools(object):
    """
    管道开发的工具函数
    """

    @classmethod
    def get_node_id_by_name(cls, node_name: str, pipeline_obj):
        """
        通过节点配置名获取节点id

        @param {str} node_name - 节点配置名
        @param {Pipeline} pipeline_obj - 管道对象

        @return {str} - 对应的节点id，找不到返回None
        """
        for _key in pipeline_obj.pipeline.keys():
            if pipeline_obj.pipeline[_key]['name'] == node_name:
                return _key

        return None


class PipelineProcesser(object):
    """
    管道处理器框架类
    """
    @classmethod
    def initialize(cls):
        """
        初始化处理类，仅在装载的时候执行一次初始化动作
        """
        pass

    @classmethod
    def processer_name(cls) -> str:
        """
        处理器名称，唯一标识处理器

        @returns {str} - 当前处理器名称
        """
        raise NotImplementedError()

    @classmethod
    def is_asyn(cls) -> bool:
        """
        是否异步处理

        @returns {bool} - 标识处理器是否异步处理，返回Fasle代表管道要等待处理器执行完成
        """
        return False

    @classmethod
    def execute(cls, input_data, context: dict, pipeline_obj):
        """
        执行处理

        @param {object} input_data - 处理器输入数据值，除第一个处理器外，该信息为上一个处理器的输出值
        @param {dict} context - 传递上下文，该字典信息将在整个管道处理过程中一直向下传递，可以在处理器中改变该上下文信息
            上下文固有的信息包括：
                trace_list {list} - 执行追踪列表，按顺序放入执行信息，每个执行信息包括
                    node_id {str} 节点配置id
                    node_name {str} 节点配置名
                    processor_name {str} 处理器名
                    start_time {datetime} 开始时间
                    end_time {datetime} 结束时间
                    status {str} 执行状态，'S' - 成功，'E' - 出现异常
                    status_msg {str} 状态描述，当异常时送入异常信息
                    router_name : 路由名(直线路由可以不设置路由器)
                node_id {str} 当前节点配置id
                node_status {str} I - 初始化，R - 正在执行, E - 执行失败， S-执行成功
                start_time {datetime} 开始时间
                total {int} 节点运行进度总任务数
                done {int} 节点运行进度当前完成数
        @param {Pipeline} pipeline_obj - 管道对象，作用如下：
            1、更新执行进度
            2、输出执行日志
            3、异步执行的情况主动通知继续执行管道处理

        @returns {object} - 处理结果输出数据值，供下一个处理器处理，异步执行的情况返回None
        """
        raise NotImplementedError()


class PipelineRouter(object):
    """
    管道路由器框架类
    """

    @classmethod
    def initialize(cls):
        """
        初始化处理类，仅在装载的时候执行一次初始化动作
        """
        pass

    @classmethod
    def router_name(cls) -> str:
        """
        路由器名称，唯一标识路由器

        @returns {str} - 当前路由器名称
        """
        raise NotImplementedError()

    @classmethod
    def get_next(cls, output, context: dict, pipeline_obj, **kwargs):
        """
        获取路由下一节点

        @param {object} output - 上一个节点的输出结果
        @param {dict} context - 上下文字典
        @param {Pipeline} pipeline_obj - 管道对象
        @param {kwargs} - 传入的扩展参数

        @returns {str} - 下一节点的配置id，如果是最后的节点，返回None
        """
        raise NotImplementedError()


class Pipeline(object):
    """
    管道控制框架
    """

    #############################
    # 静态工具函数
    #############################
    @classmethod
    def add_plugin(cls, class_obj):
        """
        添加插件

        @param {object} class_obj - 插件类
        """
        # 获取插件字典
        _plugins = RunTool.get_global_var(PIPELINE_PLUGINS_VAR_NAME)
        if _plugins is None:
            _plugins = {
                'processer': dict(),
                'router': dict()
            }
            RunTool.set_global_var(PIPELINE_PLUGINS_VAR_NAME, _plugins)

        # 判断类型
        _type_fun = getattr(class_obj, 'processer_name', None)
        _plugin_type = 'processer'
        if _type_fun is None or not callable(_type_fun):
            _type_fun = getattr(class_obj, 'router_name', None)
            _plugin_type = 'router'

        if _type_fun is None or not callable(_type_fun):
            # 不是标准插件类
            return

        # 执行初始化
        class_obj.initialize()

        # 放入插件配置
        _plugins[_plugin_type][_type_fun()] = class_obj

    @classmethod
    def load_plugins_by_path(cls, path: str):
        """
        装载指定目录下的管道插件(处理器和路由器)

        @param {str} path - 要装载的目录
        """
        _file_list = FileTool.get_filelist(path=path, regex_str=r'.*\.py$', is_fullname=True)
        for _file in _file_list:
            if _file == '__init__.py':
                continue

            cls.load_plugins_by_file(_file)

    @classmethod
    def load_plugins_by_file(cls, file: str):
        """
        装载指定文件的管道插件

        @param {str} file - 模块文件路径
        """
        # 执行加载
        _file = os.path.realpath(file)
        if not _file.endswith('.py'):
            raise AttributeError('not supported plugins file [%s]!' % _file)

        _module_name = os.path.split(_file)[1][0: -3]
        _module = ImportTool.import_module(
            _module_name, extend_path=os.path.split(_file)[0], is_force=True)
        _clsmembers = inspect.getmembers(_module, inspect.isclass)
        for (_class_name, _class) in _clsmembers:
            if _module.__name__ != _class.__module__:
                # 不是当前模块定义的函数
                continue

            cls.add_plugin(_class)

    @classmethod
    def get_plugin(cls, plugin_type: str, name: str):
        """
        获取制定插件

        @param {str} plugin_type - 插件类型
            processer - 处理器
            router - 路由器
        @param {str} name - 插件名称

        @returns {object} - 插件类对象，如果找不到返回None
        """
        # 获取插件字典
        _plugins = RunTool.get_global_var(PIPELINE_PLUGINS_VAR_NAME)
        if _plugins is None:
            _plugins = {
                'processer': dict(),
                'router': dict()
            }
            RunTool.set_global_var(PIPELINE_PLUGINS_VAR_NAME, _plugins)

        return _plugins.get(plugin_type, dict()).get(name, None)

    #############################
    # 构造函数
    #############################
    def __init__(self, name: str, pipeline_config: str, is_asyn=False, asyn_notify_fun=None,
                 running_notify_fun=None, end_running_notify_fun=None,
                 logger=None):
        """
        构造函数

        @param {str} name - 管道名称
        @param {str} pipeline_config - 管道配置json字符串, 注意节点顺序必须是从1开始的连续整数
            {
                "1": {
                    "name": "节点配置名",
                    "processor": "处理器名",
                    "context": {},  # 要更新的上下文字典，执行处理器前将更新该上下文
                    "router": "",  # 路由器名，执行完将执行该路由器找下一个执行节点，置空或不设置值的情况直接按顺序找下一个节点
                    "router_para": {}, # 路由器的传入参数, 作为**kwargs传入路由器，置空或不设置值的情况传入{}
                    "exception_router": "", 执行处理器出现异常时执行的路由器名，置空或不设置值将抛出异常并结束管道执行
                    "exception_router_para": {}  # 异常路由器的传入参数， 作为**kwargs传入路由器，置空或不设置值的情况传入{}
                },
                "2": {
                    ...
                },
                ...
            }
        @param {bool} is_asyn=False - 是否异步返回结果
        @param {function} asyn_notify_fun=None - 异步结果通知函数，格式如下：
            fun(name, status, context, output)
                name {str} - 管道名称
                status {str} - 管道状态
                context {dict} - 当前上下文
                output {object} - 管道输出数据
        @param {function} running_notify_fun=None = 节点运行通知函数，格式如下：
            fun(name, node_id, node_name)
                name {str} - 管道名称
                node_id {str} - 运行节点id
                node_name {str} - 运行节点配置名
        @param {function} end_running_notify_fun=None = 节点运行完成通知函数，格式如下：
            fun(name, node_id, node_name, status, status_msg)
                name {str} - 管道名称
                node_id {str} - 运行节点id
                node_name {str} - 运行节点配置名
                status {str} 执行状态，'S' - 成功，'E' - 出现异常
                status_msg {str} 状态描述，当异常时送入异常信息
        @param {Simple_log.Logger} logger=None - 日志对象
        """
        self.logger = logger
        self.name = name
        self.pipeline_config = pipeline_config
        self.pipeline = json.loads(pipeline_config)
        self.is_asyn = is_asyn  # 是否异步
        self.asyn_notify_fun = asyn_notify_fun  # 异步结果通知函数
        self.running_notify_fun = running_notify_fun
        self.end_running_notify_fun = end_running_notify_fun

        # 管道状态
        self._status_lock = threading.Lock()
        self._status = 'init'
        self._context = dict()  # 通用上下文对象
        self._context['trace_list'] = list()  # 执行追踪列表

        # 临时变量
        self._current_input = None  # 当前执行环节输入数据
        self._output = None  # 最终输出结果
        self._thread_running = False  # 标识线程是否还在运行

    #############################
    # 管道状态查询
    #
    #############################
    @property
    def status(self):
        """
        获取管道状态
        @property {str} - 当前状态，init-初始化，pause-暂停，running-运行中，success-成功结束，exception-异常结束
        """
        self._status_lock.acquire()
        try:
            return self._status
        finally:
            self._status_lock.release()

    @property
    def context(self):
        """
        获取管道当前上下文
        @property {dict} - 当前上下文字典
        """
        return self._context

    @property
    def trace_list(self):
        """
        获取管道当前执行追踪列表
        @property {list} - 当前执行追踪列表
        """
        return self._context['trace_list']

    #############################
    # 处理函数
    #############################
    def start(self, input_data=None, context: dict = {}):
        """
        执行管道(从第一个节点开始执行)

        @param {object} input_data=None - 初始输入数据值
        @param {dict} context={} - 初始上下文

        @returns {str, object} - 同步情况返回 status, output，异步情况返回None

        @throws {RuntimeError} - 当状态为running、pause时抛出异常
        """
        self._status_lock.acquire()
        try:
            if self._status in ('running', 'pause'):
                _msg = 'Pipeline [%s] is running!' % self.name
                self.log_error('Error: ' % _msg)
                raise RuntimeError(_msg)

            # 初始化变量
            self._current_input = input_data
            self._context = context
            self._context['node_id'] = "1"
            self._context['node_status'] = 'I'
            self._context['trace_list'] = list()
            self._output = None
            self._status = 'running'
        finally:
            self._status_lock.release()

        # 启动任务执行线程
        self._start_running_thread()

        # 判断是否结束运行
        if self.is_asyn:
            # 异步执行，不用等待
            return None

        while self.status in ('running'):
            time.sleep(0.0002)

        return self.status, self._output

    def pause(self):
        """
        暂停管道执行
        """
        if self.status != 'running':
            _msg = 'Pipeline [%s] not running!' % self.name
            self.log_error('Error: ' % _msg)
            raise RuntimeError(_msg)

        # 只要设置管道状态为 pause 即可
        self._set_status('pause')
        while self._thread_running:
            # 等待运行线程结束
            time.sleep(0.01)

        # 记录日志
        self.log_info('Pipeline [%s] pause!' % self.name)

    def resume(self):
        """
        从中断点重新执行
        """
        if self.status == 'pause':
            # 从暂停重新启动
            self._set_status('running')
            self._start_running_thread()
            self.log_info('Pipeline [%s] resume!' % self.name)
        elif self.status == 'exception':
            # 从异常的节点重新发起
            self._context['node_status'] = 'I'
            self._set_status('running')
            self._start_running_thread()
            self.log_info('Pipeline [%s] resume!' % self.name)
        else:
            _msg = 'Pipeline [%s] status is not pause or exception!!' % self.name
            self.log_error('Error: ' % _msg)
            raise RuntimeError(_msg)

    def asyn_node_feeback(self, node_id: str, output=None, status: str = 'S', status_msg: str = 'success', context: dict = {}):
        """
        异步节点执行结果反馈

        @param {str} node_id - 节点配置id
        @param {object} output=None - 节点执行输出结果
        @param {str} status='S' - 节点运行状态，'S' - 成功，'E' - 出现异常
        @param {str} status_msg='success' - 运行状态描述
        @param {dict} context={} - 要修改的上下文信息
        """
        if self._context['node_id'] != node_id:
            _msg = '[Pipeline:%s] Not correct node id [%s]!' % (self.name, node_id)
            self.log_error('Error: ' % _msg)
            raise AttributeError(_msg)

        self._context.update(context)
        _next_id = self._run_router(node_id, output=output, status=status, status_msg=status_msg)
        if _next_id is not None:
            # 设置上下文，执行下一个节点
            self._context['node_id'] = _next_id
            self._context['node_status'] = 'I'

            # 启动处理线程
            if self._status == 'running':
                self._start_running_thread()

    def node_process_feeback(self, node_id: str, total: int, done: int):
        """
        节点进度反馈函数
        供节点运行过程中更新进度信息

        @param {str} node_id - 节点id
        @param {int} total - 节点运行进度总任务数
        @param {int} done - 节点运行进度当前完成数
        """
        if self._context['node_id'] == node_id:
            self._context['total'] = total
            self._context['done'] = done
            self.log_debug('[Pipeline:%s] Node [%s] process %d/%d!' %
                           (self.name, node_id, done, total))

    def get_node_process(self, node_id: str):
        """
        获取当前节点运行进度

        @param {str} node_id - 节点配置id

        @returns {int, int} - 返回 total, done 进度信息
        """
        if self._context['node_id'] == node_id:
            return self._context.get('total', 1), self._context.get('done', 0)
        else:
            # 非当前节点，返回完成状态
            return 1, 1

    #############################
    # 日志函数
    #############################

    def log_info(self, msg: str, *args, **kwargs):
        """
        输出info日志

        @param {str} msg - 要输出的日志
        """
        if self.logger:
            if 'extra' not in kwargs:
                kwargs['extra'] = {'callFunLevel': 2}

            self.logger.info(msg, *args, **kwargs)

    def log_debug(self, msg: str, *args, **kwargs):
        """
        输出debug日志

        @param {str} msg - 要输出的日志
        """
        if self.logger:
            if 'extra' not in kwargs:
                kwargs['extra'] = {'callFunLevel': 2}

            self.logger.debug(msg, *args, **kwargs)

    def log_error(self, msg: str, *args, **kwargs):
        """
        输出error日志

        @param {str} msg - 要输出的日志
        """
        if self.logger:
            if 'extra' not in kwargs:
                kwargs['extra'] = {'callFunLevel': 2}

            self.logger.error(msg, *args, **kwargs)

    #############################
    # 内部函数
    #############################
    def _set_status(self, status: str):
        """
        设置状态值

        @param {str} status - 要设置的状态字符串
        """
        self._status_lock.acquire()
        try:
            self._status = status
        finally:
            self._status_lock.release()

    def _run_node(self, node_id: str):
        """
        执行处理节点

        @param {str} node_id - 要执行的节点ID

        @returns {str} - 返回下一节点ID，返回None代表结束管道执行，返回空字符串''代表异步处理
        """
        _node_config = self.pipeline[node_id]
        # 执行节点处理器
        try:
            self._context['node_id'] = node_id
            self._context['node_status'] = 'R'
            self._context['start_time'] = datetime.datetime.now()
            self._context['total'] = 1
            self._context['done'] = 0

            _processer: PipelineProcesser = self.get_plugin('processer', _node_config['processor'])
            self._context.update(_node_config.get('context', {}))

            # 通知开始运行节点
            self.log_info('[Pipeline:%s] Start running node [%s]' % (self.name, node_id))
            if self.running_notify_fun is not None:
                self.running_notify_fun(self.name, node_id, _node_config.get('name', ''))

            # 运行节点
            if _processer.is_asyn():
                # 异步处理，发起执行后直接返回''
                _processer.execute(self._current_input, self._context, self)
                return ''
            else:
                # 同步处理
                _output = _processer.execute(self._current_input, self._context, self)
                return self._run_router(node_id, output=_output, status='S', status_msg='success')
        except:
            _status_msg = traceback.format_exc()
            self.log_error('Error: [Pipeline:%s] Running node [%s] error: %s' %
                           (self.name, node_id, _status_msg))
            return self._run_router(node_id, output=None, status='E', status_msg=_status_msg)

    def _run_router(self, node_id: str, output=None, status: str = 'S', status_msg: str = 'success') -> str:
        """
        执行路由判断

        @param {str} node_id - 当前运行的节点
        @param {object} output=None - 节点执行输出结果
        @param {str} status='S' - 节点运行状态，'S' - 成功，'E' - 出现异常
        @param {str} status_msg='success' - 运行状态描述

        @returns {str} - 返回下一节点ID，如果已是最后节点返回None
        """
        _node_config = self.pipeline[node_id]
        _router_name = ''
        _router_para = {}
        if status != 'S' and _node_config.get('exception_router', '') == '':
            _router_name = _node_config['exception_router']
            _router_para = _node_config.get('exception_router_para', {})
        elif status == 'S':
            _router_name = _node_config.get('router', '')
            _router_para = _node_config.get('router_para', {})

        # 登记记录
        self._context['trace_list'].append({
            'node_id': node_id,
            'node_name': _node_config.get('name', ''),
            'processor_name': _node_config['processor'],
            'start_time': self._context['start_time'],
            'end_time': datetime.datetime.now(),
            'status': status,
            'status_msg': status_msg,
            'router_name': _router_name
        })

        # 通知运行结束节点
        self.log_info('[Pipeline:%s]Running node [%s] end: status[%s] status_msg[%s]' %
                      (self.name, node_id, status, status_msg))
        if self.end_running_notify_fun is not None:
            self.end_running_notify_fun(
                self.name, node_id, _node_config.get('name', ''), status, status_msg
            )

        # 尝试获取下一个处理节点
        _next_id = None
        if status != 'S' and _router_name == '':
            # 异常，结束管道运行
            self._context['node_status'] = 'E'
            self._set_status('exception')
            self._output = None
        else:
            # 更新临时变量
            self._context['node_status'] = status
            self._current_input = output

            # 获取下一个节点
            if _router_name == '':
                # 没有设置路由器，按顺序获取下一个节点（已排除了异常情况）
                _temp_id = str(int(node_id) + 1)
                if _temp_id in self.pipeline.keys():
                    _next_id = _temp_id
            else:
                _router: PipelineRouter = self.get_plugin('router', _router_name)
                _next_id = _router.get_next(output, self._context, self, **_router_para)

            # 判断是否完结
            if _next_id is None:
                self._output = output
                self._set_status('success')

        # 异步情况通知结果
        if _next_id is None and self.is_asyn:
            self.asyn_notify_fun(self.name, self._status, self._context, self._output)

        return _next_id

    def _start_running_thread(self):
        """
        启动运行线程
        """
        # 启动运行线程
        _running_thread = threading.Thread(
            target=self._running_thread_fun,
            name='Thread-Pipeline-Running'
        )
        _running_thread.setDaemon(True)
        _running_thread.start()

    def _running_thread_fun(self):
        """
        启动管道运行线程
        """
        self._thread_running = True
        try:
            while self.status == 'running':
                if self._context['node_status'] == 'R':
                    # 当前节点正在执行，未返回执行结果
                    break

                # 执行当前节点
                _next_id = self._run_node(self._context['node_id'])
                if _next_id is None:
                    # 已经是最后一个节点
                    break
                elif _next_id == '':
                    # 异步模式，直接退出线程处理
                    break
                else:
                    # 设置上下文，执行下一个节点
                    self._context['node_id'] = _next_id
                    self._context['node_status'] = 'I'
                    time.sleep(0.0001)
        except:
            # 如果在线程中出了异常，结束掉执行
            self._context['node_status'] = 'E'
            self._set_status('exception')
            self._output = None
            raise
        finally:
            self._thread_running = False


if __name__ == '__main__':
    # 当程序自己独立运行时执行的操作
    # 打印版本信息
    print(('模块名：%s  -  %s\n'
           '作者：%s\n'
           '发布日期：%s\n'
           '版本：%s' % (__MOUDLE__, __DESCRIPT__, __AUTHOR__, __PUBLISH__, __VERSION__)))

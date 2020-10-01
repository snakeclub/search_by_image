#!/usr/bin/env python3
# -*- coding: UTF-8 -*-
# Copyright 2019 黎慧剑
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

"""
通用管道路由器模块
@module router
@file router.py
"""

import os
import sys
# 根据当前文件路径将包路径纳入，在非安装的情况下可以引用到
sys.path.append(os.path.abspath(os.path.join(
    os.path.dirname(__file__), os.path.pardir)))
from search_by_image.lib.pipeline import Tools, PipelineRouter


__MOUDLE__ = 'router'  # 模块名
__DESCRIPT__ = u'管道路由器模块'  # 模块描述
__VERSION__ = '0.1.0'  # 版本
__AUTHOR__ = u'黎慧剑'  # 作者
__PUBLISH__ = '2020.09.09'  # 发布日期


class GoToNode(PipelineRouter):
    """
    跳转到指定节点
    """
    @classmethod
    def router_name(cls) -> str:
        """
        路由器名称，唯一标识路由器

        @returns {str} - 当前路由器名称
        """
        return 'GoToNode'

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
        _goto_node_id = ''
        _goto_node_name = ''
        # 优先以context的参数进行处理
        if 'goto_node_id' in context.keys():
            _goto_node_id = str(context.pop('goto_node_id'))
        elif 'goto_node_name' in context.keys():
            _goto_node_name = context.pop('goto_node_name')

        # 尝试从管道参数中获取跳转参数
        if _goto_node_id == '' and _goto_node_name == '':
            if 'goto_node_id' in kwargs.keys():
                _goto_node_id = kwargs['goto_node_id']
            elif 'goto_node_name' in kwargs.keys():
                _goto_node_name = kwargs['goto_node_name']

        # 处理跳转
        if _goto_node_id != '':
            _next_id = _goto_node_id
        elif _goto_node_name != '':
            _next_id = Tools.get_node_id_by_name(_goto_node_name, pipeline_obj)
            if _next_id is None:
                raise RuntimeError(
                    'GoToNode Router Error: goto_node_name[%s] not found!' % _goto_node_name)
        else:
            raise RuntimeError(
                'GoToNode Router Error: goto para not found in context or pipeline para!')

        # 返回路由节点
        return _next_id


if __name__ == '__main__':
    # 当程序自己独立运行时执行的操作
    # 打印版本信息
    print(('模块名：%s  -  %s\n'
           '作者：%s\n'
           '发布日期：%s\n'
           '版本：%s' % (__MOUDLE__, __DESCRIPT__, __AUTHOR__, __PUBLISH__, __VERSION__)))

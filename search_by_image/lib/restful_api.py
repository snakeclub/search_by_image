#!/usr/bin/env python3
# -*- coding: UTF-8 -*-
# Copyright 2019 黎慧剑
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

"""
对外提供的restful api服务
@module restful_api
@file restful_api.py
"""

import os
import sys
import base64
import urllib
import json
import re
import random
import inspect
import traceback
import uuid
import datetime
from io import BytesIO
from functools import wraps
from flask import Flask, request, jsonify
from werkzeug.routing import Rule
from HiveNetLib.base_tools.run_tool import RunTool
from HiveNetLib.base_tools.file_tool import FileTool
from HiveNetLib.base_tools.string_tool import StringTool
# 根据当前文件路径将包路径纳入，在非安装的情况下可以引用到
sys.path.append(os.path.abspath(os.path.join(
    os.path.dirname(__file__), os.path.pardir, os.path.pardir)))
from search_by_image.lib.search import SearchEngine


__MOUDLE__ = 'restful_api'  # 模块名
__DESCRIPT__ = u'对外提供的restful api服务'  # 模块描述
__VERSION__ = '0.1.0'  # 版本
__AUTHOR__ = u'黎慧剑'  # 作者
__PUBLISH__ = '2020.06.17'  # 发布日期


class FlaskTool(object):
    """
    Flash工具类，提供路由，内容解析等通用处理功能
    """
    @classmethod
    def add_route_by_class(cls, app: Flask, class_objs: list):
        """
        通过类对象动态增加路由

        @param {Flask} app - 要增加服务的Flask应用
        @param {list} class_objs - Api类对象清单
        """
        for _class in class_objs:
            _class_name = _class.__name__
            # 遍历所有函数
            for _name, _value in inspect.getmembers(_class):
                if not _name.startswith('_') and callable(_value):
                    _endpoint = '%s.%s' % (_class_name, _name)
                    _route = '/api{$ver$}/%s/%s' % (_class_name, _name)
                    _methods = None
                    _ver = ''
                    _para_list = RunTool.get_function_parameter_defines(_value)
                    for _para in _para_list:
                        if _para['name'] == 'methods':
                            # 指定了处理方法
                            _methods = _para['default']
                        elif _para['name'] == 'ver':
                            # 有指定ver的入参，在路由api后面进行变更
                            _ver = '/<ver>'
                        else:
                            _type = ''
                            if _para['annotation'] == int:
                                _type = 'int:'
                            elif _para['annotation'] == float:
                                _type = 'float:'

                            _route = '%s/<%s%s>' % (_route, _type, _para['name'])

                    # 创建路由
                    app.url_map.add(
                        Rule(_route.replace('{$ver$}', _ver), endpoint=_endpoint, methods=_methods)
                    )
                    if _ver != '':
                        # 也支持不传入版本的情况
                        app.url_map.add(
                            Rule(_route.replace('{$ver$}', ''),
                                 endpoint=_endpoint, methods=_methods)
                        )

                    app.view_functions[_endpoint] = _value

    @classmethod
    def log(cls, func):
        """
        登记日志的修饰符
        """
        @wraps(func)
        def wrapper(*args, **kwargs):
            _fun_name = func.__name__
            _start_time = datetime.datetime.now()
            _loader = RunTool.get_global_var('SER_LOADER')
            _IP = request.remote_addr
            _trace_id = str(uuid.uuid1())
            _enconding = 'utf-8' if request.charset == '' else request.charset
            _len_max = 2000  # 打印长度的限制

            # 打印日志
            if _loader.logger and _loader.debug:
                _log_str = '[API-FUN:%s][IP:%s][INF-RECV][TRACE-API:%s]%s %s\n%s%s' % (
                    _fun_name, _IP, _trace_id, request.method, request.path,
                    str(request.headers),
                    str(request.data, encoding=_enconding) if (request.mimetype.startswith('text/') or request.mimetype in [
                        'application/json', 'application/xml']) and len(request.data) <= _len_max else ''
                )
                _loader.logger.debug(_log_str, extra={'callFunLevel': 1})

            # 执行函数
            _ret = func(*args, **kwargs)

            # 打印日志
            if _loader.logger and _loader.debug:
                _enconding = 'utf-8' if _ret.charset == '' else _ret.charset
                _log_str = '[API-FUN:%s][IP:%s][INF-RET][TRACE-API:%s][USE:%s]%s%s' % (
                    _fun_name, _IP, _trace_id, str(
                        (datetime.datetime.now() - _start_time).total_seconds()),
                    str(_ret.headers),
                    str(_ret.data, encoding=_enconding) if (_ret.mimetype.startswith('text/') or _ret.mimetype in [
                        'application/json', 'application/xml']) and len(_ret.data) < _len_max else ''
                )
                _loader.logger.debug(_log_str, extra={'callFunLevel': 1})
            return _ret
        return wrapper


#############################
# Restful Api 的实现类，只要定义了，通过FlaskTool加入到路由就可以完成接口的发布
# 规则如下：
#        1、每个非'_'开头的静态函数为一个对外API服务；
#        2、可以通过函数最后的methods参数指定api的动作，例如指定GET、POST等，例如['GET']、['GET', 'POST']
#        3、可以通过函数最后的ver参数指定api支持版本号，注意需要设置当调用不传入版本号时的默认值
#        4、函数的入参定义会反映到路由中（methods/ver参数除外）
#    例如：
#        Test(a:str, b:int, methods=['GET'], ver='0.5')会自动配置路由为：
#            Rule('/api/<ver>/ClassName/Test/<a>/<int:b>', endpoint='ClassName.Test', methods=['GET'])
#            Rule('/api/ClassName/Test/<a>/<int:b>', endpoint='ClassName.Test', methods=['GET'])
#        Test(a:str, b:int, methods=['GET'])会自动配置路由为：
#            Rule('/api/ClassName/Test/<a>/<int:b>', endpoint='ClassName.Test', methods=['GET'])
#    函数内部可以使用以下方法获取传入参数：
#        1、通过request.args['key']，获取'?key=value&key1=value1'这类的传参
#        2、通过request.json['key']，获取在body传入的json结构对应的key的值，例如
#            request.json['id']可以获取body中的“{"id": 1234, "info": "测试\\n一下"}” 的id的值
#            注意：报文头的Content-Type必须为application/json
#        3、通过request.files['file']，获取上传的文件
#    函数可以通过jsonify将python对象转换为json字符串返回到请求端
#############################

class SearchServer(object):
    """
    以图搜图搜索服务
    """

    #############################
    # 搜索相似图片
    #############################
    @classmethod
    @FlaskTool.log
    def SearchByUpload(cls, methods=['POST']):
        """
        通过上传文件方式搜索相似图片 (/api/SearchServer/SearchByUpload)
            在客户端需通过FormData模式传入文件和字典信息
            file : 要搜索的文件信息
            interface_seq_id : (可选)客户端序号，客户端可传入该值来支持异步调用
            pipeline : 指定使用的管道名(可选择pipeline_config配置中的管道)
            collection : 指定要搜索的分类，如不指定传入''字符串

        @return {str} - 返回回答的json字符串
            status : 处理状态
                00000 - 成功
                10001 - 没有指定上传文件
                2XXXX - 处理失败
            msg : 处理状态对应的描述
            match_images: 匹配的图片数组(已按匹配度排序), 每个图片的信息为导入图片的image_doc字典
                [
                    {
                        图片导入时的字典信息,
                        ...
                        'ids': {str} - Milvus的id
                        'score': {float} - 匹配分数
                        'distance': {float} - 欧氏距离
                        'collection': {str} - 图片分类
                    },
                    ...
                ]

        """
        _ret_json = {
            'interface_seq_id': '',
            'status': '00000',
            'msg': 'success',
            'match_images': []
        }
        _loader = RunTool.get_global_var('SER_LOADER')
        try:
            _ret_json['interface_seq_id'] = request.form.get('interface_seq_id', '')

            if 'file' not in request.files or request.files['file'].filename == '':
                _ret_json['status'] = '10001'
                _ret_json['msg'] = 'No file upload!'
                return jsonify(_ret_json)

            # 处理文件为二进制
            _file = request.files['file']
            _img_bytesio = BytesIO()
            _file.save(_img_bytesio)

            # 执行查询处理
            _ret_json['match_images'] = _loader.search_engine.search(
                _img_bytesio.getvalue(), request.form['pipeline'],
                init_collection=request.form.get('collection', '')
            )
        except:
            if _loader.logger:
                _loader.logger.error(
                    'Exception: %s' % traceback.format_exc(),
                    extra={'callFunLevel': 1}
                )
            _ret_json['status'] = '20001'
            _ret_json['msg'] = '上传文件异常'

        return jsonify(_ret_json)

    @classmethod
    @FlaskTool.log
    def SearchByBase64(cls, methods=['POST']):
        """
        通过上传Base64文件编码方式搜索相似图片 (/api/SearchServer/SearchByBase64)
            传入JSON信息如下：
            {
                file : 要搜索的文件Base64编码字符串
                interface_seq_id : (可选)客户端序号，客户端可传入该值来支持异步调用
                pipeline : 指定使用的管道名(可选择pipeline_config配置中的管道)
                collection : 指定要搜索的分类，如不指定传入''字符串
            }

        @return {str} - 返回回答的json字符串
            status : 处理状态
                00000 - 成功
                10001 - 没有指定上传文件
                2XXXX - 处理失败
            msg : 处理状态对应的描述
            match_images: 匹配的图片数组(已按匹配度排序), 每个图片的信息为导入图片的image_doc字典
                [
                    {
                        图片导入时的字典信息,
                        ...
                        'ids': {str} - Milvus的id
                        'score': {float} - 匹配分数
                        'distance': {float} - 欧氏距离
                        'collection': {str} - 图片分类
                    },
                    ...
                ]

        """
        _ret_json = {
            'interface_seq_id': '',
            'status': '00000',
            'msg': 'success',
            'match_images': []
        }
        _loader = RunTool.get_global_var('SER_LOADER')
        try:
            _ret_json['interface_seq_id'] = request.json.get('interface_seq_id', '')

            # Base64转为二进制
            _image = base64.b64decode(
                re.sub('^data:.*;base64,', '', request.json['file'])
            )

            # 执行查询处理
            _ret_json['match_images'] = _loader.search_engine.search(
                _image, request.json['pipeline'],
                init_collection=request.json.get('collection', '')
            )
        except:
            if _loader.logger:
                _loader.logger.error(
                    'Exception: %s' % traceback.format_exc(),
                    extra={'callFunLevel': 1}
                )
            _ret_json['status'] = '20001'
            _ret_json['msg'] = '上传文件异常'

        return jsonify(_ret_json)

    @classmethod
    @FlaskTool.log
    def SearchByUrl(cls, methods=['POST']):
        """
        通过上传文件Url方式搜索相似图片 (/api/SearchServer/SearchByUrl)
            传入JSON信息如下：
            {
                url : 要搜索的文件的Url地址
                interface_seq_id : (可选)客户端序号，客户端可传入该值来支持异步调用
                pipeline : 指定使用的管道名(可选择pipeline_config配置中的管道)
                collection : 指定要搜索的分类，如不指定传入''字符串
            }

        @return {str} - 返回回答的json字符串
            status : 处理状态
                00000 - 成功
                10001 - 没有指定上传文件
                2XXXX - 处理失败
            msg : 处理状态对应的描述
            match_images: 匹配的图片数组(已按匹配度排序), 每个图片的信息为导入图片的image_doc字典
                [
                    {
                        图片导入时的字典信息,
                        ...
                        'ids': {str} - Milvus的id
                        'score': {float} - 匹配分数
                        'distance': {float} - 欧氏距离
                        'collection': {str} - 图片分类
                    },
                    ...
                ]
        """
        _ret_json = {
            'interface_seq_id': '',
            'status': '00000',
            'msg': 'success',
            'match_images': []
        }
        _loader = RunTool.get_global_var('SER_LOADER')
        try:
            _ret_json['interface_seq_id'] = request.json.get('interface_seq_id', '')

            # 下载图片信息
            _image = urllib.request.urlopen(request.json['url']).read()

            # 执行查询处理
            _ret_json['match_images'] = _loader.search_engine.search(
                _image, request.json['pipeline'],
                init_collection=request.json.get('collection', '')
            )
        except:
            if _loader.logger:
                _loader.logger.error(
                    'Exception: %s' % traceback.format_exc(),
                    extra={'callFunLevel': 1}
                )
            _ret_json['status'] = '20001'
            _ret_json['msg'] = '上传文件异常'

        return jsonify(_ret_json)

    #############################
    # 图片搜索库维护
    #############################
    @classmethod
    @FlaskTool.log
    def ImportByUpload(cls, methods=['POST']):
        """
        通过上传文件方式导入图片信息 (/api/SearchServer/ImportByUpload)
            在客户端需通过FormData模式传入文件和字典信息
            file : 要导入图片文件
            interface_seq_id : (可选)客户端序号，客户端可传入该值来支持异步调用
            pipeline : 指定使用的管道名(可选择pipeline_config配置中的管道)
            collection : 指定要导入的分类，如不指定传入''字符串
            image_doc : 要传入的图片信息字典

        @return {str} - 返回回答的json字符串
            status : 处理状态
                00000 - 成功
                10001 - 没有指定上传文件
                2XXXX - 处理失败
            msg : 处理状态对应的描述
        """
        _ret_json = {
            'interface_seq_id': '',
            'status': '00000',
            'msg': 'success'
        }
        _loader = RunTool.get_global_var('SER_LOADER')
        try:
            _ret_json['interface_seq_id'] = request.form.get('interface_seq_id', '')

            if 'file' not in request.files or request.files['file'].filename == '':
                _ret_json['status'] = '10001'
                _ret_json['msg'] = 'No file upload!'
                return jsonify(_ret_json)

            # 处理文件为二进制
            _file = request.files['file']
            _img_bytesio = BytesIO()
            _file.save(_img_bytesio)

            # 执行导入处理
            _loader.search_engine.image_to_search_db(
                _img_bytesio.getvalue(), json.loads(request.form['image_doc']),
                request.form['pipeline'],
                init_collection=request.form.get('collection', '')
            )
        except:
            if _loader.logger:
                _loader.logger.error(
                    'Exception: %s' % traceback.format_exc(),
                    extra={'callFunLevel': 1}
                )
            _ret_json['status'] = '20001'
            _ret_json['msg'] = '上传文件异常'

        return jsonify(_ret_json)

    @classmethod
    @FlaskTool.log
    def ImportByBase64(cls, methods=['POST']):
        """
        通过上传Base64文件编码方式导入图片信息 (/api/SearchServer/ImportByBase64)
            传入JSON信息如下：
            {
                file : 要导入的文件Base64编码字符串
                interface_seq_id : (可选)客户端序号，客户端可传入该值来支持异步调用
                pipeline : 指定使用的管道名(可选择pipeline_config配置中的管道)
                collection : 指定要导入的分类，如不指定传入''字符串
                image_doc : 要传入的图片信息字典
            }

        @return {str} - 返回回答的json字符串
            status : 处理状态
                00000 - 成功
                10001 - 没有指定上传文件
                2XXXX - 处理失败
            msg : 处理状态对应的描述
        """
        _ret_json = {
            'interface_seq_id': '',
            'status': '00000',
            'msg': 'success'
        }
        _loader = RunTool.get_global_var('SER_LOADER')
        try:
            _ret_json['interface_seq_id'] = request.json.get('interface_seq_id', '')

            # Base64转为二进制
            _image = base64.b64decode(
                re.sub('^data:.*;base64,', '', request.json['file'])
            )

            # 执行导入处理
            _loader.search_engine.image_to_search_db(
                _image, request.form['image_doc'], request.form['pipeline'],
                init_collection=request.form.get('collection', '')
            )
        except:
            if _loader.logger:
                _loader.logger.error(
                    'Exception: %s' % traceback.format_exc(),
                    extra={'callFunLevel': 1}
                )
            _ret_json['status'] = '20001'
            _ret_json['msg'] = '上传文件异常'

        return jsonify(_ret_json)

    @classmethod
    @FlaskTool.log
    def ImportByUrl(cls, methods=['POST']):
        """
        通过上传文件Url方式导入图片信息 (/api/SearchServer/ImportByUrl)
            传入JSON信息如下：
            {
                url : 要导入的文件的Url地址
                interface_seq_id : (可选)客户端序号，客户端可传入该值来支持异步调用
                pipeline : 指定使用的管道名(可选择pipeline_config配置中的管道)
                collection : 指定要导入的分类，如不指定传入''字符串
                image_doc : 要传入的图片信息字典
            }

        @return {str} - 返回回答的json字符串
            status : 处理状态
                00000 - 成功
                10001 - 没有指定上传文件
                2XXXX - 处理失败
            msg : 处理状态对应的描述
        """
        _ret_json = {
            'interface_seq_id': '',
            'status': '00000',
            'msg': 'success'
        }
        _loader = RunTool.get_global_var('SER_LOADER')
        try:
            _ret_json['interface_seq_id'] = request.json.get('interface_seq_id', '')

            # 下载图片信息
            _image = urllib.request.urlopen(request.json['url']).read()

            # 执行导入处理
            _loader.search_engine.image_to_search_db(
                _image, request.form['image_doc'], request.form['pipeline'],
                init_collection=request.form.get('collection', '')
            )
        except:
            if _loader.logger:
                _loader.logger.error(
                    'Exception: %s' % traceback.format_exc(),
                    extra={'callFunLevel': 1}
                )
            _ret_json['status'] = '20001'
            _ret_json['msg'] = '上传文件异常'

        return jsonify(_ret_json)

    @classmethod
    @FlaskTool.log
    def RemoveImageDoc(cls, methods=['POST']):
        """
        删除已导入的图片信息
        传入JSON信息如下：
            {
                interface_seq_id : (可选)客户端序号，客户端可传入该值来支持异步调用
                collection : 要查询的分类信息
                field_name : 要查询的条件域名，如果不需要条件送null
                field_values : 要查询的条件清单，如果传入数组代表使用in条件，如果传入字符串代表使用=条件
            }

        @return {str} - 返回回答的json字符串
            status : 处理状态
                00000 - 成功
                2XXXX - 处理失败
            msg : 处理状态对应的描述
        """
        _ret_json = {
            'interface_seq_id': '',
            'status': '00000',
            'msg': 'success'
        }
        _loader = RunTool.get_global_var('SER_LOADER')
        try:
            _ret_json['interface_seq_id'] = request.json.get('interface_seq_id', '')

            # 执行删除处理
            _ret_json['images'] = _loader.search_engine.remove_images(
                request.json.get('field_name', None), request.json.get('field_values', None),
                request.json.get('collection', '')
            )
        except:
            if _loader.logger:
                _loader.logger.error(
                    'Exception: %s' % traceback.format_exc(),
                    extra={'callFunLevel': 1}
                )
            _ret_json['status'] = '20001'
            _ret_json['msg'] = '处理异常'

        return jsonify(_ret_json)

    @classmethod
    @FlaskTool.log
    def GetImageDoc(cls, methods=['POST']):
        """
        获取已导入的图片信息
        传入JSON信息如下：
            {
                interface_seq_id : (可选)客户端序号，客户端可传入该值来支持异步调用
                collection : 要查询的分类信息
                field_name : 要查询的条件域名，如果不需要条件送null
                field_values : 要查询的条件清单，如果传入数组代表使用in条件，如果传入字符串代表使用=条件
                page_size ：分页大小
                page_num : 第几页 ，从1开始
            }

        @return {str} - 返回回答的json字符串
            status : 处理状态
                00000 - 成功
                2XXXX - 处理失败
            msg : 处理状态对应的描述
            images: 查询到的图片数组, 每个图片的信息为导入图片的image_doc字典
                [
                    {
                        图片导入时的字典信息,
                        ...
                        'collection': {str} - 图片分类
                    },
                    ...
                ]
        """
        _ret_json = {
            'interface_seq_id': '',
            'status': '00000',
            'msg': 'success',
            'images': []
        }
        _loader = RunTool.get_global_var('SER_LOADER')
        try:
            _ret_json['interface_seq_id'] = request.json.get('interface_seq_id', '')

            # 执行查询处理
            _ret_json['images'] = _loader.search_engine.get_images(
                request.json.get('field_name', None), request.json.get('field_values', None),
                request.json.get('collection', ''),
                request.json.get('page_size', 15), request.json.get('page_num', 1)
            )

            for _item in _ret_json['images']:
                # 删除非json字段
                del _item['_id']
        except:
            if _loader.logger:
                _loader.logger.error(
                    'Exception: %s' % traceback.format_exc(),
                    extra={'callFunLevel': 1}
                )
            _ret_json['status'] = '20001'
            _ret_json['msg'] = '查询异常'

        return jsonify(_ret_json)


if __name__ == '__main__':
    # 当程序自己独立运行时执行的操作
    # 打印版本信息
    print(('模块名：%s  -  %s\n'
           '作者：%s\n'
           '发布日期：%s\n'
           '版本：%s' % (__MOUDLE__, __DESCRIPT__, __AUTHOR__, __PUBLISH__, __VERSION__)))

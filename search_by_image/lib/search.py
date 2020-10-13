#!/usr/bin/env python3
# -*- coding: UTF-8 -*-
# Copyright 2019 黎慧剑
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

"""
搜索服务引擎
@module search
@file search.py
"""

import os
import sys
import copy
import json
import traceback
from HiveNetLib.base_tools.file_tool import FileTool
# 根据当前文件路径将包路径纳入，在非安装的情况下可以引用到
sys.path.append(os.path.abspath(os.path.join(
    os.path.dirname(__file__), os.path.pardir, os.path.pardir)))
from search_by_image.lib.pipeline import Pipeline
from search_by_image.lib.storage import MongoStorage, MilvusIns


__MOUDLE__ = 'search'  # 模块名
__DESCRIPT__ = u'搜索服务引擎'  # 模块描述
__VERSION__ = '0.1.0'  # 版本
__AUTHOR__ = u'黎慧剑'  # 作者
__PUBLISH__ = '2020.08.27'  # 发布日期


class SearchEngine(object):
    """
    搜索服务引擎
    """

    def __init__(self, server_config: dict, logger=None):
        # 基础参数
        self.logger = logger  # 日志对象
        self.search_config = copy.deepcopy(server_config['search_config'])
        self.pipeline_config = copy.deepcopy(server_config['pipeline']['pipeline_config'])
        self.app_name = self.search_config['app_name']
        self.database = server_config['mongodb'].get('authSource', self.app_name)

        # 数据存储对象
        self.mongo_db = MongoStorage(server_config['mongodb'])
        self.milvus_db = MilvusIns(server_config['milvus'], logger=logger)

        # 创建milvus和mongodb要使用的集合
        self._create_collections()

    #############################
    # 图片搜索
    #############################

    def search(self, image_data: bytes, pipeline: str, init_collection: str = '') -> list:
        """
        搜索指定图片的相似图片信息

        @param {bytes} image_data - 影像内容二进制数据
        @param {str} pipeline - 处理管道标识
        @param {str} init_collection='' - 默认集合名，用于传入管道进行处理

        @returns {list} - 返回相似图片文档信息
        """
        # 获取当前图片的特征向量
        _collection, _vertor = self._get_image_vertor(
            image_data, self._get_pipeline(pipeline), init_collection=init_collection
        )

        # 查询匹配的特征向量
        _ids = self.milvus_db.search_vectors(
            f'{self.app_name}_{_collection}', [_vertor.tolist(), ], topk=self.search_config['topk'],
            nprobe=self.search_config['nprobe']
        )

        if len(_ids) == 0:
            # 没有找到任何匹配项
            return []

        # 选取匹配项
        _ids_dict = {}
        for _match in _ids[0]:
            _score = 1.0 / (1.0 + _match.distance)
            if _score >= self.search_config['match_score']:
                _ids_dict[_match.id] = {
                    'score': _score,
                    'distance': _match.distance
                }

        # 查询图片信息
        _images = self.mongo_db.search_by_vector_id(
            self.database, _collection, list(_ids_dict.keys())
        )

        # 补充距离信息
        for _index in range(len(_images)):
            # 转换为相似度
            _id = _images[_index]['ids']
            _images[_index]['score'] = _ids_dict[_id]['score']
            _images[_index]['distance'] = _ids_dict[_id]['distance']
            _images[_index]['collection'] = _collection
            # 删除_id这个非json对象
            del _images[_index]['_id']

        # 进行排序
        _images.sort(key=lambda x: x['distance'])

        return _images

    #############################
    # 搜索库处理函数
    #############################

    def image_to_search_db(self, image_data: bytes, image_doc: dict, pipeline: str, init_collection: str = ''):
        """
        将图片插入搜索库

        @param {bytes} image_data - 影像内容二进制数据
        @param {dict} image_doc - 图片信息字典
        @param {str} pipeline - 处理管道标识
        @param {str} init_collection='' - 默认集合名，用于传入管道进行处理

        @returns {str, str} - 返回 mongodb_id, collection
        """
        return self._image_to_search_db(
            image_data, image_doc, self._get_pipeline(pipeline),
            init_collection=init_collection
        )

    def import_images(self, path: str, pipeline: str, encoding: str = 'utf-8'):
        """
        将指定路径的图片导入搜索库

        @param {str} path - 图片及信息字典所在路径，包含文件:
            图片文件，例如"abc.jpg"
            对应的json信息字典文件，例如"abc.json"，文件内容按标准json字符串格式编写
            注：json中可以通过添加collection域指定该图片的所属分类集合名
        @param {str} pipeline - 处理管道标识
        @param {str} encoding='utf-8' - json文件的编码
        """
        _pipeline_obj = self._get_pipeline(pipeline)
        _file_list = FileTool.get_filelist(path, regex_str=r'^((?!\.json$).)*$', is_fullname=True)
        for _file in _file_list:
            try:
                # 获取图片的信息字典
                _ext = FileTool.get_file_ext(_file)
                _json_file = _file[0: -len(_ext)] + 'json'
                if not os.path.exists(_json_file):
                    self.log_debug('Json file not exists, not imported: [%s]!' % _file)
                    continue

                with open(_json_file, 'r', encoding=encoding) as _fid:
                    _image_doc = json.loads(_fid.read())

                # 导入图片
                _collection = _image_doc.get('collection', '')
                with open(_file, 'rb') as _fid:
                    self._image_to_search_db(
                        _fid.read(), _image_doc, _pipeline_obj, init_collection=_collection
                    )

                # 输出日志
                self.log_debug('image [%s] imported success' % _file)
            except:
                self.log_debug('image [%s] import error: %s' % (_file, traceback.format_exc()))

    def get_images(self, field_name: str, field_values: list, collection: str = '',
                   page_size: int = 15, page_num: int = 1) -> list:
        """
        获取图片信息

        @param {str} field_name - image_doc字典的字段名，如果不需要筛选传None
        @param {list|str} field_values - 要匹配的字段值清单,list时用in模式，str时用=模式
        @param {str} collection='' - 是否指定分类
        @param {int} page_size=15 - 分页每页大小, 如果不分页，传0
        @param {int} page_num=1 - 第几页，从1开始

        @returns {list} - image_doc字典清单
        """
        if collection != '':
            # 指定集合清单的情况，直接查询返回即可
            _res = self.mongo_db.search_by_field(
                self.database, collection, field_name, field_values,
                page_size=page_size, page_num=page_num
            )
            # 补充所属集合信息
            for _index in range(len(_res)):
                _res[_index]['collection'] = collection
        else:
            # 获取集合清单
            _collections = self.search_config['collections'].split(',')
            _res = []
            _skip = page_size * (page_num - 1)
            _get_size = page_size
            for _collection in _collections:
                _collection = _collection.strip()
                if page_size <= 0:
                    # 不分页
                    _temp_res = self.mongo_db.search_by_field(
                        self.database, _collection, field_name, field_values,
                        page_size=page_size, page_num=page_num
                    )
                else:
                    if _get_size <= 0:
                        # 不需要再获取数据，跳出循环
                        break

                    _count = self.mongo_db.count_by_field(
                        self.database, _collection, field_name, field_values
                    )

                    if _count < _skip:
                        # 数据在需要跳过的范围，不取数据
                        _skip -= _count
                        continue

                    # 获取数据
                    _temp_res = self.mongo_db.search_with_skip(
                        self.database, _collection, field_name, field_values,
                        _skip, _get_size
                    )

                    _get_size -= len(_temp_res)

                # 补充所属集合信息
                for _index in range(len(_temp_res)):
                    _temp_res[_index]['collection'] = _collection

                _res.extend(_temp_res)

        # 返回结果
        return _res

    def remove_images(self, field_name: str, field_values: list, collection: str = ''):
        """
        删除已导入的图片信息

        @param {str} field_name - image_doc字典的字段名，如果不需要筛选传None
        @param {list|str} field_values - 要匹配的字段值清单,list时用in模式，str时用=模式
        @param {str} collection='' - 是否指定分类
        """
        _images = self.get_images(
            field_name, field_values, collection=collection,
            page_size=0
        )
        for _image_doc in _images:
            # 删除特征向量
            self.milvus_db.del_vectors(
                f"{self.app_name}_{_image_doc['collection']}", [_image_doc['ids'], ]
            )

            # 删除mongodb
            self.mongo_db.delete_by_id(
                self.database, _image_doc['collection'], str(_image_doc['_id'])
            )

            self.log_debug('delete image_doc success: %s' % str(_image_doc))

    def clear_search_db(self):
        """
        清空搜索库的信息
        """
        # 清理milvus向量数据
        _collections = self.milvus_db.list_collection()
        _del_list = []
        for _collection in _collections:
            if _collection.startswith(f'{self.app_name}_'):
                _del_list.append(_collection)

        if len(_del_list) > 0:
            self.milvus_db.del_collections(_del_list)
            self.log_debug('clear milvus collections: %s' % str(_del_list))

        # 清理mongodb数据库
        _collections = self.mongo_db.list_collection(self.database)
        self.mongo_db.delete_collections(self.database, _collections)
        self.log_debug('clear mongodb [%s] collections' % self.database)

        # 重新创建集合
        self._create_collections()

    #############################
    # 内部函数
    #############################

    def _get_pipeline(self, pipeline: str) -> Pipeline:
        """
        获取可用的管道对象

        @param {str} pipeline - 处理管道标识

        @returns {Pipeline} - 返回管道对象
        """
        return Pipeline(
            pipeline, self.pipeline_config[pipeline], is_asyn=False, logger=self.logger
        )

    def _get_image_vertor(self, image_data: bytes, pipeline_obj: Pipeline, init_collection: str = ''):
        """
        获取影像的特征向量

        @param {bytes} image_data - 影像内容二进制数据
        @param {Pipeline} pipeline_obj - 可用管道对象
        @param {str} init_collection='' - 指定默认的分类

        @returns {str, numpy.ndarray} - 匹配到的影像分类, 特征向量
        """
        _input = {
            'image': image_data,
            'collection': init_collection
        }

        _status, _output = pipeline_obj.start(
            _input, {}
        )

        if _status != 'success':
            raise RuntimeError('Pipeline run error: status [%s]!' % _status)

        _collection = self.search_config['default_collection'] if _output['collection'] == '' else _output['collection']

        return _collection, _output['vertor']

    def _image_to_search_db(self, image_data: bytes, image_doc: dict, pipeline_obj: Pipeline, init_collection: str = ''):
        """
        将图片插入搜索库

        @param {bytes} image_data - 影像内容二进制数据
        @param {dict} image_doc - 图片信息字典
        @param {Pipeline} pipeline_obj - 可用管道对象
        @param {str} init_collection='' - 默认集合名，用于传入管道进行处理

        @returns {str, str} - 返回 mongodb_id, collection
        """
        # 先获取图片所属数据集和向量
        _collection, _vertor = self._get_image_vertor(
            image_data, pipeline_obj, init_collection=init_collection
        )

        # 将图片特征向量存入Mivlus（待确认，是否需要进行变量的加工处理）
        _vids = self.milvus_db.insert_vectors(
            f'{self.app_name}_{_collection}', [_vertor.tolist(), ]
        )

        # 将影像信息存入MongoDB
        image_doc['ids'] = _vids[0]
        return self.mongo_db.insert_document(self.database, _collection, image_doc), _collection

    def _create_collections(self):
        """
        创建milvus和mongodb要使用的集合
        """
        _collections = self.search_config['collections'].split(',')
        _milvus_collections = []
        _mongo_collections = []
        for _collection in _collections:
            _collection = _collection.strip()
            # Mivlus
            _milvus_collections.append(f'{self.app_name}_{_collection}')
            # Mongo
            _mongo_collections.append(_collection)

        self.milvus_db.add_collections(_milvus_collections)
        self.mongo_db.new_collections(self.database, _mongo_collections)

    #############################
    # 日志输出相关函数
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


if __name__ == '__main__':
    # 当程序自己独立运行时执行的操作
    # 打印版本信息
    print(('模块名：%s  -  %s\n'
           '作者：%s\n'
           '发布日期：%s\n'
           '版本：%s' % (__MOUDLE__, __DESCRIPT__, __AUTHOR__, __PUBLISH__, __VERSION__)))

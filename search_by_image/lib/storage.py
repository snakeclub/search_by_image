#!/usr/bin/env python3
# -*- coding: UTF-8 -*-
# Copyright 2019 黎慧剑
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

"""
数据存储处理
@module storage
@file storage.py
"""

import os
import sys
import copy
import milvus as mv
from pymongo import MongoClient
from gridfs import GridFS
from bson import ObjectId
# 根据当前文件路径将包路径纳入，在非安装的情况下可以引用到
sys.path.append(os.path.abspath(os.path.join(
    os.path.dirname(__file__), os.path.pardir, os.path.pardir)))


__MOUDLE__ = 'storage'  # 模块名
__DESCRIPT__ = u'数据存储处理'  # 模块描述
__VERSION__ = '0.1.0'  # 版本
__AUTHOR__ = u'黎慧剑'  # 作者
__PUBLISH__ = '2020.08.26'  # 发布日期


class MongoStorage(object):
    """
    MongoDB的存储驱动
    """

    def __init__(self, connect_para: dict):
        """
        构造函数

        @param {dict} connect_para - 数据存储初始化参数, MongoClient的入参
            参考地址：https://pymongo.readthedocs.io/en/stable/api/pymongo/mongo_client.html#pymongo.mongo_client.MongoClient
            host {str} - 数据库地址
            port {int} - 数据库端口，默认27017
            username {str} - 登陆用户名
            password {str} - 登陆密码
            maxPoolSize {int} - 连接池最大数量，默认100
            minPoolSize {int} - 连接池最小数量，默认0
        """
        self.db = MongoClient(**connect_para)

    def list_collection(self, database: str):
        """
        获取集合（表）清单

        @param {str} database - 数据库名

        @returns {list} - 清单名
        """
        _database = self.db[database]
        return _database.list_collection_names()

    def new_collections(self, database: str, collections: list):
        """
        新增集合(table)

        @param {str} database - 数据库名
        @param {list} collections - 集合名列表(str)
        """
        _database = self.db[database]
        for collection in collections:
            if not self.collection_exists(database, collection):
                _database.create_collection(collection)

    def delete_collections(self, database: str, collections: list):
        """
        删除集合(table)

        @param {str} database - 数据库名
        @param {list} collections - 集合名列表(str)
        """
        _database = self.db[database]
        for collection in collections:
            if self.collection_exists(database, collection):
                _database.drop_collection(collection)

    def collection_exists(self, database: str, collection: str) -> bool:
        """
        判断集合是否存在

        @param {str} database - 数据库名
        @param {str} collection - 要判断的集合

        @returns {bool} - 是否存在
        """
        _database = self.db[database]
        if collection in _database.list_collection_names():
            return True
        return False

    def insert_file(self, database: str, collection: str, filename: str, file_data: bytes) -> str:
        """
        保存文件

        @param {str} database - 文件保存到的数据库名
        @param {str} collection - 文件保存到的集合名（table）
        @param {str} filename - 文件名
        @param {bytes} file_data - 文件二进制内容

        @returns {str} - 保存后的文件ID
        """
        _fs = GridFS(self.db[database], collection)
        _object_id = _fs.put(file_data, filename=filename)
        return str(_object_id)

    def get_file_id(self, database: str, collection: str, filename: str) -> str:
        """
        通过文件名获取文件id

        @param {str} database - 文件保存到的数据库名
        @param {str} collection - 文件保存到的集合名（table）
        @param {str} filename - 文件名

        @returns {str} - 保存后的文件ID
        """
        _fs = GridFS(self.db[database], collection)
        _object_id = _fs.find_one({'filename': filename})._id
        return str(_object_id)

    def get_file(self, database: str, collection: str, obj_id: str):
        """
        获取文件内容

        @param {str} database - 文件保存到的数据库名
        @param {str} collection - 文件保存到的集合名（table）
        @param {str} obj_id - 文件id

        @returns {bytes, dict} - 文件内容, 文件属性字典
            属性字典包括：
                filename {str} 文件名
                size {int} 文件大小
                md5 {str} 文件的md5值
                createtime {datetime} - 创建时间
        """
        _fs = GridFS(self.db[database], collection)
        _gf = _fs.get(ObjectId(obj_id))
        _file_data = _gf.read()  # 文件二进制数据
        _attri = {}  # 文件属性信息
        _attri["filename"] = _gf.filename
        _attri['size'] = _gf.length
        _attri['md5'] = _gf.md5
        _attri["createtime"] = _gf.upload_date

        return _file_data, _attri

    def delete_file(self, database: str, collection: str, obj_id: str):
        """
        删除文件

        @param {str} database - 文件保存到的数据库名
        @param {str} collection - 文件保存到的集合名（table）
        @param {str} obj_id - 文件id
        """
        _fs = GridFS(self.db[database], collection)
        _fs.delete(ObjectId(obj_id))  # 只能是id

    def insert_document(self, database: str, collection: str, doc: dict) -> str:
        """
        插入文档

        @param {str} database - 数据库名
        @param {str} collection - 集合名（table）
        @param {dict} doc - 要插入文档记录

        @returns {str} - 记录ID
        """
        return self.db[database][collection].insert_one(doc).inserted_id

    def search_by_id(self, database: str, collection: str, obj_id: str):
        """
        通过id获取文档

        @param {str} database - 数据库名
        @param {str} collection - 集合名（table）
        @param {str} obj_id - 文档id
        """
        return self.db[database][collection].find({"_id": ObjectId(obj_id)}).limit(1)

    def delete_by_id(self, database: str, collection: str, obj_id: str):
        """
        通过id删除文档

        @param {str} database - 数据库名
        @param {str} collection - 集合名（table）
        @param {str} obj_id - 文档id
        """
        return self.db[database][collection].delete_many({"_id": ObjectId(obj_id)})

    def search_by_vector_id(self, database: str, collection: str, ids: list) -> list:
        """
        通过向量id清单获取文档清单

        @param {str} database - 数据库名
        @param {str} collection - 集合名（table）
        @param {list} ids - milvus_id清单

        @returns {list} - 获取到的文档清单
        """
        _res = self.db[database][collection].find({"ids": {"$in": ids}})
        return list(_res)

    def search_by_field(self, database: str, collection: str, field_name: str, field_values: list,
                        page_size: int = 0, page_num: int = 1) -> list:
        """
        根据指定域值查找数据

        @param {str} database - 数据库名
        @param {str} collection - 集合名（table）
        @param {str} field_name - 域名，如果为None则代表不加条件查询
        @param {list|str} field_values - 要查找的域值，如果是list则用in模式, 如果为字符则为=模式
        @param {int} page_size=15 - 分页每页大小, 如果不分页，传0
        @param {int} page_num=1 - 第几页，从1开始

        @returns {list} - 获取到的文档清单
        """
        _filter = None
        if field_name is not None:
            _filter = {
                field_name: field_values if type(field_values) == str else {"$in": field_values}
            }

        if page_size <= 0:
            _res = self.db[database][collection].find(filter=_filter)
        else:
            # 分页处理
            _skip = page_size * (page_num - 1)
            _res = self.db[database][collection].find(filter=_filter).skip(_skip).limit(page_size)

        return list(_res)

    def delete_by_field(self, database: str, collection: str, field_name: str, field_values: list):
        """
        通过域值删除数据

        @param {str} database - 数据库名
        @param {str} collection - 集合名（table）
        @param {str} field_name - 域名，如果为None则代表不加条件查询
        @param {list|str} field_values - 要查找的域值，如果是list则用in模式, 如果为字符则为=模式
        """
        _filter = None
        if field_name is not None:
            _filter = {
                field_name: field_values if type(field_values) == str else {"$in": field_values}
            }
        return self.db[database][collection].delete_many(filter=_filter)

    def count_by_field(self, database: str, collection: str, field_name: str, field_values: list):
        """
        查询记录数量

        @param {str} database - 数据库名
        @param {str} collection - 集合名（table）
        @param {str} field_name - 域名，如果为None则代表不加条件查询
        @param {list|str} field_values - 要查找的域值，如果是list则用in模式, 如果为字符则为=模式

        @returns {int} - 返回记录数
        """
        if field_name is not None:
            _filter = {
                field_name: field_values if type(field_values) == str else {"$in": field_values}
            }
            return self.db[database][collection].count_documents(_filter)
        else:
            return self.db[database][collection].estimated_document_count()

    def search_with_skip(self, database: str, collection: str, field_name: str, field_values: list,
                         skip: int, size: int):
        """
        获取指定条件记录，并指定跳过数量和获取记录大小

        @param {str} database - 数据库名
        @param {str} collection - 集合名（table）
        @param {str} field_name - 域名，如果为None则代表不加条件查询
        @param {list|str} field_values - 要查找的域值，如果是list则用in模式, 如果为字符则为=模式
        @param {int} skip - 要跳过的数量
        @param {int} size - 要获取的大小
        @returns {list} - 获取到的文档清单
        """
        _filter = None
        if field_name is not None:
            _filter = {
                field_name: field_values if type(field_values) == str else {"$in": field_values}
            }
        _res = self.db[database][collection].find(filter=_filter).skip(skip).limit(size)

        return list(_res)


class MilvusIns(object):
    """
    Milvus的操作类
    """

    def __init__(self, milvus_para: dict, logger=None):
        """
        构造函数

        @param {dict} milvus_para - Milvus服务连接参数，server.xml的milvus配置
        @param {bool} logger=None - 日志对象
        """
        self.logger = logger
        self.milvus_para = copy.deepcopy(milvus_para)
        self.index_file_size = self.milvus_para.get('index_file_size', 1024)
        self.dimension = self.milvus_para.get('dimension', 2048)
        self.metric_type = eval('mv.MetricType.%s' % self.milvus_para.get('metric_type', 'L2'))

    #############################
    # 工具函数
    #############################
    def confirm_milvus_status(self, status: mv.Status, fun_name: str):
        """
        确认milvus执行结果，如果失败抛出异常

        @param {mv.Status} status - 执行结果
        @param {str} fun_name - 执行函数名
        """
        if status.code != 0:
            raise RuntimeError('execute milvus.%s error: %s' % (fun_name, str(status)))

    def get_milvus(self) -> mv.Milvus:
        """
        获取可用的milvus连接对象

        @returns {Milvus} - 返回要使用的Milvus对象
        """
        return mv.Milvus(
            host=self.milvus_para['host'], port=self.milvus_para['port'],
            pool=self.milvus_para.get('pool', 'SingletonThread')
        )

    #############################
    # 处理函数
    #############################
    def list_collection(self) -> list:
        """
        获取集合清单

        @returns {list} - 返回集合清单
        """
        with self.get_milvus() as _milvus:
            _status, _list = _milvus.list_collections()
            self.confirm_milvus_status(_status, 'list_collections')

            return _list

    def add_collections(self, collections: list):
        """
        新增Milvus集合

        @param {list} collection - 集合名列表(str)
        """
        with self.get_milvus() as _milvus:
            for _collection in collections:
                _status, _exists = _milvus.has_collection(_collection)
                self.confirm_milvus_status(_status, 'has_collection')

                if not _exists:
                    _param = {
                        "collection_name": _collection,
                        "dimension": self.dimension,
                        "index_file_size": self.index_file_size,
                        "metric_type": self.metric_type
                    }
                    self.confirm_milvus_status(
                        _milvus.create_collection(_param), 'create_collection'
                    )

                    self._log_debug('added Milvus collection [%s]' % _collection)

    def del_collections(self, collections: list, truncate: bool = False):
        """
        删除Milvus集合

        @param {list} collections - 集合名列表(str)
        @param {bool} truncate=False - 是否删除所有集合
        """
        with self.get_milvus() as _milvus:
            if truncate:
                # 清空所有
                _status, _clist = _milvus.list_collections()
                self.confirm_milvus_status(_status, 'list_collections')
            else:
                # 只清空传入列表
                _clist = []
                for _collection in collections:
                    _status, _exists = _milvus.has_collection(_collection)
                    self.confirm_milvus_status(_status, 'has_collection')
                    if _exists:
                        _clist.append(_collection)

            # 开始清除操作
            for _collection in _clist:
                self.confirm_milvus_status(
                    _milvus.drop_collection(_collection), 'drop_collection'
                )
                self._log_debug('deleted Milvus collection [%s]' % _collection)

    def insert_vectors(self, collection: str, vectors: list) -> list:
        """
        插入向量

        @param {str} collection - 集合名
        @param {list} vectors - 多个要插入的向量列表

        @returns {list} - 插入的每个向量的 milvus id 列表
        """
        with self.get_milvus() as _milvus:
            _status, _milvus_ids = _milvus.insert(collection_name=collection, records=vectors)
            self.confirm_milvus_status(_status, 'insert')
            self._log_debug('insert _milvus_ids: %s' % str(_milvus_ids))
            return _milvus_ids

    def search_vectors(self, collection: str, vector, topk: int = 10, nprobe: int = 16):
        """
        搜索匹配变量

        @param {str} collection - 集合名
        @param {list} vector - 变量对象数组
        @param {int} topk=10 - 获取最近匹配的数量
        @param {int} nprobe=16 - 查的单元数量(cell number of probe)

        @returns {list} - 返回匹配上的特征向量清单
        """
        with self.get_milvus() as _milvus:
            _search_param = {'nprobe': nprobe}
            _status, _milvus_ids = _milvus.search(collection_name=collection, query_records=vector,
                                                  top_k=topk, params=_search_param)
            self.confirm_milvus_status(_status, 'search')
            return _milvus_ids

    def del_vectors(self, collection: str, ids: list):
        """
        删除向量

        @param {str} collection - 集合名
        @param {list} ids - 要删除的 milvus id 列表
        """
        with self.get_milvus() as _milvus:
            _milvus.delete_entity_by_id(collection_name=collection, id_array=ids)
            self._log_debug('delete [%s] _milvus_ids: %s' % (collection, str(ids)))

    #############################
    # 日志输出相关函数
    #############################
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

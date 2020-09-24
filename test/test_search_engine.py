#!/usr/bin/env python3
# -*- coding: UTF-8 -*-

"""
测试搜索引擎
@module test_search_engine
@file test_search_engine.py
"""

import os
import sys
import json
import math
from io import BytesIO
from PIL import Image, ImageDraw, ImageFont
import matplotlib
# matplotlib.use('agg')
from matplotlib import pyplot as plt
from HiveNetLib.simple_xml import SimpleXml
from HiveNetLib.simple_log import Logger
from HiveNetLib.base_tools.run_tool import RunTool
from HiveNetLib.base_tools.file_tool import FileTool
from HiveNetLib.base_tools.string_tool import StringTool
# 根据当前文件路径将包路径纳入，在非安装的情况下可以引用到
sys.path.append(os.path.abspath(os.path.join(
    os.path.dirname(__file__), os.path.pardir)))
from search_by_image.lib.pipeline import Pipeline
from search_by_image.lib.search import SearchEngine


class TestSearchEngine(object):
    """
    测试搜索引擎
    """

    def __init__(self):
        """
        初始化测试参数
        """
        # 获取配置
        self.execute_path = os.path.realpath(os.path.join(
            os.path.dirname(__file__), os.path.pardir, 'search_by_image'
        ))
        RunTool.set_global_var('EXECUTE_PATH', self.execute_path)

        _config = os.path.join(self.execute_path, 'conf/server_jade.xml')
        _config_xml = SimpleXml(_config, encoding='utf-8')
        self.server_config = _config_xml.to_dict()['server']

        # 装载管道插件
        RunTool.set_global_var(
            'PIPELINE_PROCESSER_PARA', self.server_config['pipeline']['processer_para']
        )
        RunTool.set_global_var('PIPELINE_ROUTER_PARA',
                               self.server_config['pipeline']['router_para'])
        _plugins_path_list = self.server_config['pipeline']['plugins_path'].split(',')
        for _plugins_path in _plugins_path_list:
            Pipeline.load_plugins_by_path(
                os.path.join(self.execute_path, _plugins_path.strip())
            )

        # 日志对象
        self.logger: Logger = None
        if 'logger' in self.server_config.keys():
            _logger_config = self.server_config['logger']
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

        # 创建搜索引擎
        self.search_engine = SearchEngine(self.server_config, logger=self.logger)

    #############################
    # 测试函数
    #############################
    def test_import_images(self, path: str, pipeline: str, url_prefix: str):
        """
        测试插入图片

        @param {str} path - 要处理的图片路径
        @param {str} pipeline - 管道标识
        """
        # 先尝试增加信息字典文件
        self._add_images_doc(path, path, url_prefix)

        # 逐个目录进行文件导入
        self._import_images(path, pipeline)

    def test_search_image(self, path: str, pipeline: str):
        """
        测试匹配图片

        @param {str} path - 要测试图片所在目录
        @param {str} pipeline - 管道标识
        """
        _file_list = FileTool.get_filelist(path)
        for _file in _file_list:
            with open(_file, 'rb') as _fid:
                _matchs = self.search_engine.search(
                    _fid.read(), pipeline
                )

            # 打印信息
            print('Search File: %s' % _file)

            # 计算结果有多少行
            _line_count = math.ceil(len(_matchs) / 3) + 1

            # 展示出来
            _image = Image.open(_file)
            plt.subplot(_line_count, 3, 2)
            plt.imshow(_image)
            plt.title('source pic')
            plt.xticks([])
            plt.yticks([])

            _index = 1
            for _image_doc in _matchs:
                print('Match: %s' % str(_image_doc))
                _image_file = _image_doc['path']
                _image = Image.open(_image_file)
                plt.subplot(_line_count, 3, _index + 3)
                plt.imshow(_image)
                plt.title(
                    'match %d: %.2f, %.3f' %
                    (_index, _image_doc['distance'], _image_doc['score'])
                )
                plt.xticks([])
                plt.yticks([])

                _index += 1

            plt.show()

    #############################
    # 工具函数
    #############################
    @classmethod
    def rename_file_to_num(cls, path: str, start_index: int = 1) -> int:
        """
        重命名文件为数字序号

        @param {str} path - 要处理的文件夹
        @param {int} start_index=1 - 开始序号

        @returns {int} - 返回当前序号
        """
        # 处理当前目录
        _start_index = start_index
        _path = os.path.realpath(path)
        _file_list = FileTool.get_filelist(_path, is_fullname=False)
        for _file in _file_list:
            _ext = FileTool.get_file_ext(_file)
            os.rename(
                os.path.join(_path, _file),
                os.path.join(_path, StringTool.fill_fix_string(
                    str(_start_index), 10, '0') + '.' + _ext)
            )
            _start_index += 1

        # 处理子目录
        _sub_dir_list = FileTool.get_dirlist(_path)
        for _sub_dir in _sub_dir_list:
            _start_index = cls.rename_file_to_num(_sub_dir, start_index=_start_index)

        # 返回当前序号值
        return _start_index

    @classmethod
    def test_images_show(cls, path: str):
        """
        测试图片显示

        @param {str} path - 图片目录
        """
        _file_list = FileTool.get_filelist(path)
        _image = Image.open(_file_list[0])
        plt.subplot(2, 2, 3)
        plt.imshow(_image)
        plt.title('source pic 1-1')
        plt.xticks([])
        plt.yticks([])

        plt.subplot(4, 3, 7)
        plt.imshow(_image)
        plt.title('source pic 2-1')
        plt.xticks([])
        plt.yticks([])

        plt.subplot(4, 3, 8)
        plt.imshow(_image)
        plt.title('source pic 2-2')
        plt.xticks([])
        plt.yticks([])

        plt.subplot(4, 3, 9)
        plt.imshow(_image)
        plt.title('source pic 2-3')
        plt.xticks([])
        plt.yticks([])

        plt.subplot(4, 3, 10)
        plt.imshow(_image)
        plt.title('source pic 3-1')
        plt.xticks([])
        plt.yticks([])

        plt.show()

    #############################
    # 内部函数
    #############################

    def _add_images_doc(self, path: str, import_path: str, url_prefix: str):
        """
        为文件夹下的图片添加信息字典文件(id为不含扩展的文件名)

        @param {str} path - 要处理的文件目录
        """
        _import_path = os.path.realpath(import_path)

        # 处理当前文件夹
        _file_list = FileTool.get_filelist(path, regex_str=r'^((?!\.json$).)*$', is_fullname=True)
        for _file in _file_list:
            _ext = FileTool.get_file_ext(_file)
            _json_file = _file[0: -len(_ext)] + 'json'
            if os.path.exists(_json_file):
                # 字典文件已存在，无需处理
                continue

            # 生成并写入字典
            _file_name = FileTool.get_file_name_no_ext(_file)
            _url = os.path.realpath(_file)[len(_import_path):].replace('\\', '/').lstrip('/')
            _url = '%s/%s' % (url_prefix, _url)
            _image_doc = {
                'id': _file_name,
                'url': _url,
                'path': _file
            }
            _json_str = json.dumps(_image_doc, ensure_ascii=False)
            with open(_json_file, 'wb') as _fid:
                _fid.write(_json_str.encode(encoding='utf-8'))

        # 处理子文件夹
        _sub_dir_list = FileTool.get_dirlist(path)
        for _sub_dir in _sub_dir_list:
            self._add_images_doc(_sub_dir, import_path, url_prefix)

    def _import_images(self, path: str, pipeline: str):
        """
        按目录结构导入文件

        @param {str} path - 要处理的路径
        @param {str} pipeline - 管道标识
        """
        # 先处理当前目录
        self.search_engine.import_images(
            path, pipeline
        )

        # 处理子文件夹
        _sub_dir_list = FileTool.get_dirlist(path)
        for _sub_dir in _sub_dir_list:
            self._import_images(_sub_dir, pipeline)


if __name__ == '__main__':
    # 当程序自己独立运行时执行的操作
    _current_path = os.path.dirname(__file__)
    _import_pic_path = os.path.realpath(os.path.join(_current_path, '../test_data/imported_pic'))
    _search_pic_path = os.path.realpath(os.path.join(_current_path, '../test_data/test_pic'))

    # 测试图片显示
    # TestSearchEngine.test_images_show(_search_pic_path)

    # 如果目录的文件名不标准，可以使用这个函数修改文件名
    # TestSearchEngine.rename_file_to_num(_pic_path)

    # 初始化
    _search_obj = TestSearchEngine()

    # 清理已导入的搜索图片信息
    _search_obj.search_engine.clear_search_db()

    # 导入图片信息
    _search_obj.test_import_images(_import_pic_path, 'JadeSearch', '/static/imported_pic')

    # 查询已导入的图片
    # _images = _search_obj.search_engine.get_images(
    #     'id', ['0000000142', '0000000143']
    # )
    # print('no collection: ', _images)

    # _images = _search_obj.search_engine.get_images(
    #     'id', ['0000000142', '0000000143'], collection='bangle'
    # )
    # print('with collection: ', _images)

    # 删除已导入的图片
    # _search_obj.search_engine.remove_images(
    #     'id', ['0000000142', '0000000143']
    # )

    # 搜索图片
    # _search_obj.test_search_image(_search_pic_path, 'JadeSearch')

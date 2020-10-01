#!/usr/bin/env python3
# -*- coding: UTF-8 -*-

"""
测试处理器
@module test_processer
@file test_processer.py
"""

import os
import sys
import math
import itertools
import numpy as np
from io import BytesIO
from PIL import Image, ImageDraw, ImageFont
import matplotlib.pyplot as plt
from HiveNetLib.simple_log import Logger
from HiveNetLib.simple_xml import SimpleXml
from HiveNetLib.base_tools.run_tool import RunTool
from HiveNetLib.base_tools.file_tool import FileTool
# 根据当前文件路径将包路径纳入，在非安装的情况下可以引用到
sys.path.append(os.path.abspath(os.path.join(
    os.path.dirname(__file__), os.path.pardir)))
from search_by_image.lib.pipeline import Pipeline, PipelineProcesser


def init_pipeline_plugins():
    """
    装载管道插件
    """
    # 装载配置
    _execute_path = os.path.realpath(os.path.join(
        os.path.dirname(__file__), os.path.pardir, 'search_by_image'
    ))
    RunTool.set_global_var('EXECUTE_PATH', _execute_path)

    _config = os.path.join(_execute_path, 'conf/server_jade.xml')
    _config_xml = SimpleXml(_config, encoding='utf-8')
    _server_config = _config_xml.to_dict()['server']

    RunTool.set_global_var(
        'PIPELINE_PROCESSER_PARA', _server_config['pipeline']['processer_para']
    )
    RunTool.set_global_var('PIPELINE_ROUTER_PARA', _server_config['pipeline']['router_para'])
    _plugins_path_list = _server_config['pipeline']['plugins_path'].split(',')
    for _plugins_path in _plugins_path_list:
        Pipeline.load_plugins_by_path(
            os.path.join(_execute_path, _plugins_path.strip())
        )

    _logger: Logger = None
    if 'logger' in _server_config.keys():
        _logger_config = _server_config['logger']
        if len(_logger_config['conf_file_name']) > 0 and _logger_config['conf_file_name'][0] == '.':
            # 相对路径
            _logger_config['conf_file_name'] = os.path.join(
                _execute_path, _logger_config['conf_file_name']
            )
        if len(_logger_config['logfile_path']) > 0 and _logger_config['logfile_path'][0] == '.':
            # 相对路径
            _logger_config['logfile_path'] = os.path.join(
                _execute_path, _logger_config['logfile_path']
            )
        _logger = Logger.create_logger_by_dict(_logger_config)

    # 创建空管道用于测试
    _empty_pipeline = Pipeline('empty', '{}', logger=_logger)
    RunTool.set_global_var('EMPTY_PIPELINE', _empty_pipeline)

    # 创建测试管道
    _jade_pipeline = Pipeline(
        'jade_search',
        _server_config['pipeline']['pipeline_config']['JadeSearch'],
        logger=_logger
    )
    RunTool.set_global_var('JADE_PIPELINE', _jade_pipeline)


def test_JadeTypeDetect():
    """
    测试翡翠类型处理器
    """
    _execute_path = RunTool.get_global_var('EXECUTE_PATH')
    _pipeline = RunTool.get_global_var('EMPTY_PIPELINE')
    _processer_class: PipelineProcesser = Pipeline.get_plugin('processer', 'JadeTypeDetect')
    _filelist = FileTool.get_filelist(
        os.path.join(_execute_path, os.path.pardir, 'test_data/test_pic/'),
        is_fullname=True
    )
    for _file in _filelist:
        # 遍历执行
        with open(_file, 'rb') as _fid:
            _file_bytes = _fid.read()
            _input = {
                'type': '',
                'sub_type': '',
                'image': Image.open(_file_bytes),
                'score': 0.0
            }
            _output = _processer_class.execute(_input, {}, _pipeline)

            # 输出图片和对应文字
            _image = _output['image']
            _print_str = 'type: %s\nsub_type: %s\nscore: %s' % (
                _output['type'], _output['sub_type'], str(_output['score']))
            _draw = ImageDraw.Draw(_image)  # PIL图片上打印汉字
            # 参数1：字体文件路径，参数2：字体大小；Windows系统“simhei.ttf”默认存储在路径：C:\Windows\Fonts中
            _font = ImageFont.truetype("simhei.ttf", 20, encoding="utf-8")
            _draw.text((0, 0), _print_str, (255, 0, 0), font=_font)

            plt.figure(_file)
            plt.imshow(_image)
            plt.show()


def test_PendantTypeDetect():
    """
    测试翡翠挂件类型处理器
    """
    _execute_path = RunTool.get_global_var('EXECUTE_PATH')
    _pipeline = RunTool.get_global_var('EMPTY_PIPELINE')
    _processer_class: PipelineProcesser = Pipeline.get_plugin('processer', 'PendantTypeDetect')
    _filelist = FileTool.get_filelist(
        os.path.join(_execute_path, os.path.pardir, 'test_data/test_pic/'),
        is_fullname=True
    )
    for _file in _filelist:
        # 遍历执行
        with open(_file, 'rb') as _fid:
            _file_bytes = _fid.read()
            _input = {
                'type': '',
                'sub_type': '',
                'image': Image.open(_file_bytes),
                'score': 0.0
            }
            _output = _processer_class.execute(_input, {}, _pipeline)

            # 输出图片和对应文字
            _image = _output['image']
            _print_str = 'type: %s\nsub_type: %s\nscore: %s' % (
                _output['type'], _output['sub_type'], str(_output['score']))
            _draw = ImageDraw.Draw(_image)  # PIL图片上打印汉字
            # 参数1：字体文件路径，参数2：字体大小；Windows系统“simhei.ttf”默认存储在路径：C:\Windows\Fonts中
            _font = ImageFont.truetype("simhei.ttf", 20, encoding="utf-8")
            _draw.text((0, 0), _print_str, (255, 0, 0), font=_font)

            plt.figure(_file)
            plt.imshow(_image)
            plt.show()


def test_HistogramVetor():
    """
    测试直方图特征变量生成
    """
    _execute_path = RunTool.get_global_var('EXECUTE_PATH')
    _pipeline = RunTool.get_global_var('EMPTY_PIPELINE')
    _processer_class: PipelineProcesser = Pipeline.get_plugin('processer', 'HistogramVetor')
    _filelist = FileTool.get_filelist(
        os.path.join(_execute_path, os.path.pardir, 'test_data/test_pic/'),
        is_fullname=True
    )
    for _file in _filelist:
        # 遍历执行
        with open(_file, 'rb') as _fid:
            _file_bytes = _fid.read()
            _input = {
                'type': '',
                'sub_type': '',
                'image': Image.open(_file_bytes),
                'score': 0.0
            }
            _output = _processer_class.execute(_input, {}, _pipeline)

            print(_output['vertor'])


def test_jade_pipeline():
    """
    测试管道
    """
    _execute_path = RunTool.get_global_var('EXECUTE_PATH')
    _pipeline: Pipeline = RunTool.get_global_var('JADE_PIPELINE')
    _filelist = FileTool.get_filelist(
        os.path.join(_execute_path, os.path.pardir, 'test_data/test_pic/'),
        is_fullname=True
    )
    for _file in _filelist:
        # 遍历执行
        with open(_file, 'rb') as _fid:
            _file_bytes = _fid.read()
            _input = {
                'image': _file_bytes
            }

            _status, _output = _pipeline.start(
                _input, {}
            )

            print('Pipeline run status: %s' % _status)
            if _status == 'success':
                # 执行成功
                print('Image Vertor: %s' % str(_output['vertor']))

                # 输出图片和对应文字
                _image = Image.open(BytesIO(_output['image']))
                _print_str = 'type: %s\nsub_type: %s\nscore: %s' % (
                    _output['type'], _output['sub_type'], str(_output['score']))
                _draw = ImageDraw.Draw(_image)  # PIL图片上打印汉字
                # 参数1：字体文件路径，参数2：字体大小；Windows系统“simhei.ttf”默认存储在路径：C:\Windows\Fonts中
                _font = ImageFont.truetype("simhei.ttf", 20, encoding="utf-8")
                _draw.text((0, 0), _print_str, (255, 0, 0), font=_font)

                plt.figure(_file)
                plt.imshow(_image)
                plt.show()


def test_jade_pipeline_pic_compare():
    """
    测试通道结果比较
    """
    _execute_path = RunTool.get_global_var('EXECUTE_PATH')
    _pipeline: Pipeline = RunTool.get_global_var('JADE_PIPELINE')
    _filelist = FileTool.get_filelist(
        os.path.join(_execute_path, os.path.pardir, 'test_data/pic_compare/'),
        is_fullname=True
    )
    _row = len(_filelist)  # 行数
    _col = 3  # 图片列数
    _index = 1  # 当前图片序号
    _y_max = 0.5  # y坐标最大值
    _vertor_list = []  # 向量清单
    for _file in _filelist:
        # 遍历执行
        with open(_file, 'rb') as _fid:
            _file_bytes = _fid.read()
            _input = {
                'image': _file_bytes
            }

            _status, _output = _pipeline.start(
                _input, {}
            )

            print('Pipeline run status: %s' % _status)
            if _status == 'success':
                # 执行成功, 显示相关图片
                _src_img = Image.open(_file)
                plt.subplot(_row, _col, _index)
                plt.imshow(_src_img)
                plt.title('source pic')
                plt.xticks([])
                plt.yticks([])
                _index += 1

                # 处理后的图
                _image = Image.open(BytesIO(_output['image']))
                plt.subplot(_row, _col, _index)
                plt.imshow(_image)
                plt.title(_output['collection'])
                plt.xticks([])
                plt.yticks([])
                _index += 1

                # 统计图
                plt.subplot(_row, _col, _index)
                _x = list(range(1, 6 * 4 * 3 + 1))
                plt.plot(_x, _output['vertor'])
                plt.axis([1, 6 * 4 * 3, 0.0, _y_max])
                _index += 1

                # 加入向量清单
                _vertor_list.append(_output['vertor'])

    # 计算两两之间的欧式距离（L2）
    _compare = list(itertools.combinations(list(range(_row)), 2))
    for _item in _compare:
        _sum = 0
        _v1 = _vertor_list[_item[0]].tolist()
        _v2 = _vertor_list[_item[1]].tolist()
        for _index in range(len(_v1)):
            _sum += (_v1[_index] - _v2[_index])**2

        _l2 = math.sqrt(_sum)

        print('%d - %d : %f, %f' % (
            _item[0] + 1, _item[1] + 1,
            # np.linalg.norm(_vertor_list[_item[0]] - _vertor_list[_item[1]])
            np.sqrt(np.sum(np.square(_vertor_list[_item[0]] - _vertor_list[_item[1]]))),
            _l2
        ))

    # 统一显示
    plt.show()


def test_hsv_color():
    """
    测试HSV的颜色聚类处理
    """
    _execute_path = RunTool.get_global_var('EXECUTE_PATH')
    _filelist = FileTool.get_filelist(
        os.path.join(_execute_path, os.path.pardir, 'test_data/test_pic/'),
        is_fullname=True
    )

    def convert_color(RGB: tuple, split_h: int = 6, split_s: int = 2, split_v: int = 2):
        """
        颜色聚类转换

        @param {tuple} RGB - (r,g,b)颜色数组
        @param {int} split_h=6 - 指定将HSV颜色坐标的基础色转换为几个分类([0, 359])
        @param {int} split_s=2 - 指定将HSV颜色坐标的饱和度转换为几个分类([0, 1])
        @param {int} split_v=2 - 指定将HSV颜色坐标的亮度转换为几个分类([0, 1])
        """
        # 转换RBG颜色为HSV
        r, g, b = RGB[0] / 255.0, RGB[1] / 255.0, RGB[2] / 255.0
        mx = max(r, g, b)
        mn = min(r, g, b)
        df = mx - mn
        if mx == mn:
            h = 0
        elif mx == r:
            h = (60 * ((g - b) / df) + 360) % 360
        elif mx == g:
            h = (60 * ((b - r) / df) + 120) % 360
        elif mx == b:
            h = (60 * ((r - g) / df) + 240) % 360
        if mx == 0:
            s = 0
        else:
            s = df / mx
        v = mx

        # 根据HSV坐标将颜色归类
        df = 360.0 / split_h
        h = round(h / df) * df
        if h >= 360:
            h = 0

        if split_s <= 1:
            s = 1.0
        else:
            df = 1.0 / (split_s - 1)
            s = round(s / df) * df

        if split_v <= 1:
            v = 1.0
        else:
            df = 1.0 / (split_v - 1)
            v = round(v / df) * df

        # 将HSV转换为RGB
        h60 = h / 60.0
        h60f = math.floor(h60)
        hi = int(h60f) % 6
        f = h60 - h60f
        p = v * (1 - s)
        q = v * (1 - f * s)
        t = v * (1 - (1 - f) * s)
        r, g, b = 0, 0, 0
        if hi == 0:
            r, g, b = v, t, p
        elif hi == 1:
            r, g, b = q, v, p
        elif hi == 2:
            r, g, b = p, v, t
        elif hi == 3:
            r, g, b = p, q, v
        elif hi == 4:
            r, g, b = t, p, v
        elif hi == 5:
            r, g, b = v, p, q
        r, g, b = int(r * 255), int(g * 255), int(b * 255)

        return (r, g, b)

    for _file in _filelist:
        _image = Image.open(_file)
        _image = _image.resize((299, 299)).convert("RGB")
        _pix = _image.load()
        for _x in range(299):
            for _y in range(299):
                # 遍历每个变量修改颜色
                _pix[_x, _y] = convert_color(_pix[_x, _y], split_s=4, split_v=3)

        # 显示转换后的图片
        _image_src = Image.open(_file)
        plt.subplot(1, 2, 1)
        plt.imshow(_image_src)
        plt.title('source pic')
        plt.xticks([])
        plt.yticks([])

        plt.subplot(1, 2, 2)
        plt.imshow(_image)
        plt.title('dest pic')
        plt.xticks([])
        plt.yticks([])

        plt.show()


def test_histogram():
    """
    测试直方图的处理
    """
    # 创建纯白色图片
    _w_img = Image.new('RGB', (299, 299), (255, 255, 255))
    _w_h = _w_img.histogram()
    for i in range(768):
        if _w_h[i] > 0:
            print('white 1: %d - %d' % (i, _w_h[i]))

    # 增加10个黑色像素
    _w_pix = _w_img.load()
    for i in range(10):
        _w_pix[0, i] = (0, 0, 0)

    # _w_img.show()
    _w_h = _w_img.histogram()
    for i in range(768):
        if _w_h[i] > 0:
            print('white 2: %d - %d' % (i, _w_h[i]))

    # 创建纯黑色图片
    _b_img = Image.new('RGB', (299, 299), (0, 0, 0))
    _b_h = _b_img.histogram()
    for i in range(768):
        if _b_h[i] > 0:
            print('black 1: %d - %d' % (i, _b_h[i]))

    # 增加10个白色像素
    _b_pix = _b_img.load()
    for i in range(10):
        _b_pix[0, i] = (255, 255, 255)

    # _b_img.show()
    _b_h = _b_img.histogram()
    for i in range(768):
        if _b_h[i] > 0:
            print('black 2: %d - %d' % (i, _b_h[i]))


if __name__ == '__main__':
    # 装载管道插件
    init_pipeline_plugins()

    # 测试JadeTypeDetect
    # test_JadeTypeDetect()

    # 测试PendantTypeDetect
    # test_PendantTypeDetect()

    # 测试HistogramVetor
    # test_HistogramVetor()

    # 测试管道
    test_jade_pipeline()

    # 测试颜色算法
    # test_hsv_color()

    # 测试直方图
    # test_histogram()

    # 比较图片
    # test_jade_pipeline_pic_compare()

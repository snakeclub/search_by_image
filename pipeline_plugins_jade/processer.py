#!/usr/bin/env python3
# -*- coding: UTF-8 -*-
# Copyright 2019 黎慧剑
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

"""
管道处理器模块
@module processer
@file processer.py
"""

from __future__ import division

import os
import sys
import math
from io import BytesIO
import tensorflow as tf
from PIL import Image
import numpy as np
from HiveNetLib.base_tools.run_tool import RunTool
# 根据当前文件路径将包路径纳入，在非安装的情况下可以引用到
sys.path.append(os.path.abspath(os.path.join(
    os.path.dirname(__file__), os.path.pardir)))
from search_by_image.lib.pipeline import Pipeline, PipelineProcesser


__MOUDLE__ = 'processer'  # 模块名
__DESCRIPT__ = u'管道处理器模块'  # 模块描述
__VERSION__ = '0.1.0'  # 版本
__AUTHOR__ = u'黎慧剑'  # 作者
__PUBLISH__ = '2020.09.03'  # 发布日期


# JadeTypeDetect的物体识别模型全局变量名
PR_JADE_TYPE_DETECT_GRAPH = 'PR_JADE_TYPE_DETECT_GRAPH'

# 识别挂件类型的物体识别模型全局变量名
PR_PENDANT_TYPE_DETECT_GRAPH = 'PR_PENDANT_TYPE_DETECT_GRAPH'


class Tools(object):
    """
    工具函数
    """

    @classmethod
    def load_labelmap(cls, path: str, encoding: str = 'utf-8') -> dict:
        """
        装载labelmap.pbtxt文件到字典

        @param {str} path - labelmap文件路径, 文件格式如下
            item {
                id: 1
                name: 'ping_buckle'
            }

            item {
                id: 2
                name: 'nothing_card'
            }
        @param {str} encoding='utf-8' - 编码

        @returns {dict, int} - 返回 id映射字典, other的id
            {
                id : name,
            }, int
        """
        _map = dict()
        _other_id = -1
        _id = -1
        _name = ''
        with open(path, 'r', encoding=encoding) as _fid:
            _lines = _fid.readlines()
            for _line in _lines:
                # 逐行处理
                _line = _line.strip()
                if _line == '':
                    continue
                elif _line == 'item {':
                    # 内容开始
                    _id = -1
                    _name = ''
                elif _line == '}':
                    # 内容结束
                    _map[_id] = _name
                else:
                    # 具体内容
                    _para = _line.split(':')
                    if _para[0].strip() == 'id':
                        _id = int(_para[1].strip())
                    elif _para[0].strip() == 'name':
                        _name = eval(_para[1].strip())

                    if _name == 'other':
                        _other_id = _id

        # 返回值
        return _map, _other_id

    @classmethod
    def load_image_into_numpy_array(cls, image):
        """
        将图片转换为numpy数组
        """
        (im_width, im_height) = image.size
        return np.array(image.getdata()).reshape((im_height, im_width, 3)).astype(np.uint8)

    @classmethod
    def detect_processer_initialize(cls, graph_var_name: str, processer_name: str):
        """
        物体识别处理器的公共初始化函数

        @param {str} graph_var_name - 对象识别冻结图全局变量名
        @param {str} processer_name - 处理器名
        """
        _graph = RunTool.get_global_var(graph_var_name)
        if _graph is None:
            _graph = dict()
            RunTool.set_global_var(graph_var_name, _graph)
        else:
            # 模型已装载，无需继续处理
            return

        _execute_path = RunTool.get_global_var('EXECUTE_PATH')
        if _execute_path is None:
            _execute_path = os.getcwd()
        _config = RunTool.get_global_var('PIPELINE_PROCESSER_PARA')[processer_name]

        _pb_file = os.path.join(_execute_path, _config['frozen_graph'])
        _pb_labelmap = os.path.join(_execute_path, _config['labelmap'])

        # 识别基础参数
        _graph['min_score'] = _config.get('min_score', 0.8)
        _graph['labelmap'], _graph['other_id'] = Tools.load_labelmap(
            _pb_labelmap, encoding=_config.get('encoding', 'utf-8')
        )

        _detection_graph = tf.Graph()
        with _detection_graph.as_default():
            _od_graph_def = tf.GraphDef()
            with tf.gfile.GFile(_pb_file, 'rb') as _fid:
                _serialized_graph = _fid.read()
                _od_graph_def.ParseFromString(_serialized_graph)
                tf.import_graph_def(_od_graph_def, name='')

            _graph['session'] = tf.Session(graph=_detection_graph)

        # Input tensor is the image
        _graph['image_tensor'] = _detection_graph.get_tensor_by_name('image_tensor:0')
        # Output tensors are the detection boxes, scores, and classes
        # Each box represents a part of the image where a particular object was detected
        _graph['detection_boxes'] = _detection_graph.get_tensor_by_name('detection_boxes:0')
        # Each score represents level of confidence for each of the objects.
        # The score is shown on the result image, together with the class label.
        _graph['detection_scores'] = _detection_graph.get_tensor_by_name('detection_scores:0')
        _graph['detection_classes'] = _detection_graph.get_tensor_by_name('detection_classes:0')
        # Number of objects detected
        _graph['num_detections'] = _detection_graph.get_tensor_by_name('num_detections:0')

    @classmethod
    def detect_processer_execute(cls, graph_var_name: str, processer_name: str, input,
                                 context: dict, pipeline_obj):
        """
        物体识别处理器的公共执行函数

        @param {str} graph_var_name - 对象识别冻结图全局变量名
        @param {str} processer_name - 处理器名
        @param {object} input - 处理器输入数据值
            输入图片信息字典
            {
                'type': # {str} 识别到的对象分类, ''代表没有找到分类
                'sub_type': # {str} 识别到的对象子分类， ''代表没有子分类
                'image': # {bytes} 图片bytes对象
                'score': # {float} 匹配分数
            }
        @param {dict} context - 传递上下文，该字典信息将在整个管道处理过程中一直向下传递，可以在处理器中改变该上下文信息
        @param {Pipeline} pipeline_obj - 管道对象

        @returns {object} - 处理结果输出数据值
            返回图片分类及对应处理后的图片截图字典:
                {
                    'type': # {str} 识别到的对象分类, ''代表没有找到分类
                    'sub_type': # {str} 识别到的对象子分类， ''代表没有子分类
                    'image': # {bytes} 通过截图处理后的图片bytes对象
                    'score': # {float} 匹配分数
                }
        """
        # 如果是翡翠类型判断但又送了挂件类型进来，直接不处理
        if input['type'] == 'pendant' and processer_name == 'JadeTypeDetect':
            return input

        _graph = RunTool.get_global_var(graph_var_name)

        # 准备图片
        _image = Image.open(BytesIO(input['image']))
        _image_np = Tools.load_image_into_numpy_array(_image)
        _image_np_expanded = np.expand_dims(_image_np, axis=0)

        # 进行识别
        (_boxes, _scores, _classes, _num) = _graph['session'].run(
            [_graph['detection_boxes'], _graph['detection_scores'],
             _graph['detection_classes'], _graph['num_detections']],
            feed_dict={_graph['image_tensor']: _image_np_expanded})

        _np_scores = np.squeeze(_scores)
        _np_boxes = np.squeeze(_boxes)
        _np_classes = np.squeeze(_classes)

        # 区分不同情况的图片获取
        _index = 0
        _match_index = -1
        _match_score = -1
        if processer_name == 'JadeTypeDetect':
            # 判断翡翠类型
            for _score in _np_scores:
                # 遍历找到最佳匹配
                if _score >= _graph['min_score'] and int(_np_classes[_index]) != _graph['other_id']:
                    if _score > _match_score:
                        if input['type'] != '':
                            # 指定分类的情况
                            _type = _graph['labelmap'][int(_np_classes[_index])]
                            if input['type'] == _type or (input['type'] == 'bangle' and _type.startswith('bangle_')):
                                # 匹配上
                                _match_index = _index
                                _match_score = _score
                        else:
                            # 未指定分类
                            _match_index = _index
                            _match_score = _score

                # 下一个
                _index += 1
        else:
            # 判断挂件类型
            for _score in _np_scores:
                if _score >= _graph['min_score']:
                    if _score > _match_score:
                        _match_score = _score
                        _match_index = _index

                    _index += 1

        if _match_index == -1:
            # 没有找到最佳匹配的图片, 直接返回原图片的输入信息即可
            return input

        # 进行截图处理
        _ymin = int(_np_boxes[_match_index][0] * _image.size[1])
        _xmin = int(_np_boxes[_match_index][1] * _image.size[0])
        _ymax = int(_np_boxes[_match_index][2] * _image.size[1])
        _xmax = int(_np_boxes[_match_index][3] * _image.size[0])
        _obj_image = _image.crop((_xmin, _ymin, _xmax, _ymax))

        _img_bytesio = BytesIO()
        _obj_image.save(_img_bytesio, format='JPEG')

        # 处理类型
        _type = _graph['labelmap'][int(_np_classes[_match_index])]
        if _type.startswith('bangle_'):
            # 手镯的情况
            _sub_type = _type
            _type = 'bangle'
        elif input['type'] == '':
            if processer_name == 'PendantTypeDetect':
                # 挂件
                _sub_type = _type
                _type = 'pendant'
            else:
                _sub_type = ''
        else:
            _sub_type = _type
            _type = input['type']

        # 如果执行两次判断，则第二次为子分类
        return {
            'type': _type,
            'sub_type': _sub_type,
            'image': _img_bytesio.getvalue(),
            'score': float(_np_scores[_match_index])
        }

    @classmethod
    def rgb_to_hsv(cls, rgb: tuple):
        """
        将颜色的RGB坐标转换为HSV坐标

        @param {tuple} rgb - (r:int, g:int, b:int)颜色坐标

        @returns {tuple} - 转换后的HSV坐标(h:float, s:float, v:float)
        """
        r, g, b = rgb[0] / 255.0, rgb[1] / 255.0, rgb[2] / 255.0
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

        return (h, s, v)

    @classmethod
    def hsv_to_rgb(cls, hsv: tuple):
        """
        将颜色的HSV坐标转换为RGB坐标

        @param {tuple} hsv - (h:float, s:float, v:float) HSV 颜色坐标

        @param {tuple} - 转换后的RGB坐标(r:int, g:int, b:int)
        """
        h, s, v = hsv[0], hsv[1], hsv[2]
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

    @classmethod
    def hsv_cluster(cls, hsv: tuple, h_split_num: int, s_split_num: int, v_split_num: int):
        """
        HSV坐标聚类算法

        @param {tuple} hsv - 输入原始的HSV坐标 (h:float, s:float, v:float)
        @param {int} h_split_num - 颜色坐标(H [0, 360])的分割数量(按360度平均切割数量)
        @param {int} s_split_num - 饱和度坐标(S [0, 1])的分割数量
        @param {int} v_split_num - 亮度坐标(V [0, 1])的分割数量

        @returns {tuple} - 返回转换后的HSV坐标(h:float, s:float, v:float)
        """
        # H坐标聚合，环形
        df = 360.0 / h_split_num
        h = round(hsv[0] / df) * df
        if h >= 360:
            h = 0

        # S坐标聚合，直线型，包含两个端点
        if s_split_num <= 1:
            s = 1.0
        else:
            df = 1.0 / (s_split_num - 1)
            s = round(hsv[1] / df) * df

        if v_split_num <= 1:
            v = 1.0
        else:
            df = 1.0 / (v_split_num - 1)
            v = round(hsv[2] / df) * df

        # 返回转换后的颜色坐标
        return (h, s, v)


class JadeTypeDetect(PipelineProcesser):
    """
    识别翡翠类型及其物体范围

    @example 管道的processer_para配置如下
        <JadeTypeDetect>
            <frozen_graph>../test_data/tf_models/jade_type/frozen_inference_graph.pb</frozen_graph>
            <labelmap>../test_data/tf_models/jade_type/labelmap.pbtxt</labelmap>
            <encoding>utf-8</encoding>
            <min_score type="float">0.8</min_score>
        </JadeTypeDetect>
    """
    @classmethod
    def initialize(cls):
        """
        初始化处理类
        装载TF识别模型冻结图
        """
        Tools.detect_processer_initialize(PR_JADE_TYPE_DETECT_GRAPH, cls.processer_name())

    @classmethod
    def processer_name(cls) -> str:
        """
        处理器名称，唯一标识处理器

        @returns {str} - 当前处理器名称
        """
        return 'JadeTypeDetect'

    @classmethod
    def execute(cls, input_data, context: dict, pipeline_obj):
        """
        执行处理

        @param {object} input_data - 处理器输入数据值
            输入图片信息字典
            {
                'type': # {str} 识别到的对象分类, ''代表没有找到分类
                'sub_type': # {str} 识别到的对象子分类， ''代表没有子分类
                'image': # {bytes} 图片bytes对象
                'score': # {float} 匹配分数
            }
        @param {dict} context - 传递上下文，该字典信息将在整个管道处理过程中一直向下传递，可以在处理器中改变该上下文信息
        @param {Pipeline} pipeline_obj - 管道对象

        @returns {object} - 处理结果输出数据值
            返回图片分类及对应处理后的图片截图字典:
                {
                    'type': # {str} 识别到的对象分类, ''代表没有找到分类
                    'sub_type': # {str} 识别到的对象子分类， ''代表没有子分类
                    'image': # {bytes} 通过截图处理后的图片bytes对象
                    'score': # {float} 匹配分数
                }
        """
        return Tools.detect_processer_execute(
            PR_JADE_TYPE_DETECT_GRAPH, cls.processer_name(), input_data, context, pipeline_obj
        )


class PendantTypeDetect(PipelineProcesser):
    """
    识别翡翠挂件类型及其物体范围

    @example 管道的processer_para配置如下
        <PendantTypeDetect>
            <frozen_graph>../test_data/tf_models/pendant_type/frozen_inference_graph.pb</frozen_graph>
            <labelmap>../test_data/tf_models/pendant_type/labelmap.pbtxt</labelmap>
            <encoding>utf-8</encoding>
            <min_score type="float">0.8</min_score>
        </PendantTypeDetect>
    """
    @classmethod
    def initialize(cls):
        """
        初始化处理类
        装载TF识别模型冻结图
        """
        Tools.detect_processer_initialize(PR_PENDANT_TYPE_DETECT_GRAPH, cls.processer_name())

    @classmethod
    def processer_name(cls) -> str:
        """
        处理器名称，唯一标识处理器

        @returns {str} - 当前处理器名称
        """
        return 'PendantTypeDetect'

    @classmethod
    def execute(cls, input_data, context: dict, pipeline_obj):
        """
        执行处理

        @param {object} input_data - 处理器输入数据值
            输入图片信息字典
            {
                'type': # {str} 识别到的对象分类, ''代表没有找到分类
                'sub_type': # {str} 识别到的对象子分类， ''代表没有子分类
                'image': # {bytes} 图片bytes对象
                'score': # {float} 匹配分数
            }
        @param {dict} context - 传递上下文，该字典信息将在整个管道处理过程中一直向下传递，可以在处理器中改变该上下文信息
        @param {Pipeline} pipeline_obj - 管道对象

        @returns {object} - 处理结果输出数据值
            返回图片分类及对应处理后的图片截图字典:
                {
                    'type': # {str} 识别到的对象分类, ''代表没有找到分类
                    'sub_type': # {str} 识别到的对象子分类， ''代表没有子分类
                    'image': # {bytes} 通过截图处理后的图片bytes对象
                    'score': # {float} 匹配分数
                }
        """
        return Tools.detect_processer_execute(
            PR_PENDANT_TYPE_DETECT_GRAPH, cls.processer_name(), input_data, context, pipeline_obj
        )


class HistogramVetor(PipelineProcesser):
    """
    获取图片直方图特征向量

    @example 管道的processer_para配置如下

    """

    @classmethod
    def processer_name(cls) -> str:
        """
        处理器名称，唯一标识处理器

        @returns {str} - 当前处理器名称
        """
        return 'HistogramVetor'

    @classmethod
    def execute(cls, input_data, context: dict, pipeline_obj):
        """
        执行处理

        @param {object} input_data - 处理器输入数据值
            输入图片信息字典
            {
                'type': # {str} 识别到的对象分类, ''代表没有找到分类
                'sub_type': # {str} 识别到的对象子分类， ''代表没有子分类
                'image': # {bytes} 图片bytes对象
                'score': # {float} 匹配分数
            }
        @param {dict} context - 传递上下文，该字典信息将在整个管道处理过程中一直向下传递，可以在处理器中改变该上下文信息
        @param {Pipeline} pipeline_obj - 管道对象

        @returns {object} - 处理结果输出数据值
            {
                'type': # {str} 识别到的对象分类, ''代表没有找到分类
                'sub_type': # {str} 识别到的对象子分类， ''代表没有子分类
                'image': # {bytes} 图片bytes对象
                'score': # {float} 匹配分数
                'vertor': # {numpy.ndarray} 特征向量
            }
        """
        _config = RunTool.get_global_var('PIPELINE_PROCESSER_PARA')[cls.processer_name()]
        _size = _config.get('image_size', 299)

        # 转换图片大小
        _image = Image.open(BytesIO(input_data['image']))
        _image = _image.resize((_size, _size)).convert("RGB")
        _histogram = _image.histogram()

        # 对直方图进行归一化处理
        _max = float(_size * _size)
        _min = 0
        _normalize = [float(i) / (_max - _min)for i in _histogram]

        # 返回特征变量
        input_data['vertor'] = np.array(_normalize)
        return input_data


class HSVClusterHistogramVetor(PipelineProcesser):
    """
    通过HSV颜色坐标进行聚类转换得到的颜色直方图特征向量

    @example 管道的processer_para配置如下
        <HSVClusterHistogramVetor>
        </HSVClusterHistogramVetor>
    """

    @classmethod
    def processer_name(cls) -> str:
        """
        处理器名称，唯一标识处理器

        @returns {str} - 当前处理器名称
        """
        return 'HSVClusterHistogramVetor'

    @classmethod
    def execute(cls, input_data, context: dict, pipeline_obj):
        """
        执行处理

        @param {object} input_data - 处理器输入数据值
            输入图片信息字典
            {
                'type': # {str} 识别到的对象分类, ''代表没有找到分类
                'sub_type': # {str} 识别到的对象子分类， ''代表没有子分类
                'image': # {bytes} 图片bytes对象
                'score': # {float} 匹配分数
            }
        @param {dict} context - 传递上下文，该字典信息将在整个管道处理过程中一直向下传递，可以在处理器中改变该上下文信息
        @param {Pipeline} pipeline_obj - 管道对象

        @returns {object} - 处理结果输出数据值
            {
                'type': # {str} 识别到的对象分类, ''代表没有找到分类
                'sub_type': # {str} 识别到的对象子分类， ''代表没有子分类
                'image': # {bytes} 图片bytes对象
                'score': # {float} 匹配分数
                'vertor': # {numpy.ndarray} 特征向量
            }
        """
        _config = RunTool.get_global_var('PIPELINE_PROCESSER_PARA')[cls.processer_name()]
        _size = _config.get('image_size', 299)
        _h_split_num = _config.get('h_split_num', 6)
        _s_split_num = _config.get('s_split_num', 4)
        _v_split_num = _config.get('v_split_num', 3)
        _remove_line = _config.get('remove_line', 0.01)

        # 转换图片大小
        _image = Image.open(BytesIO(input_data['image']))
        _image = _image.resize((_size, _size)).convert("RGB")

        # 遍历图片每个像素修改颜色
        _dimension = _h_split_num * _s_split_num * _v_split_num
        _hsv_histogram = [0] * _dimension
        _pix_count = 0  # 有效的像素数量，用于归一化的时候处理(归一化比例)
        _pix = _image.load()
        for _x in range(_size):
            for _y in range(_size):
                # 转换为hsv坐标
                _hsv = Tools.rgb_to_hsv(_pix[_x, _y])

                # 执行HSV的颜色聚类，原理是将丰富的颜色根据3个坐标近似到分割好的聚类坐标上
                _hsv = Tools.hsv_cluster(_hsv, _h_split_num, _s_split_num, _v_split_num)

                # 修改图片
                _pix[_x, _y] = Tools.hsv_to_rgb(_hsv)

                if _hsv == (0.0, 0.0, 0.0) or _hsv == (0.0, 0.0, 100.0):
                    # 删除黑色和白色的点，减少背景的干扰, 只看有颜色的部分
                    continue

                # 将像素值添加到直方图
                _h_index = round(_hsv[0] / (360.0 / _h_split_num))

                if _s_split_num <= 1:
                    _s_index = 0
                else:
                    _s_index = round(_hsv[1] / (1.0 / (_s_split_num - 1)))

                if _v_split_num <= 1:
                    _v_index = 0
                else:
                    _v_index = round(_hsv[2] / (1.0 / (_v_split_num - 1)))

                _index = _h_index * (_s_split_num * _v_split_num) + \
                    _s_index * _v_split_num + _v_index

                # 增加距离维度对数据的影响，突出颜色位置的距离区别，两个颜色距离越近，取值越相似
                _add_count = abs(_index - round(_dimension / 2))
                _hsv_histogram[_index] += _add_count
                _pix_count += _add_count

        # 消除小值（让图片特征更明显）
        _remove_flag = _remove_line * _pix_count
        for _index in range(_h_split_num * _s_split_num * _v_split_num):
            if _hsv_histogram[_index] <= _remove_flag:
                _hsv_histogram[_index] = 0
                _pix_count -= 1

        # 对直方图进行归一化处理
        _max = _pix_count
        _min = 0
        _normalize = [float(i) / (_max - _min) for i in _hsv_histogram]

        # 获取图片的二进制编码
        _img_bytesio = BytesIO()
        _image.save(_img_bytesio, format='JPEG')

        # 返回特征变量
        input_data['vertor'] = np.array(_normalize)
        input_data['image'] = _img_bytesio.getvalue()
        return input_data


class SearchImageInputAdpter(PipelineProcesser):
    """
    图片搜索引擎输入适配处理器
    """
    @classmethod
    def processer_name(cls) -> str:
        """
        处理器名称，唯一标识处理器

        @returns {str} - 当前处理器名称
        """
        return 'SearchImageInputAdpter'

    @classmethod
    def execute(cls, input_data, context: dict, pipeline_obj):
        """
        执行处理

        @param {object} input_data - 处理器输入数据值
            输入图片信息字典
            {
                'image': # {bytes} 图片bytes对象
                'collection': # {str} 初始化时可以指定集合
            }
        @param {dict} context - 传递上下文，该字典信息将在整个管道处理过程中一直向下传递，可以在处理器中改变该上下文信息
        @param {Pipeline} pipeline_obj - 管道对象

        @returns {object} - 处理结果输出数据值
            返回图像识别的标准化入参:
                {
                    'type': # {str} 识别到的对象分类, ''代表没有找到分类
                    'sub_type': # {str} 识别到的对象子分类， ''代表没有子分类
                    'image': # {bytes} 通过截图处理后的图片bytes对象
                    'score': # {float} 匹配分数
                }
        """
        _output = {
            'type': input_data.get('collection', ''),  # 初始化的数据集
            'sub_type': '',
            'image': input_data['image'],
            'score': 0.0
        }

        return _output


class SearchImageOutputAdpter(PipelineProcesser):
    """
    图片搜索引擎输出适配处理器
    """
    @classmethod
    def processer_name(cls) -> str:
        """
        处理器名称，唯一标识处理器

        @returns {str} - 当前处理器名称
        """
        return 'SearchImageOutputAdpter'

    @classmethod
    def execute(cls, input_data, context: dict, pipeline_obj):
        """
        执行处理

        @param {object} input_data - 处理器输入数据值
            输入识别处理后的图片信息字典
            {
                'type': # {str} 识别到的对象分类, ''代表没有找到分类
                'sub_type': # {str} 识别到的对象子分类， ''代表没有子分类
                'image': # {bytes} 图片bytes对象
                'score': # {float} 匹配分数
                'vertor': # {numpy.ndarray} 特征向量
            }
        @param {dict} context - 传递上下文，该字典信息将在整个管道处理过程中一直向下传递，可以在处理器中改变该上下文信息
        @param {Pipeline} pipeline_obj - 管道对象

        @returns {object} - 处理结果输出数据值, 标准输出
            {
                'collection': {str} 匹配到的集合类型
                'image': # {bytes} 图片bytes对象
                'vertor': # {numpy.ndarray} 特征向量
            }
        """
        _config = RunTool.get_global_var('PIPELINE_PROCESSER_PARA')[cls.processer_name()]
        if _config['pendant_use_subtype']:
            # 挂件使用子类进行分类处理
            if input_data['type'] == 'pendant':
                input_data['collection'] = 'pendant_%s' % input_data['sub_type']
            else:
                input_data['collection'] = input_data['type']
        else:
            # 只使用主分类进行分类处理
            input_data['collection'] = input_data['type']

        return input_data


if __name__ == '__main__':
    # 当程序自己独立运行时执行的操作
    # 打印版本信息
    print(('模块名：%s  -  %s\n'
           '作者：%s\n'
           '发布日期：%s\n'
           '版本：%s' % (__MOUDLE__, __DESCRIPT__, __AUTHOR__, __PUBLISH__, __VERSION__)))

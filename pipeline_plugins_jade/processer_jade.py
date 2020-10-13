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
import copy
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

# 识别手镯掩码的物体识别模型全局变量
PR_BANGLE_MASK_DETECT_GRAPH = 'PR_BANGLE_MASK_DETECT_GRAPH'


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
    def reframe_box_masks_to_image_masks(cls, box_masks, boxes, image_height,
                                         image_width):
        """Transforms the box masks back to full image masks.

        Embeds masks in bounding boxes of larger masks whose shapes correspond to
        image shape.

        Args:
            box_masks: A tf.float32 tensor of size [num_masks, mask_height, mask_width].
            boxes: A tf.float32 tensor of size [num_masks, 4] containing the box
                corners. Row i contains [ymin, xmin, ymax, xmax] of the box
                corresponding to mask i. Note that the box corners are in
                normalized coordinates.
            image_height: Image height. The output mask will have the same height as
                        the image height.
            image_width: Image width. The output mask will have the same width as the
                        image width.

        Returns:
            A tf.float32 tensor of size [num_masks, image_height, image_width].
        """
        def reframe_box_masks_to_image_masks_default():
            """The default function when there are more than 0 box masks."""
            def transform_boxes_relative_to_boxes(boxes, reference_boxes):
                boxes = tf.reshape(boxes, [-1, 2, 2])
                min_corner = tf.expand_dims(reference_boxes[:, 0:2], 1)
                max_corner = tf.expand_dims(reference_boxes[:, 2:4], 1)
                transformed_boxes = (boxes - min_corner) / (max_corner - min_corner)
                return tf.reshape(transformed_boxes, [-1, 4])

            box_masks_expanded = tf.expand_dims(box_masks, axis=3)
            num_boxes = tf.shape(box_masks_expanded)[0]
            unit_boxes = tf.concat(
                [tf.zeros([num_boxes, 2]), tf.ones([num_boxes, 2])], axis=1)
            reverse_boxes = transform_boxes_relative_to_boxes(unit_boxes, boxes)
            return tf.image.crop_and_resize(
                image=box_masks_expanded,
                boxes=reverse_boxes,
                box_ind=tf.range(num_boxes),
                crop_size=[image_height, image_width],
                extrapolation_value=0.0)
        image_masks = tf.cond(
            tf.shape(box_masks)[0] > 0,
            reframe_box_masks_to_image_masks_default,
            lambda: tf.zeros([0, image_height, image_width, 1], dtype=tf.float32))
        return tf.squeeze(image_masks, axis=3)

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
    def detect_processer_execute(cls, graph_var_name: str, processer_name: str, input_data,
                                 context: dict, pipeline_obj):
        """
        物体识别处理器的公共执行函数

        @param {str} graph_var_name - 对象识别冻结图全局变量名
        @param {str} processer_name - 处理器名
        @param {object} input_data - 处理器输入数据值
            输入图片信息字典
            {
                'type': # {str} 识别到的对象分类, ''代表没有找到分类
                'sub_type': # {str} 识别到的对象子分类， ''代表没有子分类
                'image': # {PIL.Image.Image} 图片对象
                'score': # {float} 匹配分数
            }
        @param {dict} context - 传递上下文，该字典信息将在整个管道处理过程中一直向下传递，可以在处理器中改变该上下文信息
        @param {Pipeline} pipeline_obj - 管道对象

        @returns {object} - 处理结果输出数据值
            返回图片分类及对应处理后的图片截图字典:
                {
                    'type': # {str} 识别到的对象分类, ''代表没有找到分类
                    'sub_type': # {str} 识别到的对象子分类， ''代表没有子分类
                    'image': # {PIL.Image.Image} 通过截图处理后的图片对象
                    'score': # {float} 匹配分数
                }
        """
        # 如果是翡翠类型判断但又送了挂件类型进来，直接不处理，按流程走挂件的处理
        if input_data['type'] == 'pendant' and processer_name == 'JadeTypeDetect':
            return input_data

        _config = RunTool.get_global_var('PIPELINE_PROCESSER_PARA')[processer_name]
        _graph = RunTool.get_global_var(graph_var_name)

        # 准备图片
        _image = input_data['image']
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
                # 找到第一个匹配上的对象，这是最优匹配
                if _score >= _graph['min_score']:
                    if _score > _match_score and int(_np_classes[_index]) != _graph['other_id']:
                        if input_data['type'] != '':
                            # 指定分类的情况
                            _type = _graph['labelmap'][int(_np_classes[_index])]
                            if input_data['type'] == _type or (input_data['type'] == 'bangle' and _type.startswith('bangle_')):
                                # 匹配上
                                _match_index = _index
                                _match_score = _score
                                break
                        else:
                            # 未指定分类
                            _match_index = _index
                            _match_score = _score
                            break
                else:
                    # 分数达不到，后续分数会更低，因此直接退出
                    break

                # 下一个
                _index += 1
        elif input_data['type'] in ['earrings', 'chain']:
            # 耳环及项链的情况，在二次挂件识别中组合识别到的挂件图片，按比例处理
            _corp_images = []  # 识别到的挂件图片清单
            _max_width = 0
            _max_height = 0
            for _score in _np_scores:
                if _score >= _graph['min_score']:
                    if _index == 0:
                        _match_score = _score
                        _match_index = 0
                    # 截图
                    _ymin = int(_np_boxes[_index][0] * _image.size[1])
                    _xmin = int(_np_boxes[_index][1] * _image.size[0])
                    _ymax = int(_np_boxes[_index][2] * _image.size[1])
                    _xmax = int(_np_boxes[_index][3] * _image.size[0])
                    _corp = cls.get_image_center(
                        _image.crop((_xmin, _ymin, _xmax, _ymax)),
                        center_field=_config.get('cut_center_field', 0.7)
                    )
                    _corp_images.append(
                        cls.get_image_center(
                            _image.crop((_xmin, _ymin, _xmax, _ymax)),
                            center_field=_config.get('cut_center_field', 0.7)
                        )
                    )
                    if _corp.size[0] > _max_width:
                        _max_width = _corp.size[0]
                    if _corp.size[1] > _max_height:
                        _max_height = _corp.size[1]
                else:
                    break

                # 下一个
                _index += 1

            # 将多个识别到的翡翠拼成一张图片
            if _match_index == 0:
                _obj_image = Image.new('RGB', (100 * len(_corp_images), 100), (0, 0, 0))  # 纯黑色图片
                for _i in range(len(_corp_images)):
                    # 根据比例改变图片大小
                    _width = round(_corp_images[_i].size[0] / float(_max_width) * 100.0)
                    _height = round(_corp_images[_i].size[1] / float(_max_height) * 100.0)
                    _corp = _corp_images[_i].resize((_width, _height))

                    # 粘贴上去
                    _obj_image.paste(
                        _corp,
                        (100 * _i, 0, 100 * _i + _width, _height)
                    )
        else:
            # 判断挂件类型
            if len(_np_scores) > 0 and _np_scores[0] >= _graph['min_score']:
                _match_score = _np_scores[0]
                _match_index = 0

        if _match_index == -1:
            # 没有找到最佳匹配的图片, 直接返回原图片的输入信息即可
            return input_data

        if not (processer_name == 'PendantTypeDetect' and input_data['type'] in ['earrings', 'chain']):
            # 非耳环和项链的二次挂件识别，进行截图处理
            _ymin = int(_np_boxes[_match_index][0] * _image.size[1])
            _xmin = int(_np_boxes[_match_index][1] * _image.size[0])
            _ymax = int(_np_boxes[_match_index][2] * _image.size[1])
            _xmax = int(_np_boxes[_match_index][3] * _image.size[0])
            _obj_image = _image.crop((_xmin, _ymin, _xmax, _ymax))

            if processer_name == 'PendantTypeDetect':
                # 挂件，获取中间部分，以去掉非翡翠部分背景
                _obj_image = cls.get_image_center(
                    _obj_image, center_field=_config.get('cut_center_field', 0.7)
                )

        # 处理类型
        _type = _graph['labelmap'][int(_np_classes[_match_index])]
        if _type.startswith('bangle_'):
            # 手镯的情况
            _sub_type = _type
            _type = 'bangle'
        elif input_data['type'] == '':
            if processer_name == 'PendantTypeDetect':
                # 挂件
                _sub_type = _type
                _type = 'pendant'
            else:
                _sub_type = ''
        else:
            _sub_type = _type
            _type = input_data['type']

        # 如果执行两次判断，则第二次为子分类
        return {
            'type': _type,
            'sub_type': _sub_type,
            'image': _obj_image,
            'score': float(_np_scores[_match_index])
        }

    @classmethod
    def mask_processer_initialize(cls, graph_var_name: str, processer_name: str):
        """
        对象识别掩码处理器的公共初始化函数

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

        _mask_graph = tf.Graph()
        with _mask_graph.as_default():
            _od_graph_def = tf.GraphDef()
            with tf.gfile.GFile(_pb_file, 'rb') as _fid:
                _serialized_graph = _fid.read()
                _od_graph_def.ParseFromString(_serialized_graph)
                tf.import_graph_def(_od_graph_def, name='')

        _ops = _mask_graph.get_operations()
        _all_tensor_names = {output.name for op in _ops for output in op.outputs}
        _tensor_dict = {}
        for key in ['num_detections', 'detection_boxes', 'detection_scores', 'detection_classes', 'detection_masks']:
            _tensor_name = key + ':0'
            if _tensor_name in _all_tensor_names:
                _tensor_dict[key] = _mask_graph.get_tensor_by_name(_tensor_name)

        _graph['session'] = tf.Session(graph=_mask_graph)
        _graph['tensor_dict'] = _tensor_dict
        _graph['image_tensor'] = _mask_graph.get_tensor_by_name('image_tensor:0')

    @classmethod
    def mask_processer_execute(cls, graph_var_name: str, processer_name: str, input_data,
                               context: dict, pipeline_obj):
        """
        对象识别掩码处理器的公共执行函数

        @param {str} graph_var_name - 对象识别冻结图全局变量名
        @param {str} processer_name - 处理器名
        @param {object} input_data - 处理器输入数据值
            输入图片信息字典
            {
                'type': # {str} 识别到的对象分类, ''代表没有找到分类
                'sub_type': # {str} 识别到的对象子分类， ''代表没有子分类
                'image': # {PIL.Image.Image} 图片对象
                'score': # {float} 匹配分数
            }
        @param {dict} context - 传递上下文，该字典信息将在整个管道处理过程中一直向下传递，可以在处理器中改变该上下文信息
        @param {Pipeline} pipeline_obj - 管道对象

        @returns {object} - 处理结果输出数据值
            返回图片分类及对应处理后的图片截图字典:
                {
                    'type': # {str} 识别到的对象分类, ''代表没有找到分类
                    'sub_type': # {str} 识别到的对象子分类， ''代表没有子分类
                    'image': # {PIL.Image.Image} 通过截图处理后的图片对象
                    'score': # {float} 匹配分数
                }
        """
        # _config = RunTool.get_global_var('PIPELINE_PROCESSER_PARA')[processer_name]
        _graph = RunTool.get_global_var(graph_var_name)
        _tensor_dict = copy.copy(_graph['tensor_dict'])

        # 准备图片
        _image = input_data['image']
        _image_np_expanded = np.expand_dims(_image, axis=0)

        # 掩码图片处理
        _detection_boxes = tf.squeeze(_tensor_dict['detection_boxes'], [0])
        _detection_masks = tf.squeeze(_tensor_dict['detection_masks'], [0])
        # Reframe is required to translate mask from box coordinates to image coordinates and fit the image size.
        _real_num_detection = tf.cast(_tensor_dict['num_detections'][0], tf.int32)
        _detection_boxes = tf.slice(_detection_boxes, [0, 0], [_real_num_detection, -1])
        _detection_masks = tf.slice(_detection_masks, [0, 0, 0], [_real_num_detection, -1, -1])
        # detection_masks_reframed = utils_ops.reframe_box_masks_to_image_masks(
        #     detection_masks, detection_boxes, image.shape[0], image.shape[1])
        _detection_masks_reframed = cls.reframe_box_masks_to_image_masks(
            _detection_masks, _detection_boxes, _image.size[1], _image.size[0])
        _detection_masks_reframed = tf.cast(
            tf.greater(_detection_masks_reframed, 0.5), tf.uint8)
        # Follow the convention by adding back the batch dimension
        _tensor_dict['detection_masks'] = tf.expand_dims(
            _detection_masks_reframed, 0)

        # 进行识别
        _output_dict = _graph['session'].run(_tensor_dict,
                                             feed_dict={_graph['image_tensor']: _image_np_expanded})

        # all outputs are float32 numpy arrays, so convert types as appropriate
        _output_dict['num_detections'] = int(_output_dict['num_detections'][0])
        if _output_dict['num_detections'] <= 0 or float(_output_dict['detection_scores'][0][0]) < _graph['min_score']:
            # 没有匹配到对象, 直接返回原图片的输入信息即可
            return input_data

        _output_dict['detection_classes'] = _output_dict[
            'detection_classes'][0][0].astype(np.uint8)
        _output_dict['detection_boxes'] = _output_dict['detection_boxes'][0][0]
        _output_dict['detection_scores'] = float(_output_dict['detection_scores'][0][0])
        _output_dict['detection_masks'] = _output_dict['detection_masks'][0][0]

        # 进行图片处理，仅保留mask部分内容，其余部分为黑色
        input_data['score'] = _output_dict['detection_scores']
        _image_pix = _image.load()
        for _x in range(_image.size[0]):
            for _y in range(_image.size[1]):
                if _output_dict['detection_masks'][_y][_x] == 0:
                    _image_pix[_x, _y] = (0, 0, 0)

        input_data['image'] = _image
        return input_data

    @classmethod
    def get_image_center(cls, image, center_field: float = 1.0):
        """
        截取图片中间区域

        @param {PIL.Image.Image} image - 要截取的图片
        @param {float} center_field=1.0 - 要获取的图片中间区域比例

        @returns {PIL.Image.Image} - 返回截取后的图片对象
        """
        _center_field = min(max(center_field, 0.0), 1.0)
        _x_cut = round((image.size[0] * (1.0 - _center_field)) / 2.0)
        _y_cut = round((image.size[1] * (1.0 - _center_field)) / 2.0)
        return image.crop((_x_cut, _y_cut, image.size[0] - _x_cut, image.size[0] - _y_cut))

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
                'image': # {PIL.Image.Image} 图片对象
                'score': # {float} 匹配分数
            }
        @param {dict} context - 传递上下文，该字典信息将在整个管道处理过程中一直向下传递，可以在处理器中改变该上下文信息
        @param {Pipeline} pipeline_obj - 管道对象

        @returns {object} - 处理结果输出数据值
            返回图片分类及对应处理后的图片截图字典:
                {
                    'type': # {str} 识别到的对象分类, ''代表没有找到分类
                    'sub_type': # {str} 识别到的对象子分类， ''代表没有子分类
                    'image': # {PIL.Image.Image} 通过截图处理后的图片对象
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
            <cut_center_field type="float">0.7</cut_center_field>
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
                'image': # {PIL.Image.Image} 图片对象
                'score': # {float} 匹配分数
            }
        @param {dict} context - 传递上下文，该字典信息将在整个管道处理过程中一直向下传递，可以在处理器中改变该上下文信息
        @param {Pipeline} pipeline_obj - 管道对象

        @returns {object} - 处理结果输出数据值
            返回图片分类及对应处理后的图片截图字典:
                {
                    'type': # {str} 识别到的对象分类, ''代表没有找到分类
                    'sub_type': # {str} 识别到的对象子分类， ''代表没有子分类
                    'image': # {PIL.Image.Image} 通过截图处理后的图片对象
                    'score': # {float} 匹配分数
                }
        """
        return Tools.detect_processer_execute(
            PR_PENDANT_TYPE_DETECT_GRAPH, cls.processer_name(), input_data, context, pipeline_obj
        )


class BangleMaskDetect(PipelineProcesser):
    """
    识别手镯的掩码图片处理

    @example 管道的processer_para配置如下
        <BangleMaskDetect>
            <frozen_graph>../test_data/tf_models/bangle_mask/frozen_inference_graph.pb</frozen_graph>
            <labelmap>../test_data/tf_models/bangle_mask/labelmap.pbtxt</labelmap>
            <encoding>utf-8</encoding>
            <min_score type="float">0.8</min_score>
        </BangleMaskDetect>
    """
    @classmethod
    def initialize(cls):
        """
        初始化处理类
        装载TF识别模型冻结图
        """
        Tools.mask_processer_initialize(PR_BANGLE_MASK_DETECT_GRAPH, cls.processer_name())

    @classmethod
    def processer_name(cls) -> str:
        """
        处理器名称，唯一标识处理器

        @returns {str} - 当前处理器名称
        """
        return 'BangleMaskDetect'

    @classmethod
    def execute(cls, input_data, context: dict, pipeline_obj):
        """
        执行处理

        @param {object} input_data - 处理器输入数据值
            输入图片信息字典
            {
                'type': # {str} 识别到的对象分类, ''代表没有找到分类
                'sub_type': # {str} 识别到的对象子分类， ''代表没有子分类
                'image': # {PIL.Image.Image} 图片对象
                'score': # {float} 匹配分数
            }
        @param {dict} context - 传递上下文，该字典信息将在整个管道处理过程中一直向下传递，可以在处理器中改变该上下文信息
        @param {Pipeline} pipeline_obj - 管道对象

        @returns {object} - 处理结果输出数据值
            返回图片分类及对应处理后的图片截图字典:
                {
                    'type': # {str} 识别到的对象分类, ''代表没有找到分类
                    'sub_type': # {str} 识别到的对象子分类， ''代表没有子分类
                    'image': # {PIL.Image.Image} 通过截图处理后的图片对象
                    'score': # {float} 匹配分数
                }
        """
        return Tools.mask_processer_execute(
            PR_BANGLE_MASK_DETECT_GRAPH, cls.processer_name(), input_data, context, pipeline_obj
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
                'image': # {PIL.Image.Image} 图片对象
                'score': # {float} 匹配分数
            }
        @param {dict} context - 传递上下文，该字典信息将在整个管道处理过程中一直向下传递，可以在处理器中改变该上下文信息
        @param {Pipeline} pipeline_obj - 管道对象

        @returns {object} - 处理结果输出数据值
            {
                'type': # {str} 识别到的对象分类, ''代表没有找到分类
                'sub_type': # {str} 识别到的对象子分类， ''代表没有子分类
                'image': # {PIL.Image.Image} 图片对象
                'score': # {float} 匹配分数
                'vertor': # {numpy.ndarray} 特征向量
            }
        """
        _config = RunTool.get_global_var('PIPELINE_PROCESSER_PARA')[cls.processer_name()]
        _size = _config.get('image_size', 299)

        # 转换图片大小
        _image = input_data['image']
        _image = _image.resize((_size, _size)).convert("RGB")
        _histogram = _image.histogram()

        # 对直方图进行归一化处理
        _max = float(_size * _size)
        _min = 0
        _normalize = [float(i) / (_max - _min)for i in _histogram]

        # 返回特征变量
        input_data['vertor'] = np.array(_normalize)
        input_data['image'] = _image
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
                'image': # {PIL.Image.Image} 图片对象
                'score': # {float} 匹配分数
            }
        @param {dict} context - 传递上下文，该字典信息将在整个管道处理过程中一直向下传递，可以在处理器中改变该上下文信息
        @param {Pipeline} pipeline_obj - 管道对象

        @returns {object} - 处理结果输出数据值
            {
                'type': # {str} 识别到的对象分类, ''代表没有找到分类
                'sub_type': # {str} 识别到的对象子分类， ''代表没有子分类
                'image': # {PIL.Image.Image} 图片对象
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
        _image = input_data['image']
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

                # if _hsv == (0.0, 0.0, 0.0) or _hsv == (0.0, 0.0, 100.0):
                if _hsv == (0.0, 0.0, 0.0):
                    # 删除黑色的点，减少背景的干扰, 只看有颜色的部分(保留白色，反光部分可能有影响)
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

        # 返回特征变量
        input_data['vertor'] = np.array(_normalize)
        input_data['image'] = _image
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
                    'image': # {PIL.Image.Image} 通过截图处理后的图片对象
                    'score': # {float} 匹配分数
                }
        """
        _output = {
            'type': input_data.get('collection', ''),  # 初始化的数据集
            'sub_type': '',
            'image': Image.open(BytesIO(input_data['image'])),
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
                'image': # {PIL.Image.Image} 图片对象
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

        # 转换图片对象
        _img_bytesio = BytesIO()
        input_data['image'].save(_img_bytesio, format='JPEG')
        input_data['image'] = _img_bytesio.getvalue()

        return input_data


if __name__ == '__main__':
    # 当程序自己独立运行时执行的操作
    # 打印版本信息
    print(('模块名：%s  -  %s\n'
           '作者：%s\n'
           '发布日期：%s\n'
           '版本：%s' % (__MOUDLE__, __DESCRIPT__, __AUTHOR__, __PUBLISH__, __VERSION__)))

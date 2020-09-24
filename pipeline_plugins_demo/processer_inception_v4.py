#!/usr/bin/env python3
# -*- coding: UTF-8 -*-
# Copyright 2019 黎慧剑
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

"""
Inception_V4的处理器模块
@module processer_inception_v4
@file processer_inception_v4.py
"""

import os
import sys
import tensorflow as tf
import numpy as np
from HiveNetLib.base_tools.run_tool import RunTool
# 根据当前文件路径将包路径纳入，在非安装的情况下可以引用到
sys.path.append(os.path.abspath(os.path.join(
    os.path.dirname(__file__), os.path.pardir)))
from search_by_image.lib.pipeline import PipelineProcesser


__MOUDLE__ = 'processer_inception_v4'  # 模块名
__DESCRIPT__ = u'Inception_V4的处理器模块'  # 模块描述
__VERSION__ = '0.1.0'  # 版本
__AUTHOR__ = u'黎慧剑'  # 作者
__PUBLISH__ = '2020.09.14'  # 发布日期


# inception_v4特征变量获取全局变量名
PR_INCEPTION_V4_VERTOR_GRAPH = 'PR_INCEPTION_V4_VERTOR_GRAPH'


class Tools(object):
    """
    工具函数
    """

    @classmethod
    def load_label(cls, path: str, encoding: str = 'utf-8') -> dict:
        """
        装载*.label文件到字典

        @param {str} path - labelmap文件路径, 文件格式如下
            0:daisy
            1:dandelion
            2:roses
            3:sunflowers
            4:tulips
        @param {str} encoding='utf-8' - 编码

        @returns {dict} - 返回的字典
            {
                id : name,
            }
        """
        _map = dict()
        with open(path, 'r', encoding=encoding) as _fid:
            _lines = _fid.readlines()
            for _line in _lines:
                # 逐行处理
                _line = _line.strip()
                if _line == '':
                    continue
                else:
                    _para = _line.split(':')
                    _map[int(_para[0].strip())] = _para[1].strip()

        # 返回字典
        return _map

    @classmethod
    def inception_v4_processer_initialize(cls, graph_var_name: str, processer_name: str):
        """
        inception_v4图像分类模型的公共初始化函数

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
        _graph['image_size'] = _config.get('image_size', 299)
        _graph['labelmap'] = Tools.load_label(
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

        # 图像分类出口
        _graph['softmax_tensor'] = _detection_graph.get_tensor_by_name(
            'InceptionV4/Logits/Predictions:0')

        # 特征变量出口
        _graph['vertor_tensor'] = _detection_graph.get_tensor_by_name(
            'InceptionV4/Logits/AvgPool_1a/AvgPool:0')

    @classmethod
    def inception_v4_preprocess_image(cls, image, height, width, central_fraction=None):
        if image.dtype != tf.float32:
            image = tf.image.convert_image_dtype(image, dtype=tf.float32)
        # Crop the central region of the image with an area containing 87.5% of
        # the original image.
        if central_fraction:
            image = tf.image.central_crop(image, central_fraction=central_fraction)

        if height and width:
            # Resize the image to the specified height and width.
            image = tf.expand_dims(image, 0)
            image = tf.image.resize_bilinear(image, [height, width],
                                             align_corners=False)
            image = tf.squeeze(image, [0])
        image = tf.subtract(image, 0.5)
        image = tf.multiply(image, 2.0)
        return image


class InceptionV4Vertor(PipelineProcesser):
    """
    inception_v4分类算法特征变量获取

    @example 管道的processer_para配置如下
        <InceptionV4Vertor>
            <frozen_graph>../test_data/tf_models/inception_v4/inception_v4_freeze.pb</frozen_graph>
            <labelmap>../test_data/tf_models/inception_v4/inception_v4_freeze.label</labelmap>
            <encoding>utf-8</encoding>
            <image_size type="int">299</image_size>
            <min_score type="float">0.1</min_score>
        </InceptionV4Vertor>
    """

    @classmethod
    def initialize(cls):
        """
        初始化处理类
        装载TF识别模型冻结图
        """
        Tools.inception_v4_processer_initialize(PR_INCEPTION_V4_VERTOR_GRAPH, cls.processer_name())

    @classmethod
    def processer_name(cls) -> str:
        """
        处理器名称，唯一标识处理器

        @returns {str} - 当前处理器名称
        """
        return 'InceptionV4Vertor'

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
            {
                'collection': {str} 匹配到的集合类型
                'image': # {bytes} 图片bytes对象
                'vertor': # {numpy.ndarray} 特征向量
            }
        """
        _graph = RunTool.get_global_var(PR_INCEPTION_V4_VERTOR_GRAPH)

        # 进行图像预处理
        with tf.Graph().as_default():
            _image_data = tf.image.decode_jpeg(input_data['image'])
            _image_data = Tools.inception_v4_preprocess_image(
                _image_data, _graph['image_size'], _graph['image_size']
            )
            _image_data = tf.expand_dims(_image_data, 0)
            with tf.Session() as sess:
                # pass
                _image_data = sess.run(_image_data)

        # 运行模型
        _predictions = _graph['session'].run(_graph['vertor_tensor'], {'input:0': _image_data})
        _predictions = np.squeeze(_predictions)

        # 返回特征变量
        input_data['vertor'] = _predictions
        return input_data


class InceptionV4Classifier(PipelineProcesser):
    """
    inception_v4分类处理器

    @example 管道的processer_para配置如下
        <InceptionV4Vertor>
            <frozen_graph>../test_data/tf_models/inception_v4/inception_v4_freeze.pb</frozen_graph>
            <labelmap>../test_data/tf_models/inception_v4/inception_v4_freeze.label</labelmap>
            <encoding>utf-8</encoding>
            <image_size type="int">299</image_size>
            <min_score type="float">0.1</min_score>
        </InceptionV4Vertor>
    """
    @classmethod
    def initialize(cls):
        """
        初始化处理类
        装载TF识别模型冻结图
        """
        Tools.inception_v4_processer_initialize(PR_INCEPTION_V4_VERTOR_GRAPH, 'InceptionV4Vertor')

    @classmethod
    def processer_name(cls) -> str:
        """
        处理器名称，唯一标识处理器

        @returns {str} - 当前处理器名称
        """
        return 'InceptionV4Classifier'

    @classmethod
    def execute(cls, input_data, context: dict, pipeline_obj):
        """
        执行处理

        @param {object} input_data - 处理器输入数据值
            输入图片信息字典
            {
                'image': # {bytes} 图片bytes对象
            }
        @param {dict} context - 传递上下文，该字典信息将在整个管道处理过程中一直向下传递，可以在处理器中改变该上下文信息
        @param {Pipeline} pipeline_obj - 管道对象

        @returns {object} - 处理结果输出数据值
            返回图片分类及对应处理后的图片截图字典:
                {
                    'class': # {str} 分类
                    'image': # {bytes} 通过截图处理后的图片bytes对象
                    'score': # {float} 匹配分数
                }
        """
        _graph = RunTool.get_global_var(PR_INCEPTION_V4_VERTOR_GRAPH)

        # 进行图像预处理
        with tf.Graph().as_default():
            _image_data = tf.image.decode_jpeg(input_data['image'])
            _image_data = Tools.inception_v4_preprocess_image(
                _image_data, _graph['image_size'], _graph['image_size']
            )
            _image_data = tf.expand_dims(_image_data, 0)
            with tf.Session() as sess:
                # pass
                _image_data = sess.run(_image_data)

        # 运行模型
        _predictions = _graph['session'].run(_graph['softmax_tensor'], {'input:0': _image_data})
        _predictions = np.squeeze(_predictions)

        # 排序
        _num_top_predictions = 1  # 只取第一个
        _top_k = _predictions.argsort()[-_num_top_predictions:][::-1]

        input_data['class'] = ''
        if _predictions[0] > _graph['min_score']:
            input_data['class'] = _graph['labelmap'][_top_k[0]]
            input_data['score'] = float(_predictions[0])

        return input_data


if __name__ == '__main__':
    # 当程序自己独立运行时执行的操作
    # 打印版本信息
    print(('模块名：%s  -  %s\n'
           '作者：%s\n'
           '发布日期：%s\n'
           '版本：%s' % (__MOUDLE__, __DESCRIPT__, __AUTHOR__, __PUBLISH__, __VERSION__)))

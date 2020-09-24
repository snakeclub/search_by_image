# 以图搜图（search_by_image）
该开源项目是基于Milvus（一个开源的特征向量相似度搜索引擎），实现以图搜图的功能，基于一张上传的找到已存储的相似图片。所用到的技术包括：

（1）图片特征向量提取：可以用多种技术获取图片的特征向量，本文采用的是TensorFLow Slim的图像分类算法 inception_v4 进行训练并获取图片特征；您也可以使用其他技术处理，例如VGG16，或者使用OpenCV来获取图像特征；

（2）特征向量相似度搜索：通过对比图片特征向量的相似度来确认图像是否相似，本文采用的是Milvus作为特征向量存储及相似度搜索。



# 安装依赖服务

## 安装MySQL

本项目使用MySql 5.7作为Milvus的持久化数据库。

1、通过docker安装数据库

```
# 获取镜像
$ sudo docker pull mysql:5.7
```

2、自定义数据库的启动参数

```
# 创建本地目录
mkdir -p /home/ubuntu18/milvus/mysql/conf /home/ubuntu18/milvus/mysql/logs /home/ubuntu18/milvus/mysql/data

# 启动镜像
$ docker run -p 3306:3306 --name mysql5.7 -e MYSQL_ROOT_PASSWORD=123456 -d mysql:5.7

# 获取dockers的容器id (CONTAINER ID)
$ docker ps

# 复制docker默认的mysql配置文件，用于修改成自己的配置文件
$ docker cp 2d1d71afff2f:/etc/mysql/mysql.cnf /home/ubuntu18/milvus/mysql/conf/my.cnf

# 编辑my.cnf
$ vi my.cnf

# 删除临时docker
$ docker stop 2d1d71afff2f
$ docker rm 2d1d71afff2f
```

可以编辑的my.cnf内容如下，按需定制：

```
# 原默认内容
!includedir /etc/mysql/conf.d/
!includedir /etc/mysql/mysql.conf.d/

[client]
#客户端设置
port=3306
default-character-set=utf8mb4

[mysql.server]
default-character-set=utf8mb4

[mysqld_safe]
default-character-set=utf8mb4

[mysqld]
#mysql启动时使用的用户
user=mysql
#默认连接端口
port=3306
#端口绑定的ip地址，0.0.0.0表示允许所有远程访问，127.0.0.1表示只能本机访问，默认值为*
bind-address=0.0.0.0
 
#系统数据库编码设置，排序规则
character_set_server=utf8mb4
collation_server=utf8mb4_bin
 
#secure_auth 为了防止低版本的MySQL客户端(<4.1)使用旧的密码认证方式访问高版本的服务器。MySQL 5.6.7开始secure_auth 默认为启用值1
secure_auth=1
 
#linux下要严格区分大小写，windows下不区分大小写
#1表示不区分大小写，0表示区分大小写。
lower_case_table_names=0
```

3、启动正式的镜像

```
# 启动镜像
$ docker run -p 3306:3306 --name milvusdb \
-v /home/ubuntu18/milvus/mysql/conf/my.cnf:/etc/mysql/my.cnf \
-v /home/ubuntu18/milvus/mysql/data:/var/lib/mysql \
-v /home/ubuntu18/milvus/mysql/logs:/var/log/mysql \
-e MYSQL_ROOT_PASSWORD=123456 -d mysql:5.7

# 进入mysql的容器命令行
$ docker exec -ti milvusdb bash

# 登陆
mysql -uroot -p123456

# 开启远程连接
GRANT ALL PRIVILEGES ON *.* TO 'root'@'%' IDENTIFIED BY '123456' WITH GRANT OPTION;
FLUSH PRIVILEGES;

# 创建数据库
create database milvus_image;

# 退出
exit;
```

4、查找docker宿主机的访问IP地址（用于milvus的配置通过docker访问）

```
# 查找docker宿主机的访问IP地址
$ ip addr show docker0
3: docker0: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500 qdisc noqueue state UP group default qlen 1000
    link/ether 56:84:7a:fe:97:99 brd ff:ff:ff:ff:ff:ff
    inet 172.17.42.1/16 scope global docker0
       valid_lft forever preferred_lft forever
    inet6 fe80::5484:7aff:fefe:9799/64 scope link 
       valid_lft forever preferred_lft forever
```



## 安装Milvus服务

详细安装材料可参考官网文档：https://milvus.io/cn/docs/v0.10.0/guides/get_started/install_milvus/cpu_milvus_docker.md

建议采用docker方式进行安装（注意要求docker版本19.03以上），具体步骤如下：

1、通过docker pull获取docker镜像

```
sudo docker pull milvusdb/milvus:0.10.0-cpu-d061620-5f3c00
```

注:  安装过程可能会遇到以下问题，可参考以下解决方案

（1）docker pull中间取消后，重新获取出现“Repository milvusdb/milvus already being pulled by another client. Waiting.”错误，该问题是一个bug，可以通过重启docker方法解决：

```
sudo service docker stop
sudo service docker start
```

2、下载配置文件及创建相应目录

```
$ mkdir -p /home/ubuntu18/search_by_image/milvus/conf
$ cd /home/ubuntu18/search_by_image/milvus
$ mkdir -p db logs wal
$ cd /home/ubuntu18/search_by_image/milvus/conf
$ wget https://raw.githubusercontent.com/milvus-io/milvus/v0.10.0/core/conf/demo/server_config.yaml
```

注：如果下载不了，可自行编辑创建该配置文件

3、修改配置文件server_config.yaml，指定持久化至mysql数据库中

```
# 将meta_uri参数修改为（注意IP地址为MySQL docker宿主机的访问IP地址）
meta_uri: mysql://root:123456@172.17.42.1:3306/milvus_image
```

4、启动容器（注意：由于本机已经启动一个milvus服务，因此映射的端口进行了调整）

```
$ sudo docker run -d --name milvus_image \
-p 19531:19530 \
-p 19122:19121 \
-v /home/ubuntu18/search_by_image/milvus/db:/var/lib/milvus/db \
-v /home/ubuntu18/search_by_image/milvus/conf:/var/lib/milvus/conf \
-v /home/ubuntu18/search_by_image/milvus/logs:/var/lib/milvus/logs \
-v /home/ubuntu18/search_by_image/milvus/wal:/var/lib/milvus/wal \
milvusdb/milvus:0.10.0-cpu-d061620-5f3c00
```

上述命令中用到的 `docker run` 参数定义如下：

- `-d`: 运行 container 到后台并打印 container id。
- `--name`: 为 container 分配一个名字。
- `-p`: 暴露 container 端口到 host。
- `-v`: 将路径挂载至 container。

5、确认 Milvus 运行状态

```
$ docker ps
```

如果docker没有正常启动，可以执行以下命令查看错误日志：

```
 # 获得运行 Milvus 的 container ID。
 $ docker ps -a
 # 检查 docker 日志。
 $ docker logs <milvus container id>
```



## MongoDB

MongoDB 是一个免费的开源跨平台面向文档的 NoSQL 数据库程序，本项目使用MongoDB登记每张图片的特征向量存储id（milvus_id）和图像的基本信息（如图片url等）。

1、通过docker获取数据库镜像

```
# 获取镜像，需要注意版本为4.4以下，这个是目前pymongo所支持的版本
$ sudo docker pull mongo:latest

# 或选择指定版本的镜像
$ sudo docker pull mongo:4.4
```

2、创建本地化的目录

```
$ mkdir /home/ubuntu18/search_by_image/mongodb
$ cd /home/ubuntu18/search_by_image/mongodb
$ mkdir -p data backup configdb conf
```

3、在 conf 目录下创建配置文件 mongodb.conf ，内容如下：

```
# 绑定服务IP，若绑定127.0.0.1，则只能本机访问，不指定默认本地所有IP
# bind_ip=127.0.0.1
# 指定服务端口号，默认端口27017
port=27017
```

4、启动容器

```
$ sudo docker run -d --name mongodb_image \
-p 27017:27017 \
-v /home/ubuntu18/search_by_image/mongodb/data:/data/db \
-v /home/ubuntu18/search_by_image/mongodb/configdb:/data/configdb \
-v /home/ubuntu18/search_by_image/mongodb/backup:/data/backup \
-v /home/ubuntu18/search_by_image/mongodb/conf:/etc/mongo \
mongo \
--auth \
--config /etc/mongo/mongodb.conf
```

5、添加用户和设置密码，并且尝试连接

```
$ docker exec -it mongodb_image mongo admin
# 创建管理员用户
> use admin
> db.createUser({ user: 'root', pwd: 'root', roles: [ { role: "userAdminAnyDatabase", db: "admin" } ] })

# 使用管理员用户连接数据库
> db.auth('root', 'root')

# 创建应用连接用户，注意需指定数据库
> use jade_search_db
> db.createUser(
  {
    user: "jade",
    pwd: "123456",
    roles: [ { role: "readWrite", db: "jade_search_db" }
             ]
  }
)

# 退出
> exit
```



# 安装search_by_image

## 安装及启动应用

1、将search_by_image源码下载到服务器：https://github.com/snakeclub/search_by_image

2、安装依赖包，基于源码目录下的requriment.txt安装清单：

```
$ pip install -i https://pypi.tuna.tsinghua.edu.cn/simple -r requriment.txt
```

3、按照《附录 - Demo示例 inception_v4 准备方法》章节，生成 inception_v4 冻结模型，并将模型文件 inception_v4_freeze.pb 放置在 search_by_image/test_data/tf_models/inception_v4_pre/ 目录下；此外也需将转换tf-record中生成的 labels.txt 复制到该目录下；（该步骤为运行Demo所需，如果执行自己的应用可以不处理）

4、按实际环境情况，修改 search_by_image/search_by_image/conf/server.xml的配置信息，主要需要修改的信息包括：

mongodb ： MongoDB的连接配置

milvus  : Milvus服务器的连接配置

5、导入Demo测试数据，执行 import_demo_image.py 脚本：

```
$ cd ~search_by_image/test/
$ python import_demo_image.py
```

**注：该脚本导入了猫、狗、仓鼠3类动物图片用于测试，如果需导入其他图片可以自行修改或添加 IMPORT_URLS 字典。**

6、使用search_by_image/search_by_image/server.py启动以图搜图服务

```
$ cd ~search_by_image/search_by_image/
$ python server.py
```

程序将自动找到当前目录下的./conf/server.xml配置文件，如果需要指定其他配置文件，可以在命令中指定配置文件：

```
$ python server.py config="d:/test/server.xml"
```

8、通过浏览器打开Demo页面：http://127.0.0.1:8002/

9、在百度上找一个猫的图片，填入图片URL地址，然后点击URL图片搜索，可以搜索出有相似特征的猫的图片，如下图：

![image-20200924132632215](README.assets/image-20200924132632215.png)



## 维护搜索图片库

search_by_image服务端并不存储图片文件，仅存储图片的特征向量数组（值在0-1之间的浮点数数组）和图片信息字典（可以json字典存储图片的一些信息，例如文件id、文件名、访问url等），因此具体应用自行保存图片文件，以及实现根据图片信息字典展示图片的功能。

搜索图片库可以采取以下两类方法进行维护：

**1、自行实现导入代码**

利用 search_by_image/search_by_image/lib/search.py 的 SearchEngine 图片导入处理，具体方法包括：

- clear_search_db : 清楚已导入的所有搜索图片信息
- image_to_search_db : 单个图片导入
- import_images : 指定目立下多个图片批量导入，要求相同目录下必须有同样文件名的json文件记录图片信息，例如 "abc.jpg" 对应的json文件为 “abc.json”
- remove_images : 通过指定条件删除已导入的特定图片
- get_images : 查询已导入的图片清单，支持分页

**2、通过 restful api 接口导入**

启动search_by_image服务，利用服务提供的 restful api 接口进行单个搜索图片的导入处理，具体接口参数定义见 search_by_image/search_by_image/lib/restful_api.py 的定义：

- /api/SearchServer/ImportByUpload : 通过上传本地文件的方式导入搜索图片
- /api/SearchServer/ImportByBase64 : 通过传入文件BASE64编码的方式导入搜索图片
- /api/SearchServer/ImportByUrl : 通过指定图片访问url的方式导入搜索图片（推荐）
- /api/SearchServer/RemoveImageDoc : 通过指定条件删除已导入的搜索图片
- /api/SearchServer/GetImageDoc : 获取已导入的搜索图片信息



# 利用管道（Pipeline）插件自定义搜索应用

不同的特征向量提取技术所得到的图片特征不同，如果想自行实现一些特殊的图片搜索功能（例如基于主体颜色搜索，或者对图片进行识别、截取、颜色变换等方式处理后再搜索），可通过开发自定义的管道（Pipeline）插件实现相关功能。

## 图像搜索处理流程

- 搜索图片导入流程：【图片文件(data) +  指定分类（collection, 可选）】 -> 特征向量处理管道 -> 【特征向量(vertor) + 分类(collection)】-> 存入Milvus向量库（存入指定collection） -> 【向量ID + 信息字典(image_doc) + 分类(collection)】-> 存入MongoDB
- 搜索流程：【图片文件(data) +  指定分类（collection, 可选）】 -> 特征向量处理管道 -> 【特征向量(vertor) + 分类(collection)】-> 通过Milvus向量库查询相似向量 -> 【相似向量ID清单(top、匹配度筛选) + 分类(collection)】-> 从MongoDB获取信息 -> 【匹配信息字典清单(image_doc)】

可以看出来，判断图片是否相似的关键在于图片的特征向量提取环节，也就是 “特征向量处理管道” 所提取到的图像特征向量值，搜索图片导入和搜索流程所使用的是同一个处理管道，可以通过变更管道实现来支持各种不同的搜索应用需求。

## 管道开发及部署步骤

**1、进行管道插件开发**

管道插件有两类：

- 管道处理器（PipelineProcesser）：针对管道的输入数据（input_data）进行处理，其输出的处理结果数据（output）将作为下一个管道处理器的输入；管道处理器需继承 search_by_image/search_by_image/lib/pipeline.py 的 PipelineProcesser 类；
- 管道路由器（PipelineRouter）：衔接管道处理器之间的执行判断，如果管道之间没有设置管道路由器，则会按顺序执行，可通过管道路由器控制跳转到特定处理节点（Node），实现灵活的管道执行流设置；管道路由器需继承 search_by_image/search_by_image/lib/pipeline.py 的 PipelineRouter 类；

开发search_by_image的管道插件有以下注意要点：

- 管道的标准输入（input_data）固定为如下字典，注意第一个处理节点（Node）的管道处理器应支持该输入：

```
{
    'image': # {bytes} 图片bytes对象
    'collection': # {str} 初始化时可以指定集合
}
```

- 管道的标准输出（output）必须固定为以下字典，注意最后一个处理节点（Node）的管道处理器应按照该字典形式进行输出：

```
{
    'collection': {str} 匹配到的集合类型
    'image': # {bytes} 图片bytes对象
    'vertor': # {numpy.ndarray} 特征向量
}
```

- 管道中间处理节点（Node）的管道处理器可以按照具体应用需要设计自身的输入和输出，但要注意在管道流程设计中衔接的两个管道处理器的输入和输出必须匹配；

- 管道处理器和管道路由器均可以通过上下文字典（context）获取及放入全流程共享的变量值，用于进行逻辑处理及路由的判断；
- 一个py文件可以同时放多个管道处理器和管道路由器，也可以拆分为多个py文件，只是需要将这些插件文件放入到相同目录用于加载（例如d:\plugins\）;同时注意插件名称不应出现重复的情况。

**2、在 server.xml 文件配置管道插件装载目录，可以支持加载多个目录下的插件：**

```
<pipeline>
	<plugins_path>../pipeline_plugins, ../pipeline_plugins_demo</plugins_path>
	...
</pipeline>
```

**3、在 server.xml 文件配置管道插件自身的配置，相关参数可通过全局变量 “PIPELINE_PROCESSER_PARA” 获取，以管道处理器 “InceptionV4Vertor” 插件为示例：**

```
<pipeline>
	<processer_para>
        <InceptionV4Vertor>
            <frozen_graph>../test_data/tf_models/inception_v4_pre/inception_v4_freeze.pb</frozen_graph>
            <labelmap>../test_data/tf_models/inception_v4_pre/labels.txt</labelmap>
            <encoding>utf-8</encoding>
            <image_size type="int">299</image_size>
            <min_score type="float">0.1</min_score>
        </InceptionV4Vertor>
        ...
    </processer_para>
    ...
</pipeline>
```

注：管道路由器的配置在 router_para 标签下

**4、在 server.xml 文件配置管道流程，具体流程配置的要求可参考 search_by_image/search_by_image/lib/pipeline.py 的 Pipeline 的初始化参数入参定义：**

```
<pipeline>
	<pipeline_config>
        <DemoSearch>{
            "1": {
                "name": "input",
                "processor": "InceptionV4Vertor",
                "context": {},
                "router": "",
                "exception_router": ""
            }
        }
        </DemoSearch>
    </pipeline_config>
   ...
</pipeline>
```

**5、在 server.xml 文件修改 Milvus 的向量精度（dimension）参数，需要按最后一个处理节点的输出特征向量（vertor）的维度（数组长度）进行修改：**

```
<milvus>
	...
    <dimension type="int">1536</dimension>
    ...
</milvus>
```

**5、最后在导入搜索图片和进行图片搜索操作时，需统一传入该管道流程名（示例为 DemoSearch）进行处理。**



# 附录 - Demo示例 inception_v4 准备方法

本示例直接使用 Google 预训练的 inception_v4 模型进行相似图片的匹配，如果需要针对性的对某一类图片进行相似判断，可以在该模型的基础上进行重新训练或迁移训练，得到训练后的模型以针对特定场景。

inception_v4 预训练模型的下载地址：http://download.tensorflow.org/models/inception_v4_2016_09_09.tar.gz

进行模型训练、冻结模型输出的完整方法可参考：[TensorFlow-Slim图像分类训练及应用](https://github.com/snakeclub/DevStandards/blob/master/docs/ml/TensorFlow-Slim图像分类训练及应用.md)

以下我们以直接使用预训练模型的方式进行准备，由于预训练模型只有checkpoint文件（.ckpt），不能直接使用，因此我们可以通过以下步骤获取到可直接调用的冻结模型（注意以下方案所使用的tensorflow版本为1.15.0，对于2.x版本需要自行调整相关代码，针对完整训练方法，这里在代码上做了一些优化，简化了数据处理的操作步骤）：

1、安装tf-slim，参考[TensorFlow-Slim图像分类训练及应用](https://github.com/snakeclub/DevStandards/blob/master/docs/ml/TensorFlow-Slim图像分类训练及应用.md)；

2、准备要训练的图片，图片的目录名为训练的分类名，具体图片放在分类目录下；我们这边只是准备2张cat的图片，结构如下（放到dataset目录下，如果需要自己训练其他图片，可以自行放置更多的图片和分类目录）：

```
search_by_image
  |__inception_v4
    |__dataset
      |__cat
        |__00000001.jpg
        |__00000002.jpg
```

3、将训练图片转换为tf-record文件格式（使用convert_tool）：

编辑 ~/inception_v4/convert_tool 目录下的 convert_to_tfrecord.py 文件，调整验证集数量和分隔文件数：

```
# 图片验证集的数量
# The number of images in the validation set.
_NUM_VALIDATION = 1
...
# 将数据集拆分为多少个tfrecord文件
# The number of shards per dataset split.
_NUM_SHARDS = 1
```

执行以下命令进行转换：

```
$ cd ~/inception_v4/convert_tool
$ python convert_to_tfrecord.py --dataset_dir=../dataset --output_dir=../tf_dataset
```

4、解压预训练模型 inception_v4_2016_09_09.tar.gz 得到 预训练模型的ckpt文件；

5、进行自定义训练：

编辑 ~/inception_v4/train_tool 目录下的 train_image_classifier.py 文件，修改slim模型的路径为安装路径：

```
# 以下需要将slim模型的路径加入系统目录中：/home/ubuntu18/models-1.13.0/research/slim
sys.path.append('/home/ubuntu18/models-1.13.0/research/slim/')
```

执行以下命令进行训练：

```
$ cd ~/inception_v4/train_tool
$ python train_image_classifier.py \
  --train_dir=/home/ubuntu18/cc/training/inception_v4_src/trainning \
  --dataset_name=data \
  --dataset_split_name=train \
  --dataset_dir=/home/ubuntu18/cc/training/inception_v4_src/tf_dataset/ \
  --model_name=inception_v4 \
  --checkpoint_path=/home/ubuntu18/cc/training/inception_v4_src/inception_v4.ckpt \
  --checkpoint_exclude_scopes=InceptionV4/Logits,InceptionV4/AuxLogits/Aux_logits \
  --trainable_scopes=InceptionV4/Logits,InceptionV4/AuxLogits/Aux_logits \
  --max_number_of_steps=1 \
  --batch_size=32 \
  --learning_rate=0.00001 \
  --learning_rate_decay_type=fixed \
  --save_interval_secs=600 \
  --save_summaries_secs=600 \
  --log_every_n_steps=10 \
  --optimizer=rmsprop \
  --weight_decay=0.00004
```

**注：因为我们只是打算使用预训练模型的得到图片匹配的特征向量，因此训练只是为了产生冻结模型，所以只设置了执行一步（max_number_of_steps=1）。**

6、导出前向传播图

```
$ cd ~/inception_v4/train_tool
$ python export_inference_graph.py \
  --alsologtostderr \
  --dataset_dir=/home/ubuntu18/cc/training/inception_v4_src/tf_dataset/ \
  --dataset_name=data \
  --model_name=inception_v4 \
  --image_size=299 \
  --output_file=/home/ubuntu18/cc/training/inception_v4_src/export/inception_v4_inf.pb
```

7、导出冻结模型，得到可以获取特征变量的冻结模型文件 inception_v4_freeze.pb

```
$ cd ~/inception_v4/train_tool
$ python -u /home/ubuntu18/anaconda3/envs/tensorflow/lib/python3.7/site-packages/tensorflow_core/python/tools/freeze_graph.py \
  --input_graph=/home/ubuntu18/cc/training/inception_v4_src/export/inception_v4_inf.pb \
  --input_checkpoint=/home/ubuntu18/cc/training/inception_v4_src/trainning/model.ckpt-1 \
  --output_graph=/home/ubuntu18/cc/training/inception_v4_src/export/inception_v4_freeze.pb \
  --input_binary=True \
  --output_node_name=InceptionV4/Logits/Predictions
```

**注：需要找到tensorflow_core的安装目录获取冻结模型脚本。**
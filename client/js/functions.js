// 自定义函数
(function ($) {

    // Base64临时存储变量
    $.Base64 = '';

    // 获取图片展示HTML代码
    $.GetImageHtml = function (src, text) {
        html = "<div class=\"ImgContainer\">";
        html += "<a href=\"" + src + "\" target=\"_blank\"><img src=\"" + src + "\" alt=\"" + text + "\" /></a>";
        html += "<br /><a>" + text + "</a></div>";
        return html;
    };

    // 显示源图片（含清空对象）
    $.ShowSrcImage = function (src, text) {
        var divObj = $("#src_img_container");

        // 清空子对象
        divObj.empty();

        // 显示图片
        divObj.append($.GetImageHtml(src, text));
    };

    // 显示目标图片，不清空对象
    $.ShowDestImage = function (src, text) {
        var divObj = $("#dest_img_container");
        divObj.append($.GetImageHtml(src, text));
    };

    // 获取文件选择框并显示在源文件图片中
    $.GetFileAndShow = function () {
        var files = $('#file').get(0).files;
        if (!files || files.length == 0) {
            alert('没有选择图片文件！');
            return;
        };
        var file = files[0];

        // 获取 window 的 URL 工具
        var URL = window.URL || window.webkitURL;
        // 通过 file 生成目标 url
        var imgURL = URL.createObjectURL(file);
        // 使用下面这句可以在内存中释放对此 url 的伺服，跑了之后那个 URL 就无效了
        // URL.revokeObjectURL(imgURL);
        $.ShowSrcImage(imgURL, "源图");

        return file;
    };

    // 显示返回的相似图片
    $.ShowSearchImages = function (image_list) {
        // 逐个显示
        for (i = 0; i < image_list.length; i++) {
            var image = image_list[i];
            var text = "id:" + image.id + ", score:" + image.score + ", collection:" + image.collection;
            $.ShowDestImage(image.url, text);
        }
    };

    // 显示返回的已导入图片
    $.ShowImportedImages = function (image_list) {
        // 逐个显示
        for (i = 0; i < image_list.length; i++) {
            var image = image_list[i];
            var text = "id:" + image.id + ", collection:" + image.collection;
            $.ShowDestImage(image.url, text);
        }
    };

    // 生成随机字符串
    $.GetRandomString = function (len) {
        len = len || 32;
        var chars = 'ABCDEFGHJKMNPQRSTWXYZabcdefhijkmnprstwxyz2345678'; // 默认去掉了容易混淆的字符oOLl,9gq,Vv,Uu,I1
        var maxPos = chars.length;
        var pwd = '';
        for (i = 0; i < len; i++) {
            pwd += chars.charAt(Math.floor(Math.random() * maxPos));
        }
        return pwd;
    };


    // 导入本地图片
    $.Import = function () {
        var file = $.GetFileAndShow();
        if (!file) {
            return;
        }

        var url = 'file:///' + $('#image_path').val() + '/' + file.name;

        // 将文件对象打包成form表单类型的数据
        var formdata = new FormData;
        formdata.append('file', file);

        // 添加请求的json值, 将在form字典中获取
        formdata.append('interface_seq_id', $.GetRandomString(12));
        formdata.append('pipeline', $("#pipeline").val());
        formdata.append('collection', $("#collection").val());
        formdata.append('image_doc', '{"id": "' + Math.uuid() + '", "url": "' + url + '"}');

        var headers = {};

        // 进行文件数据的上传
        $.ajax({
            url: '/api/SearchServer/ImportByUpload',
            type: 'post',
            datatype: 'json',
            contentType: false,
            headers: headers,
            data: formdata,
            processData: false,
            async: true, // 异步处理
            success: function (result) {
                // 对数据json解析
                var retObj = result;
                if (retObj.status == "00000") {
                    // 上传成功
                    alert('上传成功');
                } else {
                    // 上传失败
                    alert('图片上传失败[' + retObj.status + '][' + retObj.msg + ']');
                }
            },
            error: function (xhr, status, error) {
                alert("图片上传异常: " + error);
            }
        });
    };

    // 导入BASE64图片
    $.ImportBase64 = function () {
        var file = $.GetFileAndShow();
        if (!file) {
            return;
        }

        // 将文件转换为Base64编码
        var reader = new FileReader();
        reader.onload = function () {
            // 生成调用参数
            var sendObj = new Object();
            sendObj.file = this.result;
            sendObj.interface_seq_id = $.GetRandomString(12);
            sendObj.pipeline = $("#pipeline").val();
            sendObj.collection = $("#collection").val();
            var url = 'file:///' + $('#image_path').val() + '/' + file.name;
            sendObj.image_doc = new Object();
            sendObj.image_doc.id = Math.uuid();
            sendObj.image_doc.url = url;

            var headers = {};

            // 调用问题查询处理
            $.ajax({
                url: "/api/SearchServer/ImportByBase64",
                type: 'post',
                contentType: 'application/json',
                headers: headers,
                data: JSON.stringify(sendObj),
                timeout: 10000,
                async: true, // 异步处理
                success: function (result) {
                    // 对数据json解析
                    var retObj = result;
                    if (retObj.status == "00000") {
                        // 上传成功
                        alert('上传成功');
                    } else {
                        // 上传失败
                        alert('图片上传失败[' + retObj.status + '][' + retObj.msg + ']');
                    }
                },
                error: function (xhr, status, error) {
                    alert("图片上传异常: " + error);
                }
            });
        }
        reader.readAsDataURL(file);
    };

    // 导入Url图片
    $.ImportUrl = function () {
        // 获取图片url并显示
        var img_url = $("#image_url").val();
        $.ShowSrcImage(img_url, "源图");

        // 生成调用参数
        var sendObj = new Object();
        sendObj.url = img_url;
        sendObj.interface_seq_id = $.GetRandomString(12);
        sendObj.pipeline = $("#pipeline").val();
        sendObj.collection = $("#collection").val();
        sendObj.image_doc = new Object();
        sendObj.image_doc.url = img_url;
        sendObj.image_doc.id = Math.uuid();

        var headers = {};

        // 调用问题查询处理
        $.ajax({
            url: "/api/SearchServer/ImportByUrl",
            type: 'post',
            contentType: 'application/json',
            headers: headers,
            data: JSON.stringify(sendObj),
            timeout: 10000,
            async: true, // 异步处理
            success: function (result) {
                // 对数据json解析
                var retObj = result;
                if (retObj.status == "00000") {
                    // 上传成功
                    alert('上传成功');
                } else {
                    // 上传失败
                    alert('图片上传失败[' + retObj.status + '][' + retObj.msg + ']');
                }
            },
            error: function (xhr, status, error) {
                alert("图片上传异常: " + error);
            }
        });
    };

    // 搜索本地图片
    $.Search = function () {
        // 清空原显示信息
        $("#dest_img_container").empty();

        var file = $.GetFileAndShow();
        if (!file) {
            return;
        }

        // 处理参数
        var interface_seq_id = $.GetRandomString(12);
        var pipeline = $("#pipeline").val();
        var collection = $("#collection").val();

        // 将文件对象打包成form表单类型的数据
        var formdata = new FormData;
        formdata.append('file', file);

        // 添加请求的json值, 将在form字典中获取
        formdata.append('interface_seq_id', interface_seq_id);
        formdata.append('pipeline', pipeline);
        formdata.append('collection', collection);

        var headers = {};

        // 进行文件数据的上传
        $.ajax({
            url: '/api/SearchServer/SearchByUpload',
            type: 'post',
            datatype: 'json',
            contentType: false,
            headers: headers,
            data: formdata,
            processData: false,
            async: true, // 异步处理
            success: function (result) {
                // 对数据json解析
                var retObj = result;
                if (retObj.status == "00000") {
                    // 上传成功
                    $.ShowSearchImages(retObj.match_images);
                } else {
                    // 上传失败
                    alert('图片上传失败[' + retObj.status + '][' + retObj.msg + ']');
                }
            },
            error: function (xhr, status, error) {
                alert("图片上传异常: " + error);
            }
        });
    };

    // 搜索BASE64图片
    $.SearchBase64 = function () {
        // 清空原显示信息
        $("#dest_img_container").empty();

        var file = $.GetFileAndShow();
        if (!file) {
            return;
        }

        // 将文件转换为Base64编码
        var reader = new FileReader();
        reader.onload = function () {
            // 生成调用参数
            var sendObj = new Object();
            sendObj.file = this.result;
            sendObj.interface_seq_id = $.GetRandomString(12);
            sendObj.pipeline = $("#pipeline").val();
            sendObj.collection = $("#collection").val();

            var headers = {};

            // 调用问题查询处理
            $.ajax({
                url: "/api/SearchServer/SearchByBase64",
                type: 'post',
                contentType: 'application/json',
                headers: headers,
                data: JSON.stringify(sendObj),
                timeout: 10000,
                async: true, // 异步处理
                success: function (result) {
                    // 对数据json解析
                    var retObj = result;
                    if (retObj.status == "00000") {
                        // 上传成功
                        $.ShowSearchImages(retObj.match_images);
                    } else {
                        // 上传失败
                        alert('图片上传失败[' + retObj.status + '][' + retObj.msg + ']');
                    }
                },
                error: function (xhr, status, error) {
                    alert("图片上传异常: " + error);
                }
            });
        }
        reader.readAsDataURL(file);
    };

    // 搜索Url图片
    $.SearchUrl = function () {
        // 清空原显示信息
        $("#dest_img_container").empty();

        // 获取图片url并显示
        var img_url = $("#image_url").val();
        $.ShowSrcImage(img_url, "源图");

        // 生成调用参数
        var sendObj = new Object();
        sendObj.url = img_url;
        sendObj.interface_seq_id = $.GetRandomString(12);
        sendObj.pipeline = $("#pipeline").val();
        sendObj.collection = $("#collection").val();

        var headers = {};

        // 调用问题查询处理
        $.ajax({
            url: "/api/SearchServer/SearchByUrl",
            type: 'post',
            contentType: 'application/json',
            headers: headers,
            data: JSON.stringify(sendObj),
            timeout: 10000,
            async: true, // 异步处理
            success: function (result) {
                // 对数据json解析
                var retObj = result;
                if (retObj.status == "00000") {
                    // 上传成功
                    $.ShowSearchImages(retObj.match_images);
                } else {
                    // 上传失败
                    alert('图片上传失败[' + retObj.status + '][' + retObj.msg + ']');
                }
            },
            error: function (xhr, status, error) {
                alert("图片上传异常: " + error);
            }
        });
    };

    // 查询已导入图片
    $.GetImages = function () {
        // 清空原显示信息
        $("#dest_img_container").empty();

        // 生成调用参数
        var sendObj = new Object();
        sendObj.interface_seq_id = $.GetRandomString(12);
        sendObj.collection = $("#collection").val();
        sendObj.field_name = null;
        sendObj.field_values = null;
        sendObj.page_size = 20;
        sendObj.page_num = 1;

        var headers = {};

        // 调用问题查询处理
        $.ajax({
            url: "/api/SearchServer/GetImageDoc",
            type: 'post',
            contentType: 'application/json',
            headers: headers,
            data: JSON.stringify(sendObj),
            timeout: 10000,
            async: true, // 异步处理
            success: function (result) {
                // 对数据json解析
                var retObj = result;
                if (retObj.status == "00000") {
                    // 上传成功
                    $.ShowImportedImages(retObj.images);
                } else {
                    // 上传失败
                    alert('获取导入图片失败[' + retObj.status + '][' + retObj.msg + ']');
                }
            },
            error: function (xhr, status, error) {
                alert("获取导入图片异常: " + error);
            }
        });
    };

    // 删除已导入图片
    $.RemoveImage = function () {
        var id = $('#reomve_id').val();
        if (!id || id == "") {
            alert('需输入要删除的图片id!');
        }

        // 生成调用参数
        var sendObj = new Object();
        sendObj.interface_seq_id = $.GetRandomString(12);
        sendObj.collection = $("#collection").val();
        sendObj.field_name = 'id';
        sendObj.field_values = id;

        var headers = {};

        // 调用问题查询处理
        $.ajax({
            url: "/api/SearchServer/RemoveImageDoc",
            type: 'post',
            contentType: 'application/json',
            headers: headers,
            data: JSON.stringify(sendObj),
            timeout: 10000,
            async: true, // 异步处理
            success: function (result) {
                // 对数据json解析
                var retObj = result;
                if (retObj.status == "00000") {
                    // 上传成功
                    alert('删除成功');
                } else {
                    // 上传失败
                    alert('删除导入图片失败[' + retObj.status + '][' + retObj.msg + ']');
                }
            },
            error: function (xhr, status, error) {
                alert("删除导入图片异常: " + error);
            }
        });
    };


})(jQuery);
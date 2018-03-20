from django.core.files.storage import Storage
from fdfs_client.client import Fdfs_client
from dailyfresh import settings

class FDFSStorage(Storage):
    """自定义文件存储类"""

    def __init__(self, client_conf=None, server_url=None):
        """初始化"""
        # 加载两个参数,方便初始化
        # django要求一定要有默认值
        if client_conf is None:
            client_conf = settings.FDFS_CLIENT_CONF
        self.fdfs_client_conf = client_conf

        if server_url is None:
            server_url = settings.FDFS_SERVER_URL
        self.fdfs_server_url= server_url

    # def _open(self, name, mode="rb"):
    #     pass


    def _save(self, name, content):
        """保存文件"""
        # name: 上传文件名
        # content: 上传文件内容

        # 上传文件到fdfs
        client = Fdfs_client(self.fdfs_client_conf)
        response = client.upload_by_buffer(content.read())  # 返回包含结果信息的字典

        # 处理可能的失败,失败时抛异常避免保存错误数据
        if response is None or response.get("Status") != "Upload successed.":    #
            raise Exception("文件上传失败")

        # 返回文件id,保存到数据库商品表image字段中
        file_id = response.get("Remote file_id")
        return file_id

    def exists(self, name):
        """判断文件是否已存在"""
        return False

    def url(self, name):
        """返回文件访问路径"""
        # name: _save()保存的值,从数据库中获取
        # 具体格式应为：nginxip:port/文件id
        # 在settings中做好相应配置,从init中传入,避免以后更改文件
        # 以后变换统一在settings中更改
        return self.fdfs_server_url + name
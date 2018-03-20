from haystack import indexes
# 导入你的模型类
from apps.goods.models import GoodsSKU


# 指定对于某个类的某些数据建立索引
# 索引类名格式: 模型类名+Index
class GoodsSKUIndex(indexes.SearchIndex, indexes.Indexable):
    """索引类"""
    # 索引字段， use_template=True说明需要在一个文件中指定根据表中哪些字段的内容建立索引数据
    text = indexes.CharField(document=True, use_template=True)

    def get_model(self):
        # 返回你的模型类
        return GoodsSKU

    # index_queryset返回哪些数据，就会对哪些数据建立索引
    def index_queryset(self, using=None):
        return self.get_model().objects.all()

# 抽取装饰视图类的功能抽取与封装成一个类，使用时继承该类即可
from django.views.generic import View
from django.contrib.auth.decorators import login_required
from celery_tasks.tasks import generate_static_index_html
from django.core.cache import cache


# 方式1.自定义类继承View的全部功能,再让视图类单一继承自定义类
# 缺点：若需求有变而不继承该类时,视图类没有其他作用
class LoginRequiredView(View):
    """装饰视图类：login_required"""
    @classmethod
    def as_view(cls, **initkwargs):
        view = super().as_view()
        return login_required(view)


# 方式2.自定义类只继承object,视图类多继承自定义类与View
# 使用多继承的方式，巧妙地调用View中的super并对其包装
# 只需继承即可使用，不继承时也还有从View继承来的内容
# 注意多继承时调用方法的顺序：父类中的super()指的是子类的另一父类
class LoginRequiredView(object):
    """装饰视图类：login_required"""
    @classmethod
    def as_view(cls, **initkwargs):
        view = super().as_view()
        return login_required(view)


class BaseModelAdmin(object):
    """管理器类：修改表内容时重新生成静态文件"""
    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        # 在修改类之后,重新生成静态文件:发出celery任务
        print("增加/更新：重新生成静态主页内容")
        generate_static_index_html.delay()

        # 表更新后,同时更新缓存内容
        cache.delete("index_page_data")

    def delete_model(self, request, obj):
        super().delete_model(request, obj)
        # 在修改类之后,重新生成静态文件:发出celery任务
        print("删除：重新生成静态主页内容")
        generate_static_index_html.delay()

        # 表更新后,同时更新缓存内容
        cache.delete("index_page_data")
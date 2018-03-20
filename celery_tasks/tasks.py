from django.conf import settings
from django.core.mail import send_mail
from django.template import loader
from django.core.cache import cache

# 导入Celery类
from celery import Celery

# 这两行代码在启动worker进行的一端打开
# 设置django配置依赖的环境变量
import os
# import django
# os.environ.setdefault("DJANGO_SETTINGS_MODULE", "dailyfresh.settings")
# django.setup()
from apps.goods.models import IndexGoodsBanner, GoodsType, IndexPromotionBanner, IndexTypeGoodsBanner

# from goods.models import GoodsType, IndexGoodsBanner, IndexPromotionBanner, IndexTypeGoodsBanner

# 创建一个Celery类的对象,指定中间人redis的地址与仓库
app = Celery('celery_tasks.tasks', broker='redis://localhost:6379/11')


# 定义任务函数
@app.task
def send_register_active_email(to_email, username, token):
    """发送激活邮件"""
    # 组织邮件内容
    subject = "嗨哎～"#'天天生鲜欢迎信息'
    message = ''
    sender = settings.EMAIL_FROM
    receiver = [to_email]
    # html_message = """
    #                     <h1>%s, 欢迎您成为天天生鲜注册会员</h1>
    #                     请点击以下链接激活您的账户<br/>
    #                     <a href="http://127.0.0.1:8000/user/active/%s">http://127.0.0.1:8000/user/active/%s</a>
    #                 """ % (username, token, token)
    html_message = """
                            <h1>%s, 贪玩蓝月</h1>
                            只需散混中，爱向姐款游戏<br/>
                            <a href="http://127.0.0.1:8000/user/active/%s">点一下，玩一年</a>
                        """ % (username, token)

    # 发送激活邮件
    # send_mail(subject=邮件标题, message=邮件正文,from_email=发件人, recipient_list=收件人列表)
    import time
    time.sleep(5)
    send_mail(subject, message, sender, receiver, html_message=html_message)


@app.task
def generate_static_index_html():
    """生成静态首页"""

    # 操作数据库
    goods_count = 0 # 购物车默认为0,而关系到用户动态数据的部分不能保存为静态内容,应该独立出来

    types = GoodsType.objects.all()

    turn_pics = IndexGoodsBanner.objects.all().order_by("index")

    sale_goods = IndexPromotionBanner.objects.all().order_by("index")   # 促销商品

    for type in types:
        image_banner = IndexTypeGoodsBanner.objects.filter(type=type, display_type=1)
        title_banner = IndexTypeGoodsBanner.objects.filter(type=type, display_type=0)

        # 每一种商品类型显示一行,所以把类型要显示的信息设为属性保存在类型对象中
        type.image_banner = image_banner
        type.title_banner = title_banner

    # 组织上下文
    context = {
        "types": types,
        "turn_pics": turn_pics,
        "sale_goods": sale_goods,
        "goods_count": goods_count,
    }

    # 使用模板对象,用于存储.不能用快捷键自动完成
    temp = loader.get_template("static_index.html")
    # 渲染模板
    static_html = temp.render(context)

    # 保存模板为静态文件(保存在Celery对象指定的redis数据库中),并写入渲染好的模板
    save_path = os.path.join(settings.BASE_DIR, 'static/index.html')    # 写到static/index.html
    with open(save_path, "w") as f:
        f.write(static_html)


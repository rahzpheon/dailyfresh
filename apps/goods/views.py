from django.shortcuts import render
from django.views.generic import View
from apps.goods.models import IndexGoodsBanner,GoodsType,IndexPromotionBanner,IndexTypeGoodsBanner
from apps.goods.models import Goods,GoodsSKU
from apps.order.models import OrderGoods
from django.shortcuts import redirect
from django.core.urlresolvers import reverse
from django.core.paginator import Paginator
import django_redis


from django.core.cache import cache
# Create your views here.


# http://127.0.0.1:8000
# /
# def index(request):
class IndexView(View):
    """首页"""
    def get(self, request):

        # 使用缓存减少数据库操作
        context = cache.get("index_page_data")

        if context is None:

            # 购物车：
            # 判断用户是否登陆,登陆时从redis中获取商品数量,未登录时设为0
            cart_count = 0

            # 通过nginx,从FDFS中获取数据
            # 从数据库中取出所有由_save存储的文件id
            # 1.获取商品分类信息
            types = GoodsType.objects.all()

            # 2.获取轮播图信息
            turn_pics = IndexGoodsBanner.objects.all().order_by("index")

            # 3.获取促销商品信息
            sale_goods = IndexPromotionBanner.objects.all().order_by("index")

            # 4.获取分类商品详细信息
            # 分为文字信息与图片信息
            # 可以通过前面分类信息的对象进行获取 name, image
            # 将他们保存为type对象的新属性,让模板可以通过模板变量type调用它们

            for type in types:
                image_banner= IndexTypeGoodsBanner.objects.filter(type=type, display_type=1)
                title_banner = IndexTypeGoodsBanner.objects.filter(type=type, display_type=0)

                # 每一种商品类型显示一行,所以把类型要显示的信息设为属性保存在类型对象中
                type.image_banner = image_banner
                type.title_banner = title_banner

            # 组织上下文
            context = {
                "types":types,
                "turn_pics":turn_pics,
                "sale_goods":sale_goods,
                "cart_count":cart_count,
            }

            # 缓存context ,会把内容自动转为文本
            cache.set("index_page_data", context, 3600)

        # 由于用户购物车是动态内容,应该放在缓存操作之后再进行更新
        cart_count = 0
        if request.user.is_authenticated():
            conn = django_redis.get_redis_connection("default")
            cart_count = conn.hlen("cart_%d" % request.user.id)
        context.update(cart_count=cart_count)

        return render(request, 'index.html', context)


class DetailView(View):
    """商品详情页面"""

    def get(self, request, sku_id):
        """显示页面"""
        # 获取商品id对应的商品对象,sku_id由index页面点击时传递进来
        try:
            sku = GoodsSKU.objects.get(id=sku_id)   # 获取商品对象可传递其属性

        except GoodsSKU.DoesNotExist:
            return redirect(reverse("goods:index"))

        # 获取商品分类的信息
        types = GoodsType.objects.all()

        # 获取商品的评论信息
        order_skus = OrderGoods.objects.filter(sku=sku).exclude(comment='').order_by('-update_time')

        # 获取和商品同一个SPU的其他规格的商品
        same_spu_skus = GoodsSKU.objects.filter(goods=sku.goods).exclude(id=sku_id)

        # 获取和商品同一种类的两个新品信息
        new_skus = GoodsSKU.objects.filter(type=sku.type).order_by('-create_time')[:2]

        # 获取用户购物车商品数量
        cart_count = 0
        if request.user.is_authenticated():
            cart_id = "cart_%d" % request.user.id
            conn = django_redis.get_redis_connection("default")
            cart_count = conn.hlen(cart_id)

        # 添加用户浏览历史
        # 拼接key
        history_key = "history_%d" % request.user.id

        # 先尝试从redis的表中移除当前浏览商品sku_id
        conn.lrem(history_key, 0, sku_id)
        # 添加当前商品sku_id到列表左侧
        conn.lpush(history_key, sku_id)
        # 只保留5个最近浏览商品
        conn.ltrim(history_key, 0, 4)

        # 组织模板上下文
        context = {
            'sku': sku,
            'types': types,
            'order_skus': order_skus,
            'same_spu_skus': same_spu_skus,
            'new_skus': new_skus,
            'cart_count': cart_count
        }

        return render(request, "detail.html", context)


class ListView(View):
    """列表页面"""

    def get(self, request, type_id, page):
        # 首页点击商品类型图标
        # 接受前端传递的三个参数   type_id page sort'
        # /list/type_id/page?sort=sort

        # 获取商品种类
        try:
            type = GoodsType.objects.get(id=type_id)
        except GoodsType.DoesNotExist:
            return redirect(reverse("goods:index"))

        # 所有商品种类信息
        types = GoodsType.objects.all()

        # 获取排序方式
        # sort=price: 按照商品的价格(price)从低到高排序
        # sort=hot: 按照商品的人气(sales)从高到低排序
        # sort=default: 按照默认排序方式(id)从高到低排序
        sort = request.GET.get("sort")

        # 获取种类对应所有商品的信息,根据分类方式排序
        if sort == 'price':
            skus = GoodsSKU.objects.filter(type=type).order_by("price")
        elif sort == 'hot':
            skus = GoodsSKU.objects.filter(type=type).order_by("-sales")
        else:
            sort = 'default'
            skus = GoodsSKU.objects.filter(type=type).order_by("-id")

        # 分页
        paginator = Paginator(skus, 2)
        page = int(page)    # 处理str

        # 默认获取第一页内容,包括越界
        if page > paginator.num_pages:
            page = 1

        # 获取该页内容
        skus_page = paginator.page(page)

        # 页码处理
        # 如果分页之后页码超过5页，最多在页面上只显示5个页码：当前页前2页，当前页，当前页后2页
        # 1) 分页页码小于5页，显示全部页码
        # 2）当前页属于1-3页，显示1-5页
        # 3) 当前页属于后3页，显示后5页
        # 4) 其他请求，显示当前页前2页，当前页，当前页后2页
        num_pages = paginator.num_pages # 总页数
        if num_pages < 5:
            pages = range(1, num_pages+1)
        elif page <= 3:
            pages = range(1, 6)
        elif num_pages - page <= 2:
            pages = range(num_pages-4, num_pages+1)
        else:
            pages = range(page-2, page+3)

        # 获取同type的两个新品
        new_skus = GoodsSKU.objects.filter(type=type).order_by("-create_time")

        # 用户登陆时获取购物车
        cart_count = 0
        if request.user.is_authenticated():
            conn = django_redis.get_redis_connection("default")
            cart_count = conn.hlen("cart_%d" % request.user.id)

        context = {
            'type':type,
            'types':types,
            'skus_page':skus_page,
            'cart_count':cart_count,
            'sort':sort,
            'pages':pages,
            'new_skus':new_skus
        }

        return render(request, 'list.html', context)
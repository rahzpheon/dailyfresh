from django.shortcuts import render
from django.http import JsonResponse
from django.views.generic import View
from apps.goods.models import GoodsSKU
from django_redis import get_redis_connection
from utils.mixin import LoginRequiredView

# Create your views here.

# /cart/add
class CartAddView(View):
    '''加入购物车'''
    def post(self, request):
        # 判断是否登陆
        if not request.user.is_authenticated():
            return JsonResponse({'res':4, 'errmsg':'请先登陆'})

        # 接受参数
        sku_id = request.POST.get('sku_id')
        count = request.POST.get('count')

        # 参数校验
        if not all([sku_id, count]):
            # 由于ajax局部请求,应该返回Json数据而非重定向
            return JsonResponse({'res':0, 'errmsg':'数据不完整'})

        # 商品是否存在    过滤urllib,requests等模仿浏览器发出的错误请求
        try:
            sku = GoodsSKU.objects.get(id=sku_id)

        except Exception:
            return JsonResponse({'res': 1, 'errmsg': '商品不存在'})

        # 数量是否数字
        try:
            count = int(count)

        except Exception:
            return  JsonResponse({'res':2, 'errmsg':'商品数量错误'})

        # 数量是否大于库存
        if count > sku.stock:
            return JsonResponse({'res': 3, 'errmsg': '库存不足'})

        # 业务处理：修改redis中内容
        conn = get_redis_connection('default')
        cart_key = "cart_%d" % request.user.id
        # 先获取,如果已有同类商品时做累加
        cart_count = conn.hget(cart_key, sku_id)

        if cart_count:      # 居然直接拿来加,None并不能加啊.
            count += int(cart_count)    # 注意错误数据导致cart_count为“None”的情形
            print(count)
        conn.hset(cart_key, sku_id, count) # hset:存在则修改,不存在则新建

        # 返回结果
        cart_count = conn.hlen(cart_key)

        return JsonResponse({'res':5, 'errmsg':'添加成功！', 'cart_count':cart_count})


# /cart
class CartInfoView(LoginRequiredView, View):
    '''购物车页面'''
    def get(self, request):

        conn = get_redis_connection('default')

        # 获取用户购物车中的所有记录
        cart_key = "cart_%d" % request.user.id
        cart_dict = conn.hgetall(cart_key)  # 返回一个字典

        total_amount = 0    # 所有商品总价
        total_count = 0   # 所有商品总量

        skus = []   # 商品列表

        # 获取对应商品信息
        for sku_id,count in cart_dict.items():
            try:
                sku = GoodsSKU.objects.get(id=sku_id)
            except Exception:
                pass

            # 为商品对象建立属性记住该商品的总价与总量
            amount = sku.price * int(count) # 拿出来的值是str
            sku.amount = amount # 单个商品总价
            sku.count = count   # 单个商品总量

            skus.append(sku)
            total_amount += amount
            total_count += int(count)

        context = {
                   'skus':skus,
                   "total_amount":total_amount,
                   "total_count":total_count
                   }

        return render(request, 'cart.html', context)


# /cart/delete
class CartDeleteView(View):
    '''删除购物车商品'''
    def post(self, request):
        print('后台')
        # 判断是否登陆
        if not request.user.is_authenticated():
            return JsonResponse({'res': 4, 'errmsg': '请先登陆'})

        # 接受参数
        sku_id = request.POST.get('sku_id')

        # 参数校验
        if not all([sku_id]):
            # 由于ajax局部请求,应该返回Json数据而非重定向
            return JsonResponse({'res': 0, 'errmsg': '数据不完整'})

        # 商品是否存在    过滤urllib,requests等模仿浏览器发出的错误请求
        try:
            sku = GoodsSKU.objects.get(id=sku_id)

        except Exception:
            return JsonResponse({'res': 1, 'errmsg': '商品不存在'})

        # 业务处理:删除redis中对应商品
        conn = get_redis_connection('default')
        cart_key = 'cart_%d' % request.user.id
        conn.hdel(cart_key, sku_id)

        return JsonResponse({'res':5, 'errmsg':'成功删除.'})


# /cart/update
class CartUpdateView(View):
    # ajax请求更新页面
    def post(self, request):
        # 在前端修改页面内容的同时,对redis也作相应修改
        # 前端传递参数： 1.商品id 2.商品数量

        # 先对ajax请求进行登陆校验
        if not request.user.is_authenticated():
            return JsonResponse({'res':0, 'errmsg': '请先登陆.'})

        # 接受参数
        sku_id = request.POST.get('sku_id')
        count = request.POST.get('count')

        # 参数检验
        if not all([sku_id, count]):
            return JsonResponse({'res':1, 'errmsg': '数据不完整'})

        try:
            sku = GoodsSKU.objects.get(id=sku_id)
        except GoodsSKU.DoesNotExist:
            return JsonResponse({'res':2, 'errmsg': '商品不存在'})

        try:
            count = int(count)
        except Exception:
            return JsonResponse({'res': 4, 'errmsg': '数字无效.'})

        if count > sku.stock:
            return JsonResponse({'res':3, 'errmsg': '库存不足.'})

        # 业务处理
        conn = get_redis_connection('default')
        cart_key = 'cart_%d' % request.user.id
        conn.hset(cart_key, sku_id, count)

        # 计算购物车商品的总件数
        total_count = 0
        vals = conn.hvals(cart_key)
        for val in vals:
            total_count += int(val)
        print(total_count)

        return JsonResponse({'res':5, 'errmsg': '成功', 'total_count':total_count})


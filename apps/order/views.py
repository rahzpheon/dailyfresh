from django.shortcuts import render,redirect
from django.views.generic import View
from apps.goods.models import GoodsSKU
from apps.user.models import Address
from apps.order.models import OrderInfo,OrderGoods
from django_redis import get_redis_connection
from django.http import JsonResponse,HttpResponse
from django.core.urlresolvers import reverse
from alipay import AliPay
from django.db import transaction
from dailyfresh import settings
from utils.mixin import LoginRequiredView
import os
import time

# Create your views here.
class OrderPlaceView(View):
    '''提交订单'''
    def post(self, request):

        user = request.user

        # 获取前端传来的商品id列表
        sku_ids = request.POST.getlist('sku_ids')

        # 获取用户地址
        addrs = Address.addr_manager.filter(user=user)

        skus = []
        total_amount = 0
        total_count = 0

        for sku_id in sku_ids:
            sku = GoodsSKU.objects.get(id=sku_id)

            # 获取sku在redis中的数据
            conn = get_redis_connection('default')
            cart_key = 'cart_%d' % request.user.id
            sku_count = conn.hget(cart_key, sku_id)

            # 计算商品小计
            sku_amount = sku.price * int(sku_count)

            # 设为属性存储
            sku.count = sku_count
            sku.amount = sku_amount

            # 存入列表
            skus.append(sku)

            # 计算总价,总数
            total_amount += sku_amount
            total_count += int(sku_count)

        # 运费,本例中固定为10
        transit_price = 10

        # 总费用
        payment = total_amount + transit_price

        context = {
                    'addrs':addrs,
                    'skus':skus,
                    'total_amount':total_amount,
                    'total_count':total_count,
                    'transit_price':transit_price,
                    'payment':payment,
                    # 重点:将str列表组装为str
                    # 让一组商品id可以放进一个标签中
                    'sku_ids': ','.join(sku_ids)
                    }

        return render(request, 'place_order.html', context)


# /order/commit
class OrderCommitView(View):
    '''提交订单'''
    @transaction.atomic
    def post(self, request):
        # 根据数据在数据库中生成订单
        # 加上事务,让数据库操作具有ACID

        user = request.user
        if not user.is_authenticated():
            return JsonResponse({'res': 0, 'errmsg': '数据不完整'})

        # 1.接受数据
        sku_ids = request.POST.get('sku_ids')
        addr_id = request.POST.get('addr_id')
        pay_method = request.POST.get('pay_method')

        # 2.数据校验
        if not all([sku_ids, addr_id, pay_method]):
            return JsonResponse({'res':1,'errmsg':'数据不完整'})

        try:
            addr = Address.addr_manager.get(id=addr_id)
        except Exception:
            return JsonResponse({'res': 2, 'errmsg': '地址错误'})

        # 校验支付方式
        if pay_method not in OrderInfo.PAY_METHODS.keys():
            return JsonResponse({'res': 3, 'errmsg': '非法的支付方式'})

        # 3.组织订单信息
        # 订单id:时间+用户id
        from datetime import datetime
        order_id = datetime.now().strftime('%Y%m%d%H%M%S') + str(user.id)
        # 需要查询redis的数据: 总数目 总金额
        total_count = 0
        total_amount = 0

        # 运费
        transit_price = 10

        # 在执行数据库操作之前,设置事务保存点
        sid = transaction.savepoint()

        # 将数据库的操作全部放入事务中
        try:
            # 4.订单信息表 添加 一条信息
            order = OrderInfo.objects.create(order_id=order_id,
                                             user=user,
                                             addr=addr,
                                             pay_method=pay_method,
                                             total_count=total_count,
                                             total_price=total_amount,
                                             transit_price=transit_price)

            # 5.订单商品表 每个商品添加一条信息
            # 要注意修改商品的库存与销量
            sku_ids = sku_ids.split(',')  # str拆为列表
            conn = get_redis_connection('default')
            for sku_id in sku_ids:
                try:
                    sku = GoodsSKU.objects.get(id=sku_id)
                except Exception:
                    transaction.savepoint_rollback(sid)     # 回滚到保存点
                    return JsonResponse({'res':4, 'errmsg':'商品信息错误'})
                # 计算数量
                cart_key = 'cart_%d' % user.id
                count = int(conn.hget(cart_key, sku_id))

                # 判断数量是否大于库存
                if count > sku.stock:
                    transaction.savepoint_rollback(sid)
                    return JsonResponse({'res':6, 'errmsg':'库存不足'})

                # 修改库存,销量
                sku.stock -= count
                sku.sales += count
                sku.save()

                total_count += count
                total_amount += sku.price

                # 创建
                OrderGoods.objects.create(order=order,
                                          sku=sku,
                                          count=count,
                                          price=sku.price)

            order.total_price = total_amount
            order.total_count = total_count
            order.save()

        except Exception:
            # 数据库操作发生异常时回滚
            transaction.savepoint_rollback(sid)

        # 7.删除购物车中相应记录 *自动拆包
        conn.hdel(cart_key, *sku_ids)

        return JsonResponse({'res':5})


# 使用了悲观锁的订单提交视图
# 用户在提交修改之前,其他事务无法获取该锁
class OrderCommitView1(View):
    '''提交订单'''

    @transaction.atomic
    def post(self, request):
        # 根据数据在数据库中生成订单
        # 加上事务,让数据库操作具有ACID

        user = request.user
        if not user.is_authenticated():
            return JsonResponse({'res': 0, 'errmsg': '数据不完整'})

        # 1.接受数据
        sku_ids = request.POST.get('sku_ids')
        addr_id = request.POST.get('addr_id')
        pay_method = request.POST.get('pay_method')

        # 2.数据校验
        if not all([sku_ids, addr_id, pay_method]):
            return JsonResponse({'res': 1, 'errmsg': '数据不完整'})

        try:
            addr = Address.addr_manager.get(id=addr_id)
        except Exception:
            return JsonResponse({'res': 2, 'errmsg': '地址错误'})

        # 校验支付方式
        if pay_method not in OrderInfo.PAY_METHODS.keys():
            return JsonResponse({'res': 3, 'errmsg': '非法的支付方式'})

        # 3.组织订单信息
        # 订单id:时间+用户id
        from datetime import datetime
        order_id = datetime.now().strftime('%Y%m%d%H%M%S') + str(user.id)
        # 需要查询redis的数据: 总数目 总金额
        total_count = 0
        total_amount = 0

        # 运费
        transit_price = 10

        # 在执行数据库操作之前,设置事务保存点
        sid = transaction.savepoint()

        # 将数据库的操作全部放入事务中
        try:
            # 4.订单信息表 添加 一条信息
            order = OrderInfo.objects.create(order_id=order_id,
                                             user=user,
                                             addr=addr,
                                             pay_method=pay_method,
                                             total_count=total_count,
                                             total_price=total_amount,
                                             transit_price=transit_price)

            # 5.订单商品表 每个商品添加一条信息
            # 要注意修改商品的库存与销量
            sku_ids = sku_ids.split(',')  # str拆为列表
            conn = get_redis_connection('default')
            for sku_id in sku_ids:
                try:
                    sku = GoodsSKU.objects.select_for_update().get(id=sku_id)
                except Exception:
                    transaction.savepoint_rollback(sid)  # 回滚到保存点
                    return JsonResponse({'res': 4, 'errmsg': '商品信息错误'})
                # 计算数量
                cart_key = 'cart_%d' % user.id
                count = int(conn.hget(cart_key, sku_id))

                # 判断数量是否大于库存
                if count > sku.stock:
                    transaction.savepoint_rollback(sid)
                    return JsonResponse({'res': 6, 'errmsg': '库存不足'})

                # 修改库存,销量
                sku.stock -= count
                sku.sales += count
                sku.save()

                total_count += count
                total_amount += sku.price

                # 创建
                OrderGoods.objects.create(order=order,
                                          sku=sku,
                                          count=count,
                                          price=sku.price)

            order.total_price = total_amount
            order.total_count = total_count
            order.save()

        except Exception:
            # 数据库操作发生异常时回滚
            transaction.savepoint_rollback(sid)
            return JsonResponse({'res': 7, 'errmsg': '下单失败1.'})

        # 7.删除购物车中相应记录 *自动拆包
        conn.hdel(cart_key, *sku_ids)

        return JsonResponse({'res': 5})


# 使用了乐观锁的订单提交视图
# 事务在查询时不操作,只记录，
# 在修改时,先确认属性是否与记录相符,符合时修改,否则返回
# 设最大返回记录为3,超出时报错
# 注意： 这种方式提交修改要移到更新后面
# 本例中：先更新库存,在创建订单对象
class OrderCommitView2(View):
        '''提交订单'''

        @transaction.atomic
        def post(self, request):
            # 根据数据在数据库中生成订单
            # 加上事务,让数据库操作具有ACID

            user = request.user
            if not user.is_authenticated():
                return JsonResponse({'res': 0, 'errmsg': '数据不完整'})

            # 1.接受数据
            sku_ids = request.POST.get('sku_ids')
            addr_id = request.POST.get('addr_id')
            pay_method = request.POST.get('pay_method')

            # 2.数据校验
            if not all([sku_ids, addr_id, pay_method]):
                return JsonResponse({'res': 1, 'errmsg': '数据不完整'})

            try:
                addr = Address.addr_manager.get(id=addr_id)
            except Exception:
                return JsonResponse({'res': 2, 'errmsg': '地址错误'})

            # 校验支付方式
            if pay_method not in OrderInfo.PAY_METHODS.keys():
                return JsonResponse({'res': 3, 'errmsg': '非法的支付方式'})

            # 3.组织订单信息
            # 订单id:时间+用户id
            from datetime import datetime
            order_id = datetime.now().strftime('%Y%m%d%H%M%S') + str(user.id)
            # 需要查询redis的数据: 总数目 总金额
            total_count = 0
            total_amount = 0

            # 运费
            transit_price = 10

            # 在执行数据库操作之前,设置事务保存点
            sid = transaction.savepoint()

            # 将数据库的操作全部放入事务中
            try:
                # 乐观锁重试次数
                for i in range(3):
                    # 4.订单信息表 添加 一条信息
                    order = OrderInfo.objects.create(order_id=order_id,
                                                     user=user,
                                                     addr=addr,
                                                     pay_method=pay_method,
                                                     total_count=total_count,
                                                     total_price=total_amount,
                                                     transit_price=transit_price)

                    # 5.订单商品表 每个商品添加一条信息
                    # 要注意修改商品的库存与销量
                    sku_ids = sku_ids.split(',')  # str拆为列表
                    conn = get_redis_connection('default')
                    for sku_id in sku_ids:
                        try:
                            sku = GoodsSKU.objects.select_for_update().get(id=sku_id)
                        except Exception:
                            transaction.savepoint_rollback(sid)  # 回滚到保存点
                            return JsonResponse({'res': 4, 'errmsg': '商品信息错误'})
                        # 计算数量
                        cart_key = 'cart_%d' % user.id
                        count = int(conn.hget(cart_key, sku_id))

                        # 记录库存,让乐观锁使用
                        origin_stock = sku.stock
                        new_stock = origin_stock - int(count)
                        new_sales = origin_stock + int(count)

                        # 乐观锁更新库存,返回受影响条数
                        res = GoodsSKU.objects.filter(id=sku_id,stock=origin_stock).update(stock=new_stock, sales=new_sales)

                        if res == 0:
                            if i == 2:
                                transaction.savepoint_rollback(sid)
                                return JsonResponse({'res':7, 'errmsg':'下单失败2.'})
                            # 重新尝试
                            continue

                        # 创建
                        OrderGoods.objects.create(order=order,
                                                  sku=sku,
                                                  count=count,
                                                  price=sku.price)

                        total_count += count
                        total_amount += sku.price*int(count)

                        # 更新成功,退出循环
                        break



                order.total_price = total_amount
                order.total_count = total_count
                order.save()

            except Exception:
                # 数据库操作发生异常时回滚
                transaction.savepoint_rollback(sid)
                return JsonResponse({'res':7, 'errmsg':'下单失败1.'})

            # 7.删除购物车中相应记录 *自动拆包
            conn.hdel(cart_key, *sku_ids)

            return JsonResponse({'res': 5})

# 支付接口
# 前段传入参数:订单号order_id
# 实现业务功能:调用alipay.api_alipay_trade_page_pay,生成订单串,并返回给前端
def order_pay(request):
    '''订单支付'''
    user = request.user

    if not user.is_authenticated():
        return JsonResponse({'res':0, 'errmsg':'用户未登陆'})

    # 获取订单编号
    order_id = request.POST.get('order_id')

    # 校验
    if not all([order_id]):
        return JsonResponse({'res': 1, 'errmsg': '缺少订单信息'})

    try:
        order = OrderInfo.objects.get(order_id=order_id,
                                      user=user)
                                      # pay_method=3,
                                      # status=1)
    except OrderInfo.DoesNotExist:
            return JsonResponse({'res': 2, 'errmsg': '订单信息有误'})

    # 业务处理: 调用支付宝python SDK中的api_alipay_trade_page_pay函数
    # 初始化
    alipay = AliPay(
        appid=settings.ALIPAY_SANDBOX_APP_ID,   # 应用appid
        app_notify_url=settings.ALIPAY_APP_NOTIFY_URL,        # 默认回调url
        app_private_key_path=settings.APP_PRIVATE_KEY_PATH,     # 应用私钥路径
        alipay_public_key_path=settings.ALIPAY_PUBLIC_KEY_PATH, # 支付宝公钥路径
        sign_type='RSA2',   # 签名方式 RSA或RSA2
        debug=settings.ALIPAY_DEBUG # 默认False,True表示沙箱环境,False表示生产环境
    )

    # 获得支付总金额：总价格+运费
    total_pay = order.total_price + order.transit_price

    # 生成订单串
    order_string = alipay.api_alipay_trade_page_pay(
        out_trade_no=order_id,
        total_amount=str(total_pay),
        subject='天天修仙%s' % order_id,
        return_url='http://127.0.0.1:8000/order/check',
        notify_url=None,
    )

    # 拼装支付页面url：ali接口地址 + ? + 生成的订单串
    alipay_url = settings.ALIPAY_GATEWAY_URL + '?' + order_string

    # 返回支付页面url
    # 并使用location.href = ... 或 window.open(...) 打开/跳转支付页面
    return JsonResponse({'res': 3, 'message': 'ok', 'pay_url':alipay_url})

# 同步获取支付接口return_url
# http:    /order/check
def check_pay(request):
    '''支付结果检查'''
    user = request.user

    if not request.user.is_authenticated():
        return JsonResponse({'res':0, 'errmsg':'用户未登录'})

    trade_no = request.GET.get('trade_no')
    order_id = request.GET.get('out_trade_no')

    # 校验订单id
    try:
        order = OrderInfo.objects.get(order_id=order_id,
                                      user=user,
                                      #order_status=1,  # 待支付
                                      #pay_method=3,  # 支付宝支付
                                      )
    except OrderInfo.DoesNotExist:
        return HttpResponse('订单信息错误')

    alipay = AliPay(
        appid=settings.ALIPAY_SANDBOX_APP_ID,  # 应用appid
        app_notify_url=settings.ALIPAY_APP_NOTIFY_URL,  # 默认回调url
        app_private_key_path=settings.APP_PRIVATE_KEY_PATH,  # 应用私钥路径
        alipay_public_key_path=settings.ALIPAY_PUBLIC_KEY_PATH,  # 支付宝公钥路径
        sign_type='RSA2',  # 签名方式 RSA或RSA2
        debug=settings.ALIPAY_DEBUG  # 默认False,True表示沙箱环境,False表示生产环境
    )

    # 调用Python SDK 中api_alipay_trade_query

    # {
    #     "trade_no": "2017032121001004070200176844", # 支付宝交易号
    #     "code": "10000", # 网关返回码
    #     "invoice_amount": "20.00",
    #     "open_id": "20880072506750308812798160715407",
    #     "fund_bill_list": [
    #         {
    #             "amount": "20.00",
    #             "fund_channel": "ALIPAYACCOUNT"
    #         }
    #     ],
    #     "buyer_logon_id": "csq***@sandbox.com",
    #     "send_pay_date": "2017-03-21 13:29:17",
    #     "receipt_amount": "20.00",
    #     "out_trade_no": "out_trade_no15",
    #     "buyer_pay_amount": "20.00",
    #     "buyer_user_id": "2088102169481075",
    #     "msg": "Success",
    #     "point_amount": "0.00",
    #     "trade_status": "TRADE_SUCCESS", # 支付状态
    #     "total_amount": "20.00"
    # }

    response = alipay.api_alipay_trade_query(out_trade_no=order_id)

    res_code = response.get('code')

    if res_code == '10000' and response.get('trade_status')=='TRADE_SUCCESS':
        # 支付成功
        # 更新订单的支付状态和支付宝交易号
        order.order_status = 4  # 待评价
        order.trade_no = response.get('trade_no')
        order.save()

        # 返回结果
        return render(request, 'pay_result.html', {'pay_result': '支付成功'})
    else:
        # 支付失败
        return render(request, 'pay_result.html', {'pay_result': '支付失败'})
    # while True:
    #     # 获取支付结果
    #     result = alipay.api_alipay_trade_query(out_trade_no)
    #     code = result['code']
    #
    #     if code == '10000':
    #         # 支付成功
    #         trade_status = result.get('trade_status')
    #         if trade_status is None:
    #             time.sleep(5)
    #             continue
    #
    #         if trade_status == 'TRADE_SUCCESS':
    #             # 更新订单支付状态
    #             # order.trade_id = result['trade_no']
    #             # order.save()
    #             return JsonResponse({'res': 5, 'errmsg': '支付成功'})
    #
    #         elif trade_status == 'WAIT_BUYER_PAY':
    #             time.sleep(5)
    #             continue
    #
    #         else:
    #             # 支付失败
    #             return JsonResponse({'res': 4, 'errmsg': '支付失败'})
    #
    #     elif code == '40004':
    #         # 继续查询
    #         time.sleep(10)
    #         continue
    #
    #     else:
    #         return JsonResponse({'res': 4, 'errmsg': '支付失败'})



# /order/comment
class OrderCommentView(LoginRequiredView,View):
    '''订单评论'''
    def get(self, request, order_id):
        '''显示评论'''
        user = request.user

        # 验证参数
        if not order_id:
            return redirect(reverse('user:order', kwargs={"page": 1}))

        try:
            order = OrderInfo.objects.get(order_id=order_id, user=user)
        except OrderInfo.DoesNotExist:
            return redirect(reverse("user:order", kwargs={"page": 1}))

        # 根据订单状态获取订单状态标题
        order.status_name = OrderInfo.ORDER_STATUS[order.order_status]

        # 获取订单商品信息
        order_skus = OrderGoods.objects.filter(order=order)
        for order_sku in order_skus:
            # 计算商品小计
            amount = order_sku.count*order_sku.price
            order_sku.amount = amount

        # 保存
        order.order_skus = order_skus

        return render(request, 'order_comment.html', {'order':order})

    def post(self, request, order_id):
        '''处理评论提交'''

        user = request.user

        # 校验
        if not order_id:
            return redirect(reverse('user:order', kwargs={"page": 1}))

        try:
            order = OrderInfo.objects.get(order_id=order_id, user=user)
        except OrderInfo.DoesNotExist:
            return redirect(reverse("user:order", kwargs={"page": 1}))

        # 获取评论条数
        total_count = request.POST.get('total_count')
        total_count = int(total_count)

        # 循环获取订单中商品的评论内容 1-total_count
        # 并写入表中,本项目评论存储在 订单商品表 OrderGoods
        for i in range(1, total_count + 1):
            # 获取商品id
            sku_id = request.POST.get('sku_%d' % i)
            # 获取商品评论
            content = request.POST.get('content_%d' % i)

            # 从订单商品表中去除对应商品
            try:
                order_goods = OrderGoods.objects.get(order=order, sku_id=sku_id)

            except OrderGoods.DoesNotExist:
                continue        # 获取失败时继续获取下一个


            # 将评论写入
            order_goods.comment = content
            order_goods.save()

        # 评论完成后,修改订单状态
        order.order_status = 5  # 已完成
        order.save()

        # 返回用户订单页,查看评论
        return redirect(reverse('user:order', kwargs={'page':1}))
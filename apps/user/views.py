import re
from django.shortcuts import render, redirect
from django.core.urlresolvers import reverse
from django.core.mail import send_mail
from django.views.generic import View
from django.conf import settings
from django.http import HttpResponse
from django.contrib.auth import authenticate,login,logout

from itsdangerous import TimedJSONWebSignatureSerializer as Serializer
from itsdangerous import SignatureExpired
from apps.user.models import User, Address
from apps.goods.models import GoodsSKU
from apps.order.models import OrderInfo,OrderGoods
from celery_tasks.tasks import send_register_active_email
from django.core.paginator import Paginator
from utils.mixin import LoginRequiredView

from django_redis import get_redis_connection
# Create your views here.


# /user/register
def register_1(request):
    """显示注册页面"""
    return render(request, 'register.html')

# 在项目开发中视图处理一般流程
# 1.接收参数
# 2.参数校验(后端校验)
# 3.业务处理
# 4.返回应答


# /user/register_handle
def register_handle(request):
    """注册处理"""
    # 1.接收参数
    username = request.POST.get('user_name') # None
    password = request.POST.get('pwd')
    email = request.POST.get('email')

    # 2.参数校验(后端校验)
    # 校验数据的完整性
    if not all([username, password, email]):
        return render(request, 'register.html', {'errmsg': '数据不完整'})

    # 校验邮箱格式
    if not re.match(r'^[a-z0-9][\w.\-]*@[a-z0-9\-]+(\.[a-z]{2,5}){1,2}$', email):
        return render(request, 'register.html', {'errmsg': '邮箱格式不正确'})

    # 校验用户名是否已注册
    try:
        user = User.objects.get(username=username)
    except User.DoesNotExist:
        user = None

    if user is not None:
        return render(request, 'register.html', {'errmsg': '用户名已注册'})

    # 校验邮箱是否被注册...

    # 3.业务处理：注册
    user = User.objects.create_user(username, email, password)
    user.is_active = 0
    user.save()

    # 4.返回应答: 跳转到首页
    return redirect(reverse('goods:index'))


# /user/register
# get: 显示注册页面
# post: 进行注册处理
# request.method -> GET POST
def register(request):
    """注册"""
    if request.method == 'GET':
        # 显示注册页面
        return render(request, 'register.html')
    else:
        # 进行注册处理
        # 1.接收参数
        username = request.POST.get('user_name')  # None
        password = request.POST.get('pwd')
        email = request.POST.get('email')

        # 2.参数校验(后端校验)
        # 校验数据的完整性
        if not all([username, password, email]):
            return render(request, 'register.html', {'errmsg': '数据不完整'})

        # 校验邮箱格式
        if not re.match(r'^[a-z0-9][\w.\-]*@[a-z0-9\-]+(\.[a-z]{2,5}){1,2}$', email):
            return render(request, 'register.html', {'errmsg': '邮箱格式不正确'})

        # 校验用户名是否已注册
        try:
            user = User.objects.get(username=username)
        except User.DoesNotExist:
            user = None

        if user is not None:
            return render(request, 'register.html', {'errmsg': '用户名已注册'})

        # 校验邮箱是否被注册...

        # 3.业务处理：注册
        user = User.objects.create_user(username, email, password)
        user.is_active = 0
        user.save()

        # 4.返回应答: 跳转到首页
        return redirect(reverse('goods:index'))


# /user/register
class RegisterView(View):
    """注册"""
    def get(self, request):
        """显示"""
        print('get----')
        return render(request, 'register.html')

    def post(self, request):
        """注册处理"""
        print('post----')
        # 1.接收参数
        username = request.POST.get('user_name')  # None
        password = request.POST.get('pwd')
        email = request.POST.get('email')

        # 2.参数校验(后端校验)
        # 校验数据的完整性
        if not all([username, password, email]):
            return render(request, 'register.html', {'errmsg': '数据不完整'})

        # 校验邮箱格式
        if not re.match(r'^[a-z0-9][\w.\-]*@[a-z0-9\-]+(\.[a-z]{2,5}){1,2}$', email):
            return render(request, 'register.html', {'errmsg': '邮箱格式不正确'})

        # 校验用户名是否已注册
        try:
            user = User.objects.get(username=username)
        except User.DoesNotExist:
            user = None

        if user is not None:
            return render(request, 'register.html', {'errmsg': '用户名已注册'})

        # 校验邮箱是否被注册...

        # 3.业务处理：注册
        user = User.objects.create_user(username, email, password)
        user.is_active = 0
        user.save()

        # 注册之后，需要给用户的注册邮箱发送激活邮件，在激活邮件中需要包含激活链接
        # 激活链接: /user/active/用户id
        # 存在问题: 其他用户恶意请求网站进行用户激活操作
        # 解决问题: 对用户的信息进行加密，把加密后的信息放在激活链接中，激活的时候在进行解密
        # /user/active/加密后token信息

        # 对用户的身份信息进行加密，生成激活token信息
        serializer = Serializer(settings.SECRET_KEY, 3600)
        info = {'confirm': user.id}
        # 返回bytes类型
        token = serializer.dumps(info)
        # str
        token = token.decode()

        # 组织邮件信息
        # subject = '天天生鲜欢迎信息'
        # message = ''
        # sender = settings.EMAIL_FROM
        # receiver = [email]
        # html_message = """
        #     <h1>%s, 欢迎您成为天天生鲜注册会员</h1>
        #     请点击一下链接激活您的账号(1小时之内有效)<br/>
        #     <a href="http://127.0.0.1:8000/user/active/%s">http://127.0.0.1:8000/user/active/%s</a>
        # """ % (username, token, token)

        # 发送激活邮件
        # send_mail(subject='邮件标题',
        #           message='邮件正文',
        #           from_email='发件人',
        #           recipient_list='收件人列表')
        # send_mail(subject, message, sender, receiver, html_message=html_message)

        # 使用celery中间人异步发送邮件，记得打开中间人redis，记得发送存在延迟
        send_register_active_email.delay(email, username, token)

        # 4.返回应答: 跳转到首页
        return redirect(reverse('goods:index'))


# /user/active/加密token
class ActiveView(View):
    """激活"""
    def get(self, request, token):
        """激活"""
        print('---active---')
        serializer = Serializer(settings.SECRET_KEY, 3600)
        try:
            # 解密
            info = serializer.loads(token)
            # 获取待激活用户id
            user_id = info['confirm']
            # 激活用户
            user = User.objects.get(id=user_id)
            user.is_active = 1
            user.save()

            # 跳转登录页面
            return redirect(reverse('user:login'))
        except SignatureExpired as e:
            # 激活链接已失效
            # 实际开发: 返回页面，让你点击链接再发激活邮件
            return HttpResponse('激活链接已失效')


# /user/login
class LoginView(View):
    """登录"""
    def get(self, request):
        """显示"""
        # 判断是否记住用户名
        username = request.COOKIES.get('username')  # get不会报错
        checked = 'checked'
        if not username:
            username = ""
            checked = ''
        return render(request, 'login.html', {"username": username, "checked":checked})

    def post(self, request):
        """登陆验证"""
        # 1.接受参数
        username = request.POST.get('username')
        password = request.POST.get('password')
        remember = request.POST.get('remember')

        # 2.参数验证 3.业务处理 4.返回结果
        if not all([username, password]):
            return render(request, 'login.html', {'errmsg':"数据不完整"})
        user = authenticate(username=username,password=password)  # 验证加密过的密码

        if user is not None:
            # 登陆成功
            if user.is_active:
                login(request, user)

                # 跳转至之前访问的页面,默认跳转至首页
                url_str = request.GET.get("next", reverse("goods:index"))
                print(request.user.id)
                response = redirect(url_str)

                # 是否记住用户名
                if remember == "on":
                    response.set_cookie("username", username, max_age=7*24*3600)
                else:
                    response.delete_cookie("username")

                return response
            else:
                return render(request, 'login.html', {'errmsg': "用户未激活"})
        else:
            return render(request, 'login.html', {'errmsg': "用户名或密码错误"})


# /user/logout
class LogoutView(View):
    """退出登陆"""
    def get(self, request):
        logout(request)
        return redirect('/user/login')

# /user
class UserView(LoginRequiredView, View):
    """用户信息"""
    def get(self, request):
        # 显示用户浏览记录
        user = request.user
        conn = get_redis_connection("default")
        history_key = "history_%d" % user.id

        good_ids = conn.lrange(history_key, 0, 4)   # 获取最近五个浏览商品id
        skus = []
        for good_id in good_ids:
            skus.insert(0, GoodsSKU.objects.get(id=good_id))        # 根据id获取商品对象并依次从前往后放入列表

        context = {"skus":skus, "page":"user"}

        return render(request, 'user_center_info.html', context)

# /order
class UserOrderView(LoginRequiredView, View):
    """订单信息"""
    def get(self, request, page):
        # 获取订单信息
        # 前端显示信息： 订单对象（订单号， 订单创建时间，支付状态）
        #   OrderGoods  商品对象(价格图片单位),商品数量
        # 设为属性绑在订单对象上

        # 获取用户
        user = request.user

        orders = OrderInfo.objects.filter(user=user).order_by('-create_time')

        for order in orders:
            # 获取订单中的商品信息
            order_skus = OrderGoods.objects.filter(order=order)

            # 遍历计算订单中每种商品的小计
            for order_sku in order_skus:
                # 商品小计
                amount = order_sku.price * order_sku.count

                # 用属性保存小计至订单商品
                order_sku.amount = amount

            # 获取订单状态与实付款
            order.status_title = OrderInfo.ORDER_STATUS[order.order_status]
            order.total_pay = order.total_price + order.transit_price

            # 用属性保存商品信息至订单
            order.order_skus = order_skus

        # 分页:最多显示5页,每页两个订单
        paginator = Paginator(orders, 2)

        page = int(page)  # 处理str

        # 获取分页订单
        order_page =paginator.page(page)

        if page > paginator.num_pages:
            page = 1
        num_pages = paginator.num_pages

        if num_pages < 5:
            pages = range(1, num_pages+1)
        elif page <= 3:
            pages = range(1, 6)
        elif num_pages - page <= 2:
            pages = range(num_pages - 4, num_pages + 1)
        else:
            pages = range(page - 2, page + 3)

        context = {'orders':orders,     # 所有订单
                   'pages':pages,
                   'order_page':order_page
                   }

        return render(request, 'user_center_order.html',context)

# /address
# 显示地址/提交地址信息
class AddressView(LoginRequiredView, View):
    """地址信息"""
    def get(self, request):
        # 显示当前地址与默认地址
        try:
            # 获取登陆用户的默认地址
            addr = Address.addr_manager.get(user=request.user, is_default=True)
            # 获取登陆用户的当前地址
        except Address.DoesNotExist:
            addr = None             # 用于模板if判断

        # 附：所有非默认地址的下拉列表
        addr_list = Address.addr_manager.filter(user=request.user, is_default=False)

        context = {"address":addr, "page":"address", "addr_list":addr_list}
        return render(request, 'user_center_site.html',context)

    def post(self, request):
        """添加用户信息"""
        # 1.接受用户信息
        receiver = request.POST.get("receiver")
        addr = request.POST.get("addr")
        zip_code = request.POST.get("zip_code")
        phone = request.POST.get("phone")

        # 2.参数校验
        if not all([receiver, addr, zip_code, phone]):
            return render(request, reverse("user:address"), {"errmsg":"数据不完整"})
        # 邮编校验
        # 电话号码校验

        # 3.业务处理 提交用户地址信息 记得指定用户对象
        user = request.user
        # 用户没有默认地址时设为默认地址,已有默认地址时设为普通地址
        # try:
        #     address = Address.objects.get(user=user, is_default=True)
        # except Address.DoesNotExist:
        #     address = None
        address = Address.addr_manager.get_default_addr(user)

        is_default = False
        if address is None:
            is_default = True

        Address.addr_manager.create(user=user,
                               receiver=receiver,
                               addr=addr,
                               zip_code=zip_code,
                               phone=phone,
                               is_default=is_default)

        # 4.返回信息
        return redirect(reverse("user:address"))

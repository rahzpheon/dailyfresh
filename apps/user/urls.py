from django.conf.urls import url
from apps.user.views import RegisterView, ActiveView, LoginView, LogoutView
from apps.user.views import UserView,UserOrderView,AddressView
from apps.user import views
# from django.contrib.auth.decorators import login_required

urlpatterns = [
    # url(r'^register$', views.register, name='register'), # 注册
    # url(r'^register_handle$', views.register_handle, name='register_handle'), # 注册处理
    url(r'^register$', RegisterView.as_view(), name='register'), # 注册
    url(r'^active/(?P<token>.*)$', ActiveView.as_view(), name='active'), # 激活
    url(r'^login$', LoginView.as_view(), name='login'), # 登录
    url(r'^logout$', LogoutView.as_view(), name='logout'), # 退出

    url(r'^$', UserView.as_view(), name="user"),    # 用户信息模块
    url(r'^order/(?P<page>\d+)$', UserOrderView.as_view(), name="order"),    # 用户订单模块
    url(r'^address$', AddressView.as_view(), name="address"),    # 用户地址模块
]

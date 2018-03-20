from django.conf.urls import url
from apps.cart.views import CartAddView,CartInfoView,CartDeleteView,CartUpdateView

urlpatterns = [
    url(r'^add$', CartAddView.as_view(), name="add"),   # 加入购物车
    url(r'^$', CartInfoView.as_view(), name='cart'),
    url(r'^delete$', CartDeleteView.as_view(), name='delete'),
    url(r'^update$', CartUpdateView.as_view(), name='update'),
  ]

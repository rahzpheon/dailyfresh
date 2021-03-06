from django.conf.urls import url
from apps.goods.views import IndexView,DetailView,ListView

urlpatterns = [
    url(r'^index$', IndexView.as_view(), name='index'), # 首页
    url(r'^detail/(?P<sku_id>\d+)$', DetailView.as_view(), name='detail'),
    url(r'^list/(?P<type_id>\d+)/(?P<page>\d+)$', ListView.as_view(), name="list"),

]

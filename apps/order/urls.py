from django.conf.urls import url
from apps.order.views import OrderPlaceView,OrderCommitView,OrderCommentView
from apps.order import views

urlpatterns = [
    url(r'^place$', OrderPlaceView.as_view(), name='place'),
    url(r'^commit$', OrderCommitView.as_view(), name='commit'),

    url(r'^pay$', views.order_pay, name='pay'),
    url(r'^check$', views.check_pay, name='check'),

    url(r'^comment/(?P<order_id>.*)$', OrderCommentView.as_view(), name='comment'),
]

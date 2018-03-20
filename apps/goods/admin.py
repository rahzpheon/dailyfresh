from django.contrib import admin
from apps.goods.models import Goods,GoodsType,GoodsSKU,IndexPromotionBanner
from utils.mixin import BaseModelAdmin



# Register your models here.
class GoodsTypeAdmin(BaseModelAdmin, admin.ModelAdmin):
    pass

class GoodsAdmin(BaseModelAdmin, admin.ModelAdmin):
    pass

class GoodsSKUAdmin(BaseModelAdmin, admin.ModelAdmin):
    pass

class IndexPromotionBannerAdmin(BaseModelAdmin, admin.ModelAdmin):
    pass

admin.site.register(GoodsSKU, GoodsSKUAdmin)
admin.site.register(GoodsType, GoodsTypeAdmin)
admin.site.register(Goods, GoodsAdmin)
admin.site.register(IndexPromotionBanner, IndexPromotionBannerAdmin)
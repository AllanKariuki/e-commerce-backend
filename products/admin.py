from django.contrib import admin
from .models import Product, ProductCategory, SearchQuery

@admin.register(ProductCategory)
class ProductCategoryAdmin(admin.ModelAdmin):
    list_display = ['name', 'description']

@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ['name', 'category', 'price', 'units_in_stock']
    list_filter = ['category']
    search_fields = ['name', 'description']


@admin.register(SearchQuery)
class SearchQueryAdmin(admin.ModelAdmin):
    """Read-only-ish browser for visual-search queries.

    Useful for spot-checking relevance ("what did the user upload,
    what did we return?") and watching the latency distribution.
    """

    list_display = (
        'id', 'created_at', 'who', 'result_count', 'latency_ms', 'image_url',
    )
    list_filter = ('created_at',)
    search_fields = ('session_key', 'user__email', 'image_url')
    readonly_fields = (
        'image_url', 'top_result_ids', 'latency_ms', 'result_count',
        'user', 'session_key', 'created_at',
    )
    date_hierarchy = 'created_at'
    ordering = ('-created_at',)

    @admin.display(description='Who')
    def who(self, obj):
        if obj.user_id:
            return f"user:{obj.user_id}"
        if obj.session_key:
            return f"guest:{obj.session_key[:12]}…"
        return "anon"

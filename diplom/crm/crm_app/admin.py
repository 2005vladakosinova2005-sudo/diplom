from django.contrib import admin
from .models import Client, Product, Inventory, Order, OrderItem

admin.site.register(Client)
admin.site.register(Product)
admin.site.register(Inventory)
admin.site.register(Order)
admin.site.register(OrderItem)

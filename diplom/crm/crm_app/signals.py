from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import OrderItem, Inventory

@receiver(post_save, sender=OrderItem)
def update_inventory(sender, instance, created, **kwargs):
    if created:
        try:
            # Знаходимо товар на складі
            inventory = Inventory.objects.get(product=instance.product)
            # Віднімаємо кількість, яка вказана в замовленні
            inventory.quantity -= instance.quantity
            inventory.save()
        except Inventory.DoesNotExist:
            # Якщо товару немає на складі, нічого не робимо
            pass

from django.db.models.signals import post_save, pre_save, post_delete
from django.dispatch import receiver
from django.db import transaction
from .models import Order, OrderItem


@receiver(post_save, sender=OrderItem)
def decrease_stock_on_order_item_create(sender, instance, created, **kwargs):
    """Списати товар зі складу при додаванні в замовлення"""
    if created:
        product = instance.product
        product.stock -= instance.quantity
        product.save(update_fields=['stock'])


@receiver(post_delete, sender=OrderItem)
def restore_stock_on_order_item_delete(sender, instance, **kwargs):
    """Повернути товар на склад при видаленні з замовлення"""
    product = instance.product
    product.stock += instance.quantity
    product.save(update_fields=['stock'])


@receiver(pre_save, sender=Order)
def handle_order_status_change(sender, instance, **kwargs):
    """Обробка зміни статусу замовлення"""
    if instance.pk:
        try:
            old_order = Order.objects.get(pk=instance.pk)
            old_status = old_order.status
            new_status = instance.status

            # Якщо статус змінився на скасовано або повернення
            if old_status not in ['canceled', 'returned'] and new_status in ['canceled', 'returned']:
                # Повертаємо товари на склад
                with transaction.atomic():
                    for item in instance.items.all():
                        product = item.product
                        product.stock += item.quantity
                        product.save(update_fields=['stock'])

            # Якщо статус змінився з скасовано/повернення на активний
            elif old_status in ['canceled', 'returned'] and new_status not in ['canceled', 'returned']:
                # Знову списуємо товари зі складу
                with transaction.atomic():
                    for item in instance.items.all():
                        product = item.product
                        if product.stock >= item.quantity:
                            product.stock -= item.quantity
                            product.save(update_fields=['stock'])
                        else:
                            raise ValueError(
                                f"Недостатньо товару '{product.name}' на складі. "
                                f"Доступно: {product.stock}, потрібно: {item.quantity}"
                            )
        except Order.DoesNotExist:
            pass

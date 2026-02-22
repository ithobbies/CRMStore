from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models.signals import post_delete, post_save, pre_save
from django.dispatch import receiver

from .models import INACTIVE_ORDER_STATUSES, Order, OrderItem, Product


def _is_stock_managed(order):
    return order.status not in INACTIVE_ORDER_STATUSES


def _adjust_product_stock(product_id, delta):
    product = Product.objects.select_for_update().get(pk=product_id)
    new_stock = product.stock + delta
    if new_stock < 0:
        raise ValidationError(
            f"Недостатньо товару '{product.name}' на складі. "
            f"Доступно: {product.stock}, потрібно: {abs(delta)}"
        )

    product.stock = new_stock
    product.save(update_fields=['stock'])


@receiver(pre_save, sender=OrderItem)
def cache_previous_order_item(sender, instance, **kwargs):
    if not instance.pk:
        instance._previous_state = None
        return

    try:
        instance._previous_state = OrderItem.objects.select_related('order').get(pk=instance.pk)
    except OrderItem.DoesNotExist:
        instance._previous_state = None


@receiver(post_save, sender=OrderItem)
def sync_stock_on_order_item_save(sender, instance, created, **kwargs):
    if not _is_stock_managed(instance.order):
        return

    with transaction.atomic():
        if created:
            _adjust_product_stock(instance.product_id, -instance.quantity)
            return

        previous_item = getattr(instance, '_previous_state', None)
        if previous_item is None:
            return

        if previous_item.product_id == instance.product_id:
            delta = previous_item.quantity - instance.quantity
            if delta:
                _adjust_product_stock(instance.product_id, delta)
            return

        _adjust_product_stock(previous_item.product_id, previous_item.quantity)
        _adjust_product_stock(instance.product_id, -instance.quantity)


@receiver(post_delete, sender=OrderItem)
def restore_stock_on_order_item_delete(sender, instance, **kwargs):
    if not _is_stock_managed(instance.order):
        return

    with transaction.atomic():
        _adjust_product_stock(instance.product_id, instance.quantity)


@receiver(pre_save, sender=Order)
def handle_order_status_change(sender, instance, **kwargs):
    if not instance.pk:
        return

    try:
        old_order = Order.objects.get(pk=instance.pk)
    except Order.DoesNotExist:
        return

    old_is_active = old_order.status not in INACTIVE_ORDER_STATUSES
    new_is_active = instance.status not in INACTIVE_ORDER_STATUSES

    if old_is_active == new_is_active:
        return

    with transaction.atomic():
        for item in instance.items.all():
            if new_is_active:
                _adjust_product_stock(item.product_id, -item.quantity)
            else:
                _adjust_product_stock(item.product_id, item.quantity)

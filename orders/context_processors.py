from .models import Order


def new_orders_count(request):
    return {
        'new_orders_count': Order.objects.filter(status='new').count(),
    }

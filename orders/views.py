from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.db.models import Sum, Count, Q
from django.db.models.functions import TruncMonth
from django.utils import timezone
from datetime import timedelta
from decimal import Decimal

from .models import Order, OrderItem, Product, Customer
from .forms import OrderForm, OrderItemFormSet, OrderStatusForm, ProductForm


def dashboard(request):
    """Головна сторінка з KPI"""
    today = timezone.now().date()
    month_start = today.replace(day=1)
    
    # Замовлення сьогодні
    orders_today = Order.objects.filter(
        created_at__date=today
    ).exclude(status__in=['canceled', 'returned']).count()
    
    # Замовлення вчора для порівняння
    yesterday = today - timedelta(days=1)
    orders_yesterday = Order.objects.filter(
        created_at__date=yesterday
    ).exclude(status__in=['canceled', 'returned']).count()
    
    # Виручка за місяць
    month_orders = Order.objects.filter(
        created_at__date__gte=month_start,
        status='completed'
    )
    revenue_this_month = Decimal('0.00')
    for order in month_orders:
        revenue_this_month += order.get_total_cost()
    
    # Виручка минулого місяця для порівняння
    last_month_start = (month_start - timedelta(days=1)).replace(day=1)
    last_month_end = month_start - timedelta(days=1)
    last_month_orders = Order.objects.filter(
        created_at__date__gte=last_month_start,
        created_at__date__lte=last_month_end,
        status='completed'
    )
    revenue_last_month = Decimal('0.00')
    for order in last_month_orders:
        revenue_last_month += order.get_total_cost()
    
    # Відсоток зміни виручки
    if revenue_last_month > 0:
        revenue_change = ((revenue_this_month - revenue_last_month) / revenue_last_month) * 100
    else:
        revenue_change = 100 if revenue_this_month > 0 else 0
    
    # Відсоток зміни замовлень
    if orders_yesterday > 0:
        orders_change = ((orders_today - orders_yesterday) / orders_yesterday) * 100
    else:
        orders_change = 100 if orders_today > 0 else 0
    
    # Товари з низьким залишком (< 5)
    low_stock_products = Product.objects.filter(stock__lt=5).order_by('stock')
    
    # Нові замовлення (потребують обробки)
    new_orders = Order.objects.filter(status='new').count()
    
    # Останні замовлення
    recent_orders = Order.objects.select_related('customer').prefetch_related('items')[:5]
    
    # Топ продукти
    top_products = Product.objects.annotate(
        total_sold=Sum('order_items__quantity')
    ).filter(total_sold__isnull=False).order_by('-total_sold')[:5]
    
    context = {
        'orders_today': orders_today,
        'orders_change': round(orders_change, 1),
        'revenue_this_month': revenue_this_month,
        'revenue_change': round(revenue_change, 1),
        'low_stock_products': low_stock_products,
        'low_stock_count': low_stock_products.count(),
        'new_orders': new_orders,
        'recent_orders': recent_orders,
        'top_products': top_products,
    }
    return render(request, 'orders/dashboard.html', context)


def order_list(request):
    """Список замовлень"""
    orders = Order.objects.select_related('customer').prefetch_related('items').all()
    
    # Фільтр по статусу
    status_filter = request.GET.get('status', '')
    if status_filter:
        orders = orders.filter(status=status_filter)
    
    # Фільтр по даті
    date_filter = request.GET.get('date', '')
    if date_filter:
        orders = orders.filter(created_at__date=date_filter)
    
    # Пошук
    search = request.GET.get('search', '')
    if search:
        orders = orders.filter(
            Q(customer__full_name__icontains=search) |
            Q(customer__phone__icontains=search) |
            Q(ttn__icontains=search) |
            Q(city__icontains=search)
        )
    
    # Статистика для фільтрів
    status_counts = Order.objects.values('status').annotate(count=Count('id'))
    status_dict = {item['status']: item['count'] for item in status_counts}
    
    context = {
        'orders': orders,
        'status_filter': status_filter,
        'date_filter': date_filter,
        'search': search,
        'status_choices': Order.STATUS_CHOICES,
        'status_counts': status_dict,
        'total_orders': Order.objects.count(),
    }
    return render(request, 'orders/order_list.html', context)


def order_detail(request, pk):
    """Деталі замовлення"""
    order = get_object_or_404(
        Order.objects.select_related('customer').prefetch_related('items__product'),
        pk=pk
    )
    
    if request.method == 'POST':
        status_form = OrderStatusForm(request.POST, instance=order)
        if status_form.is_valid():
            status_form.save()
            messages.success(request, 'Статус замовлення оновлено!')
            return redirect('order_detail', pk=pk)
    else:
        status_form = OrderStatusForm(instance=order)
    
    context = {
        'order': order,
        'status_form': status_form,
    }
    return render(request, 'orders/order_detail.html', context)


def order_create(request):
    """Створення замовлення"""
    if request.method == 'POST':
        form = OrderForm(request.POST)
        formset = OrderItemFormSet(request.POST, prefix='items')
        
        if form.is_valid() and formset.is_valid():
            order = form.save()
            formset.instance = order
            formset.save()
            messages.success(request, f'Замовлення #{order.pk} успішно створено!')
            return redirect('order_detail', pk=order.pk)
    else:
        form = OrderForm()
        formset = OrderItemFormSet(prefix='items')
    
    context = {
        'form': form,
        'formset': formset,
        'title': 'Нове замовлення',
        'products': Product.objects.filter(stock__gt=0),
    }
    return render(request, 'orders/order_form.html', context)


def order_update(request, pk):
    """Редагування замовлення"""
    order = get_object_or_404(Order, pk=pk)
    
    if request.method == 'POST':
        form = OrderForm(request.POST, instance=order)
        formset = OrderItemFormSet(request.POST, instance=order, prefix='items')
        
        if form.is_valid() and formset.is_valid():
            form.save()
            formset.save()
            messages.success(request, f'Замовлення #{order.pk} оновлено!')
            return redirect('order_detail', pk=order.pk)
    else:
        form = OrderForm(instance=order)
        formset = OrderItemFormSet(instance=order, prefix='items')
    
    context = {
        'form': form,
        'formset': formset,
        'order': order,
        'title': f'Редагування замовлення #{order.pk}',
        'products': Product.objects.all(),
    }
    return render(request, 'orders/order_form.html', context)


def product_list(request):
    """Список товарів"""
    products = Product.objects.all()
    
    # Пошук
    search = request.GET.get('search', '')
    if search:
        products = products.filter(
            Q(name__icontains=search) | Q(sku__icontains=search)
        )
    
    # Фільтр по наявності
    stock_filter = request.GET.get('stock', '')
    if stock_filter == 'low':
        products = products.filter(stock__lt=5)
    elif stock_filter == 'out':
        products = products.filter(stock=0)
    elif stock_filter == 'in':
        products = products.filter(stock__gt=0)
    
    context = {
        'products': products,
        'search': search,
        'stock_filter': stock_filter,
    }
    return render(request, 'orders/product_list.html', context)


def product_create(request):
    """Створення нового товару"""
    if request.method == 'POST':
        form = ProductForm(request.POST)
        if form.is_valid():
            product = form.save()
            messages.success(request, f'Товар "{product.name}" успішно створено!')
            return redirect('product_list')
    else:
        form = ProductForm()
    
    context = {
        'form': form,
        'title': 'Новий товар',
    }
    return render(request, 'orders/product_form.html', context)


def product_update(request, pk):
    """Редагування товару"""
    product = get_object_or_404(Product, pk=pk)
    
    if request.method == 'POST':
        form = ProductForm(request.POST, instance=product)
        if form.is_valid():
            form.save()
            messages.success(request, f'Товар "{product.name}" оновлено!')
            return redirect('product_list')
    else:
        form = ProductForm(instance=product)
    
    context = {
        'form': form,
        'product': product,
        'title': f'Редагування: {product.name}',
    }
    return render(request, 'orders/product_form.html', context)


def customer_list(request):
    """Список клієнтів"""
    customers = Customer.objects.annotate(
        orders_count=Count('orders')
    ).all()
    
    # Пошук
    search = request.GET.get('search', '')
    if search:
        customers = customers.filter(
            Q(full_name__icontains=search) | Q(phone__icontains=search)
        )
    
    context = {
        'customers': customers,
        'search': search,
    }
    return render(request, 'orders/customer_list.html', context)

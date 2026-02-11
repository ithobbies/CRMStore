import csv
from datetime import timedelta
from decimal import Decimal

from django.contrib import messages
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Count, Q, Sum
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.dateparse import parse_date
from django.urls import reverse

from .forms import CustomerForm, OrderForm, OrderItemFormSet, OrderStatusForm, ProductForm
from .models import INACTIVE_ORDER_STATUSES, Customer, Order, Product


def _calculate_change(current, previous):
    if previous > 0:
        return ((current - previous) / previous) * 100
    return 100 if current > 0 else 0


def _extract_order_filters(params):
    status_filter = (params.get('status') or '').strip()
    date_filter = (params.get('date') or '').strip()
    search = (params.get('q') or params.get('search') or '').strip()
    date_range = (params.get('date_range') or '').strip()
    date_from = (params.get('date_from') or '').strip()
    date_to = (params.get('date_to') or '').strip()

    # Backward-compatible single-day filter.
    if date_filter and not date_from and not date_to:
        date_from = date_filter
        date_to = date_filter

    return status_filter, date_filter, search, date_range, date_from, date_to


def _apply_order_filters(
    queryset,
    status_filter='',
    date_filter='',
    search='',
    date_range='',
    date_from='',
    date_to='',
):
    if status_filter:
        queryset = queryset.filter(status=status_filter)

    today = timezone.localdate()
    if date_range == 'today':
        date_from = today.isoformat()
        date_to = today.isoformat()
    elif date_range == '7d':
        date_from = (today - timedelta(days=6)).isoformat()
        date_to = today.isoformat()
    elif date_range == 'month':
        date_from = today.replace(day=1).isoformat()
        date_to = today.isoformat()

    parsed_date_from = parse_date(date_from) if date_from else None
    parsed_date_to = parse_date(date_to) if date_to else None

    if parsed_date_from and parsed_date_to:
        queryset = queryset.filter(created_at__date__gte=parsed_date_from, created_at__date__lte=parsed_date_to)
    elif parsed_date_from:
        queryset = queryset.filter(created_at__date__gte=parsed_date_from)
    elif parsed_date_to:
        queryset = queryset.filter(created_at__date__lte=parsed_date_to)

    if search:
        queryset = queryset.filter(
            Q(customer__full_name__icontains=search)
            | Q(customer__phone__icontains=search)
            | Q(ttn__icontains=search)
            | Q(city__icontains=search)
        )

    return queryset


def _build_sales_series(days=30):
    end_date = timezone.localdate()
    start_date = end_date - timedelta(days=days - 1)
    date_range = [start_date + timedelta(days=index) for index in range(days)]
    totals_by_day = {date_value: Decimal('0.00') for date_value in date_range}

    completed_orders = Order.objects.filter(
        created_at__date__gte=start_date,
        status='completed',
    ).prefetch_related('items__product')

    for order in completed_orders:
        order_day = timezone.localtime(order.created_at).date()
        if order_day in totals_by_day:
            totals_by_day[order_day] += order.get_total_cost()

    labels = [date_value.strftime('%d.%m') for date_value in date_range]
    values = [float(totals_by_day[date_value]) for date_value in date_range]
    return labels, values


def dashboard(request):
    """Головна сторінка з KPI"""
    today = timezone.localdate()
    month_start = today.replace(day=1)
    
    # Замовлення сьогодні
    orders_today = Order.objects.filter(
        created_at__date=today
    ).exclude(status__in=INACTIVE_ORDER_STATUSES).count()
    
    # Замовлення вчора для порівняння
    yesterday = today - timedelta(days=1)
    orders_yesterday = Order.objects.filter(
        created_at__date=yesterday
    ).exclude(status__in=INACTIVE_ORDER_STATUSES).count()
    
    # Виручка/прибуток за місяць
    month_orders = list(Order.objects.filter(
        created_at__date__gte=month_start,
        status='completed'
    ).select_related('customer').prefetch_related('items__product'))
    revenue_this_month = sum((order.get_total_cost() for order in month_orders), Decimal('0.00'))
    profit_this_month = sum((order.get_profit() for order in month_orders), Decimal('0.00'))
    orders_this_month = Order.objects.filter(
        created_at__date__gte=month_start
    ).exclude(status__in=INACTIVE_ORDER_STATUSES).count()
    
    # Виручка минулого місяця для порівняння
    last_month_start = (month_start - timedelta(days=1)).replace(day=1)
    last_month_end = month_start - timedelta(days=1)
    last_month_orders = list(Order.objects.filter(
        created_at__date__gte=last_month_start,
        created_at__date__lte=last_month_end,
        status='completed'
    ).select_related('customer').prefetch_related('items__product'))
    revenue_last_month = sum((order.get_total_cost() for order in last_month_orders), Decimal('0.00'))
    profit_last_month = sum((order.get_profit() for order in last_month_orders), Decimal('0.00'))
    orders_last_month = Order.objects.filter(
        created_at__date__gte=last_month_start,
        created_at__date__lte=last_month_end
    ).exclude(status__in=INACTIVE_ORDER_STATUSES).count()

    avg_check = (revenue_this_month / len(month_orders)) if month_orders else Decimal('0.00')
    avg_check_last_month = (revenue_last_month / len(last_month_orders)) if last_month_orders else Decimal('0.00')

    # Відсоток зміни KPI
    revenue_change = _calculate_change(revenue_this_month, revenue_last_month)
    profit_change = _calculate_change(profit_this_month, profit_last_month)
    orders_change = _calculate_change(orders_today, orders_yesterday)
    avg_check_change = _calculate_change(avg_check, avg_check_last_month)
    orders_month_change = _calculate_change(orders_this_month, orders_last_month)
    
    # Товари з низьким залишком (< 5)
    low_stock_products = Product.objects.filter(stock__lt=5).order_by('stock')
    
    # Нові замовлення (потребують обробки)
    new_orders = Order.objects.filter(status='new').count()
    
    # Останні замовлення
    recent_orders = Order.objects.select_related('customer').prefetch_related('items')[:6]
    
    # Топ продукти
    top_products = Product.objects.annotate(
        total_sold=Sum('order_items__quantity')
    ).filter(total_sold__isnull=False).order_by('-total_sold')[:5]

    sales_chart_labels, sales_chart_values = _build_sales_series(days=30)
    
    context = {
        'orders_today': orders_today,
        'orders_change': round(orders_change, 1),
        'orders_this_month': orders_this_month,
        'orders_month_change': round(orders_month_change, 1),
        'revenue_this_month': revenue_this_month,
        'revenue_change': round(revenue_change, 1),
        'profit_this_month': profit_this_month,
        'profit_change': round(profit_change, 1),
        'avg_check': avg_check,
        'avg_check_change': round(avg_check_change, 1),
        'low_stock_products': low_stock_products,
        'low_stock_count': low_stock_products.count(),
        'new_orders': new_orders,
        'recent_orders': recent_orders,
        'top_products': top_products,
        'sales_chart_labels': sales_chart_labels,
        'sales_chart_values': sales_chart_values,
    }
    return render(request, 'orders/dashboard.html', context)


def order_list(request):
    """Список замовлень"""
    status_filter, date_filter, search, date_range, date_from, date_to = _extract_order_filters(request.GET)
    orders = _apply_order_filters(
        Order.objects.select_related('customer').prefetch_related('items').all(),
        status_filter=status_filter,
        date_filter=date_filter,
        search=search,
        date_range=date_range,
        date_from=date_from,
        date_to=date_to,
    )

    # Статистика для фільтрів
    status_counts_qs = Order.objects.values('status').annotate(count=Count('id'))
    status_counts = {item['status']: item['count'] for item in status_counts_qs}
    status_label_map = dict(Order.STATUS_CHOICES)

    active_filters = []
    if status_filter:
        active_filters.append({'label': 'Статус', 'value': status_label_map.get(status_filter, status_filter)})
    if search:
        active_filters.append({'label': 'Пошук', 'value': search})
    if date_from or date_to:
        active_filters.append({'label': 'Період', 'value': f"{date_from or '...'} — {date_to or '...'}"})

    context = {
        'orders': orders,
        'status_filter': status_filter,
        'date_filter': date_filter,
        'date_range': date_range,
        'date_from': date_from,
        'date_to': date_to,
        'active_filters': active_filters,
        'q': search,
        'search': search,  # Залишаємо для сумісності зі старим шаблоном/URL.
        'status_choices': Order.STATUS_CHOICES,
        'status_counts': status_counts,
        'total_orders': Order.objects.count(),
    }
    return render(request, 'orders/order_list.html', context)


def order_export(request):
    """Експорт списку замовлень у CSV з урахуванням активних фільтрів."""
    status_filter, date_filter, search, date_range, date_from, date_to = _extract_order_filters(request.GET)
    orders = _apply_order_filters(
        Order.objects.select_related('customer').prefetch_related('items').all(),
        status_filter=status_filter,
        date_filter=date_filter,
        search=search,
        date_range=date_range,
        date_from=date_from,
        date_to=date_to,
    )

    filename = f'orders_{timezone.localdate().isoformat()}.csv'
    response = HttpResponse(content_type='text/csv; charset=utf-8')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    response.write('\ufeff')  # UTF-8 BOM для коректного відкриття в Excel.

    writer = csv.writer(response)
    writer.writerow([
        'id/number',
        'created_at',
        'customer_name',
        'customer_phone',
        'city',
        'total_cost',
        'status',
        'ttn',
    ])

    for order in orders:
        writer.writerow([
            order.pk,
            timezone.localtime(order.created_at).strftime('%Y-%m-%d %H:%M:%S'),
            order.customer.full_name,
            order.customer.phone,
            order.city,
            f'{order.get_total_cost():.2f}',
            order.get_status_display(),
            order.ttn,
        ])

    return response


def order_detail(request, pk):
    """Деталі замовлення"""
    order = get_object_or_404(
        Order.objects.select_related('customer').prefetch_related('items__product'),
        pk=pk
    )

    customer_orders = list(
        Order.objects.filter(customer=order.customer)
        .exclude(pk=order.pk)
        .select_related('customer')
        .prefetch_related('items')
        .order_by('-created_at')[:6]
    )
    customer_orders_count = Order.objects.filter(customer=order.customer).count()
    customer_completed_orders = list(
        Order.objects.filter(customer=order.customer, status='completed')
        .prefetch_related('items__product')
    )
    customer_total_spent = sum((customer_order.get_total_cost() for customer_order in customer_completed_orders), Decimal('0.00'))
    customer_avg_check = (
        customer_total_spent / len(customer_completed_orders)
        if customer_completed_orders else Decimal('0.00')
    )
    status_progress_steps = ['new', 'confirmed', 'shipped', 'completed']
    status_current_index = status_progress_steps.index(order.status) if order.status in status_progress_steps else -1

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
        'customer_orders': customer_orders,
        'customer_total_spent': customer_total_spent,
        'customer_avg_check': customer_avg_check,
        'customer_orders_count': customer_orders_count,
        'status_progress_steps': status_progress_steps,
        'status_current_index': status_current_index,
    }
    return render(request, 'orders/order_detail.html', context)


def order_create(request):
    """Створення замовлення"""
    if request.method == 'POST':
        form = OrderForm(request.POST)
        formset = OrderItemFormSet(request.POST, prefix='items')
        
        if form.is_valid() and formset.is_valid():
            try:
                with transaction.atomic():
                    order = form.save()
                    formset.instance = order
                    formset.save()
            except ValidationError as exc:
                messages.error(request, '; '.join(exc.messages))
            else:
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

    if order.status in INACTIVE_ORDER_STATUSES:
        messages.error(
            request,
            'Редагування позицій недоступне для скасованих/повернених замовлень. '
            'Змініть статус у деталях замовлення.'
        )
        return redirect('order_detail', pk=order.pk)
    
    if request.method == 'POST':
        form = OrderForm(request.POST, instance=order)
        formset = OrderItemFormSet(request.POST, instance=order, prefix='items')
        
        if form.is_valid() and formset.is_valid():
            try:
                with transaction.atomic():
                    form.save()
                    formset.save()
            except ValidationError as exc:
                messages.error(request, '; '.join(exc.messages))
            else:
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
        'total_customers': customers.count(),
    }
    return render(request, 'orders/customer_list.html', context)


def customer_create(request):
    """Створення клієнта з UI без Django admin."""
    if request.method == 'POST':
        form = CustomerForm(request.POST)
        if form.is_valid():
            customer = form.save()
            messages.success(request, f'Клієнта "{customer.full_name}" успішно створено.')
            return redirect('customer_list')
    else:
        form = CustomerForm()

    context = {
        'form': form,
        'title': 'Додати клієнта',
    }
    return render(request, 'orders/customer_form.html', context)


def customer_update(request, pk):
    """Редагування клієнта з UI без Django admin."""
    customer = get_object_or_404(Customer, pk=pk)

    if request.method == 'POST':
        form = CustomerForm(request.POST, instance=customer)
        if form.is_valid():
            customer = form.save()
            messages.success(request, f'Дані клієнта "{customer.full_name}" оновлено.')
            return redirect('customer_list')
    else:
        form = CustomerForm(instance=customer)

    context = {
        'form': form,
        'customer': customer,
        'title': f'Редагування клієнта: {customer.full_name}',
    }
    return render(request, 'orders/customer_form.html', context)


def customer_detail(request, pk):
    customer = get_object_or_404(Customer, pk=pk)
    customer_orders = list(
        Order.objects.filter(customer=customer)
        .select_related('customer')
        .prefetch_related('items__product')
        .order_by('-created_at')
    )

    completed_orders = [order for order in customer_orders if order.status == 'completed']
    total_spent = sum((order.get_total_cost() for order in completed_orders), Decimal('0.00'))
    average_check = (total_spent / len(completed_orders)) if completed_orders else Decimal('0.00')

    context = {
        'customer': customer,
        'customer_orders': customer_orders,
        'orders_count': len(customer_orders),
        'completed_orders_count': len(completed_orders),
        'total_spent': total_spent,
        'average_check': average_check,
    }
    return render(request, 'orders/customer_detail.html', context)


def global_search(request):
    query = (request.GET.get('q') or '').strip()
    if len(query) < 2:
        return JsonResponse({'orders': [], 'customers': [], 'products': []})

    orders = Order.objects.select_related('customer').filter(
        Q(customer__full_name__icontains=query)
        | Q(customer__phone__icontains=query)
        | Q(ttn__icontains=query)
        | Q(city__icontains=query)
    )[:5]
    customers = Customer.objects.filter(
        Q(full_name__icontains=query) | Q(phone__icontains=query)
    )[:5]
    products = Product.objects.filter(
        Q(name__icontains=query) | Q(sku__icontains=query)
    )[:5]

    payload = {
        'orders': [
            {
                'title': f'#{order.pk} - {order.customer.full_name}',
                'meta': f'{order.get_status_display()} | {order.city}',
                'url': reverse('order_detail', args=[order.pk]),
            }
            for order in orders
        ],
        'customers': [
            {
                'title': customer.full_name,
                'meta': customer.phone,
                'url': reverse('customer_detail', args=[customer.pk]),
            }
            for customer in customers
        ],
        'products': [
            {
                'title': product.name,
                'meta': f'SKU: {product.sku}',
                'url': reverse('product_update', args=[product.pk]),
            }
            for product in products
        ],
    }
    return JsonResponse(payload)

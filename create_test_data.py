"""
Скрипт для створення тестових даних
Запуск: python manage.py shell < create_test_data.py
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'crm_project.settings')
django.setup()

from decimal import Decimal
from orders.models import Product, Customer, Order, OrderItem

# Створюємо товари
products_data = [
    {'name': 'iPhone 15 Pro Max 256GB', 'sku': 'IPH15PM256', 'purchase_price': 45000, 'selling_price': 52000, 'stock': 15},
    {'name': 'Samsung Galaxy S24 Ultra', 'sku': 'SGS24U', 'purchase_price': 42000, 'selling_price': 48000, 'stock': 10},
    {'name': 'MacBook Pro 14" M3', 'sku': 'MBP14M3', 'purchase_price': 85000, 'selling_price': 95000, 'stock': 5},
    {'name': 'AirPods Pro 2', 'sku': 'APP2', 'purchase_price': 7500, 'selling_price': 9500, 'stock': 25},
    {'name': 'Apple Watch Series 9', 'sku': 'AWS9', 'purchase_price': 15000, 'selling_price': 18500, 'stock': 8},
    {'name': 'iPad Pro 12.9" M2', 'sku': 'IPADPRO12M2', 'purchase_price': 48000, 'selling_price': 55000, 'stock': 3},
    {'name': 'Sony WH-1000XM5', 'sku': 'SONYXM5', 'purchase_price': 9000, 'selling_price': 12000, 'stock': 12},
    {'name': 'Чохол для iPhone 15 Pro Max', 'sku': 'CASE-IPH15PM', 'purchase_price': 200, 'selling_price': 450, 'stock': 50},
    {'name': 'Зарядка MagSafe 15W', 'sku': 'MAGSAFE15', 'purchase_price': 800, 'selling_price': 1500, 'stock': 2},
    {'name': 'Захисне скло iPhone 15', 'sku': 'GLASS-IPH15', 'purchase_price': 100, 'selling_price': 350, 'stock': 4},
]

print("Створюю товари...")
for data in products_data:
    Product.objects.get_or_create(sku=data['sku'], defaults=data)
print(f"Створено {Product.objects.count()} товарів")

# Створюємо клієнтів
customers_data = [
    {'full_name': 'Іван Петренко', 'phone': '+380501234567', 'source': 'instagram'},
    {'full_name': 'Марія Коваленко', 'phone': '+380672345678', 'source': 'facebook'},
    {'full_name': 'Олександр Шевченко', 'phone': '+380933456789', 'source': 'olx'},
    {'full_name': 'Анна Бондаренко', 'phone': '+380664567890', 'source': 'website'},
    {'full_name': 'Дмитро Мельник', 'phone': '+380955678901', 'source': 'referral'},
]

print("Створюю клієнтів...")
for data in customers_data:
    Customer.objects.get_or_create(phone=data['phone'], defaults=data)
print(f"Створено {Customer.objects.count()} клієнтів")

# Створюємо замовлення
print("Створюю замовлення...")
customers = list(Customer.objects.all())
products = list(Product.objects.all())

if customers and products:
    # Замовлення 1 - Нове
    order1, created = Order.objects.get_or_create(
        customer=customers[0],
        city='Київ',
        defaults={
            'status': 'new',
            'delivery_service': 'nova_poshta',
            'warehouse': 'Відділення №15',
            'payment_type': 'cod',
        }
    )
    if created:
        OrderItem.objects.create(order=order1, product=products[0], quantity=1, price=products[0].selling_price)
        OrderItem.objects.create(order=order1, product=products[3], quantity=1, price=products[3].selling_price)

    # Замовлення 2 - Виконано
    order2, created = Order.objects.get_or_create(
        customer=customers[1],
        city='Львів',
        defaults={
            'status': 'completed',
            'delivery_service': 'nova_poshta',
            'warehouse': 'Відділення №23',
            'payment_type': 'prepaid',
            'prepayment': Decimal('48000'),
            'ttn': '20450123456789',
        }
    )
    if created:
        OrderItem.objects.create(order=order2, product=products[1], quantity=1, price=products[1].selling_price)

    # Замовлення 3 - Відправлено
    order3, created = Order.objects.get_or_create(
        customer=customers[2],
        city='Одеса',
        defaults={
            'status': 'shipped',
            'delivery_service': 'nova_poshta',
            'warehouse': 'Поштомат №45',
            'payment_type': 'partial',
            'prepayment': Decimal('5000'),
            'ttn': '20450987654321',
        }
    )
    if created:
        OrderItem.objects.create(order=order3, product=products[6], quantity=1, price=products[6].selling_price)
        OrderItem.objects.create(order=order3, product=products[7], quantity=2, price=products[7].selling_price)

print(f"Створено {Order.objects.count()} замовлень")
print("\nГотово! Тестові дані створено.")

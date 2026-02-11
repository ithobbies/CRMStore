import csv
from datetime import timedelta
from decimal import Decimal
from io import StringIO

from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .models import Customer, Order, OrderItem, Product


class OrderStockSignalsTests(TestCase):
    def setUp(self):
        self.customer = Customer.objects.create(
            full_name='Test Customer',
            phone='+380000000000',
        )

    def create_product(self, sku, stock):
        return Product.objects.create(
            name=sku,
            sku=sku,
            purchase_price=Decimal('100.00'),
            selling_price=Decimal('150.00'),
            stock=stock,
        )

    def create_order(self, status='new'):
        return Order.objects.create(
            customer=self.customer,
            city='Kyiv',
            status=status,
        )

    def test_order_item_quantity_update_adjusts_stock(self):
        product = self.create_product('SKU-1', 10)
        order = self.create_order()

        item = OrderItem.objects.create(
            order=order,
            product=product,
            quantity=2,
            price=product.selling_price,
        )
        product.refresh_from_db()
        self.assertEqual(product.stock, 8)

        item.quantity = 5
        item.save()
        product.refresh_from_db()
        self.assertEqual(product.stock, 5)

        item.quantity = 1
        item.save()
        product.refresh_from_db()
        self.assertEqual(product.stock, 9)

    def test_order_item_product_change_rebalances_stock(self):
        old_product = self.create_product('SKU-2', 10)
        new_product = self.create_product('SKU-3', 7)
        order = self.create_order()

        item = OrderItem.objects.create(
            order=order,
            product=old_product,
            quantity=3,
            price=old_product.selling_price,
        )
        old_product.refresh_from_db()
        new_product.refresh_from_db()
        self.assertEqual(old_product.stock, 7)
        self.assertEqual(new_product.stock, 7)

        item.product = new_product
        item.quantity = 2
        item.price = new_product.selling_price
        item.save()

        old_product.refresh_from_db()
        new_product.refresh_from_db()
        self.assertEqual(old_product.stock, 10)
        self.assertEqual(new_product.stock, 5)

    def test_quantity_update_rejects_negative_stock(self):
        product = self.create_product('SKU-NEG', 5)
        order = self.create_order()
        item = OrderItem.objects.create(
            order=order,
            product=product,
            quantity=2,
            price=product.selling_price,
        )
        product.refresh_from_db()
        self.assertEqual(product.stock, 3)

        item.quantity = 10
        with self.assertRaises(ValidationError):
            item.save()

        product.refresh_from_db()
        item.refresh_from_db()
        self.assertEqual(product.stock, 3)
        self.assertEqual(item.quantity, 2)

    def test_item_create_for_canceled_order_does_not_deduct_stock(self):
        product = self.create_product('SKU-4', 10)
        order = self.create_order(status='canceled')

        OrderItem.objects.create(
            order=order,
            product=product,
            quantity=4,
            price=product.selling_price,
        )

        product.refresh_from_db()
        self.assertEqual(product.stock, 10)

    def test_item_delete_for_canceled_order_does_not_increase_stock(self):
        product = self.create_product('SKU-5', 10)
        order = self.create_order(status='new')
        item = OrderItem.objects.create(
            order=order,
            product=product,
            quantity=2,
            price=product.selling_price,
        )

        product.refresh_from_db()
        self.assertEqual(product.stock, 8)

        order.status = 'canceled'
        order.save()
        product.refresh_from_db()
        self.assertEqual(product.stock, 10)

        item.delete()
        product.refresh_from_db()
        self.assertEqual(product.stock, 10)

    def test_reactivate_order_uses_latest_item_quantities(self):
        product = self.create_product('SKU-6', 10)
        order = self.create_order(status='new')
        item = OrderItem.objects.create(
            order=order,
            product=product,
            quantity=2,
            price=product.selling_price,
        )
        product.refresh_from_db()
        self.assertEqual(product.stock, 8)

        order.status = 'canceled'
        order.save()
        product.refresh_from_db()
        self.assertEqual(product.stock, 10)

        item.quantity = 4
        item.save()
        product.refresh_from_db()
        self.assertEqual(product.stock, 10)

        order.status = 'new'
        order.save()
        product.refresh_from_db()
        self.assertEqual(product.stock, 6)


class OrderListAndExportViewTests(TestCase):
    def setUp(self):
        self.customer = Customer.objects.create(
            full_name='View Customer',
            phone='+380111111111',
        )
        self.product = Product.objects.create(
            name='View Product',
            sku='VIEW-SKU',
            purchase_price=Decimal('50.00'),
            selling_price=Decimal('100.00'),
            stock=50,
        )

    def create_order_with_item(self, status='new', city='Lviv', quantity=1, created_at=None):
        order = Order.objects.create(customer=self.customer, city=city, status=status)
        OrderItem.objects.create(
            order=order,
            product=self.product,
            quantity=quantity,
            price=self.product.selling_price,
        )
        if created_at:
            Order.objects.filter(pk=order.pk).update(created_at=created_at)
            order.refresh_from_db()
        return order

    def test_status_counts_rendered_and_date_filter_present(self):
        self.create_order_with_item(status='new')
        self.create_order_with_item(status='new')
        self.create_order_with_item(status='canceled')

        response = self.client.get(reverse('order_list'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'name="date"')

        count_map = response.context['status_counts']
        self.assertEqual(count_map.get('new', 0), 2)
        self.assertEqual(count_map.get('canceled', 0), 1)
        self.assertEqual(count_map.get('returned', 0), 0)

    def test_zero_status_counts_when_no_orders(self):
        response = self.client.get(reverse('order_list'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['status_counts'].get('new', 0), 0)
        self.assertContains(response, '<span class="count">0</span>', html=False)

    def test_order_export_respects_filters(self):
        now = timezone.now()
        included = self.create_order_with_item(
            status='new',
            city='Kyiv',
            quantity=2,
            created_at=now,
        )
        self.create_order_with_item(
            status='canceled',
            city='Kyiv',
            quantity=1,
            created_at=now,
        )
        self.create_order_with_item(
            status='new',
            city='Lviv',
            quantity=1,
            created_at=now - timedelta(days=1),
        )

        date_filter = now.date().isoformat()
        response = self.client.get(
            reverse('order_export'),
            {'status': 'new', 'q': 'Kyiv', 'date': date_filter},
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn('attachment; filename="orders_', response['Content-Disposition'])

        content = response.content.decode('utf-8-sig')
        rows = list(csv.reader(StringIO(content)))
        self.assertEqual(rows[0], [
            'id/number',
            'created_at',
            'customer_name',
            'customer_phone',
            'city',
            'total_cost',
            'status',
            'ttn',
        ])
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[1][0], str(included.pk))
        self.assertEqual(rows[1][4], 'Kyiv')


class OrderFormRestrictionsTests(TestCase):
    def setUp(self):
        self.customer = Customer.objects.create(
            full_name='Form Customer',
            phone='+380222222222',
        )
        self.product = Product.objects.create(
            name='Order Product',
            sku='ORDER-SKU',
            purchase_price=Decimal('30.00'),
            selling_price=Decimal('70.00'),
            stock=10,
        )

    def _build_order_payload(self, status='new'):
        return {
            'customer': self.customer.pk,
            'status': status,
            'delivery_service': 'nova_poshta',
            'city': 'Kyiv',
            'warehouse': '',
            'ttn': '',
            'payment_type': 'cod',
            'prepayment': '0',
            'seller_expenses': '0',
            'notes': '',
            'new_customer_name': '',
            'new_customer_phone': '',
            'new_customer_source': 'other',
            'items-TOTAL_FORMS': '1',
            'items-INITIAL_FORMS': '0',
            'items-MIN_NUM_FORMS': '0',
            'items-MAX_NUM_FORMS': '1000',
            'items-0-id': '',
            'items-0-product': str(self.product.pk),
            'items-0-quantity': '2',
            'items-0-price': '70.00',
            'items-0-DELETE': '',
        }

    def test_order_create_rejects_canceled_status(self):
        response = self.client.post(
            reverse('order_create'),
            data=self._build_order_payload(status='canceled'),
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Неможливо створити замовлення')
        self.assertEqual(Order.objects.count(), 0)
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 10)

    def test_inactive_order_update_redirects_to_detail(self):
        order = Order.objects.create(customer=self.customer, city='Kyiv', status='canceled')
        response = self.client.get(reverse('order_update', args=[order.pk]))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse('order_detail', args=[order.pk]))


class CustomerViewsTests(TestCase):
    def setUp(self):
        self.customer = Customer.objects.create(
            full_name='Existing Customer',
            phone='+380333333333',
        )

    def test_customer_create_and_edit_pages(self):
        create_response = self.client.get(reverse('customer_create'))
        self.assertEqual(create_response.status_code, 200)

        edit_response = self.client.get(reverse('customer_update', args=[self.customer.pk]))
        self.assertEqual(edit_response.status_code, 200)

    def test_customer_create_prevents_duplicate_phone(self):
        response = self.client.post(
            reverse('customer_create'),
            data={
                'full_name': 'Duplicate Customer',
                'phone': '+380333333333',
                'email': '',
                'source': 'other',
                'notes': '',
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Клієнт з таким телефоном вже існує')
        self.assertEqual(Customer.objects.count(), 1)

    def test_customer_update_with_same_phone_is_allowed(self):
        response = self.client.post(
            reverse('customer_update', args=[self.customer.pk]),
            data={
                'full_name': 'Existing Customer Updated',
                'phone': '+380333333333',
                'email': '',
                'source': 'other',
                'notes': '',
            },
        )
        self.assertEqual(response.status_code, 302)
        self.customer.refresh_from_db()
        self.assertEqual(self.customer.full_name, 'Existing Customer Updated')

from django.db import models, transaction
from django.core.validators import MinValueValidator
from django.core.exceptions import ValidationError
from decimal import Decimal


INACTIVE_ORDER_STATUSES = {'canceled', 'returned'}


class Product(models.Model):
    """Модель товару"""
    name = models.CharField('Назва', max_length=255)
    sku = models.CharField('Артикул', max_length=50, unique=True)
    purchase_price = models.DecimalField(
        'Ціна закупівлі', 
        max_digits=10, 
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.00'))]
    )
    selling_price = models.DecimalField(
        'Ціна продажу', 
        max_digits=10, 
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.00'))]
    )
    stock = models.PositiveIntegerField('Залишок на складі', default=0)
    created_at = models.DateTimeField('Створено', auto_now_add=True)
    updated_at = models.DateTimeField('Оновлено', auto_now=True)

    class Meta:
        verbose_name = 'Товар'
        verbose_name_plural = 'Товари'
        ordering = ['name']

    def __str__(self):
        return f"{self.name} ({self.sku})"

    def get_profit_margin(self):
        """Розрахунок маржі"""
        if self.purchase_price > 0:
            return ((self.selling_price - self.purchase_price) / self.purchase_price) * 100
        return Decimal('0.00')


class Customer(models.Model):
    """Модель клієнта"""
    SOURCE_CHOICES = [
        ('instagram', 'Instagram'),
        ('facebook', 'Facebook'),
        ('olx', 'OLX'),
        ('rozetka', 'Rozetka'),
        ('website', 'Сайт'),
        ('referral', 'Рекомендація'),
        ('other', 'Інше'),
    ]

    full_name = models.CharField('ПІБ', max_length=255)
    phone = models.CharField('Телефон', max_length=20, unique=True)
    email = models.EmailField('Email', blank=True, null=True)
    source = models.CharField(
        'Джерело', 
        max_length=20, 
        choices=SOURCE_CHOICES, 
        default='other'
    )
    notes = models.TextField('Примітки', blank=True)
    created_at = models.DateTimeField('Створено', auto_now_add=True)

    class Meta:
        verbose_name = 'Клієнт'
        verbose_name_plural = 'Клієнти'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.full_name} ({self.phone})"


class Order(models.Model):
    """Модель замовлення"""
    STATUS_CHOICES = [
        ('new', 'Новий'),
        ('confirmed', 'Підтверджено'),
        ('shipped', 'Відправлено'),
        ('completed', 'Виконано'),
        ('canceled', 'Скасовано'),
        ('returned', 'Повернення'),
    ]

    DELIVERY_CHOICES = [
        ('nova_poshta', 'Нова Пошта'),
        ('ukrposhta', 'Укрпошта'),
        ('meest', 'Meest'),
        ('pickup', 'Самовивіз'),
    ]

    PAYMENT_CHOICES = [
        ('cod', 'Накладений платіж'),
        ('prepaid', 'Передплата'),
        ('partial', 'Часткова передплата'),
    ]

    # Зв'язок з клієнтом
    customer = models.ForeignKey(
        Customer, 
        on_delete=models.PROTECT, 
        related_name='orders',
        verbose_name='Клієнт'
    )

    # Статус
    status = models.CharField(
        'Статус', 
        max_length=20, 
        choices=STATUS_CHOICES, 
        default='new'
    )

    # Доставка
    delivery_service = models.CharField(
        'Служба доставки', 
        max_length=20, 
        choices=DELIVERY_CHOICES, 
        default='nova_poshta'
    )
    city = models.CharField('Місто', max_length=100)
    warehouse = models.CharField('Відділення', max_length=255, blank=True)
    ttn = models.CharField('ТТН', max_length=50, blank=True)

    # Фінанси
    payment_type = models.CharField(
        'Тип оплати', 
        max_length=20, 
        choices=PAYMENT_CHOICES, 
        default='cod'
    )
    prepayment = models.DecimalField(
        'Передплата', 
        max_digits=10, 
        decimal_places=2, 
        default=Decimal('0.00'),
        validators=[MinValueValidator(Decimal('0.00'))]
    )
    seller_expenses = models.DecimalField(
        'Витрати продавця', 
        max_digits=10, 
        decimal_places=2, 
        default=Decimal('0.00'),
        validators=[MinValueValidator(Decimal('0.00'))],
        help_text='Додаткові витрати (пакування, доставка тощо)'
    )

    # Примітки та дати
    notes = models.TextField('Примітки', blank=True)
    created_at = models.DateTimeField('Створено', auto_now_add=True)
    updated_at = models.DateTimeField('Оновлено', auto_now=True)

    class Meta:
        verbose_name = 'Замовлення'
        verbose_name_plural = 'Замовлення'
        ordering = ['-created_at']

    def __str__(self):
        return f"Замовлення #{self.pk} - {self.customer.full_name}"

    def get_total_cost(self):
        """Загальна вартість замовлення (сума всіх товарів)"""
        total = sum(item.get_cost() for item in self.items.all())
        return total

    def get_amount_due(self):
        """Сума накладеного платежу (до сплати при отриманні)"""
        return self.get_total_cost() - self.prepayment

    def get_profit(self):
        """Прибуток із замовлення"""
        total_purchase = sum(
            item.quantity * item.product.purchase_price 
            for item in self.items.all()
        )
        return self.get_total_cost() - total_purchase - self.seller_expenses

    def get_status_color(self):
        """Колір бейджа для статусу"""
        colors = {
            'new': 'primary',
            'confirmed': 'info',
            'shipped': 'warning',
            'completed': 'success',
            'canceled': 'danger',
            'returned': 'secondary',
        }
        return colors.get(self.status, 'secondary')


class OrderItem(models.Model):
    """Модель товару в замовленні"""
    order = models.ForeignKey(
        Order, 
        on_delete=models.CASCADE, 
        related_name='items',
        verbose_name='Замовлення'
    )
    product = models.ForeignKey(
        Product, 
        on_delete=models.PROTECT, 
        related_name='order_items',
        verbose_name='Товар'
    )
    quantity = models.PositiveIntegerField(
        'Кількість', 
        default=1,
        validators=[MinValueValidator(1)]
    )
    price = models.DecimalField(
        'Ціна за одиницю', 
        max_digits=10, 
        decimal_places=2,
        help_text='Фіксована ціна на момент замовлення'
    )

    class Meta:
        verbose_name = 'Товар замовлення'
        verbose_name_plural = 'Товари замовлення'

    def __str__(self):
        return f"{self.product.name} x {self.quantity}"

    def get_cost(self):
        """Вартість позиції"""
        return self.price * self.quantity

    def save(self, *args, **kwargs):
        # Якщо ціна не встановлена, беремо поточну ціну продажу
        if not self.price:
            self.price = self.product.selling_price

        self.full_clean()
        with transaction.atomic():
            super().save(*args, **kwargs)

    def clean(self):
        """Валідація залишків при створенні та редагуванні позиції."""
        order_status = self.order.status if self.order_id else None
        if order_status in INACTIVE_ORDER_STATUSES:
            return

        if self.pk is None:
            if self.quantity > self.product.stock:
                raise ValidationError({
                    'quantity': f'Недостатньо товару на складі. Доступно: {self.product.stock}'
                })
            return

        try:
            old_item = OrderItem.objects.select_related('product').get(pk=self.pk)
        except OrderItem.DoesNotExist:
            return

        if old_item.product_id == self.product_id:
            available = self.product.stock + old_item.quantity
            if self.quantity > available:
                raise ValidationError({
                    'quantity': f'Недостатньо товару на складі. Доступно: {available}'
                })
            return

        if self.quantity > self.product.stock:
            raise ValidationError({
                'quantity': f'Недостатньо товару на складі. Доступно: {self.product.stock}'
            })

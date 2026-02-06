from django import forms
from django.forms import inlineformset_factory
from .models import Order, OrderItem, Customer, Product


class CustomerForm(forms.ModelForm):
    """Форма клієнта"""
    class Meta:
        model = Customer
        fields = ['full_name', 'phone', 'email', 'source', 'notes']
        widgets = {
            'full_name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Введіть ПІБ клієнта'
            }),
            'phone': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': '+380XXXXXXXXX'
            }),
            'email': forms.EmailInput(attrs={
                'class': 'form-control',
                'placeholder': 'email@example.com'
            }),
            'source': forms.Select(attrs={'class': 'form-select'}),
            'notes': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 2,
                'placeholder': 'Додаткова інформація про клієнта'
            }),
        }


class ProductForm(forms.ModelForm):
    """Форма товару"""
    class Meta:
        model = Product
        fields = ['name', 'sku', 'purchase_price', 'selling_price', 'stock']
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Назва товару'
            }),
            'sku': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Артикул (SKU)'
            }),
            'purchase_price': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01',
                'min': '0',
                'placeholder': '0.00'
            }),
            'selling_price': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01',
                'min': '0',
                'placeholder': '0.00'
            }),
            'stock': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': '0',
                'placeholder': '0'
            }),
        }


class OrderForm(forms.ModelForm):
    """Форма замовлення"""
    
    # Поля для нового клієнта
    new_customer_name = forms.CharField(
        label='ПІБ нового клієнта',
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Введіть ПІБ'
        })
    )
    new_customer_phone = forms.CharField(
        label='Телефон',
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': '+380XXXXXXXXX'
        })
    )
    new_customer_source = forms.ChoiceField(
        label='Джерело',
        choices=Customer.SOURCE_CHOICES,
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'})
    )

    class Meta:
        model = Order
        fields = [
            'customer', 'status', 'delivery_service', 'city', 
            'warehouse', 'ttn', 'payment_type', 'prepayment', 
            'seller_expenses', 'notes'
        ]
        widgets = {
            'customer': forms.Select(attrs={'class': 'form-select'}),
            'status': forms.Select(attrs={'class': 'form-select'}),
            'delivery_service': forms.Select(attrs={'class': 'form-select'}),
            'city': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Введіть місто'
            }),
            'warehouse': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Номер відділення'
            }),
            'ttn': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Номер ТТН'
            }),
            'payment_type': forms.Select(attrs={'class': 'form-select'}),
            'prepayment': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01',
                'min': '0'
            }),
            'seller_expenses': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01',
                'min': '0'
            }),
            'notes': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Примітки до замовлення'
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['customer'].required = False
        self.fields['customer'].queryset = Customer.objects.all()
        self.fields['customer'].empty_label = '-- Оберіть існуючого клієнта --'

    def clean(self):
        cleaned_data = super().clean()
        customer = cleaned_data.get('customer')
        new_name = cleaned_data.get('new_customer_name')
        new_phone = cleaned_data.get('new_customer_phone')

        if not customer and not (new_name and new_phone):
            raise forms.ValidationError(
                'Оберіть існуючого клієнта або введіть дані нового'
            )
        
        return cleaned_data

    def save(self, commit=True):
        instance = super().save(commit=False)
        
        # Якщо клієнт не обраний, створюємо нового
        if not instance.customer_id:
            customer = Customer.objects.create(
                full_name=self.cleaned_data['new_customer_name'],
                phone=self.cleaned_data['new_customer_phone'],
                source=self.cleaned_data.get('new_customer_source', 'other')
            )
            instance.customer = customer
        
        if commit:
            instance.save()
        return instance


class OrderItemForm(forms.ModelForm):
    """Форма товару в замовленні"""
    class Meta:
        model = OrderItem
        fields = ['product', 'quantity', 'price']
        widgets = {
            'product': forms.Select(attrs={
                'class': 'form-select product-select'
            }),
            'quantity': forms.NumberInput(attrs={
                'class': 'form-control quantity-input',
                'min': '1',
                'value': '1'
            }),
            'price': forms.NumberInput(attrs={
                'class': 'form-control price-input',
                'step': '0.01',
                'min': '0'
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['product'].queryset = Product.objects.filter(stock__gt=0)
        self.fields['product'].empty_label = '-- Оберіть товар --'
        self.fields['price'].required = False


# Formset для товарів замовлення
OrderItemFormSet = inlineformset_factory(
    Order,
    OrderItem,
    form=OrderItemForm,
    extra=1,
    can_delete=True,
    min_num=1,
    validate_min=True
)


class OrderStatusForm(forms.ModelForm):
    """Форма для зміни статусу замовлення"""
    class Meta:
        model = Order
        fields = ['status', 'ttn']
        widgets = {
            'status': forms.Select(attrs={'class': 'form-select'}),
            'ttn': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Номер ТТН'
            }),
        }

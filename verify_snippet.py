import os
import django
from django.conf import settings

# Setup Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'crm_project.settings')
django.setup()

from django.template import Template, Context
from orders.models import Product

# Test the specific line causing issues
template_string = """
{% for product in products %}
"{{ product.pk }}": {{ product.selling_price | stringformat:"f" }}{% if not forloop.last %}, {% endif %}
{% endfor %}
"""

try:
    products = Product.objects.filter(stock__gt=0)
    # Check if we have products
    print(f"Found {products.count()} products.")
    
    t = Template(template_string)
    c = Context({"products": products})
    rendered = t.render(c)
    print("Rendered output snippet:")
    print(rendered.strip())
    print("SUCCESS: Template rendered without error.")
except Exception as e:
    print(f"ERROR: {e}")

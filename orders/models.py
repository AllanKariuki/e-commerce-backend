from django.db import models
from users.models import User
from products.models import Product

# Create your models here.
class Order(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='orders')
    products = models.ManyToManyField(Product, through='OrderItem')
    status=models.CharField(max_length=50, default='pending')
    total_amount = models.DecimalField(max_digits=10, decimal_places=2)
    created_at = models.DateTimeField(auto_now_add=True)


    def __str__(self):
        return f"Order {self.id} - {self.user.username}"
    # Add other order fields as needed

class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE)
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField()
    price = models.DecimalField(max_digits=10, decimal_places=2)

    def __str__(self):
        return f"OrderItem {self.id} - {self.product.name}"
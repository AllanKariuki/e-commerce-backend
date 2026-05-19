from django.db import models
from users.models import User
from django.contrib.postgres.fields import ArrayField

# Create your models here.
class ProductCategory(models.Model):
    name = models.CharField(max_length=100)
    description = models.TextField()

    def __str__(self):
        return self.name
    
class Product(models.Model):
    name = models.CharField(max_length=100)
    description = models.TextField()
    price = models.DecimalField(max_digits=10, decimal_places=2)
    category = models.ForeignKey(ProductCategory, on_delete=models.CASCADE)
    units_in_stock = models.IntegerField()
    sizes = ArrayField(models.CharField(max_length=10), blank=True, null=True)
    colors = ArrayField(models.CharField(max_length=30), blank=True, null=True)
    material = models.CharField(max_length=50, blank=True, null=True)
    rating = models.FloatField(default=0.0)
    original_price = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    brand = models.CharField(max_length=50, blank=True, null=True)

    def __str__(self):
        return self.name
    
class ProductImage(models.Model):
    product = models.ForeignKey(Product, related_name='images', on_delete=models.CASCADE)
    image = models.ImageField(upload_to="products_images", null=True, blank=True)
    is_main = models.BooleanField(default=False)

    def __str__(self) :
        return f"Image for {self.product.name}"
    
class Review(models.Model):
    product = models.ForeignKey(Product, related_name='reviews', on_delete=models.CASCADE)
    user = models.ForeignKey(User, related_name='reviews', on_delete=models.CASCADE)
    rating = models.IntegerField(choices=[(i, i) for i in range(1, 6)])
    comment = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Review for {self.product.name} by {self.user.username}"
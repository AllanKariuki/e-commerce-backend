from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase
from django.contrib.auth import get_user_model
from products.models import Product, ProductCategory
from orders.models import Order, OrderItem
from users.models import User

class TestOrderViewSet(APITestCase):
    def setUp(self):
        # Create a test user and authenticate them
        self.user = User.objects.create(
            username="testuser",
            email="test@example.com",
            first_name="Test",
            last_name="User",
            phone="1234567890"
        )
        self.client.force_authenticate(user=self.user)

        # Create some products
        self.product1 = Product.objects.create(
            name="Product 1",
            description="Description 1",
            price=10.00,
            category=ProductCategory.objects.create(name="Category 1", description="Cat Desc 1"),
            units_in_stock=100
        )
        self.product2 = Product.objects.create(
            name="Product 2",
            description="Description 2",
            price=20.00,
            category=ProductCategory.objects.create(name="Category 2", description="Cat Desc 2"),
            units_in_stock=50
        )

        self.url = reverse('order-list')

        return super().setUp()
    
    def test_create_order_with_items(self):
        payload = {
            "total_amount": "3000.00",
            "cart_items": [
                {"product": self.product1.id, "quantity": 2, "price": "10.00"},
                {"product": self.product2.id, "quantity": 1, "price": "20.00"}
            ],
        }

        response = self.client.post(self.url, payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        order = Order.objects.get(id=response.data["id"])
        self.assertEqual(order.total_amount, 3000.00)
        
    
    def test_update_order_items(self):

        # Create an order first
        order = Order.objects.create(user=self.user, total_amount=1000)
        OrderItem.objects.create(order=order, product=self.product1, quantity=1)

        update_url = reverse("order-detail", args=[order.id])

        payload = {
            "total_amount": "2000.00",
            "cart_items": [
                {"product": self.product1.id, "quantity": 1},
                {"product": self.product2.id, "quantity": 3}
            ],
        }

        response = self.client.put(update_url, payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        order.refresh_from_db()
        self.assertEqual(order.total_amount, 2000.00)
        
        # Check update qty
        item = order.products.get(product=self.product1)
        self.assertEqual(item.quantity, 1)

        item = order.products.get(product=self.product2)
        self.assertEqual(item.quantity, 3)

    def test_delete_order_removes_items(self):
        order = Order.objects.create(user=self.user, total_amount=1000)
        OrderItem.objects.create(order=order, product=self.product1, quantity=1)

        delete_url = reverse('order-detail', args=[order.id])
        response = self.client.delete(delete_url)
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)

        self.assertFalse(Order.objects.filter(id=order.id).exists())
        self.assertFalse(OrderItem.objects.filter(order=order).exists())

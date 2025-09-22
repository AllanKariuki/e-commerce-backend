from rest_framework import serializers
from .models import Order, OrderItem

class OrderItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = OrderItem
        fields = '__all__'

class OrderSerializer(serializers.ModelSerializer):
    cart_items = OrderItemSerializer(many=True)
    class Meta:
        model = Order
        fields = ['id', 'user', 'status', 'total_amount', 'created_at']
        read_only_fields = ['id', 'created_at', 'user']

    def create(self, validated_data):
        items_data = validated_data.pop('cart_items', [])
        order = Order.objects.create(**validated_data)
        for item in items_data:
            OrderItem.objects.create(order=order, **item)
        
        return order
    
    def update(self, instance, validated_data):
        items_data = validated_data.pop("cart_items", [])
        instance.total_amount = validated_data.get("total_amount", instance.total_amount)
        instance.save()

        # Clear old items and recreate 
        instance.cart_items.all().delete()
        for item in items_data:
            OrderItem.objects.create(order=instance, **item) 
        
        return instance       


        
from rest_framework import viewsets, status
from rest_framework.permissions import IsAuthenticated
from .models import Order, OrderItem
from .serializers import OrderSerializer, OrderItemSerializer
from rest_framework.response import Response
from products.models import Product
from django.db import transaction
from django.shortcuts import get_object_or_404

class OrderViewSet(viewsets.ModelViewSet):
    # permission_classes = [IsAuthenticated]
    serializer_class = OrderSerializer
    queryset = Order.objects.all()

    def get_queryset(self):
        return Order.objects.filter(user=self.request.user)

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

    def perform_update(self, serializer):
        serializer.save(user=self.request.user)

    def perform_destroy(self, instance):
        instance.delete()

    def list(self, request, *args, **kwargs):
        queryset = self.get_queryset()
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(instance)
        return Response(serializer.data)
    
    def create(self, request, *args, **kwargs):
        order_data = {
            "user": request.data.get('user'),
            'total_amount': request.data.get('total_amount'),
        } 
        
        with transaction.atomic(): # rollback if any step fails
            serializer = self.get_serializer(data=order_data)
            serializer.is_valid(raise_exception=True)
            order = serializer.save()

            items = request.data.get("cart_items", [])
            for item in items:
                product_id = item.get('product')
                product = get_object_or_404(Product, pk=product_id)

                item["order"] = order.id
                order_item_serializer = OrderItemSerializer(data=item)
                order_item_serializer.is_valid(raise_exception=True)
                order_item_serializer.save()
        return Response(
            {"detail": "Order created successfully"},
            status=status.HTTP_201_CREATED
        )


    def update(self, request, *args, **kwargs):
        try:
            queryset = self.get_queryset()
            order = queryset.get(pk=kwargs['pk'])
            
            order_data = {
                "user": request.data.get('user'),
                'total_amount': request.data.get('total_amount'),
            }
            serializer = self.get_serializer(order, data=order_data, partial=True)
            if not serializer.is_valid():
                return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
            serializer.save()

            # Update order items
            items = request.data.get("cart_items", [])
            for item in items:
                # Check if the order items exist in the database
                order_item = OrderItem.objects.filter(order=order, product=item['product'], size=item['size']).first()
                if not order_item:
                    # Create a new order Item
                    item['order'] = serializer.data['id']
                    order_item_serializer = OrderItemSerializer(data=item)
                    order_item_serializer.is_valid(raise_exception=True)
                    order_item_serializer.save()
                
                # Update existing order item
                item['order'] = serializer.data['id']
                order_item_serializer = OrderItemSerializer(order_item, data=item, partial=True)
                order_item_serializer.is_valid(exception=True)
                order_item_serializer.save()

            return Response({'msg': 'Order updated successfully', 'code': 200}, status=status.HTTP_200_OK)
        except Order.DoesNotExist:
            return Response({'msg': 'Order does not exist', 'code': 400}, status=status.HTTP_400_BAD_REQUEST)

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        self.perform_destroy(instance)
        return Response(status=status.HTTP_204_NO_CONTENT)
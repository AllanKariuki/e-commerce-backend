import logging
from e_commerce_backend.celery import shared_task
from django.core.mail import send_mail
from django.conf import settings
from datetime import datetime
from orders.models import Order, OrderItem
from products.models import Product

@shared_task(bind=True, max_retries=3)
def process_order(self, order_id):
    """
    Process a new order with the following steps:
    1. Validate order exists
    2. Check stock availability
    3. Update product inventory
    4. Update order status
    5. Send confirmation email
    
    Args:
        order_id (int): The ID of the order to process
        
    Returns:
        str: Success message with order ID
        
    Raises:
        Order.DoesNotExist: If order not found
        ValueError: If insufficient stock
    """
    try:
        # Get the order
        order = Order.objects.select_related('user').prefetch_related('items__product').get(id=order_id)
        
        # Update order status
        order.status = 'processing'
        order.save()
        
        # Check and update inventory
        for item in order.items.all():
            product = item.product
            
            # Check if enough stock is available
            if product.stock < item.quantity:
                raise ValueError(f"Insufficient stock for product {product.name}")
            
            # Update inventory
            product.stock -= item.quantity
            product.save()
        
        # Mark order as completed
        order.status = 'completed'
        order.save()
        
        # Send confirmation email
        send_mail(
            subject='Your Order Has Been Processed',
            message=f"""
            Dear {order.user.username},
            
            Your order #{order.id} has been successfully processed.
            Total amount: ${order.total_amount}
            
            Thank you for shopping with us!
            """,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[order.user.email],
            fail_silently=False,
        )
        
        logging.info(f"Order {order_id} processed successfully")
        return f"Order {order_id} processed successfully"
        
    except Order.DoesNotExist:
        logging.error(f"Order {order_id} not found")
        raise
        
    except ValueError as e:
        logging.error(f"Stock error for order {order_id}: {str(e)}")
        order.status = 'failed'
        order.save()
        raise
        
    except Exception as exc:
        logging.error(f"Error processing order {order_id}: {str(exc)}")
        order.status = 'failed'
        order.save()
        self.retry(exc=exc, countdown=60)  # Retry after 1 minute
    
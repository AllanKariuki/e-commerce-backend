from rest_framework import serializers
from .models import Product, ProductCategory, ProductImage

class ProductCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductCategory
        fields = '__all__'

class ProductImageSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductImage
        fields = '__all__'

class ProductSerializer(serializers.ModelSerializer):
    product_images = ProductImageSerializer(many=True)
    class Meta:
        model = Product
        fields = '__all__'

    def create(self, validated_data):
        images_data = validated_data.pop('product_images', [])
        product = Product.objects.create(**validated_data)
        for idx, image_data in images_data:
            ProductImage.objects.create(
                product=product, 
                is_main=(idx == 0),
                **image_data
            )

        return product
    
    def update(self, instance, validated_data):
        images_data = validated_data.pop('product_images', [])
        instance.name = validated_data.get('name', instance.name)
        instance.description = validated_data.get('description', instance.description)
        instance.price = validated_data.get('price', instance.price)
        instance.stock = validated_data.get('stock', instance.stock)
        instance.category = validated_data.get('category', instance.category)
        instance.save()

        # Clear old images and recreate
        instance.product_images.all().delete()
        for idx, image_data in enumerate(images_data):
            ProductImage.objects.create(
                product=instance, 
                is_main=(idx == 0),
                **image_data
                )

        return instance

# from rest_framework import serializers
# from .models import Product, ProductCategory, ProductImage

# class ProductCategorySerializer(serializers.ModelSerializer):
#     class Meta:
#         model = ProductCategory
#         fields = '__all__'

# class ProductImageSerializer(serializers.ModelSerializer):
#     class Meta:
#         model = ProductImage
#         fields = '__all__'

# class ProductSerializer(serializers.ModelSerializer):
#     # read-only nested images for responses
#     product_images = ProductImageSerializer(many=True, read_only=True)
#     # write-only list of image files for incoming form-data
#     product_images_files = serializers.ListField(
#         child=serializers.ImageField(allow_empty_file=False, use_url=False),
#         write_only=True,
#         required=False
#     )
#     class Meta:
#         model = Product
#         fields = '__all__'

#     def create(self, validated_data):
#         images_data = validated_data.pop('product_images_files', [])
#         product = Product.objects.create(**validated_data)
#         for idx, image_data in enumerate(images_data):
#             ProductImage.objects.create(
#                 product=product, 
#                 is_main=(idx == 0),
#                 **image_data
#             )

#         return product
    
#     def update(self, instance, validated_data):
#         images = validated_data.pop('product_images_files', None)

#         # Update simple fields generically
#         for attr, value in validated_data.items():
#             setattr(instance, attr, value)
#         instance.save()

#         # If client sent new files, replace images
#         if images is not None:
#             instance.product_images.all().delete()
#             for idx, image in enumerate(images):
#                 ProductImage.objects.create(
#                     product=instance,
#                     image=image,
#                     is_main=(idx == 0)
#                 )

#         return instance

# serializers.py
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
    # read-only nested images for responses (no source argument)
    product_images = ProductImageSerializer(many=True, read_only=True, source='images')
    main_image = serializers.SerializerMethodField(read_only=True)

    # write-only list of uploaded image files for incoming form-data
    product_images_files = serializers.ListField(
        child=serializers.ImageField(allow_empty_file=False, use_url=False),
        write_only=True,
        required=False
    )

    class Meta:
        model = Product
        fields = '__all__'

    def get_main_image(self, obj):
        """
        Return the main image serialized. Id none is marked is_main=True
        fallback to the first image.Return None if no images.
        """

        # try to get the one fladded as main
        main = obj.images.filter(is_main=True).first()
        if not main:
            main = obj.images.first()
        if not main:
            return None
        
        # provide full serialized representation.(ensures image URL uses request in context)
        return ProductImageSerializer(main, context=self.context).data

    def create(self, validated_data):
        images = validated_data.pop('product_images_files', [])
        product = Product.objects.create(**validated_data)

        # images are UploadedFile objects — create ProductImage with image=image
        for idx, image in enumerate(images):
            ProductImage.objects.create(
                product=product,
                image=image,
                is_main=(idx == 0)
            )
        return product

    def update(self, instance, validated_data):
        images = validated_data.pop('product_images_files', None)

        # update model fields (skip product_images_files)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        if images is not None:
            # replace existing images
            ProductImage.objects.filter(product=instance).delete()
            # instance.product_images.all().delete()
            for idx, image in enumerate(images):
                ProductImage.objects.create(
                    product=instance,
                    image=image,
                    is_main=(idx == 0)
                )
        return instance

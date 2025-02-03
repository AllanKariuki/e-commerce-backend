from django.shortcuts import render
from rest_framework import viewsets, status
from rest_framework.response import Response
from .models import Product, ProductCategory
from .serializers import ProductSerializer, ProductCategorySerializer


class ProductCategoryViewSet(viewsets.ModelViewSet):
    queryset = ProductCategory.objects.all()
    serializer_class = ProductCategorySerializer

    def create(self, request):
        try :
            serializer = self.get_serializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            serializer.save()
            return Response({
                'detail': 'Product Category created successfully',
                'data': serializer.data,
            })
        except ProductCategory.AlreadyExists:
            return Response({
                'detail': 'Product Category already exists',
            }, status=status.HTTP_400_BAD_REQUEST)
    
    def list(self, request):
        queryset = self.get_queryset()
        serializer = self.get_serializer(queryset, many=True)
        return Response({'detail': serializer.data}, status = status.HTTP_200_OK) 
    
    def retrieve(self, request, pk=None):
        try:
            queryset = self.get_queryset()
            product_category = queryset.get(pk=pk)
            serializer = self.get_serializer(product_category)
            return Response({'detail': serializer.data}, status = status.HTTP_200_OK)
        except ProductCategory.DoesNotExist:
            return Response({'detail': 'Product Category not found'}, status=status.HTTP_404_NOT_FOUND)

    def update(self, request, pk=None):
        try:
            queryset = self.get_queryset()
            product_category = queryset.get(pk=pk)
            serializer = self.get_serializer(product_category, data=request.data, partial=True)
            serializer.is_valid(raise_exception=True)
            serializer.save()
            return Response({
                'detail': 'Product Category updated successfully',
                'data': serializer.data,
            })
        except ProductCategory.DoesNotExist:
            return Response({'detail': 'Product Category not found'}, status=status.HTTP_404_NOT_FOUND)

    def destroy(self, request, pk=None):
        try:
            queryset = self.get_queryset()
            product_category = queryset.get(pk=pk).delete()
            return Response({'detail': 'Product Category deleted successfully'}, status=status.HTTP_204_NO_CONTENT)
        except ProductCategory.DoesNotExist:
            return Response({'detail': 'Product Category not found'}, status=status.HTTP_404_NOT_FOUND)
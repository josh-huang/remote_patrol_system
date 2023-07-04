from django.shortcuts import render
from rest_framework import generics
from rest_framework.views import APIView
from rest_framework.response import Response
from .serializers import RoomSerializers
from .models import Room

# Create your views here.
class RoomView(generics.CreateAPIView):
    def get(self, request):
        queryset = Room.objects.all()
        serializer_class = RoomSerializers
        
class

from django.urls import path
from . import views

urlpatterns = [
    # Account API
    path('registerAccount/', views.registerAccount, name='registerAccount'),
    path('loginAccount/', views.loginAccount, name='loginAccount'),

    # Pocket API
    path('getPocketList/', views.getPocketList, name='getPocketList'),
    path('newPocket/', views.newPocket, name='newPocket'),
    path('editPocket/', views.editPocket, name='editPocket'),
    path('removePocket/', views.removePocket, name='removePocket'),

    # Restaurant API
    path('getRestaurantList/', views.getRestaurantList, name='getRestaurantList'),
    path('newRestaurant/', views.newRestaurant, name='newRestaurant'),
    path('editRestaurant/', views.editRestaurant, name='editRestaurant'),
    path('removeRestaurant/', views.removeRestaurant, name='removeRestaurant'),

    # VisitRecord API
    path('getVisitRecords/', views.getVisitRecords, name='getVisitRecords'),
    path('newVisit/', views.newVisit, name='newVisit'),
    path('editVisitRecord/', views.editVisitRecord, name='editVisitRecord'),
    path('removeVisitRecord/', views.removeVisitRecord, name='removeVisitRecord'),
]

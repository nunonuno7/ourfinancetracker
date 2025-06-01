from django.urls import path
from . import views

urlpatterns = [
    path('', views.lista_transacoes, name='lista_transacoes'),
    path('nova/', views.nova_transacao, name='nova_transacao'),
]

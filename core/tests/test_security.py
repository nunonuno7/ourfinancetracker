import pytest
from django.test import TestCase, Client
from django.contrib.auth.models import User
from django.core.cache import cache
from core.views import _cache_key
from datetime import date

class SecurityTestCase(TestCase):
    def setUp(self):
        self.user1 = User.objects.create_user('user1', 'user1@test.com', 'pass123')
        self.user2 = User.objects.create_user('user2', 'user2@test.com', 'pass123')
        self.client = Client()

    def test_cache_key_isolation(self):
        """Verificar que utilizadores têm cache keys diferentes"""
        start_date = date(2025, 1, 1)
        end_date = date(2025, 1, 31)
        
        key1 = _cache_key(self.user1.id, start_date, end_date)
        key2 = _cache_key(self.user2.id, start_date, end_date)
        
        self.assertNotEqual(key1, key2)
        self.assertIn(str(self.user1.id), key1)
        self.assertIn(str(self.user2.id), key2)

    def test_user_data_isolation(self):
        """Verificar que utilizadores não acedem a dados de outros"""
        self.client.login(username='user1', password='pass123')
        
        # Tentar aceder a dados de outro utilizador deve falhar
        response = self.client.get('/api/transactions/')
        self.assertEqual(response.status_code, 200)
        
        # Verificar que só vê os seus dados
        # Adicionar lógica específica baseada na tua API

    def test_csrf_protection(self):
        """Verificar proteção CSRF em operações POST"""
        response = self.client.post('/transactions/create/', {
            'description': 'Teste',
            'amount': 100
        })
        # Deve falhar sem CSRF token
        self.assertEqual(response.status_code, 403)

from django.test import TestCase
from django.contrib.auth.models import User
from rest_framework.test import APIClient

class AuthenticationTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(username='testuser', password='password123')

    def test_user_registration(self):
        response = self.client.post('/api/auth/register/', {
            'username': 'newuser',
            'email': 'new@example.com',
            'password': 'password123'
        })
        self.assertEqual(response.status_code, 201)
        self.assertTrue(User.objects.filter(username='newuser').exists())

    def test_user_login(self):
        response = self.client.post('/api/auth/login/', {
            'username': 'testuser',
            'password': 'password123'
        })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['status'], 'success')

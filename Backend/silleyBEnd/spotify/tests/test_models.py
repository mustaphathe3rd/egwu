from django.test import TestCase
from django.utils import timezone
from datetime import timedelta
from spotify.models import SpotifyToken, User

class SpotifyTokenTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123',
            display_name='Test User'
        )
        
        self.token = SpotifyToken.objects.create(
            user=self.user,
            access_token='test_token',
            refresh_token='refresh_token',
            expires_at=timezone.now() + timedelta(hours=1)
        )

    def test_token_creation(self):
        """Test token is created correctly"""
        self.assertEqual(self.token.user, self.user)
        self.assertEqual(self.token.access_token, 'test_token')

    def test_is_expired_with_future_date(self):
        """Test token not expired when expiry is in future"""
        self.assertFalse(self.token.is_expired())

    def test_is_expired_with_past_date(self):
        """Test token expired when expiry is in past"""
        self.token.expires_at = timezone.now() - timedelta(minutes=10)
        self.token.save()
        self.assertTrue(self.token.is_expired())

    def test_is_expired_with_buffer(self):
        """Test token expiry with buffer time"""
        self.token.expires_at = timezone.now() + timedelta(minutes=3)
        self.token.save()
        self.assertTrue(self.token.is_expired(buffer_time=300))
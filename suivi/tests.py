#from django.test import TestCase
from django.conf import settings
from django.test import SimpleTestCase


class ConfigurationSmokeTests(SimpleTestCase):
    def test_secret_key_is_configured(self):
        self.assertTrue(settings.SECRET_KEY)

    def test_secret_key_is_not_the_old_default(self):
        self.assertFalse(settings.SECRET_KEY.startswith("django-insecure"))
# Create your tests here.

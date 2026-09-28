from django.conf import settings
from django.contrib import messages
from django.contrib.auth.views import LoginView
from django.core.cache import cache
from django.http import HttpResponseForbidden


class SecureHeadersMiddleware:
    """Add conservative browser security headers without breaking local Chart.js/Bootstrap CDNs."""
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        response.setdefault('Referrer-Policy', 'strict-origin-when-cross-origin')
        response.setdefault('Permissions-Policy', 'camera=(), microphone=(), geolocation=()')
        response.setdefault('Cross-Origin-Opener-Policy', 'same-origin')
        return response


class ThrottledLoginView(LoginView):
    template_name = 'asset_mgmt/login.html'
    MAX_ATTEMPTS = 8
    WINDOW_SECONDS = 15 * 60

    def _key(self):
        # REMOTE_ADDR cannot be user-spoofed through an arbitrary X-Forwarded-For header.
        ip = self.request.META.get('REMOTE_ADDR', 'unknown')
        username = self.request.POST.get('username', '').strip().lower()
        return f'login-attempt:{ip}:{username}'

    def dispatch(self, request, *args, **kwargs):
        if request.method == 'POST' and cache.get(self._key(), 0) >= self.MAX_ATTEMPTS:
            return HttpResponseForbidden('Too many failed login attempts. Try again after 15 minutes.')
        return super().dispatch(request, *args, **kwargs)

    def form_invalid(self, form):
        key = self._key()
        attempts = cache.get(key, 0) + 1
        cache.set(key, attempts, self.WINDOW_SECONDS)
        messages.error(self.request, 'Invalid login credentials.')
        return super().form_invalid(form)

    def form_valid(self, form):
        cache.delete(self._key())
        return super().form_valid(form)

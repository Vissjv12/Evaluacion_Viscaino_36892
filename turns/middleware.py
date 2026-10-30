class SecurityHeadersMiddleware:
    """Small, explicit security-header layer for the prototype."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        response["Content-Security-Policy"] = (
            "default-src 'self'; style-src 'self'; "
            "img-src 'self' data:; script-src 'self'; frame-ancestors 'none'; "
            "base-uri 'self'; form-action 'self'"
        )
        response["X-Content-Type-Options"] = "nosniff"
        response["Referrer-Policy"] = "same-origin"
        response["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        response["X-Frame-Options"] = "DENY"
        if request.user.is_authenticated:
            response["Cache-Control"] = "no-store"
        return response

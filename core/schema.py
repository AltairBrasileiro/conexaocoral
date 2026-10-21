"""Extensões do drf-spectacular para a documentação OpenAPI."""
from drf_spectacular.contrib.rest_framework_simplejwt import SimpleJWTScheme


class WhitelistJWTScheme(SimpleJWTScheme):
    """Documenta ``WhitelistJWTAuthentication`` como esquema Bearer JWT."""

    target_class = "core.authentication.whitelist_jwt.WhitelistJWTAuthentication"
    name = "jwtAuth"

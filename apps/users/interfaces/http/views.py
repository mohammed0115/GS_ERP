"""
Authentication and user-profile HTTP endpoints.

Thin adapters around `django.contrib.auth` and `rest_framework_simplejwt`.
Business rules that go beyond "is this user active and are the credentials
correct" belong in `apps.users.application.use_cases`.
"""
from __future__ import annotations

from django.contrib.auth import authenticate
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import RefreshToken

from apps.users.domain.exceptions import (
    InvalidCredentialsError,
    UserInactiveError,
)
from apps.users.infrastructure.models import User
from apps.users.interfaces.http.serializers import (
    LoginSerializer,
    MeSerializer,
    RefreshSerializer,
    TokenPairSerializer,
)


def _issue_tokens(user: User) -> dict[str, str]:
    refresh = RefreshToken.for_user(user)
    return {"refresh": str(refresh), "access": str(refresh.access_token)}


class LoginView(APIView):
    permission_classes = (AllowAny,)

    def post(self, request: Request) -> Response:
        payload = LoginSerializer(data=request.data)
        payload.is_valid(raise_exception=True)

        user = authenticate(
            request,
            username=payload.validated_data["email"],
            password=payload.validated_data["password"],
        )
        if user is None:
            raise InvalidCredentialsError()
        if not user.is_active:
            raise UserInactiveError()

        tokens = _issue_tokens(user)
        return Response(TokenPairSerializer(tokens).data, status=status.HTTP_200_OK)


class RefreshView(APIView):
    permission_classes = (AllowAny,)

    def post(self, request: Request) -> Response:
        payload = RefreshSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        try:
            refresh = RefreshToken(payload.validated_data["refresh"])
        except TokenError as exc:
            raise InvalidCredentialsError(message=str(exc)) from exc
        return Response(
            {"access": str(refresh.access_token), "refresh": str(refresh)},
            status=status.HTTP_200_OK,
        )


class LogoutView(APIView):
    permission_classes = (IsAuthenticated,)

    def post(self, request: Request) -> Response:
        payload = RefreshSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        try:
            token = RefreshToken(payload.validated_data["refresh"])
            token.blacklist()
        except (TokenError, AttributeError):
            # AttributeError if blacklist app is not installed; fail gracefully.
            pass
        return Response(status=status.HTTP_204_NO_CONTENT)


class MeView(APIView):
    permission_classes = (IsAuthenticated,)

    def get(self, request: Request) -> Response:
        user = (
            User.objects
            .prefetch_related("memberships__organization", "memberships__branch")
            .get(pk=request.user.pk)
        )
        return Response(MeSerializer(user).data)

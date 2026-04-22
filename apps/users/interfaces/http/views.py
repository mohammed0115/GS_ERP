"""
Authentication and user-profile HTTP endpoints.

Thin adapters around `django.contrib.auth` and `rest_framework_simplejwt`.
Business rules that go beyond "is this user active and are the credentials
correct" belong in `apps.users.application.use_cases`.
"""
from __future__ import annotations

from django.conf import settings
from django.contrib.auth import authenticate
from django.core.mail import send_mail
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
from apps.users.infrastructure.models import OTPCode, User
from apps.users.interfaces.http.serializers import (
    LoginSerializer,
    MeSerializer,
    OTPVerifySerializer,
    RefreshSerializer,
    TokenPairSerializer,
)


def _issue_tokens(user: User) -> dict[str, str]:
    refresh = RefreshToken.for_user(user)
    return {"refresh": str(refresh), "access": str(refresh.access_token)}


def _send_otp_email(user: User, code: str) -> None:
    send_mail(
        subject="Your GS ERP verification code",
        message=(
            f"Hello {user.first_name or user.email},\n\n"
            f"Your one-time verification code is:\n\n"
            f"  {code}\n\n"
            f"This code expires in {settings.OTP_EXPIRY_MINUTES} minutes.\n"
            f"If you did not request this, please ignore this email.\n\n"
            f"— GS ERP"
        ),
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[user.email],
        fail_silently=False,
    )


class LoginView(APIView):
    """Step 1: validate credentials and send OTP."""

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

        otp = OTPCode.generate_for(user, expiry_minutes=settings.OTP_EXPIRY_MINUTES)
        _send_otp_email(user, otp.code)

        return Response(
            {"detail": "OTP sent to your email.", "email": user.email},
            status=status.HTTP_202_ACCEPTED,
        )


class OTPVerifyView(APIView):
    """Step 2: verify OTP and issue JWT tokens."""

    permission_classes = (AllowAny,)

    def post(self, request: Request) -> Response:
        payload = OTPVerifySerializer(data=request.data)
        payload.is_valid(raise_exception=True)

        email = payload.validated_data["email"]
        code = payload.validated_data["code"]

        try:
            user = User.objects.get(email=email, is_active=True)
        except User.DoesNotExist:
            raise InvalidCredentialsError()

        otp = (
            OTPCode.objects
            .filter(user=user, is_used=False)
            .order_by("-created_at")
            .first()
        )

        if not otp or not otp.is_valid() or otp.code != code:
            raise InvalidCredentialsError(message="Invalid or expired OTP.")

        otp.consume()
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

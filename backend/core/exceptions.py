"""Uniform error format: {"detail": "...", "errors": {...}}."""
from django.core.exceptions import PermissionDenied as DjangoPermissionDenied
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db.models import ProtectedError
from rest_framework import exceptions, status
from rest_framework.response import Response
from rest_framework.views import exception_handler as drf_exception_handler


class BusinessRuleError(exceptions.APIException):
    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = "The request breaks a business rule."
    default_code = "business_rule"


def exception_handler(exc, context):
    if isinstance(exc, DjangoValidationError):
        exc = exceptions.ValidationError(getattr(exc, "message_dict", None) or exc.messages)
    elif isinstance(exc, DjangoPermissionDenied):
        exc = exceptions.PermissionDenied(str(exc) or None)
    elif isinstance(exc, ProtectedError):
        return Response(
            {"detail": "This record is in use by other records and cannot be deleted.", "errors": {}},
            status=status.HTTP_409_CONFLICT,
        )

    response = drf_exception_handler(exc, context)
    if response is None:
        return None

    data = response.data
    if isinstance(exc, exceptions.ValidationError):
        if isinstance(data, dict):
            detail = data.pop("detail", None) if "detail" in data else None
            non_field = data.get("non_field_errors")
            if not detail:
                detail = non_field[0] if non_field else "Please correct the highlighted fields."
            response.data = {"detail": str(detail), "errors": data}
        else:
            response.data = {"detail": str(data[0]) if data else "Invalid input.", "errors": {"non_field_errors": data}}
    else:
        detail = data.get("detail") if isinstance(data, dict) else data
        response.data = {"detail": str(detail), "errors": {}}
    return response

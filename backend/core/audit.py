"""Helpers for writing the immutable audit trail."""
import datetime
import decimal
import uuid

from django.db import models

from .models import AuditLog


def _json_value(value):
    if isinstance(value, (decimal.Decimal, uuid.UUID)):
        return str(value)
    if isinstance(value, (datetime.date, datetime.datetime)):
        return value.isoformat()
    if isinstance(value, models.fields.files.FieldFile):
        return value.name or None
    return value


def snapshot(instance):
    """Plain dict of concrete field values (FKs as ids)."""
    data = {}
    for field in instance._meta.concrete_fields:
        if field.name in ("password",):
            continue
        data[field.attname] = _json_value(getattr(instance, field.attname))
    return data


def diff(old, new):
    keys = set(old) | set(new)
    return {
        k: {"old": old.get(k), "new": new.get(k)}
        for k in sorted(keys)
        if old.get(k) != new.get(k) and k not in ("updated_at",)
    }


def log(user, action, instance, changes=None, note=""):
    return AuditLog.objects.create(
        entity_type=instance._meta.label_lower,
        entity_id=str(instance.pk),
        entity_repr=str(instance)[:200],
        action=action,
        user=user if user and user.is_authenticated else None,
        changes=changes or {},
        note=note[:300],
    )


def log_create(user, instance, note=""):
    return log(user, AuditLog.Action.CREATE, instance, {"new": snapshot(instance)}, note)


def log_update(user, instance, old_snapshot, note=""):
    changes = diff(old_snapshot, snapshot(instance))
    if changes:
        return log(user, AuditLog.Action.UPDATE, instance, changes, note)
    return None


def log_delete(user, instance, note=""):
    return log(user, AuditLog.Action.DELETE, instance, {"old": snapshot(instance)}, note)


class AuditedViewSetMixin:
    """Adds audit logging and created_by/updated_by stamping to model viewsets."""

    def _stamp(self, serializer, creating):
        model = serializer.Meta.model
        names = {f.name for f in model._meta.fields}
        extra = {}
        if creating and "created_by" in names:
            extra["created_by"] = self.request.user
        if "updated_by" in names:
            extra["updated_by"] = self.request.user
        return extra

    def perform_create(self, serializer):
        instance = serializer.save(**self._stamp(serializer, True))
        log_create(self.request.user, instance)

    def perform_update(self, serializer):
        old = snapshot(serializer.instance)
        instance = serializer.save(**self._stamp(serializer, False))
        log_update(self.request.user, instance, old)

    def perform_destroy(self, instance):
        log_delete(self.request.user, instance)
        instance.delete()

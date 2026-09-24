from rest_framework.permissions import SAFE_METHODS, BasePermission

from .models import User

OWNER = User.Role.OWNER
MANAGER = User.Role.MANAGER
ACCOUNTANT = User.Role.ACCOUNTANT
SALESPERSON = User.Role.SALESPERSON
ALL_ROLES = (OWNER, MANAGER, ACCOUNTANT, SALESPERSON)


def has_role(user, *roles):
    return bool(user and user.is_authenticated and user.is_active and user.role in roles)


def roles(*allowed, read=None):
    """Permission class factory.

    roles(OWNER, MANAGER) -> only those roles may do anything.
    roles(OWNER, read=ALL_ROLES) -> everyone may read, only the owner may write.
    """
    read_roles = tuple(read) if read is not None else allowed

    class RolePermission(BasePermission):
        message = "Your role does not allow this action."

        def has_permission(self, request, view):
            if request.method in SAFE_METHODS:
                return has_role(request.user, *read_roles) or has_role(request.user, *allowed)
            return has_role(request.user, *allowed)

    RolePermission.__name__ = f"Roles_{'_'.join(allowed)}"
    return RolePermission


IsOwner = roles(OWNER)
IsOwnerOrManager = roles(OWNER, MANAGER)
IsOwnerOrAccountant = roles(OWNER, ACCOUNTANT)
IsBackOffice = roles(OWNER, MANAGER, ACCOUNTANT)
AnyStaff = roles(*ALL_ROLES)

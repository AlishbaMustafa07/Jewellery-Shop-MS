from django.core.management.base import BaseCommand, CommandError

from cashbook.services import ensure_default_heads
from core.models import ShopSettings, User


class Command(BaseCommand):
    help = "Create shop settings, default heads of account and (optionally) the owner account."

    def add_arguments(self, parser):
        parser.add_argument("--owner", help="Owner username to create")
        parser.add_argument("--password", help="Owner password")
        parser.add_argument("--shop-name", help="Shop name")

    def handle(self, *args, **opts):
        shop = ShopSettings.load()
        if opts.get("shop_name"):
            shop.shop_name = opts["shop_name"]
            shop.save()
        ensure_default_heads()
        self.stdout.write(self.style.SUCCESS("Settings and default heads of account are ready."))
        if opts.get("owner"):
            if not opts.get("password"):
                raise CommandError("--password is required with --owner")
            user, created = User.objects.get_or_create(username=opts["owner"])
            user.role = User.Role.OWNER
            user.is_staff = True
            user.is_superuser = True
            user.set_password(opts["password"])
            user.save()
            self.stdout.write(self.style.SUCCESS(f"Owner '{user.username}' {'created' if created else 'updated'}."))

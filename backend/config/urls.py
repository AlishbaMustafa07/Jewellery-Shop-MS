from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.http import FileResponse, Http404
from django.urls import include, path, re_path
from django.views.static import serve


def spa_index(request, *args, **kwargs):
    """Serve the built React app for any non-API route (client-side routing)."""
    index = settings.FRONTEND_DIST / "index.html"
    if not index.exists():
        raise Http404("Frontend not built. Run `npm run build` in frontend/ or use the Vite dev server.")
    return FileResponse(open(index, "rb"), content_type="text/html")


urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/v1/", include("core.urls")),
    path("api/v1/", include("parties.urls")),
    path("api/v1/", include("stock.urls")),
    path("api/v1/", include("sales.urls")),
    path("api/v1/", include("cashbook.urls")),
    path("api/v1/", include("refining.urls")),
    path("api/v1/", include("investors.urls")),
    path("api/v1/", include("reports.urls")),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

if not settings.DEBUG:
    # static() is a no-op without DEBUG; the shop runs on a LAN, so Django serves uploads itself.
    urlpatterns += [re_path(r"^media/(?P<path>.*)$", serve, {"document_root": settings.MEDIA_ROOT})]

urlpatterns += [
    re_path(r"^assets/(?P<path>.*)$", serve, {"document_root": settings.FRONTEND_DIST / "assets"}),
    re_path(r"^(?P<path>favicon\.svg)$", serve, {"document_root": settings.FRONTEND_DIST}),
    re_path(r"^(?!api/|admin/|media/).*$", spa_index),
]

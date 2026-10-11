from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.http import HttpResponse
from django.views.generic import TemplateView
from django.views.static import serve
from django.views.decorators.csrf import ensure_csrf_cookie


def empty_favicon(request):
    return HttpResponse(status=204)


urlpatterns = [
    path('favicon.ico', empty_favicon, name='favicon'),
    path('admin/', admin.site.urls),
    path('api/auth/', include('backend.accounts.urls')),
    path('api/', include('backend.projects.urls')),
    path('api/', include('backend.pipelines.urls')),
    path('api/', include('backend.processing.urls')),
    path('api/', include('backend.reports.urls')),
    path('api/analytics/', include('backend.analytics.urls')),
    path('', ensure_csrf_cookie(TemplateView.as_view(template_name='index.html')), name='home'),
]

for frontend_page in (
    'index', 'login', 'register', 'dashboard', 'projects', 'project-detail',
    'pipeline-editor', 'history', 'result', 'analytics', 'reports', 'report-detail',
    'api-playground',
):
    urlpatterns.append(path(
        f'{frontend_page}.html',
        ensure_csrf_cookie(TemplateView.as_view(template_name=f'{frontend_page}.html')),
        name=f'frontend-{frontend_page}',
    ))

if settings.DEBUG:
    urlpatterns += [
        path('css/<path:path>', serve, {'document_root': settings.BASE_DIR / 'frontend' / 'css'}),
        path('js/<path:path>', serve, {'document_root': settings.BASE_DIR / 'frontend' / 'js'}),
    ]
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)

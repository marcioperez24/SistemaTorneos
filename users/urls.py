from django.urls import path
from . import views
from . import views_torre

urlpatterns = [
    path('usuarios/', views.gestion_usuarios, name='gestion_usuarios'),
    path('usuarios/crear/', views.crear_usuario, name='crear_usuario'),
    path('usuarios/<int:user_id>/editar/', views.editar_usuario, name='editar_usuario'),
    path('usuarios/<int:user_id>/eliminar/', views.eliminar_usuario, name='eliminar_usuario'),
    path('roles/guardar_permisos/', views.guardar_permisos, name='guardar_permisos'),
    
    # Torre de Control
    path('torre-control/', views_torre.torre_control, name='torre_control'),
    path('torre-control/entrar/<int:org_id>/', views_torre.entrar_org, name='entrar_org'),
]

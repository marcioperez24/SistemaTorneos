from django.urls import path
from django.contrib.auth import views as auth_views
from . import views

urlpatterns = [
    # Auth
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    
    # Dirigente Portal
    path('', views.club_portal, name='club_portal'),
    path('equipo/nuevo/', views.crear_equipo, name='crear_equipo'),
    path('equipo/<int:equipo_id>/editar/', views.editar_equipo, name='editar_equipo'),
    path('equipo/<int:equipo_id>/invitar/', views.generar_invitacion, name='generar_invitacion'),
    
    # Registro de Jugador via Token
    path('invitacion/<uuid:token>/', views.registro_jugador, name='registro_jugador'),
    path('registro/exito/', views.registro_exito, name='registro_exito'),
    
    # Secretaría / Comisión Técnica
    path('secretaria/', views.secretaria_dashboard, name='secretaria_dashboard'),
    path('secretaria/aprobar/<int:ficha_id>/', views.aprobar_jugador, name='aprobar_jugador'),
    path('secretaria/rechazar/<int:ficha_id>/', views.rechazar_jugador, name='rechazar_jugador'),
    
    # Carnet y Verificación Pública (QR)
    path('carnet/<int:ficha_id>/', views.ver_carnet, name='ver_carnet'),
    path('verificar/jugador/<int:ficha_id>/', views.verificar_jugador, name='verificar_jugador'),
    path('ficha/<int:ficha_id>/', views.ver_ficha, name='ver_ficha'),
]


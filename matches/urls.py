from django.urls import path
from . import views

urlpatterns = [
    # Cartelera Pública de Partidos (Calendario)
    path('', views.partidos_lista, name='partidos_lista'),
    
    # Motor de Fixtures (Organizador)
    path('fixture/generar/', views.generar_fixture_view, name='generar_fixture'),
    # Edición manual de partidos (Organizador)
    path('editar/<int:partido_id>/', views.editar_partido, name='editar_partido'),
    
    # Vocalía Digital (Match Day)
    path('vocalia/', views.vocalia_dashboard, name='vocalia_dashboard'),
    path('vocalia/<int:partido_id>/', views.match_day, name='match_day'),
    path('vocalia/<int:partido_id>/evento/nuevo/', views.registrar_evento, name='registrar_evento'),
    path('vocalia/<int:partido_id>/cerrar/', views.cerrar_partido, name='cerrar_partido'),
    
    # Notificación WhatsApp (Mock)
    path('notificar/<int:partido_id>/', views.notificar_whatsapp_mock, name='notificar_whatsapp_mock'),
    
    # Detalle de Partido / Acta de Impresión
    path('partido/<int:partido_id>/', views.detalle_partido, name='detalle_partido'),
    
    # Gestión de Árbitros
    path('arbitros/', views.gestion_arbitros, name='gestion_arbitros'),
    path('arbitros/eliminar/<int:arbitro_id>/', views.eliminar_arbitro, name='eliminar_arbitro'),
    
    # Gestión de Vocales de Mesa
    path('vocales/', views.gestion_vocales, name='gestion_vocales'),
    path('vocales/eliminar/<int:vocal_id>/', views.eliminar_vocal, name='eliminar_vocal'),
    
    # Gestión de Torneos y Ligas
    path('torneos/', views.gestion_torneos, name='gestion_torneos'),
    path('torneos/<int:torneo_id>/', views.detalle_torneo, name='detalle_torneo'),
    path('torneos/eliminar/<int:torneo_id>/', views.eliminar_torneo, name='eliminar_torneo'),
    path('torneos/<int:torneo_id>/generar/', views.generar_fixture_torneo, name='generar_fixture_torneo'),
    path('torneos/<int:torneo_id>/crear-partido/', views.crear_partido_torneo, name='crear_partido_torneo'),
]


from django.urls import path
from . import views, views_grupos, views_fixture_personalizado, views_estadisticas_personalizado, views_eliminatorias_personalizado

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
    path('torneos/<int:torneo_id>/sortear-grupos/', views.sortear_grupos_torneo, name='sortear_grupos_torneo'),
    path('torneos/<int:torneo_id>/generar-eliminatorias/', views.generar_cruces_eliminatorios, name='generar_cruces_eliminatorios'),
    path('torneos/<int:torneo_id>/crear-partido/', views.crear_partido_torneo, name='crear_partido_torneo'),
    path('torneos/<int:torneo_id>/estadisticas/', views.estadisticas_torneo, name='estadisticas_torneo'),
    path('torneos/<int:torneo_id>/imprimir/', views.imprimir_fixture_torneo, name='imprimir_fixture_torneo'),
    
    # Torneo Personalizado por Grupos - Fase 2
    path('torneos/<int:torneo_id>/grupos/', views_grupos.configurar_grupos_torneo, name='configurar_grupos_torneo'),
    path('torneos/<int:torneo_id>/grupos/crear/', views_grupos.crear_grupo_torneo, name='crear_grupo_torneo'),
    path('torneos/<int:torneo_id>/grupos/<int:grupo_id>/editar/', views_grupos.editar_grupo_torneo, name='editar_grupo_torneo'),
    path('torneos/<int:torneo_id>/grupos/<int:grupo_id>/eliminar/', views_grupos.eliminar_grupo_torneo, name='eliminar_grupo_torneo'),
    path('torneos/<int:torneo_id>/grupos/<int:grupo_id>/estado/', views_grupos.cambiar_estado_grupo_torneo, name='cambiar_estado_grupo_torneo'),
    path('torneos/<int:torneo_id>/grupos/<int:grupo_id>/equipos/agregar/', views_grupos.agregar_equipo_grupo, name='agregar_equipo_grupo'),
    path('torneos/<int:torneo_id>/grupos/equipos/<int:asignacion_id>/mover/', views_grupos.mover_equipo_grupo, name='mover_equipo_grupo'),
    path('torneos/<int:torneo_id>/grupos/equipos/<int:asignacion_id>/retirar/', views_grupos.retirar_equipo_grupo, name='retirar_equipo_grupo'),

    # Torneo Personalizado por Grupos - Fase 3 (Fixture & Calendario)
    path('torneos/<int:torneo_id>/fixture/configurar/', views_fixture_personalizado.configurar_generar_fixture, name='configurar_generar_fixture'),
    path('torneos/<int:torneo_id>/fixture/personalizado/', views_fixture_personalizado.ver_fixture_personalizado, name='ver_fixture_personalizado'),
    path('torneos/<int:torneo_id>/fixture/reprogramar/<int:partido_id>/', views_fixture_personalizado.reprogramar_partido_personalizado, name='reprogramar_partido_personalizado'),
    path('torneos/<int:torneo_id>/fixture/imprimir-personalizado/', views_fixture_personalizado.imprimir_fixture_personalizado, name='imprimir_fixture_personalizado'),

    # Torneo Personalizado por Grupos - Fase 4 (Estadísticas, Tablas de Posiciones & Exportaciones)
    path('torneos/<int:torneo_id>/personalizado/estadisticas/', views_estadisticas_personalizado.estadisticas_torneo_personalizado, name='estadisticas_torneo_personalizado'),
    path('torneos/<int:torneo_id>/personalizado/estadisticas/imprimir/', views_estadisticas_personalizado.imprimir_estadisticas_personalizado, name='imprimir_estadisticas_personalizado'),
    path('torneos/<int:torneo_id>/personalizado/estadisticas/excel/', views_estadisticas_personalizado.exportar_excel_estadisticas_personalizado, name='exportar_excel_estadisticas_personalizado'),

    # Torneo Personalizado por Grupos - Fase 5 (Clasificación Definitiva, Sorteo de Bombos & Cuadro Eliminatorio)
    path('torneos/<int:torneo_id>/personalizado/clasificados/confirmar/', views_eliminatorias_personalizado.confirmar_clasificados_view, name='confirmar_clasificados_view'),
    path('torneos/<int:torneo_id>/personalizado/clasificados/reabrir/', views_eliminatorias_personalizado.reabrir_clasificacion_view, name='reabrir_clasificacion_view'),
    path('torneos/<int:torneo_id>/personalizado/empate/<int:grupo_id>/resolver/', views_eliminatorias_personalizado.resolver_empate_view, name='resolver_empate_view'),
    path('torneos/<int:torneo_id>/personalizado/eliminatorias/configurar/', views_eliminatorias_personalizado.configurar_sorteo_eliminatorio_view, name='configurar_sorteo_eliminatorio_view'),
    path('torneos/<int:torneo_id>/personalizado/eliminatorias/vista-previa/', views_eliminatorias_personalizado.vista_previa_sorteo_view, name='vista_previa_sorteo_view'),
    path('torneos/<int:torneo_id>/personalizado/eliminatorias/confirmar-cuadro/', views_eliminatorias_personalizado.confirmar_cuadro_view, name='confirmar_cuadro_view'),
    path('torneos/<int:torneo_id>/personalizado/eliminatorias/cuadro/', views_eliminatorias_personalizado.ver_cuadro_eliminatorio_view, name='ver_cuadro_eliminatorio_view'),
    path('torneos/<int:torneo_id>/personalizado/eliminatorias/imprimir/', views_eliminatorias_personalizado.imprimir_cuadro_eliminatorio_view, name='imprimir_cuadro_eliminatorio_view'),
    path('torneos/<int:torneo_id>/personalizado/eliminatorias/excel/', views_eliminatorias_personalizado.exportar_excel_cuadro_eliminatorio_view, name='exportar_excel_cuadro_eliminatorio_view'),
]




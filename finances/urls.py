from django.urls import path
from . import views

urlpatterns = [
    # Módulo de Tesorería General
    path('resumen/', views.resumen_financiero, name='resumen_financiero'),
    path('inscripcion/<int:pago_id>/modificar-cuota/', views.modificar_cuota_equipo, name='modificar_cuota_equipo'),
    path('inscripcion/<int:pago_id>/pagar/', views.registrar_pago_inscripcion, name='registrar_pago_inscripcion'),
    path('multa/<int:multa_id>/pagar/', views.pagar_multa, name='pagar_multa'),
    path('multa/registrar-manual/', views.registrar_multa_manual, name='registrar_multa_manual'),
    path('egreso/registrar/', views.registrar_egreso, name='registrar_egreso'),
]

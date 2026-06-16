from django.contrib import admin
from .models import PagoInscripcion, MultaTarjeta, MovimientoCaja

@admin.register(PagoInscripcion)
class PagoInscripcionAdmin(admin.ModelAdmin):
    list_display = ('equipo', 'monto', 'estado', 'metodo_pago', 'fecha_pago')
    list_filter = ('estado', 'metodo_pago')
    search_fields = ('equipo__nombre',)

@admin.register(MultaTarjeta)
class MultaTarjetaAdmin(admin.ModelAdmin):
    list_display = ('jugador', 'equipo', 'partido', 'motivo', 'monto', 'estado', 'fecha_pago')
    list_filter = ('estado', 'motivo', 'partido__temporada')
    search_fields = ('jugador__username', 'equipo__nombre')

@admin.register(MovimientoCaja)
class MovimientoCajaAdmin(admin.ModelAdmin):
    list_display = ('tipo', 'monto', 'concepto', 'fecha', 'registrado_por')
    list_filter = ('tipo', 'fecha')
    search_fields = ('concepto',)

from django.contrib import admin
from .models import Partido, EventoPartido

class EventoPartidoInline(admin.TabularInline):
    model = EventoPartido
    extra = 1

@admin.register(Partido)
class PartidoAdmin(admin.ModelAdmin):
    list_display = ('equipo_local', 'equipo_visitante', 'fecha_hora', 'estado', 'goles_local', 'goles_visitante', 'jornada', 'temporada')
    list_filter = ('estado', 'jornada', 'temporada', 'fecha_hora')
    search_fields = ('equipo_local__nombre', 'equipo_visitante__nombre', 'estadio')
    raw_id_fields = ('equipo_local', 'equipo_visitante')
    inlines = [EventoPartidoInline]

@admin.register(EventoPartido)
class EventoPartidoAdmin(admin.ModelAdmin):
    list_display = ('partido', 'tipo', 'minuto', 'jugador', 'equipo')
    list_filter = ('tipo', 'partido__temporada')
    search_fields = ('partido__equipo_local__nombre', 'partido__equipo_visitante__nombre', 'jugador__username')

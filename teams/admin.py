from django.contrib import admin
from .models import Equipo, InvitacionEquipo, FichaJugador

@admin.register(Equipo)
class EquipoAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'categoria', 'dirigente', 'fecha_creacion')
    list_filter = ('categoria', 'fecha_creacion')
    search_fields = ('nombre', 'dirigente__username', 'dirigente__email')

@admin.register(InvitacionEquipo)
class InvitacionEquipoAdmin(admin.ModelAdmin):
    list_display = ('equipo', 'token', 'creado_en', 'expira_en', 'activo')
    list_filter = ('activo', 'expira_en')
    search_fields = ('equipo__nombre',)

@admin.register(FichaJugador)
class FichaJugadorAdmin(admin.ModelAdmin):
    list_display = ('user', 'equipo', 'estado_validacion', 'tipo_sangre', 'firma_digital')
    list_filter = ('estado_validacion', 'firma_digital', 'tipo_sangre')
    search_fields = ('user__username', 'user__first_name', 'user__last_name', 'equipo__nombre')
    raw_id_fields = ('user', 'equipo')

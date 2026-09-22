from django.db import models
from django.conf import settings
from teams.models import Equipo, Categoria

class Torneo(models.Model):
    organizacion = models.ForeignKey('users.Organizacion', on_delete=models.CASCADE, verbose_name="Organización")
    TIPO_CHOICES = (
        ('liga', 'Liga (Todos contra todos por fechas)'),
        ('torneo', 'Torneo (Fase de Grupos + Eliminatorias)'),
        ('personalizado', 'Torneo Personalizado por Grupos (Sectores)'),
    )
    FASE_ELIMINATORIA_CHOICES = (
        ('dieciseisavos', '16vos de Final'),
        ('octavos', 'Octavos de Final'),
        ('cuartos', 'Cuartos de Final'),
        ('semifinal', 'Semifinales'),
    )

    nombre = models.CharField(max_length=100, verbose_name="Nombre del Torneo / Liga")
    tipo = models.CharField(max_length=20, choices=TIPO_CHOICES, default='liga', verbose_name="Tipo de Campeonato")
    categoria = models.ForeignKey(Categoria, on_delete=models.PROTECT, verbose_name="Categoría")
    temporada = models.CharField(max_length=50, default="Temporada 2026", verbose_name="Temporada")
    modalidad = models.CharField(max_length=50, default="Fútbol 11", verbose_name="Modalidad (ej. Fútbol 11, Fútbol 7)")
    max_jugadores_por_equipo = models.IntegerField(default=25, verbose_name="Máximo de Jugadores por Equipo")
    limite_amarillas_suspension = models.IntegerField(default=3, verbose_name="Límite Amarillas para Suspensión")
    costo_amarilla = models.DecimalField(max_digits=10, decimal_places=2, default=50.00, verbose_name="Costo de Tarjeta Amarilla ($)")
    costo_roja = models.DecimalField(max_digits=10, decimal_places=2, default=150.00, verbose_name="Costo de Tarjeta Roja ($)")
    equipos = models.ManyToManyField(Equipo, related_name='torneos', verbose_name="Equipos Participantes")
    
    # Configuración de Fase de Grupos + Eliminatorias
    numero_grupos = models.IntegerField(default=2, verbose_name="Número de Grupos")
    clasificados_por_grupo = models.IntegerField(default=2, verbose_name="Clasificados por Grupo")
    fase_eliminatoria_inicial = models.CharField(max_length=20, choices=FASE_ELIMINATORIA_CHOICES, default='octavos', verbose_name="Fase Eliminatoria Inicial")
    distribucion_grupos = models.JSONField(default=dict, blank=True, null=True, verbose_name="Distribución de Equipos en Grupos")

    # Configuración de Puntuación
    puntos_victoria = models.IntegerField(default=3, verbose_name="Puntos por Victoria")
    puntos_empate = models.IntegerField(default=1, verbose_name="Puntos por Empate")
    puntos_derrota = models.IntegerField(default=0, verbose_name="Puntos por Derrota")

    fecha_creacion = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Torneo / Liga"
        verbose_name_plural = "Torneos y Ligas"
        unique_together = ('organizacion', 'nombre')

    def clean(self):
        from django.core.exceptions import ValidationError
        if self.puntos_victoria is not None and self.puntos_victoria < 0:
            raise ValidationError({'puntos_victoria': "Los puntos por victoria no pueden ser negativos."})
        if self.puntos_empate is not None and self.puntos_empate < 0:
            raise ValidationError({'puntos_empate': "Los puntos por empate no pueden ser negativos."})
        if self.puntos_derrota is not None and self.puntos_derrota < 0:
            raise ValidationError({'puntos_derrota': "Los puntos por derrota no pueden ser negativos."})
        if self.puntos_victoria is not None and self.puntos_empate is not None:
            if self.puntos_victoria < self.puntos_empate:
                raise ValidationError({'puntos_victoria': "Los puntos por victoria deben ser mayores o iguales a los puntos por empate."})

    def __str__(self):
        return f"{self.nombre} - {self.get_tipo_display()} ({self.temporada})"

    def get_categoria_display(self):
        return self.categoria.nombre if self.categoria else ""


class GrupoTorneo(models.Model):
    FORMATO_ENFRENTAMIENTOS_CHOICES = (
        ('una_vuelta', 'Una Vuelta (Solo Ida)'),
        ('ida_vuelta', 'Ida y Vuelta'),
    )

    torneo = models.ForeignKey(Torneo, on_delete=models.CASCADE, related_name='grupos_personalizados', verbose_name="Torneo")
    nombre = models.CharField(max_length=100, verbose_name="Nombre del Grupo")
    sector = models.CharField(max_length=100, blank=True, null=True, verbose_name="Sector / Descripción")
    orden = models.IntegerField(default=1, verbose_name="Orden de Presentación")
    cupos_clasificacion = models.IntegerField(default=4, verbose_name="Cupos de Clasificación")
    formato_enfrentamientos = models.CharField(
        max_length=20, 
        choices=FORMATO_ENFRENTAMIENTOS_CHOICES, 
        default='una_vuelta', 
        verbose_name="Formato de Enfrentamientos"
    )
    activo = models.BooleanField(default=True, verbose_name="Grupo Activo")
    fecha_creacion = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Grupo de Torneo Personalizado"
        verbose_name_plural = "Grupos de Torneo Personalizado"
        unique_together = ('torneo', 'nombre')
        ordering = ['orden', 'id']

    def __str__(self):
        sector_str = f" ({self.sector})" if self.sector else ""
        return f"{self.nombre}{sector_str} - {self.torneo.nombre}"

    def clean(self):
        from django.core.exceptions import ValidationError
        try:
            if self.torneo and self.torneo.tipo != 'personalizado':
                raise ValidationError({'torneo': "Los grupos personalizados solo se pueden crear en torneos de tipo 'personalizado'."})
        except Torneo.DoesNotExist:
            pass
        if self.cupos_clasificacion is not None and self.cupos_clasificacion < 1:
            raise ValidationError({'cupos_clasificacion': "La cantidad de cupos de clasificación debe ser mayor a 0."})

    def save(self, *args, **kwargs):
        if self.nombre:
            self.nombre = self.nombre.strip().upper()
        if self.sector:
            self.sector = self.sector.strip().upper()
        self.full_clean()
        super().save(*args, **kwargs)


class EquipoGrupoTorneo(models.Model):
    torneo = models.ForeignKey(Torneo, on_delete=models.CASCADE, related_name='equipos_grupos_personalizados', verbose_name="Torneo")
    grupo = models.ForeignKey(GrupoTorneo, on_delete=models.CASCADE, related_name='equipos_asignados', verbose_name="Grupo")
    equipo = models.ForeignKey(Equipo, on_delete=models.CASCADE, related_name='grupos_torneo_personalizado', verbose_name="Equipo")
    orden = models.IntegerField(default=0, verbose_name="Orden / Posición de Sorteo")
    fecha_asignacion = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Asignación de Equipo a Grupo"
        verbose_name_plural = "Asignaciones de Equipos a Grupos"
        unique_together = (
            ('torneo', 'equipo'), # Garantiza que un equipo sólo pertenece a un grupo por torneo
            ('grupo', 'equipo'),  # Evita duplicar el mismo equipo en el mismo grupo
        )
        ordering = ['orden', 'id']

    def __str__(self):
        return f"{self.equipo.nombre} -> {self.grupo.nombre} ({self.torneo.nombre})"

    def clean(self):
        from django.core.exceptions import ValidationError
        if self.grupo and self.torneo and self.grupo.torneo != self.torneo:
            raise ValidationError({'grupo': "El grupo seleccionado no pertenece al torneo especificado."})
        if self.equipo and self.torneo:
            if self.equipo.organizacion != self.torneo.organizacion:
                raise ValidationError({'equipo': "El equipo y el torneo deben pertenecer a la misma organización."})
            if self.torneo.categoria and not self.equipo.pertenece_a_categoria(self.torneo.categoria):
                raise ValidationError({'equipo': f"El equipo '{self.equipo.nombre}' no pertenece a la categoría '{self.torneo.categoria.nombre}' del torneo."})

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)


class Partido(models.Model):
    ESTADOS = (
        ('programado', 'Programado'),
        ('en_curso', 'En Curso / Match Day'),
        ('finalizado', 'Finalizado'),
    )
    
    FASE_CHOICES = (
        ('regular', 'Liga / Fecha Regular'),
        ('grupos', 'Fase de Grupos'),
        ('dieciseisavos', '16vos de Final'),
        ('octavos', 'Octavos de Final'),
        ('cuartos', 'Cuartos de Final'),
        ('semifinal', 'Semifinales'),
        ('final', 'Final'),
    )

    organizacion = models.ForeignKey('users.Organizacion', on_delete=models.CASCADE, verbose_name="Organización")
    torneo = models.ForeignKey(Torneo, on_delete=models.CASCADE, related_name='partidos', null=True, blank=True, verbose_name="Torneo / Competencia")
    fase = models.CharField(max_length=20, choices=FASE_CHOICES, default='regular', verbose_name="Fase del Torneo")
    grupo = models.CharField(max_length=50, blank=True, null=True, verbose_name="Grupo (Fase de Grupos)")
    grupo_personalizado = models.ForeignKey(
        'GrupoTorneo',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='partidos',
        verbose_name="Grupo Personalizado"
    )
    numero_vuelta = models.PositiveSmallIntegerField(
        default=1,
        choices=((1, 'Primera Vuelta'), (2, 'Segunda Vuelta')),
        verbose_name="Número de Vuelta"
    )

    equipo_local = models.ForeignKey(Equipo, on_delete=models.CASCADE, related_name='partidos_local', verbose_name="Equipo Local")
    equipo_visitante = models.ForeignKey(Equipo, on_delete=models.CASCADE, related_name='partidos_visitante', verbose_name="Equipo Visitante")
    fecha_hora = models.DateTimeField(verbose_name="Fecha y Hora")
    estadio = models.CharField(max_length=100, default="Estadio Principal", verbose_name="Estadio/Cancha")
    
    # Asignaciones
    vocal = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='partidos_vocalizados',
        verbose_name="Vocal de Campo"
    )
    arbitro = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='partidos_arbitrados',
        verbose_name="Árbitro Principal"
    )
    
    # Marcador y Estado
    goles_local = models.IntegerField(default=0, verbose_name="Goles Local")
    goles_visitante = models.IntegerField(default=0, verbose_name="Goles Visitante")
    estado = models.CharField(max_length=20, choices=ESTADOS, default='programado', verbose_name="Estado del Partido")
    
    # Organización
    jornada = models.IntegerField(default=1, verbose_name="Jornada/Fecha")
    temporada = models.CharField(max_length=50, default="Temporada Apertura 2026", verbose_name="Temporada")

    # Cierre de Acta
    firma_vocal = models.BooleanField(default=False, verbose_name="Firma del Vocal")
    firma_capitan_local = models.BooleanField(default=False, verbose_name="Firma Capitán Local")
    firma_capitan_visitante = models.BooleanField(default=False, verbose_name="Firma Capitán Visitante")

    # Firmas Digitales en Base64
    firma_vocal_img = models.TextField(blank=True, null=True, verbose_name="Firma Digital Vocal (PNG Base64)")
    firma_arbitro_img = models.TextField(blank=True, null=True, verbose_name="Firma Digital Árbitro (PNG Base64)")
    firma_entrenador_local_img = models.TextField(blank=True, null=True, verbose_name="Firma Entrenador Local (PNG Base64)")
    firma_entrenador_visitante_img = models.TextField(blank=True, null=True, verbose_name="Firma Entrenador Visitante (PNG Base64)")

    # Alineaciones en vivo para el control de incidencias y cambios
    alineacion_local = models.JSONField(default=dict, blank=True, null=True, verbose_name="Alineación Local del Partido")
    alineacion_visitante = models.JSONField(default=dict, blank=True, null=True, verbose_name="Alineación Visitante del Partido")

    class Meta:
        verbose_name = "Partido"
        verbose_name_plural = "Partidos"

    def __str__(self):
        return f"J{self.jornada} - {self.equipo_local.nombre} vs {self.equipo_visitante.nombre} ({self.get_estado_display()})"


class EventoPartido(models.Model):
    TIPOS = (
        ('gol', 'Gol'),
        ('asistencia', 'Asistencia'),
        ('amarilla', 'Tarjeta Amarilla'),
        ('roja', 'Tarjeta Roja'),
        ('cambio', 'Cambio de Jugador'),
    )

    partido = models.ForeignKey(Partido, on_delete=models.CASCADE, related_name='eventos')
    tipo = models.CharField(max_length=20, choices=TIPOS, verbose_name="Tipo de Evento")
    minuto = models.IntegerField(verbose_name="Minuto")
    
    # Opcionales según el evento
    jugador = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='eventos_partido',
        verbose_name="Jugador Involucrado"
    )
    equipo = models.ForeignKey(
        Equipo, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        verbose_name="Equipo del Evento"
    )
    detalle = models.CharField(max_length=255, blank=True, null=True, verbose_name="Detalles adicionales")

    class Meta:
        verbose_name = "Evento de Partido"
        verbose_name_plural = "Eventos de Partidos"

    def __str__(self):
        jugador_str = self.jugador.get_full_name() if self.jugador else "N/A"
        return f"{self.partido} - Min {self.minuto}': {self.get_tipo_display()} ({jugador_str})"


class BitacoraTorneo(models.Model):
    organizacion = models.ForeignKey('users.Organizacion', on_delete=models.CASCADE, verbose_name="Organización")
    torneo = models.ForeignKey(Torneo, on_delete=models.CASCADE, related_name='bitacora_logs', verbose_name="Torneo")
    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Usuario Responsable")
    accion = models.CharField(max_length=100, verbose_name="Acción Realizada")
    detalles = models.TextField(blank=True, null=True, verbose_name="Detalles / Motivo")
    valores_anteriores = models.JSONField(default=dict, blank=True, null=True, verbose_name="Valores Anteriores")
    valores_nuevos = models.JSONField(default=dict, blank=True, null=True, verbose_name="Valores Nuevos")
    fecha_hora = models.DateTimeField(auto_now_add=True, verbose_name="Fecha y Hora")

    class Meta:
        verbose_name = "Bitácora de Torneo"
        verbose_name_plural = "Bitácoras de Torneos"
        ordering = ['-fecha_hora']

    def __str__(self):
        return f"[{self.fecha_hora.strftime('%Y-%m-%d %H:%M')}] {self.accion} - {self.torneo.nombre}"


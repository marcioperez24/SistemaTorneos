from django.db import models
from django.conf import settings
from teams.models import Equipo

class Torneo(models.Model):
    TIPO_CHOICES = (
        ('liga', 'Liga (Todos contra todos por fechas)'),
        ('torneo', 'Torneo (Fase de Grupos + Eliminatorias)'),
    )
    nombre = models.CharField(max_length=100, unique=True, verbose_name="Nombre del Torneo / Liga")
    tipo = models.CharField(max_length=20, choices=TIPO_CHOICES, default='liga', verbose_name="Tipo de Campeonato")
    temporada = models.CharField(max_length=50, default="Temporada 2026", verbose_name="Temporada")
    equipos = models.ManyToManyField(Equipo, related_name='torneos', verbose_name="Equipos Participantes")
    fecha_creacion = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Torneo / Liga"
        verbose_name_plural = "Torneos y Ligas"

    def __str__(self):
        return f"{self.nombre} - {self.get_tipo_display()} ({self.temporada})"


class Partido(models.Model):
    ESTADOS = (
        ('programado', 'Programado'),
        ('en_curso', 'En Curso / Match Day'),
        ('finalizado', 'Finalizado'),
    )
    
    FASE_CHOICES = (
        ('regular', 'Liga / Fecha Regular'),
        ('grupos', 'Fase de Grupos'),
        ('octavos', 'Octavos de Final'),
        ('cuartos', 'Cuartos de Final'),
        ('semifinal', 'Semifinales'),
        ('final', 'Final'),
    )

    torneo = models.ForeignKey(Torneo, on_delete=models.CASCADE, related_name='partidos', null=True, blank=True, verbose_name="Torneo / Competencia")
    fase = models.CharField(max_length=20, choices=FASE_CHOICES, default='regular', verbose_name="Fase del Torneo")
    grupo = models.CharField(max_length=50, blank=True, null=True, verbose_name="Grupo (Fase de Grupos)")

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

    class Meta:
        verbose_name = "Partido"
        verbose_name_plural = "Partidos"

    def __str__(self):
        return f"J{self.jornada} - {self.equipo_local.nombre} vs {self.equipo_visitante.nombre} ({self.get_estado_display()})"


class EventoPartido(models.Model):
    TIPOS = (
        ('gol', 'Gol'),
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

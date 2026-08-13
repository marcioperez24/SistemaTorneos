import uuid
from django.db import models
from django.conf import settings
from django.utils import timezone

class Equipo(models.Model):
    CATEGORIAS = (
        ('senior', 'Senior / Libre'),
        ('master', 'Máster (Mayores de 40)'),
        ('supermaster', 'Supermáster (Mayores de 50)'),
        ('juvenil', 'Juvenil (Sub-18)'),
        ('u15', 'Sub-15 (U-15)'),
        ('u12', 'Sub-12 (U-12)'),
        ('femenino', 'Femenino Libre'),
    )
    
    nombre = models.CharField(max_length=100, verbose_name="Nombre del Equipo")
    logo = models.ImageField(upload_to='logos_equipos/', null=True, blank=True, verbose_name="Escudo/Logo")
    categoria = models.CharField(max_length=20, choices=CATEGORIAS, default='senior', verbose_name="Categoría")
    entrenador = models.CharField(max_length=100, blank=True, null=True, verbose_name="Entrenador / DT")
    telefono_entrenador = models.CharField(max_length=20, blank=True, null=True, verbose_name="Teléfono del Entrenador")
    alineacion = models.JSONField(default=dict, blank=True, null=True, verbose_name="Alineación Táctica")
    dirigente = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.CASCADE, 
        related_name='equipos_dirigidos',
        verbose_name="Dirigente / Representante"
    )
    max_jugadores = models.IntegerField(default=25, verbose_name="Máximo de Jugadores")
    fecha_creacion = models.DateTimeField(auto_now_add=True)
 
    class Meta:
        verbose_name = "Equipo"
        verbose_name_plural = "Equipos"
        unique_together = ('nombre', 'categoria')

    def __str__(self):
        return f"{self.nombre} ({self.get_categoria_display()})"

    def get_dt(self):
        if not hasattr(self, '_cached_dt'):
            dt = self.cuerpo_tecnico.filter(estado_validacion='aprobado').first()
            if not dt:
                dt = self.cuerpo_tecnico.first()
            self._cached_dt = dt
        return self._cached_dt

    def get_dt_name(self):
        dt = self.get_dt()
        if dt:
            return dt.user.get_full_name() or dt.user.username
        return self.entrenador or "Sin Entrenador"

    def get_dt_telefono(self):
        dt = self.get_dt()
        if dt:
            return dt.user.telefono or ""
        return self.telefono_entrenador or ""


class InvitacionEquipo(models.Model):
    TIPO_CHOICES = (
        ('jugador', 'Jugador'),
        ('dt', 'Director Técnico / Staff'),
    )
    equipo = models.ForeignKey(Equipo, on_delete=models.CASCADE, related_name='invitaciones')
    torneo = models.ForeignKey('matches.Torneo', on_delete=models.CASCADE, related_name='invitaciones', null=True, blank=True)
    token = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    tipo = models.CharField(max_length=20, choices=TIPO_CHOICES, default='jugador', verbose_name="Tipo de Invitado")
    creado_en = models.DateTimeField(auto_now_add=True)
    expira_en = models.DateTimeField()
    activo = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Invitación de Equipo"
        verbose_name_plural = "Invitaciones de Equipos"

    def esta_valida(self):
        return self.activo and timezone.now() < self.expira_en

    def __str__(self):
        status = "Activa" if self.esta_valida() else "Expirada/Inactiva"
        return f"Invitación ({self.get_tipo_display()}) para {self.equipo.nombre} ({status})"


class FichaJugador(models.Model):
    ESTADOS_VALIDACION = (
        ('pendiente', 'Pendiente de Validación'),
        ('aprobado', 'Aprobado (Habilitado)'),
        ('rechazado', 'Rechazado'),
    )

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.CASCADE, 
        related_name='fichas_jugador',
        verbose_name="Usuario Jugador"
    )
    equipo = models.ForeignKey(
        Equipo, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='jugadores',
        verbose_name="Equipo"
    )
    torneo = models.ForeignKey(
        'matches.Torneo',
        on_delete=models.CASCADE,
        related_name='fichas_jugadores',
        verbose_name="Torneo / Liga",
        null=True, 
        blank=True
    )
    
    # Documentos
    foto = models.ImageField(upload_to='jugadores/selfies/', null=True, blank=True, verbose_name="Foto / Selfie Carnet")
    cedula_frontal = models.ImageField(upload_to='jugadores/cedulas/', null=True, blank=True, verbose_name="Cédula Frontal")
    cedula_posterior = models.ImageField(upload_to='jugadores/cedulas/', null=True, blank=True, verbose_name="Cédula Posterior")
    nro_cedula = models.CharField(max_length=20, blank=True, null=True, verbose_name="Número de Cédula")
    numero_camiseta = models.IntegerField(blank=True, null=True, verbose_name="Número de Camiseta")
    
    # Validación (Secretaría / Tinder-like validation)
    estado_validacion = models.CharField(
        max_length=20, 
        choices=ESTADOS_VALIDACION, 
        default='pendiente',
        verbose_name="Estado de Carnet"
    )
    motivo_rechazo = models.TextField(blank=True, null=True, verbose_name="Motivo de Rechazo")
    fecha_aprobacion = models.DateTimeField(blank=True, null=True, verbose_name="Fecha de Aprobación")
    partidos_suspension = models.IntegerField(default=0, verbose_name="Partidos de Suspensión Pendientes")
    aprobado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.SET_NULL, 
        blank=True, 
        null=True, 
        related_name='fichas_aprobadas', 
        verbose_name="Aprobado Por"
    )
    
    # Datos Médicos / Emergencia
    tipo_sangre = models.CharField(max_length=10, blank=True, null=True, verbose_name="Tipo de Sangre")
    contacto_emergencia = models.CharField(max_length=100, blank=True, null=True, verbose_name="Contacto de Emergencia")
    telefono_emergencia = models.CharField(max_length=20, blank=True, null=True, verbose_name="Teléfono de Emergencia")
    
    # Firma / Aceptación
    firma_digital = models.BooleanField(default=False, verbose_name="Aceptación de Responsabilidad y Salud")
    firma_imagen = models.TextField(blank=True, null=True, verbose_name="Firma Dibujada (Base64)")
    fecha_firma = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "Ficha de Jugador"
        verbose_name_plural = "Fichas de Jugadores"
        unique_together = ('user', 'torneo')

    def __str__(self):
        equipo_str = self.equipo.nombre if self.equipo else "Sin Equipo"
        return f"{self.user.get_full_name() or self.user.username} - {equipo_str} ({self.get_estado_validacion_display()})"


class FichaDT(models.Model):
    ESTADOS_VALIDACION = (
        ('pendiente', 'Pendiente de Validación'),
        ('aprobado', 'Aprobado (Habilitado)'),
        ('rechazado', 'Rechazado'),
    )

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.CASCADE, 
        related_name='fichas_dt',
        verbose_name="Usuario DT"
    )
    equipo = models.ForeignKey(
        Equipo, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='cuerpo_tecnico',
        verbose_name="Equipo"
    )
    torneo = models.ForeignKey(
        'matches.Torneo',
        on_delete=models.CASCADE,
        related_name='fichas_dts',
        verbose_name="Torneo / Liga",
        null=True, 
        blank=True
    )
    
    # Documentos e Identificación
    foto = models.ImageField(upload_to='dt/selfies/', null=True, blank=True, verbose_name="Foto / Selfie Carnet")
    cedula_frontal = models.ImageField(upload_to='dt/cedulas/', null=True, blank=True, verbose_name="Cédula Frontal")
    cedula_posterior = models.ImageField(upload_to='dt/cedulas/', null=True, blank=True, verbose_name="Cédula Posterior")
    nro_cedula = models.CharField(max_length=20, blank=True, null=True, verbose_name="Número de Cédula")
    
    # Validación (Secretaría)
    estado_validacion = models.CharField(
        max_length=20, 
        choices=ESTADOS_VALIDACION, 
        default='pendiente',
        verbose_name="Estado de Carnet"
    )
    motivo_rechazo = models.TextField(blank=True, null=True, verbose_name="Motivo de Rechazo")
    fecha_aprobacion = models.DateTimeField(blank=True, null=True, verbose_name="Fecha de Aprobación")
    aprobado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.SET_NULL, 
        blank=True, 
        null=True, 
        related_name='dts_aprobados', 
        verbose_name="Aprobado Por"
    )
    
    # Datos Médicos / Emergencia
    tipo_sangre = models.CharField(max_length=10, blank=True, null=True, verbose_name="Tipo de Sangre")
    contacto_emergencia = models.CharField(max_length=100, blank=True, null=True, verbose_name="Contacto de Emergencia")
    telefono_emergencia = models.CharField(max_length=20, blank=True, null=True, verbose_name="Teléfono de Emergencia")
    
    # Firma / Aceptación
    firma_digital = models.BooleanField(default=False, verbose_name="Aceptación de Responsabilidad y Salud")
    firma_imagen = models.TextField(blank=True, null=True, verbose_name="Firma Dibujada (Base64)")
    fecha_firma = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "Ficha de Director Técnico"
        verbose_name_plural = "Fichas de Directores Técnicos"
        unique_together = ('user', 'torneo')

    def __str__(self):
        equipo_str = self.equipo.nombre if self.equipo else "Sin Equipo"
        return f"{self.user.get_full_name() or self.user.username} - {equipo_str} ({self.get_estado_validacion_display()})"

from decimal import Decimal
from django.db import transaction
from django.db.models.signals import post_save
from django.dispatch import receiver
from matches.models import EventoPartido
from .models import MultaTarjeta

@receiver(post_save, sender=EventoPartido)
def generar_multa_tarjeta(sender, instance, created, **kwargs):
    if created and instance.tipo in ['amarilla', 'roja']:
        partido = instance.partido
        if not partido:
            return

        torneo = partido.torneo
        if instance.tipo == 'amarilla':
            if torneo and torneo.costo_amarilla is not None:
                monto = Decimal(str(torneo.costo_amarilla))
            else:
                monto = Decimal('50.00')
            motivo = 'amarilla'
        else:
            if torneo and torneo.costo_roja is not None:
                monto = Decimal(str(torneo.costo_roja))
            else:
                monto = Decimal('150.00')
            motivo = 'roja'

        jugador = instance.jugador
        equipo = instance.equipo
        if not equipo and jugador:
            fichas = getattr(jugador, 'fichas_jugador', None)
            if fichas:
                f = fichas.filter(torneo=torneo).first() if torneo else fichas.first()
                if f:
                    equipo = f.equipo

        if jugador and equipo:
            with transaction.atomic():
                MultaTarjeta.objects.get_or_create(
                    evento=instance,
                    defaults={
                        'partido': partido,
                        'equipo': equipo,
                        'jugador': jugador,
                        'organizacion': partido.organizacion,
                        'monto': monto,
                        'motivo': motivo,
                        'estado': 'pendiente'
                    }
                )


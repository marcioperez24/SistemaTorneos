from django.db.models.signals import post_save
from django.dispatch import receiver
from matches.models import EventoPartido
from .models import MultaTarjeta, MovimientoCaja

@receiver(post_save, sender=EventoPartido)
def generar_multa_tarjeta(sender, instance, created, **kwargs):
    if created and instance.tipo in ['amarilla', 'roja']:
        # Determinar monto
        monto = 50.00 if instance.tipo == 'amarilla' else 150.00
        motivo = 'amarilla' if instance.tipo == 'amarilla' else 'roja'
        
        # Encontrar el jugador y su equipo
        jugador = instance.jugador
        # Si el evento no tiene equipo registrado pero sí jugador, usamos el equipo de su ficha
        equipo = instance.equipo
        if not equipo and jugador:
            ficha = jugador.ficha_perfil.first()
            if ficha:
                equipo = ficha.equipo
                
        if jugador and equipo:
            # Crear la multa de forma atómica
            MultaTarjeta.objects.get_or_create(
                partido=instance.partido,
                evento=instance,
                equipo=equipo,
                jugador=jugador,
                defaults={
                    'monto': monto,
                    'motivo': motivo,
                    'estado': 'pendiente'
                }
            )

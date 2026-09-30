from django.core.management.base import BaseCommand
from teams.models import FichaJugador, FichaDT, Equipo
from teams.utils import optimizar_imagen
import os

class Command(BaseCommand):
    help = 'Optimiza y comprime imágenes existentes (fotos, cédulas y logos) para acelerar la carga del sistema.'

    def handle(self, *args, **options):
        self.stdout.write("Iniciando optimización de imágenes en el sistema...")
        total_optimizadas = 0

        # 1. Fichas de Jugadores
        fichas_jugador = FichaJugador.objects.all()
        for fj in fichas_jugador:
            modificado = False
            for campo in ['foto', 'cedula_frontal', 'cedula_posterior']:
                field = getattr(fj, campo)
                if field and field.name:
                    try:
                        if os.path.exists(field.path) and os.path.getsize(field.path) > 200 * 1024:
                            if optimizar_imagen(field, max_dimension=1280, quality=80):
                                modificado = True
                                total_optimizadas += 1
                    except Exception as e:
                        pass
            if modificado:
                fj.save(update_fields=['foto', 'cedula_frontal', 'cedula_posterior'])

        # 2. Fichas de DT
        fichas_dt = FichaDT.objects.all()
        for fdt in fichas_dt:
            modificado = False
            for campo in ['foto', 'cedula_frontal', 'cedula_posterior']:
                field = getattr(fdt, campo)
                if field and field.name:
                    try:
                        if os.path.exists(field.path) and os.path.getsize(field.path) > 200 * 1024:
                            if optimizar_imagen(field, max_dimension=1280, quality=80):
                                modificado = True
                                total_optimizadas += 1
                    except Exception as e:
                        pass
            if modificado:
                fdt.save(update_fields=['foto', 'cedula_frontal', 'cedula_posterior'])

        # 3. Logos de Equipos
        equipos = Equipo.objects.all()
        for eq in equipos:
            if eq.logo and eq.logo.name:
                try:
                    if os.path.exists(eq.logo.path) and os.path.getsize(eq.logo.path) > 150 * 1024:
                        if optimizar_imagen(eq.logo, max_dimension=600, quality=85):
                            eq.save(update_fields=['logo'])
                            total_optimizadas += 1
                except Exception as e:
                    pass

        self.stdout.write(self.style.SUCCESS(f"Optimización completada. Se optimizaron {total_optimizadas} imágenes."))

import sys
from django.core.management.base import BaseCommand, CommandError
from django.db.models import Count
from matches.models import (
    Torneo, GrupoTorneo, EquipoGrupoTorneo, Partido,
    ClasificadoTorneo, LlaveEliminatoria, ResultadoFinalTorneo, EventoPartido
)
from finances.models import MultaTarjeta


class Command(BaseCommand):
    help = "Audita la integridad de datos de un torneo personalizado por grupos de forma segura (solo lectura)."

    def add_arguments(self, parser):
        parser.add_argument(
            '--torneo',
            type=int,
            required=True,
            help="ID del torneo personalizado a auditar."
        )

    def handle(self, *args, **options):
        torneo_id = options['torneo']

        try:
            torneo = Torneo.objects.select_related('organizacion').get(id=torneo_id)
        except Torneo.DoesNotExist:
            raise CommandError(f"No existe un torneo con el ID {torneo_id}.")

        self.stdout.write(self.style.MIGRATE_HEADING(f"=== AUDITORÍA DE INTEGRIDAD: {torneo.nombre} (ID: {torneo.id}) ==="))
        self.stdout.write(f"Organización: {torneo.organizacion.nombre} | Tipo: {torneo.tipo}\n")

        errores = []
        advertencias = []
        hallazgos_ok = 0

        # 1. Verificar tipo de torneo
        if torneo.tipo != 'personalizado':
            advertencias.append(f"El torneo ID {torneo_id} no es de tipo 'personalizado' (tipo actual: '{torneo.tipo}').")

        # 2. Verificar equipos asignados a múltiples grupos
        equipos_multiples = EquipoGrupoTorneo.objects.filter(torneo=torneo).values('equipo').annotate(count=Count('grupo')).filter(count__gt=1)
        if equipos_multiples.exists():
            for em in equipos_multiples:
                errores.append(f"El equipo ID {em['equipo']} está asignado a {em['count']} grupos diferentes en el mismo torneo.")
        else:
            hallazgos_ok += 1

        # 3. Verificar objetos con organización incoherente
        grupos_otra_org = GrupoTorneo.objects.filter(torneo=torneo).exclude(torneo__organizacion=torneo.organizacion)
        if grupos_otra_org.exists():
            errores.append(f"Se encontraron {grupos_otra_org.count()} grupos asociados a una organización distinta.")

        partidos_sin_org = Partido.objects.filter(torneo=torneo, organizacion__isnull=True)
        if partidos_sin_org.exists():
            errores.append(f"Se encontraron {partidos_sin_org.count()} partidos sin organización asignada.")

        partidos_otra_org = Partido.objects.filter(torneo=torneo).exclude(organizacion=torneo.organizacion)
        if partidos_otra_org.exists():
            errores.append(f"Se encontraron {partidos_otra_org.count()} partidos con organización distinta a la del torneo.")

        # 4. Verificar partidos de la misma organización
        partidos_equipos_cruzados = Partido.objects.filter(torneo=torneo).exclude(equipo_local__organizacion=torneo.organizacion)
        if partidos_equipos_cruzados.exists():
            advertencias.append(f"Se encontraron {partidos_equipos_cruzados.count()} partidos con equipos locales de otra organización.")

        # 5. Verificar partidos sin grupo ni llave en torneo personalizado
        if torneo.tipo == 'personalizado':
            partidos_huerfanos = Partido.objects.filter(torneo=torneo, grupo_personalizado__isnull=True, fase='grupos')
            if partidos_huerfanos.exists():
                errores.append(f"Se encontraron {partidos_huerfanos.count()} partidos en fase de grupos sin 'grupo_personalizado'.")
            else:
                hallazgos_ok += 1

        # 6. Clasificados definitivos duplicados
        clasificados_dup = ClasificadoTorneo.objects.filter(torneo=torneo).values('equipo').annotate(count=Count('id')).filter(count__gt=1)
        if clasificados_dup.exists():
            for cd in clasificados_dup:
                errores.append(f"El equipo ID {cd['equipo']} posee {cd['count']} registros de clasificación definitiva duplicados.")
        else:
            hallazgos_ok += 1

        # 7. Llaves eliminatorias duplicadas o incoherentes
        llaves_dup = LlaveEliminatoria.objects.filter(torneo=torneo).values('fase', 'numero_llave').annotate(count=Count('id')).filter(count__gt=1)
        if llaves_dup.exists():
            for ld in llaves_dup:
                errores.append(f"Existe duplicidad en la llave eliminatoria fase '{ld['fase']}' número {ld['numero_llave']}.")
        else:
            hallazgos_ok += 1

        # 8. Ganadores de llave inconsistentes
        llaves_finalizadas = LlaveEliminatoria.objects.filter(torneo=torneo, estado='finalizada')
        for ll in llaves_finalizadas:
            if not ll.ganador and not ll.es_bye:
                errores.append(f"La llave #{ll.numero_llave} ({ll.fase}) está marcada como finalizada pero no posee un ganador asignado.")

        # 9. Multas duplicadas por evento
        multas_dup = MultaTarjeta.objects.filter(partido__torneo=torneo, evento__isnull=False).values('evento').annotate(count=Count('id')).filter(count__gt=1)
        if multas_dup.exists():
            errores.append(f"Se encontraron {multas_dup.count()} eventos de tarjetas con multas financieras duplicadas.")
        else:
            hallazgos_ok += 1

        # 10. Resultado Final y Cuadro de Honor
        rf = ResultadoFinalTorneo.objects.filter(torneo=torneo).first()
        if rf:
            if rf.campeon == rf.subcampeon:
                errores.append("El Resultado Final registra al mismo equipo como Campeón y Subcampeón.")
            else:
                hallazgos_ok += 1

        # Impresión del Reporte Final
        self.stdout.write(self.style.SUCCESS(f"✔ Chequeos limpios completados: {hallazgos_ok}"))

        if advertencias:
            self.stdout.write(self.style.WARNING(f"\n[ADVERTENCIAS ({len(advertencias)})]"))
            for adv in advertencias:
                self.stdout.write(self.style.WARNING(f"  • {adv}"))

        if errores:
            self.stdout.write(self.style.ERROR(f"\n[ERRORES CRÍTICOS ENCONTRADOS ({len(errores)})]"))
            for err in errores:
                self.stdout.write(self.style.ERROR(f"  ✖ {err}"))
            self.stdout.write(self.style.ERROR("\nLa auditoría detectó problemas de integridad en los datos del torneo."))
            sys.exit(1)
        else:
            self.stdout.write(self.style.SUCCESS("\n✔ La auditoría no encontró errores críticos de integridad."))

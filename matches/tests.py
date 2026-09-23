from django.test import TestCase
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone
from django.contrib.auth import get_user_model
from django.urls import reverse
from users.models import Organizacion
from teams.models import Categoria, Equipo, FichaJugador
from matches.models import Torneo, GrupoTorneo, EquipoGrupoTorneo, Partido, EventoPartido, BitacoraTorneo

User = get_user_model()


class TorneoPersonalizadoPhase1Tests(TestCase):

    def setUp(self):
        self.user = User.objects.create_user(username="dirigente1", password="password123")
        self.user2 = User.objects.create_user(username="dirigente2", password="password123")

        self.org1 = Organizacion.objects.create(nombre="Org Test 1", codigo="ORGTEST1")
        self.org2 = Organizacion.objects.create(nombre="Org Test 2", codigo="ORGTEST2")

        self.cat1 = Categoria.objects.create(nombre="Máster 40", organizacion=self.org1)
        self.cat2 = Categoria.objects.create(nombre="Libre", organizacion=self.org2)

        self.torneo_pers = Torneo.objects.create(
            nombre="Copa Intersectores",
            categoria=self.cat1,
            organizacion=self.org1,
            tipo='personalizado',
            temporada="2026"
        )
        self.torneo_liga = Torneo.objects.create(
            nombre="Liga Regular",
            categoria=self.cat1,
            organizacion=self.org1,
            tipo='liga',
            temporada="2026"
        )

        self.eq1 = Equipo.objects.create(nombre="Servicios FC", categoria=self.cat1, organizacion=self.org1, dirigente=self.user)
        self.eq2 = Equipo.objects.create(nombre="Comercio FC", categoria=self.cat1, organizacion=self.org1, dirigente=self.user)
        self.eq_org2 = Equipo.objects.create(nombre="Foráneo FC", categoria=self.cat2, organizacion=self.org2, dirigente=self.user2)

    def test_crear_torneo_personalizado(self):
        """Verifica que se puede crear un torneo con tipo personalizado."""
        self.assertEqual(self.torneo_pers.tipo, 'personalizado')

    def test_crear_grupo_torneo_exitoso(self):
        """Verifica la creación válida de un grupo personalizado."""
        grupo_a = GrupoTorneo.objects.create(
            torneo=self.torneo_pers,
            nombre="Grupo A",
            sector="Servicios",
            cupos_clasificacion=4
        )
        grupo_a.full_clean()
        self.assertEqual(grupo_a.nombre, "GRUPO A")
        self.assertEqual(grupo_a.sector, "SERVICIOS")
        self.assertEqual(grupo_a.cupos_clasificacion, 4)

    def test_validacion_grupo_solo_en_torneo_personalizado(self):
        """No debe permitir crear un GrupoTorneo en un torneo tipo 'liga'."""
        grupo_liga = GrupoTorneo(
            torneo=self.torneo_liga,
            nombre="Grupo X",
            sector="General"
        )
        with self.assertRaises(ValidationError):
            grupo_liga.full_clean()

    def test_validacion_cupos_clasificacion_positivos(self):
        """Los cupos de clasificación deben ser al menos 1."""
        grupo_invalido = GrupoTorneo(
            torneo=self.torneo_pers,
            nombre="Grupo Invalido",
            cupos_clasificacion=0
        )
        with self.assertRaises(ValidationError):
            grupo_invalido.full_clean()

    def test_asignacion_equipo_a_grupo_exitoso(self):
        """Asignar un equipo a un grupo de la misma organización y categoría."""
        grupo_a = GrupoTorneo.objects.create(torneo=self.torneo_pers, nombre="Grupo A", sector="Servicios")
        asignacion = EquipoGrupoTorneo.objects.create(
            torneo=self.torneo_pers,
            grupo=grupo_a,
            equipo=self.eq1
        )
        asignacion.full_clean()
        self.assertEqual(asignacion.equipo, self.eq1)
        self.assertEqual(asignacion.grupo, grupo_a)

    def test_impedir_equipo_otra_organizacion(self):
        """No debe permitir asignar un equipo de otra organización al grupo."""
        grupo_a = GrupoTorneo.objects.create(torneo=self.torneo_pers, nombre="Grupo A", sector="Servicios")
        asignacion_invalida = EquipoGrupoTorneo(
            torneo=self.torneo_pers,
            grupo=grupo_a,
            equipo=self.eq_org2
        )
        with self.assertRaises(ValidationError):
            asignacion_invalida.full_clean()

    def test_impedir_equipo_en_dos_grupos_mismo_torneo(self):
        """Un equipo no puede pertenecer a dos grupos dentro del mismo torneo."""
        grupo_a = GrupoTorneo.objects.create(torneo=self.torneo_pers, nombre="Grupo A", sector="Servicios")
        grupo_b = GrupoTorneo.objects.create(torneo=self.torneo_pers, nombre="Grupo B", sector="Comercio")

        EquipoGrupoTorneo.objects.create(torneo=self.torneo_pers, grupo=grupo_a, equipo=self.eq1)

        duplicado = EquipoGrupoTorneo(torneo=self.torneo_pers, grupo=grupo_b, equipo=self.eq1)
        with self.assertRaises(ValidationError):
            duplicado.full_clean()


from django.urls import reverse
from users.models import UsuarioOrganizacion
from matches.models import Partido

class TorneoPersonalizadoPhase2Tests(TestCase):

    def setUp(self):
        self.admin_user = User.objects.create_user(username="admin_comision", password="password123", role="comision")
        self.normal_user = User.objects.create_user(username="normal_user", password="password123", role="jugador")

        self.org1 = Organizacion.objects.create(nombre="Organización A", codigo="ORGA")
        self.org2 = Organizacion.objects.create(nombre="Organización B", codigo="ORGB")

        UsuarioOrganizacion.objects.create(usuario=self.admin_user, organizacion=self.org1)
        UsuarioOrganizacion.objects.create(usuario=self.normal_user, organizacion=self.org1)

        self.cat = Categoria.objects.create(nombre="Máster 40", organizacion=self.org1)
        self.cat_otra = Categoria.objects.create(nombre="Juvenil", organizacion=self.org1)

        self.torneo = Torneo.objects.create(
            nombre="Copa Sectores 2026",
            categoria=self.cat,
            organizacion=self.org1,
            tipo='personalizado',
            temporada="2026"
        )
        self.torneo_liga = Torneo.objects.create(
            nombre="Liga 2026",
            categoria=self.cat,
            organizacion=self.org1,
            tipo='liga',
            temporada="2026"
        )

        # Equipos org1
        self.eq1 = Equipo.objects.create(nombre="Servicios 1", categoria=self.cat, organizacion=self.org1, dirigente=self.admin_user)
        self.eq2 = Equipo.objects.create(nombre="Servicios 2", categoria=self.cat, organizacion=self.org1, dirigente=self.admin_user)
        self.eq3 = Equipo.objects.create(nombre="Comercio 1", categoria=self.cat, organizacion=self.org1, dirigente=self.admin_user)
        self.eq_otra_cat = Equipo.objects.create(nombre="Juveniles FC", categoria=self.cat_otra, organizacion=self.org1, dirigente=self.admin_user)

        # Equipo org2
        self.eq_org2 = Equipo.objects.create(nombre="Foráneo FC", categoria=self.cat, organizacion=self.org2, dirigente=self.admin_user)

    def _login_admin(self):
        self.client.login(username="admin_comision", password="password123")
        session = self.client.session
        session['organizacion_id'] = self.org1.id
        session.save()

    def test_acceso_configurar_grupos_usuario_autorizado(self):
        self._login_admin()
        url = reverse('configurar_grupos_torneo', kwargs={'torneo_id': self.torneo.id})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

    def test_acceso_denegado_usuario_sin_permiso(self):
        self.client.login(username="normal_user", password="password123")
        url = reverse('configurar_grupos_torneo', kwargs={'torneo_id': self.torneo.id})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 302)

    def test_no_se_puede_configurar_torneo_liga_como_personalizado(self):
        self._login_admin()
        url = reverse('configurar_grupos_torneo', kwargs={'torneo_id': self.torneo_liga.id})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 404)

    def test_crear_cuatro_grupos_distintos(self):
        self._login_admin()
        url = reverse('crear_grupo_torneo', kwargs={'torneo_id': self.torneo.id})
        nombres = ["Grupo A", "Grupo B", "Grupo C", "Grupo D"]
        for idx, nom in enumerate(nombres, start=1):
            res = self.client.post(url, {
                'nombre': nom,
                'sector': f"Sector {nom}",
                'orden': idx,
                'cupos_clasificacion': 4,
                'formato_enfrentamientos': 'una_vuelta',
                'activo': 'on'
            })
            self.assertEqual(res.status_code, 302)

        self.assertEqual(GrupoTorneo.objects.filter(torneo=self.torneo).count(), 4)

    def test_no_duplicar_nombre_grupo_mismo_torneo(self):
        self._login_admin()
        url = reverse('crear_grupo_torneo', kwargs={'torneo_id': self.torneo.id})
        self.client.post(url, {'nombre': 'Grupo A', 'cupos_clasificacion': 4, 'orden': 1, 'formato_enfrentamientos': 'una_vuelta'})
        self.client.post(url, {'nombre': 'Grupo A', 'cupos_clasificacion': 4, 'orden': 2, 'formato_enfrentamientos': 'una_vuelta'})
        self.assertEqual(GrupoTorneo.objects.filter(torneo=self.torneo).count(), 1)

    def test_asignar_equipo_disponible(self):
        self._login_admin()
        grupo = GrupoTorneo.objects.create(torneo=self.torneo, nombre="Grupo A")
        url = reverse('agregar_equipo_grupo', kwargs={'torneo_id': self.torneo.id, 'grupo_id': grupo.id})
        res = self.client.post(url, {'equipo_id': self.eq1.id})
        self.assertEqual(res.status_code, 302)
        self.assertTrue(EquipoGrupoTorneo.objects.filter(grupo=grupo, equipo=self.eq1).exists())
        self.assertTrue(self.torneo.equipos.filter(id=self.eq1.id).exists())

    def test_impedir_asignar_equipo_otra_organizacion(self):
        self._login_admin()
        grupo = GrupoTorneo.objects.create(torneo=self.torneo, nombre="Grupo A")
        url = reverse('agregar_equipo_grupo', kwargs={'torneo_id': self.torneo.id, 'grupo_id': grupo.id})
        res = self.client.post(url, {'equipo_id': self.eq_org2.id})
        self.assertEqual(res.status_code, 404)

    def test_mover_equipo_sin_partidos(self):
        self._login_admin()
        g_a = GrupoTorneo.objects.create(torneo=self.torneo, nombre="Grupo A")
        g_b = GrupoTorneo.objects.create(torneo=self.torneo, nombre="Grupo B")
        asig = EquipoGrupoTorneo.objects.create(torneo=self.torneo, grupo=g_a, equipo=self.eq1)

        url = reverse('mover_equipo_grupo', kwargs={'torneo_id': self.torneo.id, 'asignacion_id': asig.id})
        res = self.client.post(url, {'grupo_destino_id': g_b.id})
        self.assertEqual(res.status_code, 302)
        asig.refresh_from_db()
        self.assertEqual(asig.grupo, g_b)

    def test_bloquear_mover_equipo_con_partidos(self):
        from django.utils import timezone
        self._login_admin()
        g_a = GrupoTorneo.objects.create(torneo=self.torneo, nombre="Grupo A")
        g_b = GrupoTorneo.objects.create(torneo=self.torneo, nombre="Grupo B")
        asig = EquipoGrupoTorneo.objects.create(torneo=self.torneo, grupo=g_a, equipo=self.eq1)

        # Crear un partido registrado
        Partido.objects.create(
            torneo=self.torneo,
            organizacion=self.org1,
            equipo_local=self.eq1,
            equipo_visitante=self.eq2,
            jornada=1,
            fecha_hora=timezone.now()
        )

        url = reverse('mover_equipo_grupo', kwargs={'torneo_id': self.torneo.id, 'asignacion_id': asig.id})
        res = self.client.post(url, {'grupo_destino_id': g_b.id})
        self.assertEqual(res.status_code, 302)
        asig.refresh_from_db()
        self.assertEqual(asig.grupo, g_a)  # No cambió de grupo

    def test_retirar_equipo_sin_borrar_equipo(self):
        self._login_admin()
        g_a = GrupoTorneo.objects.create(torneo=self.torneo, nombre="Grupo A")
        asig = EquipoGrupoTorneo.objects.create(torneo=self.torneo, grupo=g_a, equipo=self.eq1)

        url = reverse('retirar_equipo_grupo', kwargs={'torneo_id': self.torneo.id, 'asignacion_id': asig.id})
        res = self.client.post(url)
        self.assertEqual(res.status_code, 302)
        self.assertFalse(EquipoGrupoTorneo.objects.filter(id=asig.id).exists())
        self.assertTrue(Equipo.objects.filter(id=self.eq1.id).exists())

    def test_impedir_eliminar_grupo_con_equipos(self):
        self._login_admin()
        g_a = GrupoTorneo.objects.create(torneo=self.torneo, nombre="Grupo A")
        EquipoGrupoTorneo.objects.create(torneo=self.torneo, grupo=g_a, equipo=self.eq1)

        url = reverse('eliminar_grupo_torneo', kwargs={'torneo_id': self.torneo.id, 'grupo_id': g_a.id})
        res = self.client.post(url)
        self.assertEqual(res.status_code, 302)
        self.assertTrue(GrupoTorneo.objects.filter(id=g_a.id).exists())

    def test_activar_desactivar_grupo(self):
        self._login_admin()
        g_a = GrupoTorneo.objects.create(torneo=self.torneo, nombre="Grupo A", activo=True)
        url = reverse('cambiar_estado_grupo_torneo', kwargs={'torneo_id': self.torneo.id, 'grupo_id': g_a.id})
        self.client.post(url)
        g_a.refresh_from_db()
        self.assertFalse(g_a.activo)

    def test_rechazo_solicitudes_get_en_acciones_post(self):
        self._login_admin()
        g_a = GrupoTorneo.objects.create(torneo=self.torneo, nombre="Grupo A")
        url = reverse('crear_grupo_torneo', kwargs={'torneo_id': self.torneo.id})
        res = self.client.get(url)
        self.assertEqual(res.status_code, 405)  # Method Not Allowed


from matches.services.fixture_personalizado import (
    generar_algoritmo_round_robin,
    generar_fixture_grupo_completo,
    calcular_vista_previa_fixture,
    guardar_fixture_personalizado,
    mover_equipo_y_regenerar_fixtures
)

class TorneoPersonalizadoPhase3Tests(TestCase):

    def setUp(self):
        self.admin_user = User.objects.create_user(username="admin_p3", password="password123", role="comision")
        self.org1 = Organizacion.objects.create(nombre="Org Phase 3", codigo="ORGP3")
        self.org2 = Organizacion.objects.create(nombre="Org Foránea", codigo="ORGP3F")

        UsuarioOrganizacion.objects.create(usuario=self.admin_user, organizacion=self.org1)

        self.cat = Categoria.objects.create(nombre="Senior 35", organizacion=self.org1)
        self.torneo = Torneo.objects.create(
            nombre="Copa Intersectores 2026",
            categoria=self.cat,
            organizacion=self.org1,
            tipo='personalizado',
            temporada="2026"
        )

        # Crear 7 equipos para probar números pares e impares
        self.equipos = [
            Equipo.objects.create(nombre=f"Equipo {i}", categoria=self.cat, organizacion=self.org1, dirigente=self.admin_user)
            for i in range(1, 8)
        ]

    def _login_admin(self):
        self.client.login(username="admin_p3", password="password123")
        session = self.client.session
        session['organizacion_id'] = self.org1.id
        session.save()

    def test_algoritmo_round_robin_par_4_equipos(self):
        eqs = self.equipos[:4]
        rondas = generar_algoritmo_round_robin(eqs)
        self.assertEqual(len(rondas), 3)  # 4 - 1 = 3 rondas
        tot_partidos = sum(len(r['partidos']) for r in rondas)
        self.assertEqual(tot_partidos, 6)  # 4*3/2 = 6 partidos
        for r in rondas:
            self.assertIsNone(r['descanso'])

    def test_algoritmo_round_robin_impar_5_equipos(self):
        eqs = self.equipos[:5]
        rondas = generar_algoritmo_round_robin(eqs)
        self.assertEqual(len(rondas), 5)  # 5 rondas
        tot_partidos = sum(len(r['partidos']) for r in rondas)
        self.assertEqual(tot_partidos, 10)  # 5*4/2 = 10 partidos
        descansos = [r['descanso'] for r in rondas if r['descanso'] is not None]
        self.assertEqual(len(descansos), 5)

    def test_fixture_grupo_completo_ida_vuelta_6_equipos(self):
        eqs = self.equipos[:6]
        grupo = GrupoTorneo.objects.create(torneo=self.torneo, nombre="Grupo X", formato_enfrentamientos='ida_vuelta')
        matches = generar_fixture_grupo_completo(grupo, eqs, formato='ida_vuelta')
        matches_sin_descanso = [m for m in matches if not m['descanso']]
        self.assertEqual(len(matches_sin_descanso), 30)  # 6*5 = 30 partidos
        v1 = [m for m in matches_sin_descanso if m['numero_vuelta'] == 1]
        v2 = [m for m in matches_sin_descanso if m['numero_vuelta'] == 2]
        self.assertEqual(len(v1), 15)
        self.assertEqual(len(v2), 15)

    def test_vista_previa_no_guarda_en_bd(self):
        g_a = GrupoTorneo.objects.create(torneo=self.torneo, nombre="Grupo A")
        EquipoGrupoTorneo.objects.create(torneo=self.torneo, grupo=g_a, equipo=self.equipos[0])
        EquipoGrupoTorneo.objects.create(torneo=self.torneo, grupo=g_a, equipo=self.equipos[1])

        vp = calcular_vista_previa_fixture(self.torneo, self.org1, {})
        self.assertGreater(vp['total_partidos'], 0)
        self.assertEqual(Partido.objects.filter(torneo=self.torneo).count(), 0)

    def test_confirmacion_guarda_partidos_con_atributos_correctos(self):
        g_a = GrupoTorneo.objects.create(torneo=self.torneo, nombre="Grupo A")
        EquipoGrupoTorneo.objects.create(torneo=self.torneo, grupo=g_a, equipo=self.equipos[0])
        EquipoGrupoTorneo.objects.create(torneo=self.torneo, grupo=g_a, equipo=self.equipos[1])

        vp = calcular_vista_previa_fixture(self.torneo, self.org1, {})
        partidos = guardar_fixture_personalizado(self.torneo, self.org1, self.admin_user, vp)
        self.assertGreater(len(partidos), 0)

        p1 = Partido.objects.get(id=partidos[0].id)
        self.assertEqual(p1.organizacion, self.org1)
        self.assertEqual(p1.torneo, self.torneo)
        self.assertEqual(p1.grupo_personalizado, g_a)
        self.assertEqual(p1.grupo, "GRUPO A")
        self.assertEqual(p1.fase, 'grupos')

    def test_no_duplicar_partidos_al_reconfirmar(self):
        g_a = GrupoTorneo.objects.create(torneo=self.torneo, nombre="Grupo A")
        EquipoGrupoTorneo.objects.create(torneo=self.torneo, grupo=g_a, equipo=self.equipos[0])
        EquipoGrupoTorneo.objects.create(torneo=self.torneo, grupo=g_a, equipo=self.equipos[1])

        vp = calcular_vista_previa_fixture(self.torneo, self.org1, {})
        guardar_fixture_personalizado(self.torneo, self.org1, self.admin_user, vp)
        cant_inicial = Partido.objects.filter(torneo=self.torneo).count()

        guardar_fixture_personalizado(self.torneo, self.org1, self.admin_user, vp)
        self.assertEqual(Partido.objects.filter(torneo=self.torneo).count(), cant_inicial)

    def test_bloquear_regeneracion_con_partidos_finalizados(self):
        g_a = GrupoTorneo.objects.create(torneo=self.torneo, nombre="Grupo A")
        EquipoGrupoTorneo.objects.create(torneo=self.torneo, grupo=g_a, equipo=self.equipos[0])
        EquipoGrupoTorneo.objects.create(torneo=self.torneo, grupo=g_a, equipo=self.equipos[1])

        vp = calcular_vista_previa_fixture(self.torneo, self.org1, {})
        guardar_fixture_personalizado(self.torneo, self.org1, self.admin_user, vp)

        p = Partido.objects.filter(torneo=self.torneo).first()
        p.estado = 'finalizado'
        p.save()

        with self.assertRaises(ValidationError):
            guardar_fixture_personalizado(self.torneo, self.org1, self.admin_user, vp)

    def test_reprogramar_partido_conserva_id_y_eventos(self):
        g_a = GrupoTorneo.objects.create(torneo=self.torneo, nombre="Grupo A")
        EquipoGrupoTorneo.objects.create(torneo=self.torneo, grupo=g_a, equipo=self.equipos[0])
        EquipoGrupoTorneo.objects.create(torneo=self.torneo, grupo=g_a, equipo=self.equipos[1])

        p = Partido.objects.create(
            organizacion=self.org1,
            torneo=self.torneo,
            grupo_personalizado=g_a,
            equipo_local=self.equipos[0],
            equipo_visitante=self.equipos[1],
            fecha_hora=timezone.now(),
            jornada=1
        )
        pid = p.id

        self._login_admin()
        url = reverse('reprogramar_partido_personalizado', kwargs={'torneo_id': self.torneo.id, 'partido_id': p.id})
        res = self.client.post(url, {
            'fecha': '2026-10-15',
            'hora': '15:30',
            'estadio': 'Estadio Nuevo',
            'motivo': 'Lluvia intensa'
        })
        self.assertEqual(res.status_code, 302)
        p.refresh_from_db()
        self.assertEqual(p.id, pid)
        self.assertEqual(p.estadio.upper(), 'ESTADIO NUEVO')

    def test_imprimir_fixture_personalizado_render(self):
        g_a = GrupoTorneo.objects.create(torneo=self.torneo, nombre="Grupo A")
        Partido.objects.create(
            organizacion=self.org1,
            torneo=self.torneo,
            grupo_personalizado=g_a,
            equipo_local=self.equipos[0],
            equipo_visitante=self.equipos[1],
            fecha_hora=timezone.now(),
            jornada=1
        )
        self._login_admin()
        url = reverse('imprimir_fixture_personalizado', kwargs={'torneo_id': self.torneo.id})
        res = self.client.get(url)
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, "GRUPO A")


from users.models import Organizacion, UsuarioOrganizacion

class TorneoPersonalizadoPhase4Tests(TestCase):

    def setUp(self):
        self.admin_user = User.objects.create_user(
            username="admin_p4", password="password123", role="superadmin"
        )
        self.user_jugador = User.objects.create_user(
            username="jugador_p4", first_name="Juan", last_name="Pérez", password="password123"
        )
        self.org1 = Organizacion.objects.create(nombre="Org Fase 4", codigo="ORGF4")
        self.org2 = Organizacion.objects.create(nombre="Org Ajena", codigo="ORGAJ")

        UsuarioOrganizacion.objects.create(usuario=self.admin_user, organizacion=self.org1, rol='admin', activo=True)

        self.cat1 = Categoria.objects.create(nombre="Máster 40", organizacion=self.org1)
        self.cat2 = Categoria.objects.create(nombre="Libre", organizacion=self.org2)

        self.torneo = Torneo.objects.create(
            nombre="Copa Personalizada F4",
            categoria=self.cat1,
            organizacion=self.org1,
            tipo='personalizado',
            temporada="2026",
            puntos_victoria=3,
            puntos_empate=1,
            puntos_derrota=0
        )

        self.torneo_ajeno = Torneo.objects.create(
            nombre="Torneo Ajeno",
            categoria=self.cat2,
            organizacion=self.org2,
            tipo='personalizado',
            temporada="2026"
        )

        self.grupo_a = GrupoTorneo.objects.create(
            torneo=self.torneo, nombre="Grupo A", sector="Servicios", cupos_clasificacion=2
        )
        self.grupo_b = GrupoTorneo.objects.create(
            torneo=self.torneo, nombre="Grupo B", sector="Comercio", cupos_clasificacion=1
        )

        self.equipos_a = []
        for i in range(1, 5):
            eq = Equipo.objects.create(
                nombre=f"Equipo A{i}", categoria=self.cat1, organizacion=self.org1, dirigente=self.admin_user
            )
            self.equipos_a.append(eq)
            EquipoGrupoTorneo.objects.create(torneo=self.torneo, grupo=self.grupo_a, equipo=eq, orden=i)

        self.equipos_b = []
        for i in range(1, 4):
            eq = Equipo.objects.create(
                nombre=f"Equipo B{i}", categoria=self.cat1, organizacion=self.org1, dirigente=self.admin_user
            )
            self.equipos_b.append(eq)
            EquipoGrupoTorneo.objects.create(torneo=self.torneo, grupo=self.grupo_b, equipo=eq, orden=i)

        self.ficha_jugador = FichaJugador.objects.create(
            user=self.user_jugador,
            organizacion=self.org1,
            equipo=self.equipos_a[0],
            torneo=self.torneo,
            numero_camiseta=10,
            estado_validacion='aprobado'
        )

    def _login_admin(self):
        session = self.client.session
        session['current_organizacion_id'] = self.org1.id
        session.save()
        self.client.login(username="admin_p4", password="password123")


    def test_tabla_grupo_sin_partidos(self):
        from matches.services.estadisticas_personalizado import calcular_posiciones_grupo
        res = calcular_posiciones_grupo(self.grupo_a, self.torneo, self.org1)
        self.assertEqual(len(res['tabla']), 4)
        for item in res['tabla']:
            self.assertEqual(item['PJ'], 0)
            self.assertEqual(item['PTS'], 0)
            self.assertEqual(item['DG'], 0)
            self.assertEqual(item['rendimiento'], 0.0)

    def test_tabla_grupo_sin_resultados_finalizados(self):
        from matches.services.estadisticas_personalizado import calcular_posiciones_grupo
        Partido.objects.create(
            organizacion=self.org1, torneo=self.torneo, grupo_personalizado=self.grupo_a,
            fase='grupos', equipo_local=self.equipos_a[0], equipo_visitante=self.equipos_a[1],
            fecha_hora=timezone.now(), estado='programado'
        )
        res = calcular_posiciones_grupo(self.grupo_a, self.torneo, self.org1)
        for item in res['tabla']:
            self.assertEqual(item['PJ'], 0)
            self.assertEqual(item['PTS'], 0)

    def test_victoria_local_y_visitante_y_empate(self):
        from matches.services.estadisticas_personalizado import calcular_posiciones_grupo
        # Partido 1: Local A1 (3) vs Visitante A2 (1) -> Victoria Local
        Partido.objects.create(
            organizacion=self.org1, torneo=self.torneo, grupo_personalizado=self.grupo_a,
            fase='grupos', equipo_local=self.equipos_a[0], equipo_visitante=self.equipos_a[1],
            goles_local=3, goles_visitante=1, fecha_hora=timezone.now(), estado='finalizado'
        )
        # Partido 2: Local A3 (0) vs Visitante A4 (2) -> Victoria Visitante
        Partido.objects.create(
            organizacion=self.org1, torneo=self.torneo, grupo_personalizado=self.grupo_a,
            fase='grupos', equipo_local=self.equipos_a[2], equipo_visitante=self.equipos_a[3],
            goles_local=0, goles_visitante=2, fecha_hora=timezone.now(), estado='finalizado'
        )
        # Partido 3: Local A1 (1) vs Visitante A4 (1) -> Empate
        Partido.objects.create(
            organizacion=self.org1, torneo=self.torneo, grupo_personalizado=self.grupo_a,
            fase='grupos', equipo_local=self.equipos_a[0], equipo_visitante=self.equipos_a[3],
            goles_local=1, goles_visitante=1, fecha_hora=timezone.now(), estado='finalizado'
        )

        res = calcular_posiciones_grupo(self.grupo_a, self.torneo, self.org1)
        tabla = {item['equipo_id']: item for item in res['tabla']}

        # A1: 1 vic (3), 1 emp (1) -> 4 pts, GF=4, GC=2, DG=+2
        self.assertEqual(tabla[self.equipos_a[0].id]['PTS'], 4)
        self.assertEqual(tabla[self.equipos_a[0].id]['PJ'], 2)
        self.assertEqual(tabla[self.equipos_a[0].id]['PG'], 1)
        self.assertEqual(tabla[self.equipos_a[0].id]['PE'], 1)
        self.assertEqual(tabla[self.equipos_a[0].id]['GF'], 4)
        self.assertEqual(tabla[self.equipos_a[0].id]['GC'], 2)
        self.assertEqual(tabla[self.equipos_a[0].id]['DG'], 2)

        # A4: 1 vic (3), 1 emp (1) -> 4 pts, GF=3, GC=1, DG=+2
        self.assertEqual(tabla[self.equipos_a[3].id]['PTS'], 4)

        # A2: 1 der (0) -> 0 pts
        self.assertEqual(tabla[self.equipos_a[1].id]['PTS'], 0)

    def test_partido_otro_grupo_torneo_organizacion_no_se_cuenta(self):
        from matches.services.estadisticas_personalizado import calcular_posiciones_grupo
        # Partido en Grupo B
        Partido.objects.create(
            organizacion=self.org1, torneo=self.torneo, grupo_personalizado=self.grupo_b,
            fase='grupos', equipo_local=self.equipos_b[0], equipo_visitante=self.equipos_b[1],
            goles_local=5, goles_visitante=0, fecha_hora=timezone.now(), estado='finalizado'
        )
        # Partido en Org Ajena
        Partido.objects.create(
            organizacion=self.org2, torneo=self.torneo_ajeno,
            equipo_local=self.equipos_a[0], equipo_visitante=self.equipos_a[1],
            goles_local=10, goles_visitante=0, fecha_hora=timezone.now(), estado='finalizado'
        )

        res_a = calcular_posiciones_grupo(self.grupo_a, self.torneo, self.org1)
        for item in res_a['tabla']:
            self.assertEqual(item['PJ'], 0)

    def test_clasificacion_provisional_y_advertencia_cupos(self):
        from matches.services.estadisticas_personalizado import calcular_posiciones_grupo
        Partido.objects.create(
            organizacion=self.org1, torneo=self.torneo, grupo_personalizado=self.grupo_a,
            fase='grupos', equipo_local=self.equipos_a[0], equipo_visitante=self.equipos_a[1],
            goles_local=2, goles_visitante=0, fecha_hora=timezone.now(), estado='finalizado'
        )
        res = calcular_posiciones_grupo(self.grupo_a, self.torneo, self.org1)
        # Cupos es 2 -> los 2 primeros deben ser es_clasificado_provisional=True
        self.assertTrue(res['tabla'][0]['es_clasificado_provisional'])
        self.assertTrue(res['tabla'][1]['es_clasificado_provisional'])
        self.assertFalse(res['tabla'][2]['es_clasificado_provisional'])

        # Probar advertencia cuando cupos > equipos
        self.grupo_b.cupos_clasificacion = 10
        self.grupo_b.save()
        res_b = calcular_posiciones_grupo(self.grupo_b, self.torneo, self.org1)
        self.assertIsNotNone(res_b['advertencia_cupos'])

    def test_desempate_enfrentamiento_directo(self):
        from matches.services.estadisticas_personalizado import calcular_posiciones_grupo
        # A2 vs A3 (2-0), A3 vs A1 (2-0), A1 vs A2 (1-0)
        # A2 y A3 empatan en base PTS=3, DG=+1, GF=2.
        # En enfrentamiento directo A2 le ganó a A3 2-0, por lo que A2 debe ser 1ro y A3 2do.
        Partido.objects.create(
            organizacion=self.org1, torneo=self.torneo, grupo_personalizado=self.grupo_a,
            fase='grupos', equipo_local=self.equipos_a[1], equipo_visitante=self.equipos_a[2],
            goles_local=2, goles_visitante=0, fecha_hora=timezone.now(), estado='finalizado'
        )
        Partido.objects.create(
            organizacion=self.org1, torneo=self.torneo, grupo_personalizado=self.grupo_a,
            fase='grupos', equipo_local=self.equipos_a[2], equipo_visitante=self.equipos_a[0],
            goles_local=2, goles_visitante=0, fecha_hora=timezone.now(), estado='finalizado'
        )
        Partido.objects.create(
            organizacion=self.org1, torneo=self.torneo, grupo_personalizado=self.grupo_a,
            fase='grupos', equipo_local=self.equipos_a[0], equipo_visitante=self.equipos_a[1],
            goles_local=1, goles_visitante=0, fecha_hora=timezone.now(), estado='finalizado'
        )
        res = calcular_posiciones_grupo(self.grupo_a, self.torneo, self.org1)
        # A2 (equipos_a[1]) es 1ro, A3 (equipos_a[2]) es 2do por enfrentamiento directo
        self.assertEqual(res['tabla'][0]['equipo_id'], self.equipos_a[1].id)
        self.assertEqual(res['tabla'][1]['equipo_id'], self.equipos_a[2].id)



    def test_empate_completo_marca_pendiente(self):
        from matches.services.estadisticas_personalizado import calcular_posiciones_grupo
        # A1 vs A2 0-0 sin tarjetas registradas -> Igualdad total
        Partido.objects.create(
            organizacion=self.org1, torneo=self.torneo, grupo_personalizado=self.grupo_a,
            fase='grupos', equipo_local=self.equipos_a[0], equipo_visitante=self.equipos_a[1],
            goles_local=0, goles_visitante=0, fecha_hora=timezone.now(), estado='finalizado'
        )
        res = calcular_posiciones_grupo(self.grupo_a, self.torneo, self.org1)
        # Los dos empatados deben tener empate_pendiente = True
        t_a1 = [item for item in res['tabla'] if item['equipo_id'] == self.equipos_a[0].id][0]
        t_a2 = [item for item in res['tabla'] if item['equipo_id'] == self.equipos_a[1].id][0]
        self.assertTrue(t_a1['empate_pendiente'])
        self.assertTrue(t_a2['empate_pendiente'])

    def test_estadisticas_jugadores_y_eventos(self):
        from matches.services.estadisticas_personalizado import calcular_estadisticas_jugadores_grupo
        p1 = Partido.objects.create(
            organizacion=self.org1, torneo=self.torneo, grupo_personalizado=self.grupo_a,
            fase='grupos', equipo_local=self.equipos_a[0], equipo_visitante=self.equipos_a[1],
            goles_local=2, goles_visitante=0, fecha_hora=timezone.now(), estado='finalizado'
        )
        # Registrar 2 goles, 1 asistencia, 1 amarilla, 1 roja para user_jugador
        EventoPartido.objects.create(partido=p1, tipo='gol', minuto=10, jugador=self.user_jugador, equipo=self.equipos_a[0])
        EventoPartido.objects.create(partido=p1, tipo='gol', minuto=40, jugador=self.user_jugador, equipo=self.equipos_a[0])
        EventoPartido.objects.create(partido=p1, tipo='asistencia', minuto=10, jugador=self.user_jugador, equipo=self.equipos_a[0])
        EventoPartido.objects.create(partido=p1, tipo='amarilla', minuto=55, jugador=self.user_jugador, equipo=self.equipos_a[0])
        EventoPartido.objects.create(partido=p1, tipo='roja', minuto=80, jugador=self.user_jugador, equipo=self.equipos_a[0])

        jug_stats = calcular_estadisticas_jugadores_grupo(self.grupo_a, self.torneo, self.org1)
        self.assertEqual(len(jug_stats['goleadores']), 1)
        self.assertEqual(jug_stats['goleadores'][0]['total'], 2)
        self.assertEqual(jug_stats['asistencias'][0]['total'], 1)
        self.assertEqual(jug_stats['amarillas'][0]['total'], 1)
        self.assertEqual(jug_stats['rojas'][0]['total'], 1)

    def test_vistas_web_y_exportaciones(self):
        self._login_admin()
        url_stats = reverse('estadisticas_torneo_personalizado', kwargs={'torneo_id': self.torneo.id})
        res_stats = self.client.get(url_stats)
        self.assertEqual(res_stats.status_code, 200)
        self.assertContains(res_stats, "COPA PERSONALIZADA F4")

        url_print = reverse('imprimir_estadisticas_personalizado', kwargs={'torneo_id': self.torneo.id})
        res_print = self.client.get(url_print)
        self.assertEqual(res_print.status_code, 200)

        url_excel = reverse('exportar_excel_estadisticas_personalizado', kwargs={'torneo_id': self.torneo.id})
        res_excel = self.client.get(url_excel)
        self.assertEqual(res_excel.status_code, 200)
        self.assertEqual(
            res_excel['Content-Type'],
            'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )

    def test_aislamiento_organizacion_ajena(self):
        # Crear usuario en Org 2
        user_org2 = User.objects.create_user(username="org2_user", password="password123")
        session = self.client.session
        session['organizacion_id'] = self.org2.id
        session.save()
        self.client.login(username="org2_user", password="password123")

        url = reverse('estadisticas_torneo_personalizado', kwargs={'torneo_id': self.torneo.id})
        res = self.client.get(url)
        self.assertEqual(res.status_code, 404)

    def test_sin_generacion_de_eliminatorias_en_fase4(self):
        # Verificar que no hay modelos ni métodos creados que generen cruces de playoffs o llaves en esta fase
        self.assertEqual(Partido.objects.filter(torneo=self.torneo, fase='octavos').count(), 0)
        self.assertEqual(Partido.objects.filter(torneo=self.torneo, fase='cuartos').count(), 0)


from matches.models import ClasificadoTorneo, ResolucionEmpateTorneo, LlaveEliminatoria
from matches.services.sorteo_personalizado import (
    verificar_estado_clasificacion_grupos,
    confirmar_clasificados_definitivos,
    resolver_empate_administrativo,
    reabrir_clasificacion_definitiva,
    generar_sorteo_eliminatorio,
    confirmar_y_crear_cuadro_eliminatorio,
    generar_excel_cuadro_eliminatorio
)


class TorneoPersonalizadoPhase5Tests(TestCase):

    def setUp(self):
        self.admin_user = User.objects.create_user(
            username="admin_p5", password="password123", role="superadmin"
        )
        self.org1 = Organizacion.objects.create(nombre="Org Fase 5", codigo="ORGF5")
        self.org2 = Organizacion.objects.create(nombre="Org Ajena 5", codigo="ORGF5A")

        UsuarioOrganizacion.objects.create(usuario=self.admin_user, organizacion=self.org1, rol='admin', activo=True)

        self.cat1 = Categoria.objects.create(nombre="Senior 40", organizacion=self.org1)

        self.torneo = Torneo.objects.create(
            nombre="Copa Personalizada F5",
            categoria=self.cat1,
            organizacion=self.org1,
            tipo='personalizado',
            temporada="2026",
            puntos_victoria=3,
            puntos_empate=1,
            puntos_derrota=0
        )

        self.grupo_a = GrupoTorneo.objects.create(
            torneo=self.torneo, nombre="Grupo A", sector="Sector 1", cupos_clasificacion=2
        )
        self.grupo_b = GrupoTorneo.objects.create(
            torneo=self.torneo, nombre="Grupo B", sector="Sector 2", cupos_clasificacion=2
        )

        self.equipos_a = []
        for i in range(1, 4):
            eq = Equipo.objects.create(
                nombre=f"Equipo A{i}", categoria=self.cat1, organizacion=self.org1, dirigente=self.admin_user
            )
            self.equipos_a.append(eq)
            EquipoGrupoTorneo.objects.create(torneo=self.torneo, grupo=self.grupo_a, equipo=eq, orden=i)

        self.equipos_b = []
        for i in range(1, 4):
            eq = Equipo.objects.create(
                nombre=f"Equipo B{i}", categoria=self.cat1, organizacion=self.org1, dirigente=self.admin_user
            )
            self.equipos_b.append(eq)
            EquipoGrupoTorneo.objects.create(torneo=self.torneo, grupo=self.grupo_b, equipo=eq, orden=i)

        # Crear partidos finalizados en Grupo A: A1 le gana a A2 (3-0), A2 le gana a A3 (2-0), A1 le gana a A3 (1-0)
        # Posiciones Grupo A: 1. A1 (6 pts), 2. A2 (3 pts), 3. A3 (0 pts)
        Partido.objects.create(
            organizacion=self.org1, torneo=self.torneo, grupo_personalizado=self.grupo_a,
            fase='grupos', equipo_local=self.equipos_a[0], equipo_visitante=self.equipos_a[1],
            goles_local=3, goles_visitante=0, fecha_hora=timezone.now(), estado='finalizado'
        )
        Partido.objects.create(
            organizacion=self.org1, torneo=self.torneo, grupo_personalizado=self.grupo_a,
            fase='grupos', equipo_local=self.equipos_a[1], equipo_visitante=self.equipos_a[2],
            goles_local=2, goles_visitante=0, fecha_hora=timezone.now(), estado='finalizado'
        )
        Partido.objects.create(
            organizacion=self.org1, torneo=self.torneo, grupo_personalizado=self.grupo_a,
            fase='grupos', equipo_local=self.equipos_a[0], equipo_visitante=self.equipos_a[2],
            goles_local=1, goles_visitante=0, fecha_hora=timezone.now(), estado='finalizado'
        )

        # Crear partidos finalizados en Grupo B: B1 le gana a B2 (2-1), B2 le gana a B3 (3-1), B1 le gana a B3 (2-0)
        # Posiciones Grupo B: 1. B1 (6 pts), 2. B2 (3 pts), 3. B3 (0 pts)
        Partido.objects.create(
            organizacion=self.org1, torneo=self.torneo, grupo_personalizado=self.grupo_b,
            fase='grupos', equipo_local=self.equipos_b[0], equipo_visitante=self.equipos_b[1],
            goles_local=2, goles_visitante=1, fecha_hora=timezone.now(), estado='finalizado'
        )
        Partido.objects.create(
            organizacion=self.org1, torneo=self.torneo, grupo_personalizado=self.grupo_b,
            fase='grupos', equipo_local=self.equipos_b[1], equipo_visitante=self.equipos_b[2],
            goles_local=3, goles_visitante=1, fecha_hora=timezone.now(), estado='finalizado'
        )
        Partido.objects.create(
            organizacion=self.org1, torneo=self.torneo, grupo_personalizado=self.grupo_b,
            fase='grupos', equipo_local=self.equipos_b[0], equipo_visitante=self.equipos_b[2],
            goles_local=2, goles_visitante=0, fecha_hora=timezone.now(), estado='finalizado'
        )

    def _login_admin(self):
        session = self.client.session
        session['current_organizacion_id'] = self.org1.id
        session.save()
        self.client.login(username="admin_p5", password="password123")

    def test_verificar_estado_clasificacion_grupos(self):
        estado = verificar_estado_clasificacion_grupos(self.torneo, self.org1)
        self.assertTrue(estado['todos_finalizados'])
        self.assertEqual(len(estado['empates_pendientes'] if 'empates_pendientes' in estado else []), 0)
        self.assertEqual(len(estado['grupos_info']), 2)

    def test_confirmar_clasificados_definitivos_automatico(self):
        confirmar_clasificados_definitivos(self.torneo, self.org1, self.admin_user)
        self.assertEqual(ClasificadoTorneo.objects.filter(torneo=self.torneo).count(), 4)
        a1_clas = ClasificadoTorneo.objects.get(torneo=self.torneo, equipo=self.equipos_a[0])
        self.assertEqual(a1_clas.posicion_grupo, 1)
        self.assertEqual(a1_clas.bombo, 1)

    def test_resolver_empate_administrativo(self):
        # Crear empate de prueba en Grupo A entre A1 y A2
        res = resolver_empate_administrativo(
            torneo=self.torneo,
            grupo=self.grupo_a,
            equipos_ids=[self.equipos_a[0].id, self.equipos_a[1].id],
            equipo_ganador_id=self.equipos_a[0].id,
            motivo="Sorteo ante delegados",
            observacion="Observación test",
            usuario=self.admin_user,
            organizacion=self.org1
        )
        self.assertIsNotNone(res)
        self.assertEqual(ResolucionEmpateTorneo.objects.filter(torneo=self.torneo).count(), 1)

    def test_reabrir_clasificacion_definitiva(self):
        confirmar_clasificados_definitivos(self.torneo, self.org1, self.admin_user)
        self.assertEqual(ClasificadoTorneo.objects.filter(torneo=self.torneo).count(), 4)

        reabrir_clasificacion_definitiva(self.torneo, self.org1, self.admin_user, motivo="Sorteo incorrecto realizado por error humano")
        self.assertEqual(ClasificadoTorneo.objects.filter(torneo=self.torneo).count(), 0)

    def test_generar_sorteo_eliminatorio_automatico_bombos(self):
        confirmar_clasificados_definitivos(self.torneo, self.org1, self.admin_user)
        sorteo = generar_sorteo_eliminatorio(self.torneo, self.org1, self.admin_user, params={'tipo_sorteo': 'bombos'})
        self.assertEqual(sorteo['total_clasificados'], 4)
        self.assertEqual(len(sorteo['llaves']), 2)

    def test_confirmar_y_crear_cuadro_eliminatorio_partido_unico(self):
        confirmar_clasificados_definitivos(self.torneo, self.org1, self.admin_user)
        sorteo = generar_sorteo_eliminatorio(self.torneo, self.org1, self.admin_user, params={'tipo_sorteo': 'bombos', 'formato': 'partido_unico'})
        
        llaves_creadas = confirmar_y_crear_cuadro_eliminatorio(
            torneo=self.torneo,
            organizacion=self.org1,
            usuario=self.admin_user,
            preview_data=sorteo
        )
        self.assertEqual(len(llaves_creadas), 2)
        self.assertEqual(LlaveEliminatoria.objects.filter(torneo=self.torneo).count(), 2)
        self.assertEqual(Partido.objects.filter(torneo=self.torneo, fase='semifinal').count(), 2)

    def test_confirmar_y_crear_cuadro_eliminatorio_ida_y_vuelta(self):
        confirmar_clasificados_definitivos(self.torneo, self.org1, self.admin_user)
        sorteo = generar_sorteo_eliminatorio(self.torneo, self.org1, self.admin_user, params={'tipo_sorteo': 'bombos', 'formato': 'ida_vuelta'})
        
        llaves_creadas = confirmar_y_crear_cuadro_eliminatorio(
            torneo=self.torneo,
            organizacion=self.org1,
            usuario=self.admin_user,
            preview_data=sorteo
        )
        self.assertEqual(len(llaves_creadas), 2)
        self.assertEqual(Partido.objects.filter(torneo=self.torneo, fase='semifinal').count(), 4)  # 2 llaves x 2 partidos cada una

    def test_cuadro_eliminatorio_con_byes(self):
        # Reducir cupos de Grupo B a 1 clasificado -> Total 3 clasificados
        self.grupo_b.cupos_clasificacion = 1
        self.grupo_b.save()

        confirmar_clasificados_definitivos(self.torneo, self.org1, self.admin_user)
        self.assertEqual(ClasificadoTorneo.objects.filter(torneo=self.torneo).count(), 3)

        sorteo = generar_sorteo_eliminatorio(self.torneo, self.org1, self.admin_user, params={'tipo_sorteo': 'posicion'})
        self.assertEqual(sorteo['total_clasificados'], 3)
        self.assertEqual(sorteo['num_byes'], 1)
        
        # Una de las llaves tiene es_bye = True
        byes = [ll for ll in sorteo['llaves'] if ll['es_bye']]
        self.assertEqual(len(byes), 1)

    def test_vistas_web_y_exportaciones_fase5(self):
        self._login_admin()
        
        # 1. Vista confirmación clasificados
        url_conf = reverse('confirmar_clasificados_view', kwargs={'torneo_id': self.torneo.id})
        res_conf = self.client.get(url_conf)
        self.assertEqual(res_conf.status_code, 200)

        # Confirmar clasificados vía POST
        self.client.post(url_conf)

        # 2. Vista configurar sorteo
        url_sort = reverse('configurar_sorteo_eliminatorio_view', kwargs={'torneo_id': self.torneo.id})
        res_sort = self.client.get(url_sort)
        self.assertEqual(res_sort.status_code, 200)

        # Generar sorteo vía POST -> Redirecciona a vista previa (302)
        res_prev = self.client.post(url_sort, {'formato': 'partido_unico', 'evitar_mismo_grupo': '1'})
        self.assertEqual(res_prev.status_code, 302)

        # Confirmar cuadro vía POST
        url_conf_cuadro = reverse('confirmar_cuadro_view', kwargs={'torneo_id': self.torneo.id})
        res_cuadro = self.client.post(url_conf_cuadro, {'ida_y_vuelta': 'off'})
        self.assertEqual(res_cuadro.status_code, 302)

        # 3. Vista ver cuadro
        url_ver = reverse('ver_cuadro_eliminatorio_view', kwargs={'torneo_id': self.torneo.id})
        res_ver = self.client.get(url_ver)
        self.assertEqual(res_ver.status_code, 200)

        # 4. Vista imprimir cuadro
        url_print = reverse('imprimir_cuadro_eliminatorio_view', kwargs={'torneo_id': self.torneo.id})
        res_print = self.client.get(url_print)
        self.assertEqual(res_print.status_code, 200)

        # 5. Vista exportar Excel cuadro
        url_excel = reverse('exportar_excel_cuadro_eliminatorio_view', kwargs={'torneo_id': self.torneo.id})
        res_excel = self.client.get(url_excel)
        self.assertEqual(res_excel.status_code, 200)
        self.assertEqual(
            res_excel['Content-Type'],
            'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )

    def test_aislamiento_organizacion_fase5(self):
        user_org2 = User.objects.create_user(username="org2_user5", password="password123")
        session = self.client.session
        session['organizacion_id'] = self.org2.id
        session.save()
        self.client.login(username="org2_user5", password="password123")

        url = reverse('confirmar_clasificados_view', kwargs={'torneo_id': self.torneo.id})
        res = self.client.get(url)
        self.assertEqual(res.status_code, 404)


from matches.models import ResultadoFinalTorneo
from matches.services.eliminatorias_personalizado import (
    evaluar_estado_llave,
    confirmar_ganador_llave,
    procesar_bye_llave,
    reabrir_llave_eliminatoria,
    programar_partidos_ronda_siguiente,
    generar_excel_cuadro_eliminatorio_completo
)


class TorneoPersonalizadoPhase6Tests(TestCase):

    def setUp(self):
        self.admin_user = User.objects.create_user(
            username="admin_p6", password="password123", role="superadmin"
        )
        self.normal_user = User.objects.create_user(
            username="normal_p6", password="password123", role="jugador"
        )
        self.org1 = Organizacion.objects.create(nombre="Org Fase 6", codigo="ORGF6")
        self.org2 = Organizacion.objects.create(nombre="Org Ajena 6", codigo="ORGF6A")

        UsuarioOrganizacion.objects.create(usuario=self.admin_user, organizacion=self.org1, rol='admin', activo=True)
        UsuarioOrganizacion.objects.create(usuario=self.normal_user, organizacion=self.org1, rol='miembro', activo=True)

        self.cat1 = Categoria.objects.create(nombre="Máster 50", organizacion=self.org1)

        self.torneo = Torneo.objects.create(
            nombre="Copa Personalizada F6",
            categoria=self.cat1,
            organizacion=self.org1,
            tipo='personalizado',
            temporada="2026",
            usar_gol_visitante=False,
            disputar_tercer_lugar=True
        )

        self.torneo_liga = Torneo.objects.create(
            nombre="Liga Regular Intacta",
            categoria=self.cat1,
            organizacion=self.org1,
            tipo='liga',
            temporada="2026"
        )

        self.equipos = [
            Equipo.objects.create(nombre=f"Equipo {i}", categoria=self.cat1, organizacion=self.org1, dirigente=self.admin_user)
            for i in range(1, 9)
        ]

        # Llave 1 Semifinal: Equipo 1 vs Equipo 2
        self.llave_sem1 = LlaveEliminatoria.objects.create(
            organizacion=self.org1,
            torneo=self.torneo,
            fase='semifinal',
            numero_llave=1,
            equipo_local=self.equipos[0],
            equipo_visitante=self.equipos[1],
            formato='partido_unico',
            estado='programada',
            posicion_siguiente_llave='local'
        )

        # Llave 2 Semifinal: Equipo 3 vs Equipo 4
        self.llave_sem2 = LlaveEliminatoria.objects.create(
            organizacion=self.org1,
            torneo=self.torneo,
            fase='semifinal',
            numero_llave=2,
            equipo_local=self.equipos[2],
            equipo_visitante=self.equipos[3],
            formato='partido_unico',
            estado='programada',
            posicion_siguiente_llave='visitante'
        )

        # Llave Final (espera ganadores)
        self.llave_final = LlaveEliminatoria.objects.create(
            organizacion=self.org1,
            torneo=self.torneo,
            fase='final',
            numero_llave=1,
            equipo_local=None,
            equipo_visitante=None,
            formato='partido_unico',
            estado='pendiente'
        )

        self.llave_sem1.siguiente_llave = self.llave_final
        self.llave_sem1.save()
        self.llave_sem2.siguiente_llave = self.llave_final
        self.llave_sem2.save()

    def _login_admin(self):
        session = self.client.session
        session['current_organizacion_id'] = self.org1.id
        session.save()
        self.client.login(username="admin_p6", password="password123")

    def test_01_partido_unico_ganador_local(self):
        p = Partido.objects.create(
            organizacion=self.org1, torneo=self.torneo, fase='semifinal',
            equipo_local=self.equipos[0], equipo_visitante=self.equipos[1],
            goles_local=3, goles_visitante=1, fecha_hora=timezone.now(), estado='finalizado'
        )
        res = evaluar_estado_llave(self.llave_sem1, self.org1)
        self.assertTrue(res['completa'])
        self.assertEqual(res['ganador'], self.equipos[0])
        self.assertEqual(res['metodo'], 'marcador')

    def test_02_partido_unico_ganador_visitante(self):
        p = Partido.objects.create(
            organizacion=self.org1, torneo=self.torneo, fase='semifinal',
            equipo_local=self.equipos[0], equipo_visitante=self.equipos[1],
            goles_local=0, goles_visitante=2, fecha_hora=timezone.now(), estado='finalizado'
        )
        res = evaluar_estado_llave(self.llave_sem1, self.org1)
        self.assertTrue(res['completa'])
        self.assertEqual(res['ganador'], self.equipos[1])

    def test_03_partido_unico_empatado_requiere_penales(self):
        Partido.objects.create(
            organizacion=self.org1, torneo=self.torneo, fase='semifinal',
            equipo_local=self.equipos[0], equipo_visitante=self.equipos[1],
            goles_local=2, goles_visitante=2, fecha_hora=timezone.now(), estado='finalizado'
        )
        res = evaluar_estado_llave(self.llave_sem1, self.org1)
        self.assertFalse(res['completa'])
        self.assertTrue(res['requiere_penales'])

    def test_04_registro_penales(self):
        Partido.objects.create(
            organizacion=self.org1, torneo=self.torneo, fase='semifinal',
            equipo_local=self.equipos[0], equipo_visitante=self.equipos[1],
            goles_local=1, goles_visitante=1, fecha_hora=timezone.now(), estado='finalizado'
        )
        confirmar_ganador_llave(
            self.llave_sem1, self.equipos[0].id, self.admin_user, self.org1,
            datos_confirmacion={'penales_local': 5, 'penales_visitante': 4}
        )
        self.llave_sem1.refresh_from_db()
        self.assertTrue(self.llave_sem1.definido_por_penales)
        self.assertEqual(self.llave_sem1.penales_local, 5)
        self.assertEqual(self.llave_sem1.penales_visitante, 4)
        self.assertEqual(self.llave_sem1.ganador, self.equipos[0])

    def test_05_penales_no_cuentan_como_goles_partido(self):
        p = Partido.objects.create(
            organizacion=self.org1, torneo=self.torneo, fase='semifinal',
            equipo_local=self.equipos[0], equipo_visitante=self.equipos[1],
            goles_local=1, goles_visitante=1, fecha_hora=timezone.now(), estado='finalizado'
        )
        confirmar_ganador_llave(
            self.llave_sem1, self.equipos[0].id, self.admin_user, self.org1,
            datos_confirmacion={'penales_local': 4, 'penales_visitante': 3}
        )
        p.refresh_from_db()
        self.assertEqual(p.goles_local, 1)  # Marcador de partido no cambia

    def test_06_prorroga_registro(self):
        Partido.objects.create(
            organizacion=self.org1, torneo=self.torneo, fase='semifinal',
            equipo_local=self.equipos[0], equipo_visitante=self.equipos[1],
            goles_local=2, goles_visitante=1, fecha_hora=timezone.now(), estado='finalizado'
        )
        confirmar_ganador_llave(
            self.llave_sem1, self.equipos[0].id, self.admin_user, self.org1,
            datos_confirmacion={'hubo_prorroga': True}
        )
        self.llave_sem1.refresh_from_db()
        self.assertTrue(self.llave_sem1.hubo_prorroga)

    def test_07_ida_y_vuelta_ganador_global(self):
        self.llave_sem1.formato = 'ida_vuelta'
        self.llave_sem1.save()

        # Ida: E1 (2) vs E2 (1)
        Partido.objects.create(
            organizacion=self.org1, torneo=self.torneo, fase='semifinal', numero_vuelta=1,
            equipo_local=self.equipos[0], equipo_visitante=self.equipos[1],
            goles_local=2, goles_visitante=1, fecha_hora=timezone.now(), estado='finalizado'
        )
        # Vuelta: E2 (1) vs E1 (1) -> Global E1 3 - 2 E2
        Partido.objects.create(
            organizacion=self.org1, torneo=self.torneo, fase='semifinal', numero_vuelta=2,
            equipo_local=self.equipos[1], equipo_visitante=self.equipos[0],
            goles_local=1, goles_visitante=1, fecha_hora=timezone.now(), estado='finalizado'
        )
        res = evaluar_estado_llave(self.llave_sem1, self.org1)
        self.assertTrue(res['completa'])
        self.assertEqual(res['ganador'], self.equipos[0])
        self.assertEqual(res['marcador_global_local'], 3)
        self.assertEqual(res['marcador_global_visitante'], 2)

    def test_08_localias_invertidas_calculo_correcto(self):
        self.llave_sem1.formato = 'ida_vuelta'
        self.llave_sem1.save()

        # Ida: E2 (3) vs E1 (0)
        Partido.objects.create(
            organizacion=self.org1, torneo=self.torneo, fase='semifinal', numero_vuelta=1,
            equipo_local=self.equipos[1], equipo_visitante=self.equipos[0],
            goles_local=3, goles_visitante=0, fecha_hora=timezone.now(), estado='finalizado'
        )
        # Vuelta: E1 (4) vs E2 (0) -> Global E1 4 - 3 E2
        Partido.objects.create(
            organizacion=self.org1, torneo=self.torneo, fase='semifinal', numero_vuelta=2,
            equipo_local=self.equipos[0], equipo_visitante=self.equipos[1],
            goles_local=4, goles_visitante=0, fecha_hora=timezone.now(), estado='finalizado'
        )
        res = evaluar_estado_llave(self.llave_sem1, self.org1)
        self.assertEqual(res['ganador'], self.equipos[0])

    def test_09_global_empatado_requiere_penales(self):
        self.llave_sem1.formato = 'ida_vuelta'
        self.llave_sem1.save()

        Partido.objects.create(
            organizacion=self.org1, torneo=self.torneo, fase='semifinal', numero_vuelta=1,
            equipo_local=self.equipos[0], equipo_visitante=self.equipos[1],
            goles_local=1, goles_visitante=0, fecha_hora=timezone.now(), estado='finalizado'
        )
        Partido.objects.create(
            organizacion=self.org1, torneo=self.torneo, fase='semifinal', numero_vuelta=2,
            equipo_local=self.equipos[1], equipo_visitante=self.equipos[0],
            goles_local=1, goles_visitante=0, fecha_hora=timezone.now(), estado='finalizado'
        )
        res = evaluar_estado_llave(self.llave_sem1, self.org1)
        self.assertFalse(res['completa'])
        self.assertTrue(res['requiere_penales'])

    def test_10_gol_visitante_desactivado(self):
        self.torneo.usar_gol_visitante = False
        self.torneo.save()
        self.llave_sem1.formato = 'ida_vuelta'
        self.llave_sem1.save()

        # Ida: E1 (1) vs E2 (2) -> E2 tiene 2 goles visita
        Partido.objects.create(
            organizacion=self.org1, torneo=self.torneo, fase='semifinal', numero_vuelta=1,
            equipo_local=self.equipos[0], equipo_visitante=self.equipos[1],
            goles_local=1, goles_visitante=2, fecha_hora=timezone.now(), estado='finalizado'
        )
        # Vuelta: E2 (0) vs E1 (1) -> Global 2-2. Sin gol visita -> Requiere penales
        Partido.objects.create(
            organizacion=self.org1, torneo=self.torneo, fase='semifinal', numero_vuelta=2,
            equipo_local=self.equipos[1], equipo_visitante=self.equipos[0],
            goles_local=0, goles_visitante=1, fecha_hora=timezone.now(), estado='finalizado'
        )
        res = evaluar_estado_llave(self.llave_sem1, self.org1)
        self.assertTrue(res['requiere_penales'])

    def test_11_gol_visitante_activado(self):
        self.torneo.usar_gol_visitante = True
        self.torneo.save()
        self.llave_sem1.formato = 'ida_vuelta'
        self.llave_sem1.save()

        # Ida: E1 (1) vs E2 (2) -> E2 anotó 2 de visitante
        Partido.objects.create(
            organizacion=self.org1, torneo=self.torneo, fase='semifinal', numero_vuelta=1,
            equipo_local=self.equipos[0], equipo_visitante=self.equipos[1],
            goles_local=1, goles_visitante=2, fecha_hora=timezone.now(), estado='finalizado'
        )
        # Vuelta: E2 (0) vs E1 (1) -> E1 anotó 1 de visitante -> Gana E2 por gol de visitante
        Partido.objects.create(
            organizacion=self.org1, torneo=self.torneo, fase='semifinal', numero_vuelta=2,
            equipo_local=self.equipos[1], equipo_visitante=self.equipos[0],
            goles_local=0, goles_visitante=1, fecha_hora=timezone.now(), estado='finalizado'
        )
        res = evaluar_estado_llave(self.llave_sem1, self.org1)
        self.assertTrue(res['completa'])
        self.assertEqual(res['ganador'], self.equipos[1])
        self.assertEqual(res['metodo'], 'gol_visitante')

    def test_12_confirmacion_de_ganador(self):
        Partido.objects.create(
            organizacion=self.org1, torneo=self.torneo, fase='semifinal',
            equipo_local=self.equipos[0], equipo_visitante=self.equipos[1],
            goles_local=2, goles_visitante=0, fecha_hora=timezone.now(), estado='finalizado'
        )
        confirmar_ganador_llave(self.llave_sem1, self.equipos[0].id, self.admin_user, self.org1)
        self.llave_sem1.refresh_from_db()
        self.assertEqual(self.llave_sem1.estado, 'finalizada')
        self.assertEqual(self.llave_sem1.ganador, self.equipos[0])

    def test_13_bloqueo_ganador_incorrecto(self):
        Partido.objects.create(
            organizacion=self.org1, torneo=self.torneo, fase='semifinal',
            equipo_local=self.equipos[0], equipo_visitante=self.equipos[1],
            goles_local=3, goles_visitante=0, fecha_hora=timezone.now(), estado='finalizado'
        )
        with self.assertRaises(ValidationError):
            confirmar_ganador_llave(self.llave_sem1, self.equipos[1].id, self.admin_user, self.org1)

    def test_14_avance_a_siguiente_llave(self):
        Partido.objects.create(
            organizacion=self.org1, torneo=self.torneo, fase='semifinal',
            equipo_local=self.equipos[0], equipo_visitante=self.equipos[1],
            goles_local=2, goles_visitante=0, fecha_hora=timezone.now(), estado='finalizado'
        )
        confirmar_ganador_llave(self.llave_sem1, self.equipos[0].id, self.admin_user, self.org1)
        self.llave_final.refresh_from_db()
        self.assertEqual(self.llave_final.equipo_local, self.equipos[0])
        self.assertEqual(self.llave_final.estado, 'pendiente')

    def test_15_no_crear_siguiente_partido_con_un_solo_equipo(self):
        Partido.objects.create(
            organizacion=self.org1, torneo=self.torneo, fase='semifinal',
            equipo_local=self.equipos[0], equipo_visitante=self.equipos[1],
            goles_local=2, goles_visitante=0, fecha_hora=timezone.now(), estado='finalizado'
        )
        confirmar_ganador_llave(self.llave_sem1, self.equipos[0].id, self.admin_user, self.org1)
        # La llave final tiene solo 1 equipo -> No debe crear partidos
        self.assertEqual(Partido.objects.filter(torneo=self.torneo, fase='final').count(), 0)

    def test_16_crear_partido_cuando_llegan_ambos_ganadores(self):
        Partido.objects.create(
            organizacion=self.org1, torneo=self.torneo, fase='semifinal',
            equipo_local=self.equipos[0], equipo_visitante=self.equipos[1],
            goles_local=2, goles_visitante=0, fecha_hora=timezone.now(), estado='finalizado'
        )
        Partido.objects.create(
            organizacion=self.org1, torneo=self.torneo, fase='semifinal',
            equipo_local=self.equipos[2], equipo_visitante=self.equipos[3],
            goles_local=1, goles_visitante=0, fecha_hora=timezone.now(), estado='finalizado'
        )
        confirmar_ganador_llave(self.llave_sem1, self.equipos[0].id, self.admin_user, self.org1)
        confirmar_ganador_llave(self.llave_sem2, self.equipos[2].id, self.admin_user, self.org1)

        self.llave_final.refresh_from_db()
        self.assertEqual(self.llave_final.estado, 'programada')

        # Programar la final
        partidos = programar_partidos_ronda_siguiente(self.torneo, self.org1, self.admin_user, {'fase': 'final', 'formato': 'partido_unico'})
        self.assertEqual(len(partidos), 1)
        self.assertEqual(partidos[0].equipo_local, self.equipos[0])
        self.assertEqual(partidos[0].equipo_visitante, self.equipos[2])

    def test_17_evitar_creacion_duplicada_partidos(self):
        Partido.objects.create(
            organizacion=self.org1, torneo=self.torneo, fase='semifinal',
            equipo_local=self.equipos[0], equipo_visitante=self.equipos[1],
            goles_local=2, goles_visitante=0, fecha_hora=timezone.now(), estado='finalizado'
        )
        Partido.objects.create(
            organizacion=self.org1, torneo=self.torneo, fase='semifinal',
            equipo_local=self.equipos[2], equipo_visitante=self.equipos[3],
            goles_local=1, goles_visitante=0, fecha_hora=timezone.now(), estado='finalizado'
        )
        confirmar_ganador_llave(self.llave_sem1, self.equipos[0].id, self.admin_user, self.org1)
        confirmar_ganador_llave(self.llave_sem2, self.equipos[2].id, self.admin_user, self.org1)

        programar_partidos_ronda_siguiente(self.torneo, self.org1, self.admin_user, {'fase': 'final', 'formato': 'partido_unico'})
        cant1 = Partido.objects.filter(torneo=self.torneo, fase='final').count()

        programar_partidos_ronda_siguiente(self.torneo, self.org1, self.admin_user, {'fase': 'final', 'formato': 'partido_unico'})
        cant2 = Partido.objects.filter(torneo=self.torneo, fase='final').count()
        self.assertEqual(cant1, cant2)

    def test_18_bye_procesamiento(self):
        llave_bye = LlaveEliminatoria.objects.create(
            organizacion=self.org1, torneo=self.torneo, fase='cuartos', numero_llave=1,
            equipo_local=self.equipos[4], equipo_visitante=None, es_bye=True,
            siguiente_llave=self.llave_sem1, posicion_siguiente_llave='local'
        )
        procesar_bye_llave(llave_bye, self.admin_user, self.org1)
        llave_bye.refresh_from_db()
        self.assertEqual(llave_bye.estado, 'finalizada')
        self.assertEqual(llave_bye.ganador, self.equipos[4])

    def test_19_bye_no_cuenta_como_partido_jugado(self):
        llave_bye = LlaveEliminatoria.objects.create(
            organizacion=self.org1, torneo=self.torneo, fase='cuartos', numero_llave=1,
            equipo_local=self.equipos[4], equipo_visitante=None, es_bye=True
        )
        procesar_bye_llave(llave_bye, self.admin_user, self.org1)
        self.assertEqual(Partido.objects.filter(torneo=self.torneo, fase='cuartos').count(), 0)

    def test_20_cuartos_a_semifinal(self):
        llave_cuartos = LlaveEliminatoria.objects.create(
            organizacion=self.org1, torneo=self.torneo, fase='cuartos', numero_llave=1,
            equipo_local=self.equipos[0], equipo_visitante=self.equipos[4],
            siguiente_llave=self.llave_sem1, posicion_siguiente_llave='local'
        )
        Partido.objects.create(
            organizacion=self.org1, torneo=self.torneo, fase='cuartos',
            equipo_local=self.equipos[0], equipo_visitante=self.equipos[4],
            goles_local=2, goles_visitante=1, fecha_hora=timezone.now(), estado='finalizado'
        )
        confirmar_ganador_llave(llave_cuartos, self.equipos[0].id, self.admin_user, self.org1)
        self.llave_sem1.refresh_from_db()
        self.assertEqual(self.llave_sem1.equipo_local, self.equipos[0])

    def test_21_semifinal_a_final(self):
        Partido.objects.create(
            organizacion=self.org1, torneo=self.torneo, fase='semifinal',
            equipo_local=self.equipos[0], equipo_visitante=self.equipos[1],
            goles_local=2, goles_visitante=0, fecha_hora=timezone.now(), estado='finalizado'
        )
        confirmar_ganador_llave(self.llave_sem1, self.equipos[0].id, self.admin_user, self.org1)
        self.llave_final.refresh_from_db()
        self.assertEqual(self.llave_final.equipo_local, self.equipos[0])

    def test_22_final_y_campeon(self):
        self.llave_final.equipo_local = self.equipos[0]
        self.llave_final.equipo_visitante = self.equipos[2]
        self.llave_final.estado = 'programada'
        self.llave_final.save()

        Partido.objects.create(
            organizacion=self.org1, torneo=self.torneo, fase='final',
            equipo_local=self.equipos[0], equipo_visitante=self.equipos[2],
            goles_local=3, goles_visitante=1, fecha_hora=timezone.now(), estado='finalizado'
        )
        confirmar_ganador_llave(self.llave_final, self.equipos[0].id, self.admin_user, self.org1)

        res_final = ResultadoFinalTorneo.objects.get(torneo=self.torneo)
        self.assertEqual(res_final.campeon, self.equipos[0])
        self.assertEqual(res_final.subcampeon, self.equipos[2])

    def test_23_partido_tercer_lugar(self):
        Partido.objects.create(
            organizacion=self.org1, torneo=self.torneo, fase='semifinal',
            equipo_local=self.equipos[0], equipo_visitante=self.equipos[1],
            goles_local=2, goles_visitante=0, fecha_hora=timezone.now(), estado='finalizado'
        )
        Partido.objects.create(
            organizacion=self.org1, torneo=self.torneo, fase='semifinal',
            equipo_local=self.equipos[2], equipo_visitante=self.equipos[3],
            goles_local=2, goles_visitante=1, fecha_hora=timezone.now(), estado='finalizado'
        )
        confirmar_ganador_llave(self.llave_sem1, self.equipos[0].id, self.admin_user, self.org1)
        confirmar_ganador_llave(self.llave_sem2, self.equipos[2].id, self.admin_user, self.org1)

        llave_3er = LlaveEliminatoria.objects.get(torneo=self.torneo, fase='tercer_lugar')
        self.assertEqual(llave_3er.equipo_local, self.equipos[1])  # Perdedor Sem1
        self.assertEqual(llave_3er.equipo_visitante, self.equipos[3])  # Perdedor Sem2

    def test_24_torneo_sin_tercer_lugar(self):
        self.torneo.disputar_tercer_lugar = False
        self.torneo.save()

        Partido.objects.create(
            organizacion=self.org1, torneo=self.torneo, fase='semifinal',
            equipo_local=self.equipos[0], equipo_visitante=self.equipos[1],
            goles_local=2, goles_visitante=0, fecha_hora=timezone.now(), estado='finalizado'
        )
        confirmar_ganador_llave(self.llave_sem1, self.equipos[0].id, self.admin_user, self.org1)
        self.assertFalse(LlaveEliminatoria.objects.filter(torneo=self.torneo, fase='tercer_lugar').exists())

    def test_25_confirmacion_de_campeon_y_26_subcampeon(self):
        self.llave_final.equipo_local = self.equipos[0]
        self.llave_final.equipo_visitante = self.equipos[1]
        self.llave_final.estado = 'programada'
        self.llave_final.save()

        Partido.objects.create(
            organizacion=self.org1, torneo=self.torneo, fase='final',
            equipo_local=self.equipos[0], equipo_visitante=self.equipos[1],
            goles_local=1, goles_visitante=0, fecha_hora=timezone.now(), estado='finalizado'
        )
        confirmar_ganador_llave(self.llave_final, self.equipos[0].id, self.admin_user, self.org1)

        res = ResultadoFinalTorneo.objects.get(torneo=self.torneo)
        self.assertEqual(res.campeon, self.equipos[0])
        self.assertEqual(res.subcampeon, self.equipos[1])

    def test_27_un_solo_resultado_final_por_torneo(self):
        ResultadoFinalTorneo.objects.create(
            organizacion=self.org1, torneo=self.torneo,
            campeon=self.equipos[0], subcampeon=self.equipos[1]
        )
        with self.assertRaises(Exception):
            ResultadoFinalTorneo.objects.create(
                organizacion=self.org1, torneo=self.torneo,
                campeon=self.equipos[2], subcampeon=self.equipos[3]
            )

    def test_28_reapertura_antes_de_iniciar_siguiente_ronda(self):
        Partido.objects.create(
            organizacion=self.org1, torneo=self.torneo, fase='semifinal',
            equipo_local=self.equipos[0], equipo_visitante=self.equipos[1],
            goles_local=2, goles_visitante=0, fecha_hora=timezone.now(), estado='finalizado'
        )
        confirmar_ganador_llave(self.llave_sem1, self.equipos[0].id, self.admin_user, self.org1)
        self.llave_sem1.refresh_from_db()
        self.assertEqual(self.llave_sem1.estado, 'finalizada')

        reabrir_llave_eliminatoria(self.llave_sem1, self.admin_user, self.org1, motivo="Error de digitación en acta")
        self.llave_sem1.refresh_from_db()
        self.assertEqual(self.llave_sem1.estado, 'programada')
        self.assertIsNone(self.llave_sem1.ganador)

        self.llave_final.refresh_from_db()
        self.assertIsNone(self.llave_final.equipo_local)

    def test_29_bloqueo_reapertura_con_ronda_iniciada(self):
        Partido.objects.create(
            organizacion=self.org1, torneo=self.torneo, fase='semifinal',
            equipo_local=self.equipos[0], equipo_visitante=self.equipos[1],
            goles_local=2, goles_visitante=0, fecha_hora=timezone.now(), estado='finalizado'
        )
        Partido.objects.create(
            organizacion=self.org1, torneo=self.torneo, fase='semifinal',
            equipo_local=self.equipos[2], equipo_visitante=self.equipos[3],
            goles_local=1, goles_visitante=0, fecha_hora=timezone.now(), estado='finalizado'
        )
        confirmar_ganador_llave(self.llave_sem1, self.equipos[0].id, self.admin_user, self.org1)
        confirmar_ganador_llave(self.llave_sem2, self.equipos[2].id, self.admin_user, self.org1)

        programar_partidos_ronda_siguiente(self.torneo, self.org1, self.admin_user, {'fase': 'final', 'formato': 'partido_unico'})

        p_final = Partido.objects.get(torneo=self.torneo, fase='final')
        p_final.estado = 'en_curso'
        p_final.save()

        with self.assertRaises(ValidationError):
            reabrir_llave_eliminatoria(self.llave_sem1, self.admin_user, self.org1, motivo="Intento de reabrir")

    def test_30_decision_administrativa(self):
        confirmar_ganador_llave(
            self.llave_sem1, self.equipos[1].id, self.admin_user, self.org1,
            datos_confirmacion={'motivo_admin': 'Retiro reglamentario del Equipo 1'}
        )
        self.llave_sem1.refresh_from_db()
        self.assertEqual(self.llave_sem1.ganador, self.equipos[1])
        self.assertEqual(self.llave_sem1.metodo_definicion, 'decision_administrativa')

    def test_31_aislamiento_multiempresa(self):
        user_org2 = User.objects.create_user(username="user_org2_p6", password="password123")
        session = self.client.session
        session['organizacion_id'] = self.org2.id
        session.save()
        self.client.login(username="user_org2_p6", password="password123")

        url = reverse('ver_cuadro_eliminatorio_view', kwargs={'torneo_id': self.torneo.id})
        res = self.client.get(url)
        self.assertEqual(res.status_code, 404)

    def test_32_usuario_sin_permiso(self):
        self.client.login(username="normal_p6", password="password123")
        session = self.client.session
        session['current_organizacion_id'] = self.org1.id
        session.save()

        url = reverse('confirmar_ganador_llave_view', kwargs={'torneo_id': self.torneo.id, 'llave_id': self.llave_sem1.id})
        res = self.client.post(url, {'ganador_id': self.equipos[0].id})
        self.assertEqual(res.status_code, 302)

    def test_33_confirmacion_duplicada_bloqueada(self):
        Partido.objects.create(
            organizacion=self.org1, torneo=self.torneo, fase='semifinal',
            equipo_local=self.equipos[0], equipo_visitante=self.equipos[1],
            goles_local=2, goles_visitante=0, fecha_hora=timezone.now(), estado='finalizado'
        )
        confirmar_ganador_llave(self.llave_sem1, self.equipos[0].id, self.admin_user, self.org1)
        with self.assertRaises(ValidationError):
            confirmar_ganador_llave(self.llave_sem1, self.equipos[0].id, self.admin_user, self.org1)

    def test_34_procesamiento_concurrente_atomic(self):
        Partido.objects.create(
            organizacion=self.org1, torneo=self.torneo, fase='semifinal',
            equipo_local=self.equipos[0], equipo_visitante=self.equipos[1],
            goles_local=2, goles_visitante=0, fecha_hora=timezone.now(), estado='finalizado'
        )
        # Transacción atómica
        with transaction.atomic():
            ll = LlaveEliminatoria.objects.select_for_update().get(id=self.llave_sem1.id)
            self.assertEqual(ll.estado, 'programada')

    def test_35_estadisticas_grupos_no_incluyen_eliminatorias(self):
        from matches.services.estadisticas_personalizado import calcular_posiciones_grupo
        grupo = GrupoTorneo.objects.create(torneo=self.torneo, nombre="Grupo Z")
        EquipoGrupoTorneo.objects.create(torneo=self.torneo, grupo=grupo, equipo=self.equipos[0])
        EquipoGrupoTorneo.objects.create(torneo=self.torneo, grupo=grupo, equipo=self.equipos[1])

        # Partido de eliminatoria
        Partido.objects.create(
            organizacion=self.org1, torneo=self.torneo, fase='semifinal',
            equipo_local=self.equipos[0], equipo_visitante=self.equipos[1],
            goles_local=10, goles_visitante=0, fecha_hora=timezone.now(), estado='finalizado'
        )

        res = calcular_posiciones_grupo(grupo, self.torneo, self.org1)
        for item in res['tabla']:
            self.assertEqual(item['PJ'], 0)
            self.assertEqual(item['PTS'], 0)

    def test_36_vistas_web_pantalla_campeon_e_impresion(self):
        self._login_admin()

        self.llave_final.equipo_local = self.equipos[0]
        self.llave_final.equipo_visitante = self.equipos[1]
        self.llave_final.estado = 'programada'
        self.llave_final.save()

        Partido.objects.create(
            organizacion=self.org1, torneo=self.torneo, fase='final',
            equipo_local=self.equipos[0], equipo_visitante=self.equipos[1],
            goles_local=2, goles_visitante=1, fecha_hora=timezone.now(), estado='finalizado'
        )
        confirmar_ganador_llave(self.llave_final, self.equipos[0].id, self.admin_user, self.org1)

        url_champ = reverse('pantalla_campeon_view', kwargs={'torneo_id': self.torneo.id})
        res_champ = self.client.get(url_champ)
        self.assertEqual(res_champ.status_code, 200)
        self.assertContains(res_champ, "EQUIPO 1")

        url_print = reverse('imprimir_cuadro_eliminatorio_view', kwargs={'torneo_id': self.torneo.id})
        res_print = self.client.get(url_print)
        self.assertEqual(res_print.status_code, 200)

        url_excel = reverse('exportar_excel_cuadro_eliminatorio_view', kwargs={'torneo_id': self.torneo.id})
        res_excel = self.client.get(url_excel)
        self.assertEqual(res_excel.status_code, 200)

    def test_39_formatos_liga_y_torneo_sin_cambios(self):
        self.assertEqual(self.torneo_liga.tipo, 'liga')
        # Verificar que la lógica de torneo personalizado rechaza torneos tipo liga
        with self.assertRaises(ValidationError):
            confirmar_ganador_llave(self.llave_sem1, self.equipos[0].id, self.admin_user, self.org1)


class TorneoPersonalizadoPhase7Tests(TestCase):

    def setUp(self):
        self.admin_user = User.objects.create_superuser(username="admin_p7", password="password123")
        self.vocal_user = User.objects.create_user(username="vocal_p7", password="password123", role="vocal")
        self.dirigente_user = User.objects.create_user(username="dirigente_p7", password="password123", role="dirigente")
        self.org1 = Organizacion.objects.create(nombre="Org Phase7 A", codigo="ORGP7A")
        self.org2 = Organizacion.objects.create(nombre="Org Phase7 B", codigo="ORGP7B")

        from users.models import UsuarioOrganizacion
        UsuarioOrganizacion.objects.create(usuario=self.admin_user, organizacion=self.org1, rol='admin', activo=True)

        self.cat1 = Categoria.objects.create(nombre="Máster 40", organizacion=self.org1)

        self.torneo = Torneo.objects.create(
            nombre="Copa Fase 7", tipo="personalizado", categoria=self.cat1,
            organizacion=self.org1, temporada="2026", es_publico=True
        )

        self.equipos = []
        for i in range(1, 9):
            eq = Equipo.objects.create(nombre=f"Equipo P7-{i}", categoria=self.cat1, organizacion=self.org1, dirigente=self.admin_user)
            self.torneo.equipos.add(eq)
            self.equipos.append(eq)

        self.grupo_a = GrupoTorneo.objects.create(torneo=self.torneo, nombre="Grupo A", sector="Norte", cupos_clasificacion=2)
        self.grupo_b = GrupoTorneo.objects.create(torneo=self.torneo, nombre="Grupo B", sector="Sur", cupos_clasificacion=2)

        for eq in self.equipos[:4]:
            EquipoGrupoTorneo.objects.create(torneo=self.torneo, grupo=self.grupo_a, equipo=eq)
        for eq in self.equipos[4:]:
            EquipoGrupoTorneo.objects.create(torneo=self.torneo, grupo=self.grupo_b, equipo=eq)

        self.client.login(username="admin_p7", password="password123")
        session = self.client.session
        session['current_organizacion_id'] = self.org1.id
        session.save()

    def test_01_evaluar_estado_general_torneo(self):
        from matches.services.panel_personalizado import evaluar_estado_general_torneo
        estado = evaluar_estado_general_torneo(self.torneo)
        self.assertEqual(estado, 'grupos_configurados')

    def test_02_indicador_progreso_pasos(self):
        from matches.services.panel_personalizado import obtener_indicador_progreso
        pasos = obtener_indicador_progreso(self.torneo, 'grupos_configurados')
        self.assertEqual(len(pasos), 7)
        self.assertEqual(pasos[0]['estado'], 'completado')
        self.assertEqual(pasos[1]['estado'], 'en_curso')

    def test_03_proxima_accion_recomendada(self):
        from matches.services.panel_personalizado import obtener_proxima_accion_recomendada
        rec = obtener_proxima_accion_recomendada(self.torneo, 'grupos_configurados')
        self.assertIn("Generar Fixture", rec['titulo'])
        self.assertTrue(rec['url'].startswith("/"))

    def test_04_resumen_grupos_panel(self):
        from matches.services.panel_personalizado import obtener_resumen_grupos_panel
        resumen = obtener_resumen_grupos_panel(self.torneo)
        self.assertEqual(len(resumen), 2)
        self.assertEqual(resumen[0]['equipos_count'], 4)
        self.assertEqual(resumen[0]['cupos'], 2)

    def test_05_agenda_operativa_y_alertas(self):
        from matches.services.panel_personalizado import obtener_agenda_operativa, obtener_alertas_administrativas
        agenda = obtener_agenda_operativa(self.torneo)
        self.assertIsInstance(agenda, list)

        alertas = obtener_alertas_administrativas(self.torneo)
        self.assertIsInstance(alertas, list)

    def test_06_vista_publica_torneo_publico(self):
        url = reverse('vista_publica_torneo', kwargs={'public_uuid': self.torneo.public_uuid})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "COPA FASE 7")
        self.assertContains(response, "GRUPO A")

    def test_07_vista_publica_torneo_desactivado(self):
        self.torneo.es_publico = False
        self.torneo.save()
        url = reverse('vista_publica_torneo', kwargs={'public_uuid': self.torneo.public_uuid})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 404)
        self.assertContains(response, "Torneo no disponible", status_code=404)

    def test_08_generador_enlaces_whatsapp(self):
        from matches.services.panel_personalizado import generar_enlaces_whatsapp
        link = generar_enlaces_whatsapp(self.torneo, "https://ejemplo.com/publico/torneo/123/")
        self.assertTrue(link.startswith("https://api.whatsapp.com/send?text="))

    def test_09_exportar_excel_consolidado(self):
        url = reverse('exportar_excel_consolidado_personalizado', kwargs={'torneo_id': self.torneo.id})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')

    def test_10_vista_impresion_consolidada(self):
        url = reverse('imprimir_torneo_consolidado_personalizado', kwargs={'torneo_id': self.torneo.id})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "COPA FASE 7")

    def test_11_historial_auditoria_solo_lectura(self):
        BitacoraTorneo.objects.create(
            organizacion=self.org1, torneo=self.torneo, usuario=self.admin_user,
            accion="crear_grupo", detalles="Creado Grupo C"
        )
        url = reverse('historial_auditoria_personalizado', kwargs={'torneo_id': self.torneo.id})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "CREADO GRUPO C")

    def test_12_aislamiento_multiempresa_panel(self):
        self.client.login(username="admin_p7", password="password123")
        session = self.client.session
        session['current_organizacion_id'] = self.org2.id
        session.save()

        url = reverse('panel_torneo_personalizado', kwargs={'torneo_id': self.torneo.id})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 404)


class Fase8SecurityAndAuditTests(TestCase):

    def setUp(self):
        self.user = User.objects.create_user(username="user_fase8", password="password123")
        self.org_a = Organizacion.objects.create(nombre="Org Fase 8 A", codigo="ORGF8A")
        self.org_b = Organizacion.objects.create(nombre="Org Fase 8 B", codigo="ORGF8B")

        from users.models import UsuarioOrganizacion
        UsuarioOrganizacion.objects.create(usuario=self.user, organizacion=self.org_a, rol='admin', activo=True)
        UsuarioOrganizacion.objects.create(usuario=self.user, organizacion=self.org_b, rol='espectador', activo=True)

        self.cat_a = Categoria.objects.create(nombre="Categoría A", organizacion=self.org_a)
        self.torneo_a = Torneo.objects.create(
            nombre="Copa Fase 8", tipo="personalizado", categoria=self.cat_a,
            organizacion=self.org_a, temporada="2026"
        )

    def test_01_health_check_endpoint(self):
        response = self.client.get('/health/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok", "db": "ok"})

    def test_02_comando_auditar_torneo(self):
        from django.core.management import call_command
        from io import StringIO

        out = StringIO()
        call_command('auditar_torneo_personalizado', torneo=self.torneo_a.id, stdout=out)
        self.assertIn("AUDITORÍA DE INTEGRIDAD", out.getvalue())

    def test_03_roles_diferentes_por_organizacion(self):
        self.assertEqual(self.user.get_role_in_organizacion(self.org_a), 'admin')
        self.assertEqual(self.user.get_role_in_organizacion(self.org_b), 'espectador')

        self.assertTrue(self.user.has_module_access('torneos', self.org_a))
        self.assertFalse(self.user.has_module_access('torneos', self.org_b))

    def test_04_middleware_limpia_organizacion_invalida(self):
        self.client.login(username="user_fase8", password="password123")
        session = self.client.session
        # Intentar forzar un org_id al que no pertenece
        org_c = Organizacion.objects.create(nombre="Org C Inaccesible", codigo="ORGC")
        session['current_organizacion_id'] = org_c.id
        session.save()

        # Realizar petición protegida
        url = reverse('detalle_torneo', kwargs={'torneo_id': self.torneo_a.id})
        response = self.client.get(url)
        # El middleware debe limpiar la org inválida y asignar org_a (donde el usuario es miembro activo)
        self.assertEqual(self.client.session.get('current_organizacion_id'), self.org_a.id)








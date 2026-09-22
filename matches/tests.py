from django.test import TestCase
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.contrib.auth import get_user_model
from django.urls import reverse
from users.models import Organizacion
from teams.models import Categoria, Equipo, FichaJugador
from matches.models import Torneo, GrupoTorneo, EquipoGrupoTorneo, Partido, EventoPartido

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





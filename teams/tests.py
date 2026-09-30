from django.test import TestCase, Client
from django.contrib.auth import get_user_model
from django.utils import timezone
from datetime import timedelta
import uuid

from users.models import Organizacion, UsuarioOrganizacion
from teams.models import Equipo, Categoria, InvitacionEquipo, FichaJugador, FichaDT
from matches.models import Torneo

User = get_user_model()

class RegistroJugadorTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.org = Organizacion.objects.create(
            codigo='ORG_TEST',
            nombre='Organización de Prueba'
        )
        self.cat = Categoria.objects.create(
            organizacion=self.org,
            nombre='Senior'
        )
        self.dirigente = User.objects.create_user(
            username='dirigente_test',
            password='password123',
            role='dirigente'
        )
        self.equipo = Equipo.objects.create(
            organizacion=self.org,
            nombre='Equipo Tigres',
            categoria=self.cat,
            dirigente=self.dirigente,
            max_jugadores=25
        )
        self.torneo = Torneo.objects.create(
            organizacion=self.org,
            nombre='Copa Primavera',
            categoria=self.cat,
            max_jugadores_por_equipo=20
        )
        self.invitacion_sin_torneo = InvitacionEquipo.objects.create(
            equipo=self.equipo,
            organizacion=self.org,
            torneo=None,
            tipo='jugador',
            expira_en=timezone.now() + timedelta(days=3)
        )
        self.invitacion_con_torneo = InvitacionEquipo.objects.create(
            equipo=self.equipo,
            organizacion=self.org,
            torneo=self.torneo,
            tipo='jugador',
            expira_en=timezone.now() + timedelta(days=3)
        )

    def test_invitacion_sin_torneo_get_logged_in_user(self):
        """Un usuario logueado abre un enlace de invitación sin torneo y no debe dar error 500"""
        user = User.objects.create_user(username='jugador_existente', password='password123')
        # Crear ficha previa sin torneo
        FichaJugador.objects.create(
            user=user,
            organizacion=self.org,
            equipo=self.equipo,
            torneo=None,
            nro_cedula='1700000001'
        )
        self.client.force_login(user)
        url = f'/invitacion/{self.invitacion_sin_torneo.token}/'
        response = self.client.get(url)
        # Debe redirigir a registro_exito porque ya está registrado en este equipo
        self.assertIn(response.status_code, [200, 302])
        self.assertNotEqual(response.status_code, 500)

    def test_invitacion_con_torneo_nombre_seguro(self):
        """Un usuario logueado en otro equipo no debe generar 500 y debe mostrar error controlado"""
        equipo2 = Equipo.objects.create(
            organizacion=self.org,
            nombre='Equipo Leones',
            categoria=self.cat,
            dirigente=self.dirigente
        )
        user = User.objects.create_user(username='jugador_otro_equipo', password='password123')
        FichaJugador.objects.create(
            user=user,
            organizacion=self.org,
            equipo=equipo2,
            torneo=self.torneo,
            nro_cedula='1700000002'
        )
        self.client.force_login(user)
        url = f'/invitacion/{self.invitacion_con_torneo.token}/'
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Ya te encuentras registrado en el equipo')
        self.assertContains(response, 'LEONES')

    def test_registro_existente_numero_camiseta_vacio(self):
        """POST con numero_camiseta vacío en flujo existente no debe dar ValueError ni 500"""
        user = User.objects.create_user(username='jugador_sin_dorsal', password='password123')
        FichaJugador.objects.create(
            user=user,
            organizacion=self.org,
            equipo=self.equipo,
            torneo=None,
            nro_cedula='1700000003'
        )
        self.client.force_login(user)
        # Crear otra invitación para un torneo nuevo
        torneo2 = Torneo.objects.create(
            organizacion=self.org,
            nombre='Torneo Clausura',
            categoria=self.cat
        )
        inv = InvitacionEquipo.objects.create(
            equipo=self.equipo,
            organizacion=self.org,
            torneo=torneo2,
            tipo='jugador',
            expira_en=timezone.now() + timedelta(days=3)
        )
        url = f'/invitacion/{inv.token}/'
        response = self.client.post(url, {
            'acepto_lopdp': 'on',
            'numero_camiseta': '', # vacío
            'firma_imagen': 'data:image/png;base64,sample'
        })
        self.assertEqual(response.status_code, 302)
        from django.urls import reverse
        self.assertEqual(response.url, reverse('registro_exito'))
        ficha_nueva = FichaJugador.objects.filter(user=user, torneo=torneo2).first()
        self.assertIsNotNone(ficha_nueva)
        self.assertIsNone(ficha_nueva.numero_camiseta)

    def test_registro_nuevo_jugador_sin_torneo(self):
        """Un jugador no autenticado puede registrarse mediante invitación sin torneo sin error 500"""
        url = f'/invitacion/{self.invitacion_sin_torneo.token}/'
        response = self.client.post(url, {
            'first_name': 'Carlos',
            'last_name': 'Mora',
            'nro_cedula': '1723456789',
            'telefono': '0991234567',
            'numero_camiseta': 10,
            'firma_digital': True,
            'acepto_lopdp': 'on',
        })
        self.assertEqual(response.status_code, 302)
        from django.urls import reverse
        self.assertEqual(response.url, reverse('registro_exito'))
        ficha = FichaJugador.objects.filter(nro_cedula='1723456789').first()
        self.assertIsNotNone(ficha)
        self.assertEqual(ficha.equipo, self.equipo)
        self.assertIsNone(ficha.torneo)

    def test_numero_camiseta_no_se_puede_repetir_mismo_equipo(self):
        """No se puede registrar otro jugador con el mismo número de camiseta en el mismo equipo"""
        FichaJugador.objects.create(
            user=self.dirigente,
            organizacion=self.org,
            equipo=self.equipo,
            nro_cedula='1700000001',
            numero_camiseta=10,
            estado_validacion='aprobado'
        )
        url = f'/invitacion/{self.invitacion_sin_torneo.token}/'
        response = self.client.post(url, {
            'first_name': 'Pedro',
            'last_name': 'Suarez',
            'nro_cedula': '1700000002',
            'telefono': '0990000002',
            'numero_camiseta': 10, # Ya ocupada en self.equipo
            'firma_digital': True,
            'acepto_lopdp': 'on',
        })
        # Debe fallar la validación y no redirigir a éxito
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context['form'].has_error('numero_camiseta'))

    def test_secretaria_dashboard_lista_pendientes_y_modal(self):
        """secretaria_dashboard muestra la lista desplegable de pendientes y el modal con historial"""
        self.dirigente.is_superuser = True
        self.dirigente.role = 'superadmin'
        self.dirigente.save()
        UsuarioOrganizacion.objects.get_or_create(usuario=self.dirigente, organizacion=self.org, defaults={'rol': 'superadmin', 'activo': True})
        
        self.client.force_login(self.dirigente)
        session = self.client.session
        session['current_organizacion_id'] = self.org.id
        session.save()
        
        # Crear ficha pendiente y ficha aprobada
        user_p = User.objects.create_user(username='pend_user', password='password123', first_name='Juan', last_name='Pendiente')
        user_a = User.objects.create_user(username='aprob_user', password='password123', first_name='Mario', last_name='Aprobado')
        
        FichaJugador.objects.create(
            user=user_p, organizacion=self.org, equipo=self.equipo,
            nro_cedula='1711111111', numero_camiseta=7, estado_validacion='pendiente'
        )
        FichaJugador.objects.create(
            user=user_a, organizacion=self.org, equipo=self.equipo,
            nro_cedula='1722222222', numero_camiseta=8, estado_validacion='aprobado'
        )
        
        response = self.client.get('/secretaria/')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'JUAN PENDIENTE')
        self.assertContains(response, 'card-ficha-jug-')
        self.assertContains(response, 'modalHistorialCompleto')
        self.assertContains(response, 'MARIO APROBADO')
        self.assertContains(response, 'btnAprobarMasivo')
        self.assertContains(response, 'btnRechazarMasivo')

    def test_aprobar_masivo_jugadores_y_dt(self):
        """Aprobar masivo habilita en bloque a jugadores y directores técnicos seleccionados"""
        self.dirigente.is_superuser = True
        self.dirigente.role = 'superadmin'
        self.dirigente.save()
        UsuarioOrganizacion.objects.get_or_create(usuario=self.dirigente, organizacion=self.org, defaults={'rol': 'superadmin', 'activo': True})
        
        self.client.force_login(self.dirigente)
        session = self.client.session
        session['current_organizacion_id'] = self.org.id
        session.save()

        u1 = User.objects.create_user(username='j1', password='password123')
        u2 = User.objects.create_user(username='j2', password='password123')
        f1 = FichaJugador.objects.create(user=u1, organizacion=self.org, equipo=self.equipo, nro_cedula='1001', estado_validacion='pendiente')
        f2 = FichaJugador.objects.create(user=u2, organizacion=self.org, equipo=self.equipo, nro_cedula='1002', estado_validacion='pendiente')

        response = self.client.post('/secretaria/aprobar-masivo/', {
            'fichas_jugador': [f1.id, f2.id]
        })
        self.assertEqual(response.status_code, 302)
        
        f1.refresh_from_db()
        f2.refresh_from_db()
        self.assertEqual(f1.estado_validacion, 'aprobado')
        self.assertEqual(f2.estado_validacion, 'aprobado')
        self.assertIsNotNone(f1.fecha_aprobacion)
        self.assertEqual(f1.aprobado_por, self.dirigente)

    def test_rechazar_masivo_jugadores(self):
        """Rechazar masivo rechaza en bloque y asigna el motivo de rechazo a las fichas"""
        self.dirigente.is_superuser = True
        self.dirigente.role = 'superadmin'
        self.dirigente.save()
        UsuarioOrganizacion.objects.get_or_create(usuario=self.dirigente, organizacion=self.org, defaults={'rol': 'superadmin', 'activo': True})
        
        self.client.force_login(self.dirigente)
        session = self.client.session
        session['current_organizacion_id'] = self.org.id
        session.save()

        u1 = User.objects.create_user(username='r1', password='password123')
        u2 = User.objects.create_user(username='r2', password='password123')
        f1 = FichaJugador.objects.create(user=u1, organizacion=self.org, equipo=self.equipo, nro_cedula='2001', estado_validacion='pendiente')
        f2 = FichaJugador.objects.create(user=u2, organizacion=self.org, equipo=self.equipo, nro_cedula='2002', estado_validacion='pendiente')

        response = self.client.post('/secretaria/rechazar-masivo/', {
            'fichas_jugador': [f1.id, f2.id],
            'motivo_rechazo': 'Fotos de cédula no son legibles.'
        })
        self.assertEqual(response.status_code, 302)
        
        f1.refresh_from_db()
        f2.refresh_from_db()
        self.assertEqual(f1.estado_validacion, 'rechazado')
        self.assertEqual(f2.estado_validacion, 'rechazado')
        self.assertEqual(f1.motivo_rechazo, 'Fotos de cédula no son legibles.')

    def test_firma_digital_se_normaliza_a_tinta_oscura_y_se_muestra_en_secretaria(self):
        """Firma en base64 con trazo claro se normaliza automáticamente a tinta oscura y se renderiza en secretaría"""
        import io, base64
        from PIL import Image

        # Crear imagen transparente con trazo blanco (simulando firma en pizarra negra)
        img = Image.new('RGBA', (60, 30), (0, 0, 0, 0))
        for x in range(30):
            img.putpixel((x, 15), (255, 255, 255, 255))
        buf = io.BytesIO()
        img.save(buf, format='PNG')
        firma_blanca = 'data:image/png;base64,' + base64.b64encode(buf.getvalue()).decode('utf-8')

        u = User.objects.create_user(username='firmante', password='password123', first_name='Carlos', last_name='Firmante')
        ficha = FichaJugador.objects.create(
            user=u, organizacion=self.org, equipo=self.equipo,
            nro_cedula='0999999999', estado_validacion='pendiente',
            firma_imagen=firma_blanca
        )
        
        # Verificar que se normalizó y se activó firma_digital=True
        ficha.refresh_from_db()
        self.assertTrue(ficha.firma_digital)
        header, b64data = ficha.firma_imagen.split(',', 1)
        im_res = Image.open(io.BytesIO(base64.b64decode(b64data)))
        pixel_test = im_res.getpixel((10, 15))
        self.assertEqual(pixel_test[:3], (15, 23, 42)) # Tinta oscura #0f172a

        # Verificar renderizado en secretaría
        self.dirigente.is_superuser = True
        self.dirigente.role = 'superadmin'
        self.dirigente.save()
        UsuarioOrganizacion.objects.get_or_create(usuario=self.dirigente, organizacion=self.org, defaults={'rol': 'superadmin', 'activo': True})

        self.client.force_login(self.dirigente)
        session = self.client.session
        session['current_organizacion_id'] = self.org.id
        session.save()

        response = self.client.get('/secretaria/')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Aceptada y Firmada')
        self.assertContains(response, 'data:image/png;base64,')

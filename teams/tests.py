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

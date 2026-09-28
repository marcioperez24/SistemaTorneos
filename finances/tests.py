from decimal import Decimal
from django.test import TestCase, Client
from django.urls import reverse
from django.utils import timezone
from users.models import CustomUser, Organizacion, UsuarioOrganizacion
from teams.models import Equipo, Categoria
from matches.models import Torneo, Partido, EventoPartido
from finances.models import PagoInscripcion, MultaTarjeta, MovimientoCaja

class FinanzasCuotasYTarjetasTests(TestCase):
    def setUp(self):
        self.org = Organizacion.objects.create(nombre="Liga Central", codigo="ligacentral")
        
        self.user_tesorero = CustomUser.objects.create_user(
            username="tesorero1",
            email="tesorero@test.com",
            password="password123",
            role="tesorero"
        )
        UsuarioOrganizacion.objects.create(
            usuario=self.user_tesorero,
            organizacion=self.org,
            rol="tesorero",
            activo=True
        )

        self.categoria = Categoria.objects.create(
            nombre="Primera A",
            organizacion=self.org
        )

        self.equipo_a = Equipo.objects.create(
            nombre="Equipo Alfa",
            categoria=self.categoria,
            dirigente=self.user_tesorero,
            organizacion=self.org
        )

        self.equipo_b = Equipo.objects.create(
            nombre="Equipo Beta",
            categoria=self.categoria,
            dirigente=self.user_tesorero,
            organizacion=self.org
        )

        self.torneo = Torneo.objects.create(
            nombre="Torneo Clausura",
            categoria=self.categoria,
            organizacion=self.org,
            costo_amarilla=Decimal('60.00'),
            costo_roja=Decimal('200.00')
        )

        self.partido = Partido.objects.create(
            torneo=self.torneo,
            equipo_local=self.equipo_a,
            equipo_visitante=self.equipo_b,
            fecha_hora=timezone.now(),
            organizacion=self.org
        )

        self.client = Client()
        self.client.login(username="tesorero1", password="password123")
        session = self.client.session
        session['current_organizacion_id'] = self.org.id
        session.save()

    def test_modificar_cuota_equipo(self):
        """Verifica que el tesorero puede modificar el valor de la cuota por equipo."""
        pago, _ = PagoInscripcion.objects.get_or_create(
            equipo=self.equipo_a,
            organizacion=self.org,
            defaults={'monto': Decimal('1500.00'), 'estado': 'pendiente'}
        )

        url = reverse('modificar_cuota_equipo', kwargs={'pago_id': pago.id})
        response = self.client.post(url, {
            'monto': '1850.50',
            'notas': 'Descuento especial retirado'
        })
        self.assertEqual(response.status_code, 302)

        pago.refresh_from_db()
        self.assertEqual(pago.monto, Decimal('1850.50'))
        self.assertEqual(pago.notas.upper(), 'DESCUENTO ESPECIAL RETIRADO')

    def test_registrar_pago_con_monto_ajustado(self):
        """Verifica que al registrar el pago se puede ajustar el monto final."""
        pago, _ = PagoInscripcion.objects.get_or_create(
            equipo=self.equipo_b,
            organizacion=self.org,
            defaults={'monto': Decimal('1500.00'), 'estado': 'pendiente'}
        )

        url = reverse('registrar_pago_inscripcion', kwargs={'pago_id': pago.id})
        response = self.client.post(url, {
            'monto': '1400.00',
            'metodo_pago': 'transferencia'
        })
        self.assertEqual(response.status_code, 302)

        pago.refresh_from_db()
        self.assertEqual(pago.estado, 'pagado')
        self.assertEqual(pago.monto, Decimal('1400.00'))
        self.assertEqual(pago.metodo_pago, 'transferencia')

        # Verificar movimiento de caja
        mov = MovimientoCaja.objects.filter(tipo='ingreso', monto=Decimal('1400.00')).first()
        self.assertIsNotNone(mov)
        self.assertIn("EQUIPO BETA", mov.concepto.upper())

    def test_evento_tarjeta_roja_genera_multa_automatica(self):
        """Al crearse una tarjeta roja en un partido, se genera automáticamente la MultaTarjeta con el costo del torneo."""
        evento = EventoPartido.objects.create(
            partido=self.partido,
            equipo=self.equipo_a,
            tipo='roja',
            minuto=75
        )

        multa = MultaTarjeta.objects.filter(evento=evento).first()
        self.assertIsNotNone(multa)
        self.assertEqual(multa.motivo, 'roja')
        self.assertEqual(multa.monto, Decimal('200.00')) # Definido en torneo.costo_roja
        self.assertEqual(multa.estado, 'pendiente')

    def test_auto_sincronizacion_tarjetas_en_resumen(self):
        """Tarjetas rojas preexistentes sin multa se sincronizan al entrar a resumen_financiero."""
        evento_previo = EventoPartido.objects.create(
            partido=self.partido,
            equipo=self.equipo_b,
            tipo='roja',
            minuto=82
        )
        # Eliminamos la multa que generó el signal para simular una tarjeta huérfana de multa
        MultaTarjeta.objects.filter(evento=evento_previo).delete()
        self.assertFalse(MultaTarjeta.objects.filter(evento=evento_previo).exists())

        # El tesorero visita resumen_financiero
        url = reverse('resumen_financiero')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

        # Debe haberse sincronizado y creado la multa por tarjeta roja
        multa = MultaTarjeta.objects.filter(evento=evento_previo).first()
        self.assertIsNotNone(multa)
        self.assertEqual(multa.motivo, 'roja')
        self.assertEqual(multa.monto, Decimal('200.00'))

    def test_registrar_multa_manual(self):
        """Permite al tesorero registrar una sanción / multa manual para un equipo."""
        url = reverse('registrar_multa_manual')
        response = self.client.post(url, {
            'equipo_id': self.equipo_a.id,
            'motivo': 'roja',
            'monto': '175.00'
        })
        self.assertEqual(response.status_code, 302)

        multa = MultaTarjeta.objects.filter(equipo=self.equipo_a, monto=Decimal('175.00')).first()
        self.assertIsNotNone(multa)
        self.assertEqual(multa.motivo, 'roja')
        self.assertEqual(multa.estado, 'pendiente')

    def test_pagar_multa_sin_jugador(self):
        """Verifica que una multa asignada directamente al equipo puede cobrarse sin error."""
        multa = MultaTarjeta.objects.create(
            organizacion=self.org,
            equipo=self.equipo_a,
            motivo='roja',
            monto=Decimal('200.00'),
            estado='pendiente'
        )

        url = reverse('pagar_multa', kwargs={'multa_id': multa.id})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 302)

        multa.refresh_from_db()
        self.assertEqual(multa.estado, 'pagado')
        self.assertIsNotNone(multa.fecha_pago)

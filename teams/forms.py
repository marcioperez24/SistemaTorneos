from django import forms
from django.contrib.auth import get_user_model
from .models import Equipo, FichaJugador, FichaDT, Categoria

User = get_user_model()

class EquipoForm(forms.ModelForm):
    class Meta:
        model = Equipo
        fields = ['nombre', 'logo', 'categorias', 'max_jugadores']
        widgets = {
            'nombre': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ej. Real Madrid'}),
            'logo': forms.ClearableFileInput(attrs={'class': 'form-control'}),
            'categorias': forms.CheckboxSelectMultiple(attrs={'class': 'form-check-input'}),
            'max_jugadores': forms.NumberInput(attrs={'class': 'form-control', 'min': '5', 'max': '50'}),
        }
        labels = {
            'nombre': 'Nombre del Equipo / Club',
            'logo': 'Escudo / Logo',
            'categorias': 'Categorías en las que participa',
            'max_jugadores': 'Máximo de Jugadores por Plantilla',
        }
        help_texts = {
            'categorias': 'Selecciona todas las categorías en las que este club compite (ej. Senior, Máster, Femenino).',
        }

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        organizacion = kwargs.pop('organizacion', None)
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk:
            self.fields['categorias'].required = False
        else:
            self.fields['categorias'].required = False
            
        if user and user.role == 'dirigente':
            if self.instance and self.instance.pk:
                self.fields['nombre'].disabled = True
                self.fields['logo'].disabled = True
        if organizacion:
            self.instance.organizacion = organizacion
            self.fields['categorias'].queryset = Categoria.objects.filter(organizacion=organizacion).order_by('nombre')


class PlayerRegistrationForm(forms.ModelForm):
    # Campos de User
    username = forms.CharField(max_length=150, required=False, widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Usuario único'}))
    email = forms.EmailField(required=False, widget=forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'ejemplo@correo.com'}))
    first_name = forms.CharField(max_length=150, widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Tus nombres'}))
    last_name = forms.CharField(max_length=150, widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Tus apellidos'}))
    telefono = forms.CharField(max_length=20, label="Teléfono de Contacto", widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ej. +593987654321'}))
    password = forms.CharField(required=False, widget=forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': 'Crea una contraseña segura'}))

    class Meta:
        model = FichaJugador
        fields = [
            'foto', 'cedula_frontal', 'cedula_posterior', 
            'nro_cedula', 'numero_camiseta',
            'tipo_sangre', 'contacto_emergencia', 'telefono_emergencia', 
            'firma_digital', 'firma_imagen'
        ]
        widgets = {
            'foto': forms.ClearableFileInput(attrs={'class': 'form-control', 'required': True}),
            'cedula_frontal': forms.ClearableFileInput(attrs={'class': 'form-control', 'required': True}),
            'cedula_posterior': forms.ClearableFileInput(attrs={'class': 'form-control', 'required': True}),
            'nro_cedula': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ej. 1712345678', 'required': True}),
            'numero_camiseta': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'Ej. 10', 'required': True}),
            'tipo_sangre': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ej. O+'}),
            'contacto_emergencia': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Nombre de un familiar'}),
            'telefono_emergencia': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Número del familiar'}),
            'firma_digital': forms.CheckboxInput(attrs={'class': 'form-check-input', 'required': True}),
            'firma_imagen': forms.HiddenInput(),
        }

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        self.equipo = kwargs.pop('equipo', None)
        super().__init__(*args, **kwargs)
        if self.user:
            # Eliminar campos de cuenta ya que ya está logueado
            self.fields.pop('username', None)
            self.fields.pop('email', None)
            self.fields.pop('password', None)
            # Inicializar nombres y teléfono del usuario existente
            self.fields['first_name'].initial = self.user.first_name
            self.fields['last_name'].initial = self.user.last_name
            self.fields['telefono'].initial = self.user.telefono

    def clean_numero_camiseta(self):
        numero = self.cleaned_data.get('numero_camiseta')
        if numero is not None:
            if numero < 1 or numero > 99:
                raise forms.ValidationError("El número de camiseta debe estar entre 1 y 99.")
            equipo = self.equipo or getattr(self.instance, 'equipo', None)
            if equipo:
                qs = FichaJugador.objects.filter(
                    equipo=equipo,
                    numero_camiseta=numero
                ).exclude(estado_validacion='rechazado')
                if self.instance and self.instance.pk:
                    qs = qs.exclude(pk=self.instance.pk)
                if self.user:
                    qs = qs.exclude(user=self.user)
                if qs.exists():
                    jugador_ocupante = qs.first()
                    nombre_ocupante = jugador_ocupante.user.get_full_name() or jugador_ocupante.user.username
                    raise forms.ValidationError(
                        f"El número de camiseta #{numero} ya está asignado a {nombre_ocupante} en el equipo '{equipo.nombre}'. Por favor, elige otro dorsal."
                    )
        return numero

    def clean_username(self):
        if self.user:
            return None
        username = self.cleaned_data.get('username')
        cedula = self.data.get('nro_cedula', '').strip()
        if not username:
            if cedula:
                username = f"jug_{cedula}"
            else:
                raise forms.ValidationError("Este campo es obligatorio.")
        return username

    def clean_email(self):
        if self.user:
            return None
        email = self.cleaned_data.get('email')
        username = self.cleaned_data.get('username') or self.data.get('nro_cedula', '').strip()
        if not email:
            email = f"{username}@torneos.com"
        return email

    def clean(self):
        cleaned_data = super().clean()
        if cleaned_data.get('firma_imagen'):
            cleaned_data['firma_digital'] = True
        return cleaned_data

    def save(self, commit=True, equipo=None, organizacion=None):
        cedula = self.cleaned_data.get('nro_cedula', '').strip()
        org = organizacion or (equipo.organizacion if equipo and hasattr(equipo, 'organizacion') else None)
        
        if self.user:
            user = self.user
            user.first_name = self.cleaned_data.get('first_name', user.first_name)
            user.last_name = self.cleaned_data.get('last_name', user.last_name)
            user.telefono = self.cleaned_data.get('telefono', user.telefono)
            user.save()
        else:
            username = self.cleaned_data.get('username') or (f"jug_{cedula}" if cedula else "jug_usuario")
            email = self.cleaned_data.get('email') or f"{username}@torneos.com"
            password = self.cleaned_data.get('password') or cedula or "123456"
            
            # 1. Buscar si ya existe un usuario por cédula en FichaJugador o FichaDT
            existing_user = None
            if cedula:
                f_jug = FichaJugador.objects.filter(nro_cedula=cedula).first()
                if f_jug:
                    existing_user = f_jug.user
                else:
                    f_dt = FichaDT.objects.filter(nro_cedula=cedula).first()
                    if f_dt:
                        existing_user = f_dt.user
                        
            # 2. Si no por cédula, buscar por username
            if not existing_user:
                existing_user = User.objects.filter(username=username).first()
                    
            if existing_user:
                user = existing_user
                if self.cleaned_data.get('first_name'):
                    user.first_name = self.cleaned_data['first_name']
                if self.cleaned_data.get('last_name'):
                    user.last_name = self.cleaned_data['last_name']
                if self.cleaned_data.get('telefono'):
                    user.telefono = self.cleaned_data['telefono']
                user.save()
            else:
                base_username = username
                counter = 1
                while User.objects.filter(username=username).exists():
                    username = f"{base_username}_{counter}"
                    counter += 1

                user = User.objects.create_user(
                    username=username,
                    email=email,
                    password=password,
                    first_name=self.cleaned_data.get('first_name', ''),
                    last_name=self.cleaned_data.get('last_name', ''),
                    role='jugador'
                )
                if self.cleaned_data.get('telefono'):
                    user.telefono = self.cleaned_data['telefono']
                    user.save()
        
        # Vincular usuario a la organización
        if org and user:
            from users.models import UsuarioOrganizacion
            UsuarioOrganizacion.objects.get_or_create(
                usuario=user,
                organizacion=org,
                defaults={'rol': 'jugador', 'activo': True}
            )

        # Crear la FichaJugador
        ficha = super().save(commit=False)
        ficha.user = user
        ficha.equipo = equipo
        if org:
            ficha.organizacion = org
        ficha.estado_validacion = 'pendiente'
        if ficha.firma_imagen:
            ficha.firma_digital = True
        
        if commit:
            ficha.save()
        return ficha


class DTRegistrationForm(forms.ModelForm):
    # Campos de User
    username = forms.CharField(max_length=150, required=False, widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Usuario único'}))
    email = forms.EmailField(required=False, widget=forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'ejemplo@correo.com'}))
    first_name = forms.CharField(max_length=150, widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Tus nombres'}))
    last_name = forms.CharField(max_length=150, widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Tus apellidos'}))
    telefono = forms.CharField(max_length=20, label="Teléfono de Contacto", widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ej. +593987654321'}))
    password = forms.CharField(required=False, widget=forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': 'Crea una contraseña segura'}))

    class Meta:
        model = FichaDT
        fields = [
            'foto', 'cedula_frontal', 'cedula_posterior', 
            'nro_cedula',
            'tipo_sangre', 'contacto_emergencia', 'telefono_emergencia', 
            'firma_digital', 'firma_imagen'
        ]
        widgets = {
            'foto': forms.ClearableFileInput(attrs={'class': 'form-control', 'required': True}),
            'cedula_frontal': forms.ClearableFileInput(attrs={'class': 'form-control', 'required': True}),
            'cedula_posterior': forms.ClearableFileInput(attrs={'class': 'form-control', 'required': True}),
            'nro_cedula': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ej. 1712345678', 'required': True}),
            'tipo_sangre': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ej. O+'}),
            'contacto_emergencia': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Nombre de un familiar'}),
            'telefono_emergencia': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Número del familiar'}),
            'firma_digital': forms.CheckboxInput(attrs={'class': 'form-check-input', 'required': True}),
            'firma_imagen': forms.HiddenInput(),
        }

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        if self.user:
            # Eliminar campos de cuenta ya que ya está logueado
            self.fields.pop('username', None)
            self.fields.pop('email', None)
            self.fields.pop('password', None)
            # Inicializar nombres y teléfono del usuario existente
            self.fields['first_name'].initial = self.user.first_name
            self.fields['last_name'].initial = self.user.last_name
            self.fields['telefono'].initial = self.user.telefono

    def clean_username(self):
        if self.user:
            return None
        username = self.cleaned_data.get('username')
        cedula = self.data.get('nro_cedula', '').strip()
        if not username:
            if cedula:
                username = f"dt_{cedula}"
            else:
                raise forms.ValidationError("Este campo es obligatorio.")
        return username

    def clean_email(self):
        if self.user:
            return None
        email = self.cleaned_data.get('email')
        username = self.cleaned_data.get('username') or self.data.get('nro_cedula', '').strip()
        if not email:
            email = f"{username}@torneos.com"
        return email

    def clean(self):
        cleaned_data = super().clean()
        if cleaned_data.get('firma_imagen'):
            cleaned_data['firma_digital'] = True
        return cleaned_data

    def save(self, commit=True, equipo=None, organizacion=None):
        cedula = self.cleaned_data.get('nro_cedula', '').strip()
        org = organizacion or (equipo.organizacion if equipo and hasattr(equipo, 'organizacion') else None)
        
        if self.user:
            user = self.user
            user.first_name = self.cleaned_data.get('first_name', user.first_name)
            user.last_name = self.cleaned_data.get('last_name', user.last_name)
            user.telefono = self.cleaned_data.get('telefono', user.telefono)
            user.save()
        else:
            username = self.cleaned_data.get('username') or (f"dt_{cedula}" if cedula else "dt_usuario")
            email = self.cleaned_data.get('email') or f"{username}@torneos.com"
            password = self.cleaned_data.get('password') or cedula or "123456"
            
            existing_user = None
            if cedula:
                f_dt = FichaDT.objects.filter(nro_cedula=cedula).first()
                if f_dt:
                    existing_user = f_dt.user
                else:
                    f_jug = FichaJugador.objects.filter(nro_cedula=cedula).first()
                    if f_jug:
                        existing_user = f_jug.user
                        
            if not existing_user:
                existing_user = User.objects.filter(username=username).first()
                    
            if existing_user:
                user = existing_user
                if self.cleaned_data.get('first_name'):
                    user.first_name = self.cleaned_data['first_name']
                if self.cleaned_data.get('last_name'):
                    user.last_name = self.cleaned_data['last_name']
                if self.cleaned_data.get('telefono'):
                    user.telefono = self.cleaned_data['telefono']
                user.save()
            else:
                base_username = username
                counter = 1
                while User.objects.filter(username=username).exists():
                    username = f"{base_username}_{counter}"
                    counter += 1

                user = User.objects.create_user(
                    username=username,
                    email=email,
                    password=password,
                    first_name=self.cleaned_data.get('first_name', ''),
                    last_name=self.cleaned_data.get('last_name', ''),
                    role='dt'
                )
                if self.cleaned_data.get('telefono'):
                    user.telefono = self.cleaned_data['telefono']
                    user.save()
        
        # Vincular usuario a la organización
        if org and user:
            from users.models import UsuarioOrganizacion
            UsuarioOrganizacion.objects.get_or_create(
                usuario=user,
                organizacion=org,
                defaults={'rol': 'dt', 'activo': True}
            )

        # Crear la FichaDT
        ficha = super().save(commit=False)
        ficha.user = user
        ficha.equipo = equipo
        if org:
            ficha.organizacion = org
        ficha.estado_validacion = 'pendiente'
        if ficha.firma_imagen:
            ficha.firma_digital = True
        
        if commit:
            ficha.save()
        return ficha


class CategoriaForm(forms.ModelForm):
    class Meta:
        model = Categoria
        fields = ['nombre']
        widgets = {
            'nombre': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ej. Sub-12 (U-12)'}),
        }
        labels = {
            'nombre': 'Nombre de la Categoría',
        }


class PlayerEditForm(forms.ModelForm):
    first_name = forms.CharField(max_length=150, label="Nombres", widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Nombres del jugador'}))
    last_name = forms.CharField(max_length=150, label="Apellidos", widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Apellidos del jugador'}))
    email = forms.EmailField(required=False, label="Correo Electrónico", widget=forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'correo@ejemplo.com'}))
    telefono = forms.CharField(max_length=20, required=False, label="Teléfono / WhatsApp", widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ej. 0987654321'}))

    class Meta:
        model = FichaJugador
        fields = [
            'nro_cedula', 'numero_camiseta', 'equipo', 'torneo',
            'estado_validacion', 'motivo_rechazo', 'partidos_suspension', 'es_lesionado',
            'tipo_sangre', 'contacto_emergencia', 'telefono_emergencia',
            'foto', 'cedula_frontal', 'cedula_posterior'
        ]
        widgets = {
            'nro_cedula': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ej. 1712345678'}),
            'numero_camiseta': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'Ej. 10', 'min': '1', 'max': '99'}),
            'equipo': forms.Select(attrs={'class': 'form-select'}),
            'torneo': forms.Select(attrs={'class': 'form-select'}),
            'estado_validacion': forms.Select(attrs={'class': 'form-select'}),
            'motivo_rechazo': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Motivo si se rechaza'}),
            'partidos_suspension': forms.NumberInput(attrs={'class': 'form-control', 'min': '0'}),
            'es_lesionado': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'tipo_sangre': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ej. O+'}),
            'contacto_emergencia': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Nombre familiar'}),
            'telefono_emergencia': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Teléfono emergencia'}),
            'foto': forms.ClearableFileInput(attrs={'class': 'form-control'}),
            'cedula_frontal': forms.ClearableFileInput(attrs={'class': 'form-control'}),
            'cedula_posterior': forms.ClearableFileInput(attrs={'class': 'form-control'}),
        }
        labels = {
            'nro_cedula': 'Número de Cédula / Identificación',
            'numero_camiseta': 'Número de Camiseta (Dorsal)',
            'equipo': 'Equipo / Club Asignado',
            'torneo': 'Torneo / Campeonato',
            'estado_validacion': 'Estado del Carnet (Secretaría)',
            'motivo_rechazo': 'Observación / Motivo de Rechazo',
            'partidos_suspension': 'Partidos de Suspensión',
            'es_lesionado': 'Reportar como Lesionado (Libera cupo)',
            'tipo_sangre': 'Tipo de Sangre',
            'contacto_emergencia': 'Contacto de Emergencia',
            'telefono_emergencia': 'Teléfono de Emergencia',
            'foto': 'Foto de Perfil / Selfie Carnet',
            'cedula_frontal': 'Cédula Frontal',
            'cedula_posterior': 'Cédula Posterior',
        }

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        self.organizacion = kwargs.pop('organizacion', None)
        super().__init__(*args, **kwargs)

        if self.instance and self.instance.user:
            self.fields['first_name'].initial = self.instance.user.first_name
            self.fields['last_name'].initial = self.instance.user.last_name
            self.fields['email'].initial = self.instance.user.email
            self.fields['telefono'].initial = self.instance.user.telefono

        from matches.models import Torneo
        if self.organizacion:
            self.fields['equipo'].queryset = Equipo.objects.filter(organizacion=self.organizacion).order_by('nombre')
            self.fields['torneo'].queryset = Torneo.objects.filter(organizacion=self.organizacion).order_by('-id')

        es_admin = (self.user and (self.user.role in ['superadmin', 'comision', 'secretaria'] or self.user.is_superuser))
        if not es_admin:
            self.fields['estado_validacion'].disabled = True
            self.fields['motivo_rechazo'].disabled = True
            self.fields['partidos_suspension'].disabled = True
            if self.user and self.user.role == 'dirigente':
                self.fields['equipo'].disabled = True

    def clean_numero_camiseta(self):
        numero = self.cleaned_data.get('numero_camiseta')
        equipo = self.cleaned_data.get('equipo') or (self.instance.equipo if self.instance else None)
        if numero is not None and equipo:
            if numero < 1 or numero > 99:
                raise forms.ValidationError("El número de camiseta debe estar entre 1 y 99.")
            qs = FichaJugador.objects.filter(
                equipo=equipo,
                numero_camiseta=numero
            ).exclude(estado_validacion='rechazado')
            if self.instance and self.instance.pk:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                ocupante = qs.first()
                nombre_oc = ocupante.user.get_full_name() or ocupante.user.username
                raise forms.ValidationError(
                    f"El dorsal #{numero} ya está asignado a {nombre_oc} en el equipo '{equipo.nombre}'."
                )
        return numero

    def save(self, commit=True):
        ficha = super().save(commit=False)
        if ficha.user:
            user = ficha.user
            user.first_name = self.cleaned_data.get('first_name', user.first_name)
            user.last_name = self.cleaned_data.get('last_name', user.last_name)
            user.email = self.cleaned_data.get('email', user.email)
            user.telefono = self.cleaned_data.get('telefono', user.telefono)
            user.save()
        if commit:
            ficha.save()
        return ficha


class DTEditForm(forms.ModelForm):
    first_name = forms.CharField(max_length=150, label="Nombres", widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Nombres'}))
    last_name = forms.CharField(max_length=150, label="Apellidos", widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Apellidos'}))
    email = forms.EmailField(required=False, label="Correo Electrónico", widget=forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'correo@ejemplo.com'}))
    telefono = forms.CharField(max_length=20, required=False, label="Teléfono / WhatsApp", widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ej. 0987654321'}))

    class Meta:
        model = FichaDT
        fields = [
            'nro_cedula', 'equipo', 'torneo',
            'estado_validacion', 'motivo_rechazo',
            'tipo_sangre', 'contacto_emergencia', 'telefono_emergencia',
            'foto', 'cedula_frontal', 'cedula_posterior'
        ]
        widgets = {
            'nro_cedula': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ej. 1712345678'}),
            'equipo': forms.Select(attrs={'class': 'form-select'}),
            'torneo': forms.Select(attrs={'class': 'form-select'}),
            'estado_validacion': forms.Select(attrs={'class': 'form-select'}),
            'motivo_rechazo': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Motivo si se rechaza'}),
            'tipo_sangre': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ej. O+'}),
            'contacto_emergencia': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Nombre familiar'}),
            'telefono_emergencia': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Teléfono emergencia'}),
            'foto': forms.ClearableFileInput(attrs={'class': 'form-control'}),
            'cedula_frontal': forms.ClearableFileInput(attrs={'class': 'form-control'}),
            'cedula_posterior': forms.ClearableFileInput(attrs={'class': 'form-control'}),
        }
        labels = {
            'nro_cedula': 'Número de Cédula / Identificación',
            'equipo': 'Equipo / Club Asignado',
            'torneo': 'Torneo / Campeonato',
            'estado_validacion': 'Estado del Carnet (Secretaría)',
            'motivo_rechazo': 'Observación / Motivo de Rechazo',
            'tipo_sangre': 'Tipo de Sangre',
            'contacto_emergencia': 'Contacto de Emergencia',
            'telefono_emergencia': 'Teléfono de Emergencia',
            'foto': 'Foto de Perfil / Carnet',
            'cedula_frontal': 'Cédula Frontal',
            'cedula_posterior': 'Cédula Posterior',
        }

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        self.organizacion = kwargs.pop('organizacion', None)
        super().__init__(*args, **kwargs)

        if self.instance and self.instance.user:
            self.fields['first_name'].initial = self.instance.user.first_name
            self.fields['last_name'].initial = self.instance.user.last_name
            self.fields['email'].initial = self.instance.user.email
            self.fields['telefono'].initial = self.instance.user.telefono

        from matches.models import Torneo
        if self.organizacion:
            self.fields['equipo'].queryset = Equipo.objects.filter(organizacion=self.organizacion).order_by('nombre')
            self.fields['torneo'].queryset = Torneo.objects.filter(organizacion=self.organizacion).order_by('-id')

        es_admin = (self.user and (self.user.role in ['superadmin', 'comision', 'secretaria'] or self.user.is_superuser))
        if not es_admin:
            self.fields['estado_validacion'].disabled = True
            self.fields['motivo_rechazo'].disabled = True
            if self.user and self.user.role == 'dirigente':
                self.fields['equipo'].disabled = True

    def save(self, commit=True):
        ficha = super().save(commit=False)
        if ficha.user:
            user = ficha.user
            user.first_name = self.cleaned_data.get('first_name', user.first_name)
            user.last_name = self.cleaned_data.get('last_name', user.last_name)
            user.email = self.cleaned_data.get('email', user.email)
            user.telefono = self.cleaned_data.get('telefono', user.telefono)
            user.save()
        if commit:
            ficha.save()
        return ficha

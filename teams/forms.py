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

    def save(self, commit=True, equipo=None, organizacion=None):
        cedula = self.cleaned_data.get('nro_cedula', '').strip()
        
        if self.user:
            user = self.user
            user.first_name = self.cleaned_data.get('first_name', user.first_name)
            user.last_name = self.cleaned_data.get('last_name', user.last_name)
            user.telefono = self.cleaned_data.get('telefono', user.telefono)
            user.save()
        else:
            username = self.cleaned_data.get('username') or f"jug_{cedula}"
            email = self.cleaned_data.get('email') or f"{username}@torneos.com"
            password = self.cleaned_data.get('password') or cedula or "123456"
            
            # Verificar si ya existe un usuario por username o cedula
            existing_user = User.objects.filter(username=username).first()
            if not existing_user and cedula:
                f_jug = FichaJugador.objects.filter(nro_cedula=cedula).first()
                if f_jug:
                    existing_user = f_jug.user
                    
            if existing_user:
                user = existing_user
                user.first_name = self.cleaned_data.get('first_name', user.first_name)
                user.last_name = self.cleaned_data.get('last_name', user.last_name)
                user.telefono = self.cleaned_data.get('telefono', user.telefono)
                user.save()
            else:
                user = User.objects.create_user(
                    username=username,
                    email=email,
                    password=password,
                    first_name=self.cleaned_data['first_name'],
                    last_name=self.cleaned_data['last_name'],
                    role='jugador'
                )
                user.telefono = self.cleaned_data['telefono']
                user.save()
        
        # 2. Crear la FichaJugador
        ficha = super().save(commit=False)
        ficha.user = user
        ficha.equipo = equipo
        org = organizacion or (equipo.organizacion if equipo and hasattr(equipo, 'organizacion') else None)
        if org:
            ficha.organizacion = org
        ficha.estado_validacion = 'pendiente'
        
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

    def save(self, commit=True, equipo=None, organizacion=None):
        cedula = self.cleaned_data.get('nro_cedula', '').strip()
        
        if self.user:
            user = self.user
            user.first_name = self.cleaned_data.get('first_name', user.first_name)
            user.last_name = self.cleaned_data.get('last_name', user.last_name)
            user.telefono = self.cleaned_data.get('telefono', user.telefono)
            user.save()
        else:
            username = self.cleaned_data.get('username') or f"dt_{cedula}"
            email = self.cleaned_data.get('email') or f"{username}@torneos.com"
            password = self.cleaned_data.get('password') or cedula or "123456"
            
            existing_user = User.objects.filter(username=username).first()
            if not existing_user and cedula:
                f_dt = FichaDT.objects.filter(nro_cedula=cedula).first()
                if f_dt:
                    existing_user = f_dt.user
                    
            if existing_user:
                user = existing_user
                user.first_name = self.cleaned_data.get('first_name', user.first_name)
                user.last_name = self.cleaned_data.get('last_name', user.last_name)
                user.telefono = self.cleaned_data.get('telefono', user.telefono)
                user.save()
            else:
                user = User.objects.create_user(
                    username=username,
                    email=email,
                    password=password,
                    first_name=self.cleaned_data['first_name'],
                    last_name=self.cleaned_data['last_name'],
                    role='dt'
                )
                user.telefono = self.cleaned_data['telefono']
                user.save()
        
        # 2. Crear la FichaDT
        ficha = super().save(commit=False)
        ficha.user = user
        ficha.equipo = equipo
        org = organizacion or (equipo.organizacion if equipo and hasattr(equipo, 'organizacion') else None)
        if org:
            ficha.organizacion = org
        ficha.estado_validacion = 'pendiente'
        
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

from django import forms
from django.contrib.auth import get_user_model
from .models import Equipo, FichaJugador

User = get_user_model()

class EquipoForm(forms.ModelForm):
    class Meta:
        model = Equipo
        fields = ['nombre', 'logo', 'categoria', 'entrenador', 'telefono_entrenador']
        widgets = {
            'nombre': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ej. Real Madrid'}),
            'logo': forms.ClearableFileInput(attrs={'class': 'form-control'}),
            'categoria': forms.Select(attrs={'class': 'form-select'}),
            'entrenador': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Nombre del Entrenador / Director Técnico'}),
            'telefono_entrenador': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ej. +56912345678'}),
        }

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        if user and user.role == 'dirigente':
            self.fields['nombre'].disabled = True
            self.fields['logo'].disabled = True
            self.fields['categoria'].disabled = True


class PlayerRegistrationForm(forms.ModelForm):
    # Campos de User
    username = forms.CharField(max_length=150, widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Usuario único'}))
    email = forms.EmailField(widget=forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'ejemplo@correo.com'}))
    first_name = forms.CharField(max_length=150, widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Tus nombres'}))
    last_name = forms.CharField(max_length=150, widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Tus apellidos'}))
    telefono = forms.CharField(max_length=20, label="Teléfono de Contacto", widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ej. +593987654321'}))
    password = forms.CharField(widget=forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': 'Crea una contraseña segura'}))

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

    def clean_username(self):
        username = self.cleaned_data.get('username')
        if User.objects.filter(username=username).exists():
            raise forms.ValidationError("Este nombre de usuario ya está registrado.")
        return username

    def clean_email(self):
        email = self.cleaned_data.get('email')
        if User.objects.filter(email=email).exists():
            raise forms.ValidationError("Este correo electrónico ya está registrado.")
        return email

    def save(self, commit=True, equipo=None):
        # 1. Crear el CustomUser
        user = User.objects.create_user(
            username=self.cleaned_data['username'],
            email=self.cleaned_data['email'],
            password=self.cleaned_data['password'],
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
        ficha.estado_validacion = 'pendiente'
        
        if commit:
            ficha.save()
        return ficha

from django import forms
from django.contrib.auth import get_user_model

User = get_user_model()

class ArbitroForm(forms.ModelForm):
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': 'Crea una contraseña segura'}),
        label="Contraseña"
    )
    
    class Meta:
        model = User
        fields = ['username', 'first_name', 'last_name', 'email', 'telefono', 'password']
        widgets = {
            'username': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Nombre de usuario único'}),
            'first_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ej. Juan'}),
            'last_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ej. Pérez'}),
            'email': forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'Ej. juan.perez@example.com'}),
            'telefono': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ej. +56912345678'}),
        }
        labels = {
            'username': 'Nombre de Usuario',
            'first_name': 'Nombre(s)',
            'last_name': 'Apellido(s)',
            'email': 'Correo Electrónico',
            'telefono': 'Teléfono / Celular',
        }

    def clean_username(self):
        username = self.cleaned_data.get('username')
        if User.objects.filter(username=username).exists():
            raise forms.ValidationError("Este nombre de usuario ya está registrado.")
        return username

    def clean_email(self):
        email = self.cleaned_data.get('email')
        if email and User.objects.filter(email=email).exists():
            raise forms.ValidationError("Este correo electrónico ya está registrado.")
        return email

    def save(self, commit=True):
        user = User.objects.create_user(
            username=self.cleaned_data['username'],
            email=self.cleaned_data['email'],
            password=self.cleaned_data['password'],
            first_name=self.cleaned_data['first_name'],
            last_name=self.cleaned_data['last_name'],
            role='arbitro',
            telefono=self.cleaned_data.get('telefono')
        )
        return user


class VocalForm(forms.ModelForm):
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': 'Crea una contraseña segura'}),
        label="Contraseña"
    )
    
    class Meta:
        model = User
        fields = ['username', 'first_name', 'last_name', 'email', 'telefono', 'password']
        widgets = {
            'username': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Nombre de usuario único'}),
            'first_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ej. Carlos'}),
            'last_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ej. Gómez'}),
            'email': forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'Ej. carlos.gomez@example.com'}),
            'telefono': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ej. +56912345678'}),
        }
        labels = {
            'username': 'Nombre de Usuario',
            'first_name': 'Nombre(s)',
            'last_name': 'Apellido(s)',
            'email': 'Correo Electrónico',
            'telefono': 'Teléfono / Celular',
        }

    def clean_username(self):
        username = self.cleaned_data.get('username')
        if User.objects.filter(username=username).exists():
            raise forms.ValidationError("Este nombre de usuario ya está registrado.")
        return username

    def clean_email(self):
        email = self.cleaned_data.get('email')
        if email and User.objects.filter(email=email).exists():
            raise forms.ValidationError("Este correo electrónico ya está registrado.")
        return email

    def save(self, commit=True):
        user = User.objects.create_user(
            username=self.cleaned_data['username'],
            email=self.cleaned_data['email'],
            password=self.cleaned_data['password'],
            first_name=self.cleaned_data['first_name'],
            last_name=self.cleaned_data['last_name'],
            role='vocal',
            telefono=self.cleaned_data.get('telefono')
        )
        return user


from .models import Torneo

class TorneoForm(forms.ModelForm):
    class Meta:
        model = Torneo
        fields = ['nombre', 'tipo', 'categoria', 'temporada', 'modalidad', 'max_jugadores_por_equipo', 'limite_amarillas_suspension', 'costo_amarilla', 'equipos']
        widgets = {
            'nombre': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ej. Copa de Campeones 2026'}),
            'tipo': forms.Select(attrs={'class': 'form-select'}),
            'categoria': forms.Select(attrs={'class': 'form-select', 'id': 'id_categoria'}),
            'temporada': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ej. Apertura 2026'}),
            'modalidad': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ej. Fútbol 11, Fútbol 7'}),
            'max_jugadores_por_equipo': forms.NumberInput(attrs={'class': 'form-control', 'min': '5', 'max': '50'}),
            'limite_amarillas_suspension': forms.NumberInput(attrs={'class': 'form-control', 'min': '1', 'max': '10'}),
            'costo_amarilla': forms.NumberInput(attrs={'class': 'form-control', 'min': '0', 'step': '0.01'}),
            'equipos': forms.SelectMultiple(attrs={'class': 'form-select', 'size': '8'}),
        }
        labels = {
            'nombre': 'Nombre del Torneo / Liga',
            'tipo': 'Tipo de Competencia',
            'categoria': 'Categoría',
            'temporada': 'Temporada / Año',
            'modalidad': 'Modalidad',
            'max_jugadores_por_equipo': 'Máximo de Jugadores por Equipo',
            'limite_amarillas_suspension': 'Límite de Amarillas para Suspensión',
            'costo_amarilla': 'Costo de Tarjeta Amarilla ($)',
            'equipos': 'Equipos Participantes',
        }
        help_text = {
            'equipos': 'Mantén presionado Ctrl (o Cmd en Mac) para seleccionar múltiples equipos.',
        }

    def __init__(self, *args, **kwargs):
        organizacion = kwargs.pop('organizacion', None)
        super(TorneoForm, self).__init__(*args, **kwargs)
        if organizacion:
            self.fields['equipos'].queryset = self.fields['equipos'].queryset.filter(organizacion=organizacion)
            self.fields['categoria'].queryset = self.fields['categoria'].queryset.filter(organizacion=organizacion)


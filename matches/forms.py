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
        fields = ['nombre', 'tipo', 'temporada', 'equipos']
        widgets = {
            'nombre': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ej. Copa de Campeones 2026'}),
            'tipo': forms.Select(attrs={'class': 'form-select'}),
            'temporada': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ej. Apertura 2026'}),
            'equipos': forms.SelectMultiple(attrs={'class': 'form-select', 'size': '8'}),
        }
        labels = {
            'nombre': 'Nombre del Torneo / Liga',
            'tipo': 'Tipo de Competencia',
            'temporada': 'Temporada / Año',
            'equipos': 'Equipos Participantes',
        }
        help_text = {
            'equipos': 'Mantén presionado Ctrl (o Cmd en Mac) para seleccionar múltiples equipos.',
        }


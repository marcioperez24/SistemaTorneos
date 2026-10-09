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


class VocalEdicionForm(forms.ModelForm):
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': 'Dejar en blanco para mantener la contraseña actual'}),
        label="Nueva Contraseña (Opcional)",
        required=False
    )
    
    class Meta:
        model = User
        fields = ['username', 'first_name', 'last_name', 'email', 'telefono', 'password']
        widgets = {
            'username': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Nombre de usuario'}),
            'first_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ej. Carlos'}),
            'last_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ej. Gómez'}),
            'email': forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'Ej. carlos.gomez@example.com'}),
            'telefono': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ej. 0987654321'}),
        }
        labels = {
            'username': 'Nombre de Usuario',
            'first_name': 'Nombre(s)',
            'last_name': 'Apellido(s)',
            'email': 'Correo Electrónico',
            'telefono': 'Teléfono / Celular',
            'password': 'Nueva Contraseña (Opcional)',
        }

    def clean_username(self):
        username = self.cleaned_data.get('username')
        if User.objects.filter(username=username).exclude(id=self.instance.id).exists():
            raise forms.ValidationError("Este nombre de usuario ya pertenece a otra persona.")
        return username

    def clean_email(self):
        email = self.cleaned_data.get('email')
        if email and User.objects.filter(email=email).exclude(id=self.instance.id).exists():
            raise forms.ValidationError("Este correo electrónico ya está registrado.")
        return email

    def save(self, commit=True):
        vocal = super().save(commit=False)
        password = self.cleaned_data.get('password')
        if password:
            vocal.set_password(password)
        if commit:
            vocal.save()
        return vocal


class ArbitroEdicionForm(forms.ModelForm):
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': 'Dejar en blanco para mantener la contraseña actual'}),
        label="Nueva Contraseña (Opcional)",
        required=False
    )
    
    class Meta:
        model = User
        fields = ['username', 'first_name', 'last_name', 'email', 'telefono', 'password']
        widgets = {
            'username': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Nombre de usuario'}),
            'first_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ej. Juan'}),
            'last_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ej. Pérez'}),
            'email': forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'Ej. juan.perez@example.com'}),
            'telefono': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ej. 0987654321'}),
        }
        labels = {
            'username': 'Nombre de Usuario',
            'first_name': 'Nombre(s)',
            'last_name': 'Apellido(s)',
            'email': 'Correo Electrónico',
            'telefono': 'Teléfono / Celular',
            'password': 'Nueva Contraseña (Opcional)',
        }

    def clean_username(self):
        username = self.cleaned_data.get('username')
        if User.objects.filter(username=username).exclude(id=self.instance.id).exists():
            raise forms.ValidationError("Este nombre de usuario ya pertenece a otra persona.")
        return username

    def clean_email(self):
        email = self.cleaned_data.get('email')
        if email and User.objects.filter(email=email).exclude(id=self.instance.id).exists():
            raise forms.ValidationError("Este correo electrónico ya está registrado.")
        return email

    def save(self, commit=True):
        arbitro = super().save(commit=False)
        password = self.cleaned_data.get('password')
        if password:
            arbitro.set_password(password)
        if commit:
            arbitro.save()
        return arbitro


from .models import Torneo, Estadio

class EstadioForm(forms.ModelForm):
    class Meta:
        model = Estadio
        fields = ['nombre', 'direccion', 'ciudad', 'capacidad', 'activo']
        widgets = {
            'nombre': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ej. Estadio Bellavista'}),
            'direccion': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ej. Av. Bolivariana y El Rey'}),
            'ciudad': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ej. Ambato'}),
            'capacidad': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'Ej. 16000'}),
            'activo': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }
        labels = {
            'nombre': 'Nombre del Estadio / Cancha',
            'direccion': 'Dirección / Ubicación',
            'ciudad': 'Ciudad',
            'capacidad': 'Capacidad (Aprox.)',
            'activo': 'Estadio Activo / Habilitado',
        }


class TorneoForm(forms.ModelForm):
    class Meta:
        model = Torneo
        fields = [
            'nombre', 'tipo', 'categoria', 'temporada', 'modalidad', 
            'max_jugadores_por_equipo', 'limite_amarillas_suspension', 'costo_amarilla', 'costo_roja',
            'numero_grupos', 'clasificados_por_grupo', 'fase_eliminatoria_inicial',
            'equipos'
        ]
        widgets = {
            'nombre': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ej. Copa de Campeones 2026'}),
            'tipo': forms.Select(attrs={'class': 'form-select', 'id': 'id_tipo_competencia'}),
            'categoria': forms.Select(attrs={'class': 'form-select', 'id': 'id_categoria'}),
            'temporada': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ej. Apertura 2026'}),
            'modalidad': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ej. Fútbol 11, Fútbol 7'}),
            'max_jugadores_por_equipo': forms.NumberInput(attrs={'class': 'form-control', 'min': '5', 'max': '50'}),
            'limite_amarillas_suspension': forms.NumberInput(attrs={'class': 'form-control', 'min': '1', 'max': '10'}),
            'costo_amarilla': forms.NumberInput(attrs={'class': 'form-control', 'min': '0', 'step': '0.01'}),
            'costo_roja': forms.NumberInput(attrs={'class': 'form-control', 'min': '0', 'step': '0.01'}),
            'numero_grupos': forms.NumberInput(attrs={'class': 'form-control', 'min': '2', 'max': '16', 'value': '2'}),
            'clasificados_por_grupo': forms.NumberInput(attrs={'class': 'form-control', 'min': '1', 'max': '8', 'value': '2'}),
            'fase_eliminatoria_inicial': forms.Select(attrs={'class': 'form-select'}),
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
            'costo_roja': 'Costo de Tarjeta Roja ($)',
            'numero_grupos': 'Cantidad de Grupos (Fase 1)',
            'clasificados_por_grupo': 'Clasificados por Grupo a Eliminatorias',
            'fase_eliminatoria_inicial': 'Fase Eliminatoria Inicial (Playoffs)',
            'equipos': 'Equipos Participantes',
        }
        help_text = {
            'equipos': 'Mantén presionado Ctrl (o Cmd en Mac) para seleccionar múltiples equipos.',
            'numero_grupos': 'Ej. 2 grupos (A, B) o 4 grupos (A, B, C, D).',
            'clasificados_por_grupo': 'Ej. Los 2 primeros de cada grupo clasifican a la siguiente ronda.',
        }

    def __init__(self, *args, **kwargs):
        organizacion = kwargs.pop('organizacion', None)
        super(TorneoForm, self).__init__(*args, **kwargs)
        if organizacion:
            self.instance.organizacion = organizacion
            self.fields['equipos'].queryset = self.fields['equipos'].queryset.filter(organizacion=organizacion)
            self.fields['categoria'].queryset = self.fields['categoria'].queryset.filter(organizacion=organizacion)


class TorneoEdicionForm(forms.ModelForm):
    class Meta:
        model = Torneo
        fields = [
            'nombre', 'temporada', 'modalidad', 'max_jugadores_por_equipo', 
            'limite_amarillas_suspension', 'costo_amarilla', 'costo_roja', 'es_publico'
        ]
        widgets = {
            'nombre': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Nombre del torneo'}),
            'temporada': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ej. Temporada 2026'}),
            'modalidad': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ej. Fútbol 11'}),
            'max_jugadores_por_equipo': forms.NumberInput(attrs={'class': 'form-control', 'min': '5', 'max': '50'}),
            'limite_amarillas_suspension': forms.NumberInput(attrs={'class': 'form-control', 'min': '1', 'max': '10'}),
            'costo_amarilla': forms.NumberInput(attrs={'class': 'form-control', 'min': '0', 'step': '0.01'}),
            'costo_roja': forms.NumberInput(attrs={'class': 'form-control', 'min': '0', 'step': '0.01'}),
            'es_publico': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }
        labels = {
            'nombre': 'Nombre del Torneo / Liga',
            'temporada': 'Temporada / Año',
            'modalidad': 'Modalidad',
            'max_jugadores_por_equipo': 'Máximo de Jugadores por Equipo',
            'limite_amarillas_suspension': 'Límite Amarillas para Suspensión',
            'costo_amarilla': 'Costo de Tarjeta Amarilla ($)',
            'costo_roja': 'Costo de Tarjeta Roja ($)',
            'es_publico': 'Torneo Visible en Portal Público',
        }


from .models import GrupoTorneo, EquipoGrupoTorneo, Equipo

class GrupoTorneoForm(forms.ModelForm):
    class Meta:
        model = GrupoTorneo
        fields = ['nombre', 'sector', 'orden', 'cupos_clasificacion', 'formato_enfrentamientos', 'activo']
        widgets = {
            'nombre': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ej. Grupo A'}),
            'sector': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ej. Servicios, Comercio, Transporte'}),
            'orden': forms.NumberInput(attrs={'class': 'form-control', 'min': '1', 'value': '1'}),
            'cupos_clasificacion': forms.NumberInput(attrs={'class': 'form-control', 'min': '1', 'value': '4'}),
            'formato_enfrentamientos': forms.Select(attrs={'class': 'form-select'}),
            'activo': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }
        labels = {
            'nombre': 'Nombre del Grupo',
            'sector': 'Sector / Descripción',
            'orden': 'Orden de Presentación',
            'cupos_clasificacion': 'Cupos de Clasificación',
            'formato_enfrentamientos': 'Modalidad de Enfrentamientos',
            'activo': 'Grupo Activo',
        }

    def clean_cupos_clasificacion(self):
        cupos = self.cleaned_data.get('cupos_clasificacion')
        if cupos is not None and cupos < 1:
            raise forms.ValidationError("La cantidad de cupos de clasificación debe ser al menos 1.")
        return cupos

    def clean_orden(self):
        orden = self.cleaned_data.get('orden')
        if orden is not None and orden < 1:
            raise forms.ValidationError("El orden debe ser un número entero positivo mayor a 0.")
        return orden



from django import forms
from .models import Alert, SafetyResource


class AlertForm(forms.ModelForm):
    class Meta:
        model = Alert
        fields = ['title', 'message', 'priority', 'latitude', 'longitude', 'radius', 'expires_at']
        widgets = {
            'title': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Alert title'
            }),
            'message': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 4,
                'placeholder': 'Alert message...'
            }),
            'priority': forms.Select(attrs={
                'class': 'form-select'
            }),
            'latitude': forms.HiddenInput(),
            'longitude': forms.HiddenInput(),
            'radius': forms.HiddenInput(),
            'expires_at': forms.DateTimeInput(attrs={
                'class': 'form-control',
                'type': 'datetime-local'
            }),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['latitude'].required = False
        self.fields['longitude'].required = False
        self.fields['radius'].required = False
        self.fields['expires_at'].required = False
        self.fields['expires_at'].input_formats = [
            '%Y-%m-%dT%H:%M',
            '%Y-%m-%dT%H:%M:%S',
        ]

    def clean(self):
        cleaned_data = super().clean()
        latitude = cleaned_data.get('latitude')
        longitude = cleaned_data.get('longitude')
        radius = cleaned_data.get('radius')

        if (latitude is None) != (longitude is None):
            self.add_error(
                'longitude' if latitude is not None else 'latitude',
                'Provide both coordinates or leave both blank.',
            )
        if latitude is not None and not -90 <= latitude <= 90:
            self.add_error('latitude', 'Latitude must be between -90 and 90.')
        if longitude is not None and not -180 <= longitude <= 180:
            self.add_error('longitude', 'Longitude must be between -180 and 180.')
        if radius is not None and not 1 <= radius <= 100000:
            self.add_error('radius', 'Radius must be between 1 and 100000 meters.')
        return cleaned_data


class SafetyResourceForm(forms.ModelForm):
    class Meta:
        model = SafetyResource
        fields = ['title', 'resource_type', 'description', 'contact_number', 'contact_email', 'address', 'is_active']
        widgets = {
            'title': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Resource title'
            }),
            'resource_type': forms.Select(attrs={
                'class': 'form-select'
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 4,
                'placeholder': 'Description...'
            }),
            'contact_number': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Contact number (optional)'
            }),
            'contact_email': forms.EmailInput(attrs={
                'class': 'form-control',
                'placeholder': 'Contact email (optional)'
            }),
            'address': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 2,
                'placeholder': 'Address (optional)'
            }),
            'is_active': forms.CheckboxInput(attrs={
                'class': 'form-check-input'
            }),
        }

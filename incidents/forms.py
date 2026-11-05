from django import forms
from django.core.exceptions import ValidationError
from .models import Incident, Comment, IncidentUpdate

MAX_IMAGE_UPLOAD_SIZE = 5 * 1024 * 1024
ALLOWED_IMAGE_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.webp'}


def validate_image_upload(upload):
    if upload.size > MAX_IMAGE_UPLOAD_SIZE:
        raise ValidationError('Image files must be 5 MB or smaller.')
    extension = upload.name.rsplit('.', 1)[-1].lower() if '.' in upload.name else ''
    if f'.{extension}' not in ALLOWED_IMAGE_EXTENSIONS:
        raise ValidationError('Upload a JPG, PNG, or WEBP image.')


class IncidentForm(forms.ModelForm):
    image = forms.ImageField(
        required=False,
        validators=[validate_image_upload],
        widget=forms.FileInput(attrs={
            'class': 'form-control',
            'accept': '.jpg,.jpeg,.png,.webp',
        }),
    )
    latitude = forms.DecimalField(widget=forms.HiddenInput())
    longitude = forms.DecimalField(widget=forms.HiddenInput())
    
    class Meta:
        model = Incident
        fields = ['title', 'description', 'category', 'severity', 'latitude', 'longitude', 
                  'location_description', 'image', 'is_anonymous']
        widgets = {
            'title': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Enter incident title'
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 4,
                'placeholder': 'Describe what happened...'
            }),
            'category': forms.Select(attrs={
                'class': 'form-select'
            }),
            'severity': forms.Select(attrs={
                'class': 'form-select'
            }),
            'location_description': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'e.g., Near Galeshewe Mall, Kimberley'
            }),
            'is_anonymous': forms.CheckboxInput(attrs={
                'class': 'form-check-input'
            }),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['latitude'].required = True
        self.fields['longitude'].required = True

    def clean(self):
        cleaned_data = super().clean()
        latitude = cleaned_data.get('latitude')
        longitude = cleaned_data.get('longitude')
        if latitude is not None and not -90 <= latitude <= 90:
            self.add_error('latitude', 'Latitude must be between -90 and 90.')
        if longitude is not None and not -180 <= longitude <= 180:
            self.add_error('longitude', 'Longitude must be between -180 and 180.')
        return cleaned_data


class VolunteerProgressForm(forms.Form):
    progress_notes = forms.CharField(
        required=False,
        max_length=5000,
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 5,
            'placeholder': (
                "Describe what you've done, observations, findings, next steps, etc..."
            ),
        }),
    )
    image = forms.ImageField(
        required=False,
        validators=[validate_image_upload],
        widget=forms.FileInput(attrs={
            'class': 'form-control',
            'accept': '.jpg,.jpeg,.png,.webp',
        }),
    )


class CommentForm(forms.ModelForm):
    class Meta:
        model = Comment
        fields = ['content']
        widgets = {
            'content': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Add a comment...'
            }),
        }


class IncidentStatusForm(forms.ModelForm):
    class Meta:
        model = Incident
        fields = ['status', 'investigation_notes', 'case_number']
        widgets = {
            'status': forms.Select(attrs={
                'class': 'form-select'
            }),
            'investigation_notes': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 4,
                'placeholder': 'Add investigation notes...'
            }),
            'case_number': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'e.g., KIM-2024-001'
            }),
        }


class IncidentFilterForm(forms.Form):
    status = forms.ChoiceField(
        choices=[('', 'All Statuses')] + Incident.STATUS_CHOICES,
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    severity = forms.ChoiceField(
        choices=[('', 'All Severities')] + Incident.SEVERITY_CHOICES,
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    category = forms.ChoiceField(
        choices=[('', 'All Categories')] + Incident.CATEGORY_CHOICES,
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    date_from = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={
            'class': 'form-control',
            'type': 'date'
        })
    )
    date_to = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={
            'class': 'form-control',
            'type': 'date'
        })
    )
    search = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Search incidents...'
        })
    )

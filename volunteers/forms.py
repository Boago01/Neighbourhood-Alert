from django import forms
from .models import Volunteer, VolunteerResponse, VolunteerReview


class VolunteerApplicationForm(forms.ModelForm):
    class Meta:
        model = Volunteer
        fields = ['motivation', 'experience', 'skills', 'availability']
        widgets = {
            'motivation': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 4,
                'placeholder': 'Why do you want to become a community volunteer?'
            }),
            'experience': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Describe any relevant experience (security, first aid, community work, etc.)'
            }),
            'skills': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'e.g., First Aid, Security Training, Medical, Counseling'
            }),
            'availability': forms.Select(attrs={
                'class': 'form-select'
            }),
        }


class VolunteerResponseForm(forms.ModelForm):
    class Meta:
        model = VolunteerResponse
        fields = ['notes']
        widgets = {
            'notes': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Any notes about your response...'
            }),
        }


class VolunteerResponseStatusForm(forms.ModelForm):
    class Meta:
        model = VolunteerResponse
        fields = ['status']
        widgets = {
            'status': forms.Select(attrs={
                'class': 'form-select'
            }),
        }


class VolunteerReviewForm(forms.ModelForm):
    class Meta:
        model = VolunteerReview
        fields = ['rating', 'comment']
        widgets = {
            'rating': forms.Select(attrs={
                'class': 'form-select'
            }, choices=[(i, f'{i} Star{"s" if i > 1 else ""}') for i in range(1, 6)]),
            'comment': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Share your experience with this volunteer...'
            }),
        }

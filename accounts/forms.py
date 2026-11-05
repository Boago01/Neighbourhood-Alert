from django import forms
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from volunteers.models import Volunteer
from .models import UserProfile

User = get_user_model()
MAX_PROFILE_IMAGE_SIZE = 5 * 1024 * 1024


class PasswordResetRequestForm(forms.Form):
    email = forms.EmailField(
        label='Email address',
        widget=forms.EmailInput(attrs={
            'class': 'form-control',
            'autocomplete': 'email',
            'placeholder': 'Email address',
        }),
    )


def validate_profile_picture(upload):
    if upload.size > MAX_PROFILE_IMAGE_SIZE:
        raise ValidationError('Profile pictures must be 5 MB or smaller.')


class UserRegistrationForm(UserCreationForm):
    ROLE_CHOICES = [
        ('resident', 'Resident'),
        ('volunteer', 'Community Volunteer'),
    ]
    
    email = forms.EmailField(required=True)
    first_name = forms.CharField(max_length=30, required=True)
    last_name = forms.CharField(max_length=30, required=True)
    phone_number = forms.CharField(max_length=20, required=True)
    role = forms.ChoiceField(choices=ROLE_CHOICES, required=True, widget=forms.RadioSelect)
    address = forms.CharField(widget=forms.Textarea(attrs={'rows': 3}), required=False)
    volunteer_skills = forms.CharField(
        label='Skills',
        max_length=255,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'e.g., First aid, community support',
        }),
    )
    volunteer_availability = forms.ChoiceField(
        label='Availability',
        choices=Volunteer.AVAILABILITY_CHOICES,
        required=False,
        initial='part_time',
        widget=forms.Select(attrs={'class': 'form-select'}),
    )
    
    class Meta:
        model = User
        fields = ['username', 'first_name', 'last_name', 'email', 'phone_number', 'role', 'address', 'password1', 'password2']
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['username'].widget.attrs.update({'class': 'form-control', 'placeholder': 'Username'})
        self.fields['first_name'].widget.attrs.update({'class': 'form-control', 'placeholder': 'First Name'})
        self.fields['last_name'].widget.attrs.update({'class': 'form-control', 'placeholder': 'Last Name'})
        self.fields['email'].widget.attrs.update({'class': 'form-control', 'placeholder': 'Email Address'})
        self.fields['phone_number'].widget.attrs.update({'class': 'form-control', 'placeholder': 'Phone Number'})
        self.fields['address'].widget.attrs.update({'class': 'form-control', 'placeholder': 'Your Address'})
        self.fields['password1'].widget.attrs.update({'class': 'form-control', 'placeholder': 'Password'})
        self.fields['password2'].widget.attrs.update({'class': 'form-control', 'placeholder': 'Confirm Password'})

    def clean(self):
        cleaned_data = super().clean()
        if cleaned_data.get('role') == 'volunteer':
            if not cleaned_data.get('volunteer_skills', '').strip():
                self.add_error('volunteer_skills', 'Enter at least one volunteer skill.')
            if not cleaned_data.get('volunteer_availability'):
                self.add_error(
                    'volunteer_availability',
                    'Select your volunteer availability.',
                )
        return cleaned_data
    
    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data['email']
        user.first_name = self.cleaned_data['first_name']
        user.last_name = self.cleaned_data['last_name']
        user.phone_number = self.cleaned_data['phone_number']
        user.role = self.cleaned_data['role']
        user.address = self.cleaned_data['address']
        
        if user.role == 'resident':
            user.is_approved = True
        
        if commit:
            user.save()
            UserProfile.objects.create(user=user)
            if user.role == 'volunteer':
                Volunteer.objects.create(
                    user=user,
                    motivation='Volunteer registration submitted during account signup.',
                    skills=self.cleaned_data['volunteer_skills'].strip(),
                    availability=self.cleaned_data['volunteer_availability'],
                )
        
        return user


class PoliceRegistrationForm(UserCreationForm):
    email = forms.EmailField(required=True)
    first_name = forms.CharField(max_length=30, required=True)
    last_name = forms.CharField(max_length=30, required=True)
    phone_number = forms.CharField(max_length=20, required=True)
    police_employee_number = forms.CharField(
        max_length=50,
        required=True,
        label='Employee Number',
    )
    police_station = forms.CharField(
        max_length=150,
        required=True,
        label='Police Station',
    )
    police_unit = forms.CharField(
        max_length=150,
        required=True,
        label='Unit / Department',
    )

    class Meta:
        model = User
        fields = [
            'first_name',
            'last_name',
            'email',
            'phone_number',
            'police_employee_number',
            'police_station',
            'police_unit',
            'username',
            'password1',
            'password2',
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field_name in self.fields:
            widget = self.fields[field_name].widget
            widget.attrs['class'] = 'form-control'
        self.fields['password1'].widget.attrs['placeholder'] = 'Password'
        self.fields['password2'].widget.attrs['placeholder'] = 'Confirm Password'

    def clean_email(self):
        email = self.cleaned_data['email'].strip()
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError('An account with this email already exists.')
        return email

    def clean_police_employee_number(self):
        employee_number = self.cleaned_data['police_employee_number'].strip()
        if User.objects.filter(
            police_employee_number__iexact=employee_number
        ).exists():
            raise forms.ValidationError(
                'An application with this employee number already exists.'
            )
        return employee_number

    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data['email']
        user.first_name = self.cleaned_data['first_name']
        user.last_name = self.cleaned_data['last_name']
        user.phone_number = self.cleaned_data['phone_number']
        user.police_employee_number = self.cleaned_data['police_employee_number']
        user.police_station = self.cleaned_data['police_station']
        user.police_unit = self.cleaned_data['police_unit']
        user.role = 'police'
        user.is_approved = False
        user.is_active = False
        if commit:
            user.save()
            UserProfile.objects.create(user=user)
        return user


class UserLoginForm(AuthenticationForm):
    username = forms.CharField(widget=forms.TextInput(attrs={
        'class': 'form-control',
        'placeholder': 'Username'
    }))
    password = forms.CharField(widget=forms.PasswordInput(attrs={
        'class': 'form-control',
        'placeholder': 'Password'
    }))


class UserProfileForm(forms.ModelForm):
    profile_picture = forms.ImageField(
        required=False,
        validators=[validate_profile_picture],
        widget=forms.FileInput(attrs={'class': 'form-control'}),
    )

    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'email', 'phone_number', 'address', 'profile_picture']
        widgets = {
            'first_name': forms.TextInput(attrs={'class': 'form-control'}),
            'last_name': forms.TextInput(attrs={'class': 'form-control'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
            'phone_number': forms.TextInput(attrs={'class': 'form-control'}),
            'address': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'profile_picture': forms.FileInput(attrs={'class': 'form-control'}),
        }


class UserProfileExtendedForm(forms.ModelForm):
    class Meta:
        model = UserProfile
        fields = ['emergency_contact_name', 'emergency_contact_phone', 'id_number']
        widgets = {
            'emergency_contact_name': forms.TextInput(attrs={'class': 'form-control'}),
            'emergency_contact_phone': forms.TextInput(attrs={'class': 'form-control'}),
            'id_number': forms.TextInput(attrs={'class': 'form-control'}),
        }

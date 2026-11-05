from pathlib import PurePosixPath

from django import forms
from django.core.exceptions import ValidationError

from .error_utils import sanitize_problem_page_path
from .models import ProblemReport

MAX_SCREENSHOT_SIZE = 5 * 1024 * 1024
ALLOWED_SCREENSHOT_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.webp'}
SCREENSHOT_FORMAT_BY_EXTENSION = {
    '.jpg': 'JPEG',
    '.jpeg': 'JPEG',
    '.png': 'PNG',
    '.webp': 'WEBP',
}


class ProblemReportScreenshotField(forms.ImageField):
    def to_python(self, data):
        if data and data.size > MAX_SCREENSHOT_SIZE:
            raise ValidationError('Screenshots must be 5 MB or smaller.')
        try:
            return super().to_python(data)
        except ValidationError as error:
            raise ValidationError(
                'The uploaded file is not a valid supported image.'
            ) from error


def validate_screenshot(upload):
    if upload.size > MAX_SCREENSHOT_SIZE:
        raise ValidationError('Screenshots must be 5 MB or smaller.')

    extension = PurePosixPath(upload.name).suffix.lower()
    if extension not in ALLOWED_SCREENSHOT_EXTENSIONS:
        raise ValidationError('Upload a JPG, JPEG, PNG, or WEBP image.')

    image = getattr(upload, 'image', None)
    if (
        image is None
        or image.format != SCREENSHOT_FORMAT_BY_EXTENSION.get(extension)
    ):
        raise ValidationError('The uploaded file is not a supported image.')


class ProblemReportForm(forms.ModelForm):
    screenshot = ProblemReportScreenshotField(
        required=False,
        validators=[validate_screenshot],
        widget=forms.FileInput(attrs={
            'class': 'form-control',
            'accept': '.jpg,.jpeg,.png,.webp',
        }),
    )

    class Meta:
        model = ProblemReport
        fields = [
            'category',
            'title',
            'description',
            'page_path',
            'expected_behavior',
            'screenshot',
        ]
        widgets = {
            'category': forms.Select(attrs={'class': 'form-select'}),
            'title': forms.TextInput(attrs={
                'class': 'form-control',
                'maxlength': 120,
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 5,
                'maxlength': 5000,
            }),
            'page_path': forms.TextInput(attrs={
                'class': 'form-control',
                'maxlength': 500,
                'placeholder': '/alerts/',
            }),
            'expected_behavior': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 4,
                'maxlength': 3000,
            }),
        }

    def clean_page_path(self):
        page_path = self.cleaned_data['page_path'].strip()
        if (
            len(page_path) > 500
            or not page_path.startswith('/')
            or page_path.startswith('//')
            or '\\' in page_path
            or '?' in page_path
            or '#' in page_path
            or any(ord(character) < 32 or ord(character) == 127 for character in page_path)
        ):
            raise ValidationError(
                'Enter a local page path beginning with / and without a query string or fragment.'
            )
        return sanitize_problem_page_path(page_path)


class ProblemReportReviewForm(forms.ModelForm):
    class Meta:
        model = ProblemReport
        fields = ['status', 'administrator_notes']
        widgets = {
            'status': forms.Select(attrs={'class': 'form-select'}),
            'administrator_notes': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 5,
                'maxlength': 5000,
            }),
        }


class ProblemReportFilterForm(forms.Form):
    status = forms.ChoiceField(
        choices=[('', 'All statuses')] + ProblemReport.STATUS_CHOICES,
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'}),
    )

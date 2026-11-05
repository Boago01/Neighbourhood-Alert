from django.conf import settings
from django.core.files.storage import FileSystemStorage
from django.utils.deconstruct import deconstructible


@deconstructible
class PrivateProblemReportStorage(FileSystemStorage):
    def __init__(self, location=None):
        super().__init__(
            location=location or settings.PRIVATE_PROBLEM_REPORT_ROOT,
            base_url=None,
        )

import base64
import json
import logging
import re
from dataclasses import dataclass
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlsplit
from urllib.request import Request, urlopen

from django.conf import settings
from django.contrib.auth import get_user_model
from django.db.models import Q
from django.urls import reverse
from django.utils import timezone

from .models import AlertSMSDelivery, ApprovalSMSDelivery
from volunteers.models import Volunteer

logger = logging.getLogger(__name__)

SMS_API_URL = 'https://api.bulksms.com/v1/messages'
SMS_TIMEOUT_SECONDS = 10
ALERT_DEDUPLICATION_OFFSET = 1_000_000_000
APPROVAL_DEDUPLICATION_OFFSET = 2_000_000_000


@dataclass
class SMSSubmissionResult:
    status: str
    error_code: str = ''
    http_status: int | None = None
    provider_submission_id: str = ''


def normalize_south_african_mobile(number):
    """Return a South African mobile number in international format, or None."""
    number = re.sub(r'[\s()-]', '', number or '')
    match = re.fullmatch(r'(?:\+27|0027|0)([678]\d{8})', number)
    if not match:
        return None
    return f'+27{match.group(1)}'


def _public_base_url():
    base_url = settings.BULKSMS_PUBLIC_URL
    try:
        parsed = urlsplit(base_url)
    except ValueError:
        return ''
    if (
        parsed.scheme != 'https'
        or not parsed.netloc
        or parsed.username
        or parsed.password
        or parsed.query
        or parsed.fragment
    ):
        return ''
    return base_url.rstrip('/')


def _alert_recipients(alert):
    User = get_user_model()
    creator_number = normalize_south_african_mobile(
        alert.created_by.phone_number
    )
    eligible_roles = (
        Q(role='resident')
        | Q(role='police', is_approved=True)
        | Q(
            role='volunteer',
            is_approved=True,
            volunteer__is_approved=True,
            volunteer__is_active=True,
        )
    )
    phone_numbers = User.objects.filter(
        eligible_roles,
        is_active=True,
        is_removed=False,
    ).exclude(
        pk=alert.created_by_id,
    ).exclude(
        phone_number__isnull=True,
    ).exclude(
        phone_number='',
    ).values_list('phone_number', flat=True)

    if settings.BULKSMS_TEST_MODE:
        test_number = normalize_south_african_mobile(
            settings.BULKSMS_TEST_PHONE_NUMBER
        )
        return [test_number] if test_number and test_number != creator_number else []

    return sorted({
        normalized
        for number in phone_numbers
        if (normalized := normalize_south_african_mobile(number))
        and normalized != creator_number
    })


def _approval_recipient(user):
    if (
        not user.is_active
        or not user.is_approved
        or user.is_removed
        or user.role not in ('police', 'volunteer')
    ):
        return None

    if user.role == 'police' and not user.is_police():
        return None
    if user.role == 'volunteer' and not Volunteer.objects.filter(
        user=user,
        is_approved=True,
        is_active=True,
    ).exists():
        return None

    number = normalize_south_african_mobile(user.phone_number)
    if not number:
        return []
    if settings.BULKSMS_TEST_MODE:
        test_number = normalize_south_african_mobile(
            settings.BULKSMS_TEST_PHONE_NUMBER
        )
        return [test_number] if test_number else []
    return [number]


def _alert_message(alert):
    location = 'Not specified (select a point on the alert map)'
    if alert.latitude is not None and alert.longitude is not None:
        location = f'{alert.latitude:.5f}, {alert.longitude:.5f}'
        if alert.radius:
            location = f'{location} (within {alert.radius} m)'

    details = re.sub(r'\.{2,}$', '.', alert.message.strip())
    if alert.expires_at:
        expires = timezone.localtime(alert.expires_at).strftime('%d %b %Y %H:%M %Z')
    else:
        expires = 'No expiry set'

    lines = [
        f'NEIGHBOURHOOD ALERT: {alert.title}',
        f'Priority: {alert.get_priority_display()}',
        f'Details: {details}',
        f'Location: {location}',
        f'Expires: {expires}',
    ]
    public_url = _public_base_url()
    if public_url:
        lines.append(
            f"View: {public_url}"
            f"{reverse('alert_detail', kwargs={'alert_id': alert.pk})}"
        )

    return '\n'.join(lines)


def send_alert_sms(alert):
    """Submit one public emergency alert notification to eligible users."""
    delivery, created = AlertSMSDelivery.objects.get_or_create(alert=alert)
    if not created:
        return delivery

    recipients = _alert_recipients(alert)
    delivery.recipient_count = len(recipients)
    delivery.save(update_fields=['recipient_count'])

    return _submit_sms(
        delivery=delivery,
        messages=[{'to': number, 'body': _alert_message(alert)} for number in recipients],
        deduplication_id=ALERT_DEDUPLICATION_OFFSET + alert.pk,
        operation='alert',
    )


def send_approval_welcome_sms(user):
    """Send a one-time welcome SMS after an eligible approval is saved."""
    if user.role == 'police':
        login_url = reverse('login')
        message = (
            'Welcome to Neighbourhood Alert! Your police account has been '
            'approved. You can now log in and use the website: '
        )
    elif user.role == 'volunteer':
        login_url = reverse('volunteer_dashboard')
        message = (
            'Welcome to Neighbourhood Alert! Your volunteer account has been '
            'approved. You can now log in and access your volunteer dashboard: '
        )
    else:
        return None

    recipients = _approval_recipient(user)
    if recipients is None:
        return None

    delivery, created = ApprovalSMSDelivery.objects.get_or_create(user=user)
    if not created:
        if not (
            delivery.status == 'failed'
            and delivery.error_code == 'missing_public_url'
        ):
            return delivery
        delivery.status = 'pending'
        delivery.error_code = ''
        delivery.http_status = None
        delivery.provider_submission_id = ''
        delivery.completed_at = None
        delivery.save(update_fields=[
            'status',
            'error_code',
            'http_status',
            'provider_submission_id',
            'completed_at',
        ])

    if not settings.BULKSMS_ENABLED:
        return _finish(delivery, 'skipped', 'sms_disabled')

    if not recipients:
        return _finish(delivery, 'failed', 'invalid_phone_number')

    public_url = _public_base_url()
    body = f'{message}{public_url}{login_url}' if public_url else message.rstrip(': ') + '.'
    return _submit_sms(
        delivery=delivery,
        messages=[{'to': number, 'body': body} for number in recipients],
        deduplication_id=APPROVAL_DEDUPLICATION_OFFSET + user.pk,
        operation='approval',
    )


def approval_sms_failure_message(delivery):
    """Return an actionable, non-sensitive explanation for a failed welcome SMS."""
    error_code = delivery.error_code
    if error_code == 'missing_public_url':
        return (
            'The account was approved, but the welcome SMS was not sent. '
            'Set BULKSMS_PUBLIC_URL in .env to your public HTTPS website URL '
            'and restart Django.'
        )
    if error_code == 'invalid_phone_number':
        return (
            'The account was approved, but the welcome SMS was not sent. '
            'Add a valid South African mobile number to the account.'
        )
    if error_code == 'missing_credentials':
        return (
            'The account was approved, but the welcome SMS was not sent. '
            'Configure the BulkSMS API credentials in .env and restart Django.'
        )
    return (
        'The account was approved, but BulkSMS could not submit the welcome SMS. '
        'Check the BulkSMS delivery report for the failure reason.'
    )


def _submit_sms_request(messages, deduplication_id, operation):
    if not settings.BULKSMS_ENABLED:
        return SMSSubmissionResult('skipped', 'sms_disabled')

    if not settings.BULKSMS_TOKEN_ID or not settings.BULKSMS_TOKEN_SECRET:
        return SMSSubmissionResult('failed', 'missing_credentials')

    if not messages:
        return SMSSubmissionResult('failed', 'no_valid_recipients')

    if settings.BULKSMS_DRY_RUN:
        logger.info(
            'BulkSMS dry run for %s to %s recipient(s)',
            operation,
            len(messages),
        )
        return SMSSubmissionResult('dry_run', 'dry_run')

    token = base64.b64encode(
        f'{settings.BULKSMS_TOKEN_ID}:{settings.BULKSMS_TOKEN_SECRET}'.encode()
    ).decode('ascii')
    url = SMS_API_URL
    if deduplication_id is not None:
        url = f'{url}?{urlencode({"deduplication-id": deduplication_id})}'
    request = Request(
        url,
        data=json.dumps(messages).encode('utf-8'),
        headers={
            'Authorization': f'Basic {token}',
            'Content-Type': 'application/json',
            'Accept': 'application/json',
        },
        method='POST',
    )

    try:
        with urlopen(request, timeout=SMS_TIMEOUT_SECONDS) as response:
            status_code = response.status
            response_body = response.read()
    except HTTPError as error:
        error.close()
        return SMSSubmissionResult('failed', f'http_{error.code}', error.code)
    except URLError as error:
        logger.warning(
            'BulkSMS request failed for %s: %s',
            operation,
            error.reason.__class__.__name__,
        )
        return SMSSubmissionResult('failed', 'provider_unavailable')
    except TimeoutError:
        return SMSSubmissionResult('failed', 'provider_timeout')
    except OSError:
        return SMSSubmissionResult('failed', 'provider_unavailable')

    if status_code != 201:
        return SMSSubmissionResult('failed', 'unexpected_http_status', status_code)

    try:
        provider_response = json.loads(response_body)
    except (json.JSONDecodeError, UnicodeDecodeError):
        return SMSSubmissionResult('failed', 'invalid_provider_response', status_code)

    if not isinstance(provider_response, list) or not provider_response:
        return SMSSubmissionResult('failed', 'invalid_provider_response', status_code)

    submission_ids = {
        item['submission']['id']
        for item in provider_response
        if isinstance(item, dict)
        and isinstance(item.get('submission'), dict)
        and item['submission'].get('id')
    }
    return SMSSubmissionResult(
        'submitted',
        http_status=status_code,
        provider_submission_id=next(iter(submission_ids), ''),
    )


def _submit_sms(delivery, messages, deduplication_id, operation):
    result = _submit_sms_request(messages, deduplication_id, operation)
    if result.status != 'submitted':
        return _finish(
            delivery,
            result.status,
            result.error_code,
            result.http_status,
        )

    delivery.status = result.status
    delivery.http_status = result.http_status
    delivery.provider_submission_id = result.provider_submission_id
    delivery.completed_at = timezone.now()
    delivery.save(update_fields=[
        'status',
        'http_status',
        'provider_submission_id',
        'completed_at',
    ])
    return delivery


def _finish(delivery, status, error_code, http_status=None):
    delivery.status = status
    delivery.error_code = error_code
    if http_status is not None:
        delivery.http_status = http_status
    delivery.completed_at = timezone.now()
    delivery.save(update_fields=[
        'status',
        'error_code',
        'http_status',
        'completed_at',
    ])
    if status == 'failed':
        logger.warning(
            'BulkSMS submission failed for delivery %s (%s)',
            delivery.pk,
            error_code,
        )
    return delivery

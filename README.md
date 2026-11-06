# Neighbourhood Alert - Community Crime Management System

Neighbourhood Alert is a Django-based prototype for community safety and incident management in Kimberley, Northern Cape. The project is intended to explore how residents, volunteers, police officers, and administrators could work together to report incidents, coordinate support, and share alerts.

This is a prototype, not a verified live crime-management system or proof of existing local demand or crime outcomes. The project is configured around Kimberley, but that does not automatically confirm that the system reflects real-world community needs or official operational requirements.

## Features

### User roles

1. **Resident**
   - Register and log in securely
   - Submit incident reports with a location and supporting evidence
   - Hide the reporter's name in normal incident views while keeping the account linked in the database
   - Track incident updates and review reported cases
   - Comment on incidents
   - View a community heatmap
   - Request to support equipment campaigns run by volunteers

2. **Community Volunteer**
   - Register as a volunteer and wait for approval
   - Apply for access to assigned case workflows
   - View incidents assigned by police officers
   - Update assignment status and submit progress reports
   - Create non-financial equipment support campaigns

3. **Police Officer**
   - View reports and manage approved case workflows
   - Assign approved volunteers to incidents
   - Create emergency alerts
   - View exact incident locations and authorized analytics

4. **Administrator**
   - Manage user accounts and review volunteer and police applications
   - Create alerts and review analytics
   - View incident details without changing police case status through the normal incident workflow

## Technology stack

- **Backend**: Django 5.0.x (declared in `requirements.txt` as `Django>=5.0,<5.1`)
- **Frontend**: HTML5, CSS3, JavaScript, Bootstrap 5
- **Database**: SQLite (default)
- **Maps**: Google Maps JavaScript API (requires a browser API key)
- **Charts**: Chart.js

## Installation

### Prerequisites

- Python 3.10–3.12 for the Django version declared by this project
- pip

### Setup steps

1. **Open the project directory**
   ```bash
   cd neighbourhood_alert
   ```

2. **Install the required packages**
   ```bash
   pip install -r requirements.txt
   ```

3. **Apply database migrations**
   ```bash
   python manage.py migrate
   ```

4. **Create an administrator account (optional)**
   ```bash
   python manage.py createsuperuser
   ```

5. **Start the development server**
   ```bash
   python manage.py runserver
   ```

6. **Open the app**
   - Web app: http://localhost:8000
   - Admin panel: http://localhost:8000/admin

### Password reset by email

The password-reset flow generates a single-use Django reset link for an active account and uses the configured Django email backend. By default, the project uses `EMAIL_MODE=console`, which sends messages to the server console instead of an external mail provider.

For a controlled Mailtrap test, add these settings to the ignored project-root `.env` file using a valid Mailtrap sending token and a sender address that your Mailtrap account accepts:

```dotenv
EMAIL_MODE=smtp
EMAIL_HOST=live.smtp.mailtrap.io
EMAIL_PORT=587
EMAIL_USE_TLS=true
EMAIL_HOST_USER=api
EMAIL_HOST_PASSWORD=your-mailtrap-sending-token
DEFAULT_FROM_EMAIL=noreply@your-verified-domain.example
```

The test suite switches the email backend to Django's in-memory backend, which does not test Mailtrap delivery or confirm real email sending. No successful live Mailtrap delivery has been verified for this project. Do not commit `.env` files or credentials.

After changing environment settings, restart Django. Reset links use the request host, so deployment should use the public HTTPS host. For multi-worker deployments, configure a shared cache for reset-request cooldowns.

### Production security settings

The development configuration is not intended for production use. Before deployment, configure these values in the hosting environment or an approved secret store. Do not commit them to the repository:

```dotenv
DEBUG=false
SECRET_KEY=<unique-long-random-secret>
ALLOWED_HOSTS=your-domain.example,www.your-domain.example
```

With `DEBUG=false`, Django expects a valid `SECRET_KEY` and `ALLOWED_HOSTS`, redirects HTTP traffic to HTTPS, enables secure session and CSRF cookies, and supports HSTS. Make sure HTTPS is working correctly at the app or behind a trusted reverse proxy before enabling production settings.

Local development uses `DEBUG=true` in the ignored `.env` file. Do not copy that setting to production. Only set `SECURE_SSL_REDIRECT`, `SESSION_COOKIE_SECURE`, `CSRF_COOKIE_SECURE`, and `SECURE_HSTS_SECONDS` explicitly when your hosting setup requires them.

### Emergency-alert SMS (BulkSMS)

The BulkSMS integration uses the provider's HTTPS JSON API with API-token Basic Auth. The default settings disable SMS, keep dry-run enabled, and leave test-number mode off. In dry-run mode, the code records the intention to send a message without contacting BulkSMS. When test-number mode is enabled, only the configured test number can be selected.

The code and its mocked tests do not prove provider submission or delivery to a real handset.

When you are ready to configure the integration, add the following values to the ignored project-root `.env` file. Keep the token ID and secret private. Set the public URL to the site's HTTPS address so approval messages can include a working login or dashboard link:

```dotenv
BULKSMS_ENABLED=true
BULKSMS_DRY_RUN=true
BULKSMS_TEST_MODE=true
BULKSMS_TOKEN_ID=your-bulksms-token-id
BULKSMS_TOKEN_SECRET=your-bulksms-token-secret
BULKSMS_TEST_PHONE_NUMBER=your-authorized-test-mobile-number
BULKSMS_PUBLIC_URL=https://your-public-site.example
```

Alert SMS messages should contain only public safety information. Do not include private incident details, resident information, or investigation-sensitive material. Recipients are active residents and active, approved police officers and volunteers with valid South African mobile numbers. Administrator accounts are not included in alert broadcasts.

After configuration, leave `BULKSMS_DRY_RUN=true` until an authorized, controlled provider test has been approved. Live tests must use `BULKSMS_TEST_MODE=true` and an approved test number. Do not send alerts as part of documentation or routine development. No successful live BulkSMS delivery has been verified for this project. Restart Django after changing `.env`.

Police and volunteer approval workflows send a welcome SMS once the account has been approved and is active. If `BULKSMS_PUBLIC_URL` is configured, the message includes the login or dashboard URL. Otherwise, it is sent without a link. Delivery records for alerts and approval messages are available in Django admin. Provider failures do not undo an alert or approval, and failed submissions are not retried automatically to avoid duplicate messages.

No sample accounts are included or verified in this repository. Create a local administrator with `createsuperuser`, and create test users through the registration flow or test fixtures.

## Project Structure

```
neighbourhood_alert/
├── accounts/          # User authentication and profiles
├── incidents/         # Incident reporting and management
├── volunteers/        # Volunteer coordination and applications
├── donations/         # Equipment campaigns plus legacy monetary/payout code
├── alerts/            # Emergency alerts and safety resources
├── analytics/         # Crime statistics and reports
├── templates/         # HTML templates
├── media/             # User uploads
├── neighbourhood_alert/  # Project settings
├── manage.py          # Django management script
├── requirements.txt   # Python dependencies
└── README.md          # This file
```

## Key Functionalities

### Incident reporting and management
- Authenticated residents can report incidents, provide a location, and upload
  image evidence.
- The “anonymous” option hides the reporter's displayed name; the database
  still retains the reporter account link. It is not anonymity from
  administrators/database operators.
- Residents see their own reports; police and administrators have broader
  incident visibility; approved volunteers can access cases assigned to them.
- Police users can assign approved volunteers and manage police case status.

### Heatmap and analytics
- The heatmap route is `/analytics/heatmap/`, not `/heatmap/`.
- Anonymous visitors are redirected to login. Residents and volunteers receive
  aggregated, rounded locations; police and administrators receive exact
  locations. Automated tests cover these access and aggregation rules.
- The trends and hotspot views have URL routes but reference templates that
  are absent. Do not describe those pages as working features.

### Equipment and non-financial support
- Volunteers can create equipment campaigns and residents can submit
  equipment-support requests. The code also contains monetary donation and
  payout fields/routes from legacy functionality. No payment gateway is
  configured; financial transfers are outside the active project scope and
  should not be presented as an available service.

### Police Officer Registration
- Residents and volunteers register from the regular registration page.
- Police officers submit a separate application at `/police/register/` with their employee number, station, and unit.
- Police applications remain inactive and cannot log in until an administrator approves them from User Management.
- Admin accounts are created during initial system setup; public registration does not offer the administrator role.

### Alerts and safety resources
- Police and administrators can create emergency alerts; alert acknowledgement,
  expiry/deactivation, and SMS delivery records are represented in code.
- Safety resources can be displayed, but create/edit/delete views reference
  templates that are not present. Management through those pages is incomplete.

## Security Features

- Role-based access control
- CSRF protection
- Secure password hashing
- File upload validation
- Reporter-name hiding (not anonymous storage)

## Map Configuration

Map templates use Google Maps, centered near Kimberley, Northern Cape
(-28.7282, 24.7499), and include sample named map points. These values do not
establish official service boundaries or verified incident coverage. Configure
`GOOGLE_MAPS_API_KEY` in the environment (or the local `.env` file) to load the
maps. This browser key is included in rendered pages by design; restrict it to
the app's HTTP referrers and the Maps JavaScript API in Google Cloud.

## Current known documentation and implementation limits

- Volunteer search is likely broken: `volunteers/views.py` calls `models.Q`
  without importing `models`.
- Analytics trends/hotspot routes and safety-resource create/edit/delete routes
  reference missing templates.
- Google Maps requires an internet connection and a valid, referrer-restricted
  API key; map loading has not been live-verified. BulkSMS provider availability
  and successful production delivery have not been verified.
- Password-reset tests use Django's in-memory email backend. They do not verify
  Mailtrap delivery.
- The requirements file declares Django 5.0.x. The previously inspected local
  environment had Django 6.1.2, so the installed environment does not match the
  declared dependency range.
- Local settings, SQLite, uploaded media, backups, encryption, and retention
  arrangements must be reviewed before any production use. Do not claim that
  the current development configuration is production-ready.
- No formal stakeholder interviews or verified local crime statistics were
  found in the project files. Treat local need statements as assumptions until
  supported by cited sources or genuine consultation.

## Development

### Creating Migrations
```bash
python manage.py makemigrations
```

### Running Tests
```bash
python manage.py test
```

### Collecting Static Files (Production)
```bash
python manage.py collectstatic
```

## Color Scheme

The application uses a professional color scheme:

- **Primary**: Dark Blue (#1E3A8A) - Trust and professionalism
- **Secondary**: Red (#DC2626) - Emergency and alerts
- **Accent**: Orange (#F97316) - Warnings
- **Success**: Green (#16A34A) - Resolved cases
- **Background**: Light Gray (#F3F4F6)
- **Text**: Dark Gray (#111827)

## License

No license file was found in the project root. Confirm the applicable usage
rights with the project owner before redistributing the source.

## Support

For issues or questions, please contact the development team.

---

**Developed for**: Kimberley Community Safety Initiative  
**Location**: Kimberley, Northern Cape, South Africa

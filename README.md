# Neighbourhood Alert - Community Crime Management System

A Django web application prototype for community safety workflows. The project is
configured around Kimberley, Northern Cape; this configuration does not establish
local stakeholder need or prove real-world crime outcomes.

## Features

### User Roles

1. **Resident**
   - Register and login securely
   - Submit incident reports with location and evidence
   - Hide the reporter's name in ordinary incident display (the account remains
     linked to the report in the database)
   - View and track reported incidents
   - Comment on incidents
   - View an aggregated heatmap
   - Request to donate equipment to volunteer campaigns

2. **Community Volunteer**
   - Register as a volunteer (requires approval)
   - Apply for approval before accessing assigned case workflows
   - View incidents assigned by police
   - Update assignment status and submit progress/completion reports
   - Create non-financial equipment campaigns

3. **Police Officer**
   - View incident reports and manage police case workflows after approval
   - Assign approved volunteers to incidents
   - Create emergency alerts
   - View exact incident locations and authorized analytics

4. **Administrator**
   - Manage user accounts and review volunteer/police applications
   - Create alerts and view analytics
   - View incident details, but not update police case status through the
     ordinary incident workflow

## Technology Stack

- **Backend**: Django 5.0.x (declared in `requirements.txt` as `Django>=5.0,<5.1`)
- **Frontend**: HTML5, CSS3, JavaScript, Bootstrap 5
- **Database**: SQLite (default)
- **Maps**: Google Maps JavaScript API (requires a browser API key)
- **Charts**: Chart.js

## Installation

### Prerequisites

- Python 3.10–3.12 for the Django version declared by this project
- pip

### Setup Instructions

1. **Navigate to the project directory**
   ```bash
   cd neighbourhood_alert
   ```

2. **Use a Python version supported by the declared Django release, then install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Run migrations**
   ```bash
   python manage.py migrate
   ```

4. **Create an administrator account (optional)**
   ```bash
   python manage.py createsuperuser
   ```

5. **Run the development server**
   ```bash
   python manage.py runserver
   ```

6. **Access the application**
   - Open browser: http://localhost:8000
   - Admin panel: http://localhost:8000/admin

### Password reset by email

The reset workflow creates a single-use Django reset link for a matching active
account and uses the configured Django email backend. The settings default to
`EMAIL_MODE=console`, which writes messages to the server console. For a
controlled Mailtrap SMTP test, configure the ignored project-root `.env` file
with a Mailtrap sending token and a sender address accepted by your Mailtrap
account:

```dotenv
EMAIL_MODE=smtp
EMAIL_HOST=live.smtp.mailtrap.io
EMAIL_PORT=587
EMAIL_USE_TLS=true
EMAIL_HOST_USER=api
EMAIL_HOST_PASSWORD=your-mailtrap-sending-token
DEFAULT_FROM_EMAIL=noreply@your-verified-domain.example
```

The test suite replaces SMTP with Django's in-memory email backend; it does not
test Mailtrap or prove external delivery. No successful live Mailtrap delivery
has been verified for this project. Do not commit `.env` or credentials.
Restart Django after changing environment settings. Reset links use the request
host, so use the public HTTPS host after deployment. For multi-worker
deployments, configure a shared cache for reset-request cooldowns.

### Production security settings

Development settings are not production settings. For deployment, configure
these values in the hosting environment or its protected secret store; do not
commit them:

```dotenv
DEBUG=false
SECRET_KEY=<unique-long-random-secret>
ALLOWED_HOSTS=your-domain.example,www.your-domain.example
```

With `DEBUG=false`, Django requires a configured `SECRET_KEY` and `ALLOWED_HOSTS`,
redirects HTTP to HTTPS, enables secure session and CSRF cookies, and enables
HSTS. Ensure HTTPS is working at the application or trusted reverse proxy
before enabling the deployment. Local development uses `DEBUG=true` in the
ignored `.env`; do not copy that setting to production. Set
`SECURE_SSL_REDIRECT`, `SESSION_COOKIE_SECURE`, `CSRF_COOKIE_SECURE`, and
`SECURE_HSTS_SECONDS` explicitly only when your hosting setup requires different
values.

### Emergency-alert SMS (BulkSMS)

BulkSMS integration code uses the provider's HTTPS JSON API and API-token
Basic Auth. The settings defaults are SMS disabled, dry-run enabled, and
test-number mode disabled. Dry-run records delivery intent without contacting
BulkSMS. When test-number mode is enabled, only the configured test number can
be selected. Code and mocked tests do not prove provider submission or handset
delivery.

Add these settings to the ignored project-root `.env` file when you are ready
to configure the integration. Keep the token ID and secret private. Set the
public URL to the site's HTTPS address so approval messages can include a
working login/dashboard link:

```dotenv
BULKSMS_ENABLED=true
BULKSMS_DRY_RUN=true
BULKSMS_TEST_MODE=true
BULKSMS_TOKEN_ID=your-bulksms-token-id
BULKSMS_TOKEN_SECRET=your-bulksms-token-secret
BULKSMS_TEST_PHONE_NUMBER=your-authorized-test-mobile-number
BULKSMS_PUBLIC_URL=https://your-public-site.example
```

Alert SMS includes the alert's title, priority, message/details, location, and
expiry. Put only public safety information in the alert message; do not include
private incident, resident, or investigation details. Recipients are active
residents and active, approved police officers and volunteers with valid South
African mobile numbers. Admin accounts are not included in broadcasts.

After configuration, keep `BULKSMS_DRY_RUN=true` until an authorized,
controlled provider test is approved. Live tests must use `BULKSMS_TEST_MODE=true`
and an authorized test number. Do not send broadcasts as part of documentation
or routine development. No successful live BulkSMS delivery has been verified
for this project. Restart Django after changing `.env`.

Police and volunteer approval workflows send one welcome SMS after the account
is approved and active. If `BULKSMS_PUBLIC_URL` is configured, the message
includes the login/dashboard URL; otherwise, it is sent without a link.
Delivery records for alerts and approval messages are available in Django
admin. Provider failures do not undo an alert or account approval, and failed
submissions are not retried automatically to avoid duplicate messages.

No sample accounts are provided or verified by the files in this repository.
Create a local administrator with `createsuperuser`; create test users through
the registration flow or test fixtures.

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

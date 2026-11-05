import re
from urllib.parse import urlsplit


_SENSITIVE_PATH_SEGMENT = re.compile(
    r'^(?:\d+|[0-9a-f]{8}-[0-9a-f-]{27,}|[A-Za-z0-9_-]{32,})$',
    re.IGNORECASE,
)
_SENSITIVE_PATH_WORD = re.compile(
    r'(?:token|secret|password|session|auth|api.?key)',
    re.IGNORECASE,
)
_SAFE_PATH_SEGMENT = re.compile(r'^[A-Za-z0-9._~-]+$')


def sanitize_problem_page_path(path):
    """Keep only a bounded local path and redact likely secret-bearing segments."""
    parsed_path = urlsplit(path).path
    if not parsed_path.startswith('/') or parsed_path.startswith('//'):
        return '/'

    segments = []
    for segment in parsed_path.split('/'):
        if not segment:
            continue
        if (
            _SENSITIVE_PATH_SEGMENT.fullmatch(segment)
            or _SENSITIVE_PATH_WORD.search(segment)
            or not _SAFE_PATH_SEGMENT.fullmatch(segment)
        ):
            segments.append('[redacted]')
        else:
            segments.append(segment)

    safe_path = '/' + '/'.join(segments)
    if parsed_path.endswith('/') and safe_path != '/':
        safe_path += '/'
    return safe_path[:500]

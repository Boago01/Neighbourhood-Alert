(function () {
    'use strict';

    var reportUrl = '/problem-reports/';
    var draftKey = 'neighbourhoodAlertProblemReportDraft';
    var safeSummaries = [
        'An unexpected browser error occurred.',
        'An unexpected browser operation failed.',
        'A background request returned a server error.',
        'An unexpected server error occurred.'
    ];
    var lastPromptAt = 0;
    var promptCooldownMs = 10000;
    var errorModal = document.getElementById('unexpectedErrorModal');
    var modalInstance = null;

    function currentPageIsReportArea() {
        return window.location.pathname.indexOf('/problem-reports/') === 0;
    }

    function sanitizePath(path) {
        var parsed;
        try {
            parsed = new URL(path, window.location.origin);
        } catch (_error) {
            return '/';
        }

        if (parsed.origin !== window.location.origin) {
            return '/';
        }

        var segments = parsed.pathname.split('/').filter(Boolean).map(function (segment) {
            if (
                /^\d+$/.test(segment) ||
                /^[0-9a-f]{8}-[0-9a-f-]{27,}$/i.test(segment) ||
                /^[A-Za-z0-9_-]{32,}$/.test(segment) ||
                /(token|secret|password|session|auth|api.?key)/i.test(segment) ||
                !/^[A-Za-z0-9._~-]+$/.test(segment)
            ) {
                return '[redacted]';
            }
            return segment;
        });

        var safePath = '/' + segments.join('/');
        if (parsed.pathname.endsWith('/') && safePath !== '/') {
            safePath += '/';
        }
        return safePath.slice(0, 500);
    }

    function showPrompt(summary) {
        if (!errorModal || currentPageIsReportArea()) {
            return;
        }

        var now = Date.now();
        if (now - lastPromptAt < promptCooldownMs) {
            return;
        }
        lastPromptAt = now;

        if (window.bootstrap && window.bootstrap.Modal) {
            modalInstance = window.bootstrap.Modal.getOrCreateInstance(errorModal);
            modalInstance.show();
        } else {
            errorModal.style.display = 'block';
            errorModal.classList.add('show');
            errorModal.removeAttribute('aria-hidden');
        }
        errorModal.dataset.errorSummary = summary;
    }

    function saveDraftAndNavigate(button) {
        var errorPage = document.querySelector('[data-server-error-page]');
        var pagePath = errorPage
            ? errorPage.getAttribute('data-page-path')
            : window.location.pathname;
        var summary = errorPage
            ? errorPage.getAttribute('data-error-summary')
            : (errorModal && errorModal.dataset.errorSummary) ||
                'An unexpected website error occurred.';

        try {
            window.sessionStorage.setItem(draftKey, JSON.stringify({
                pagePath: sanitizePath(pagePath),
                summary: summary
            }));
        } catch (_error) {
            // Continue to the form even when browser storage is unavailable.
        }

        window.location.assign(button.getAttribute('data-report-url') || reportUrl);
    }

    function dismissPrompt() {
        if (modalInstance) {
            modalInstance.hide();
        } else if (errorModal) {
            errorModal.style.display = 'none';
            errorModal.classList.remove('show');
            errorModal.setAttribute('aria-hidden', 'true');
        }
    }

    function isProblemReportRequest(url) {
        try {
            var parsed = new URL(url, window.location.href);
            return parsed.origin === window.location.origin &&
                parsed.pathname.indexOf('/problem-reports/') === 0;
        } catch (_error) {
            return false;
        }
    }

    document.addEventListener('click', function (event) {
        var reportButton = event.target.closest('[data-error-report-start]');
        if (reportButton) {
            saveDraftAndNavigate(reportButton);
            return;
        }
        if (event.target.closest('[data-error-dismiss]')) {
            dismissPrompt();
        }
    });

    window.addEventListener('error', function (event) {
        if (event instanceof ErrorEvent) {
            event.preventDefault();
            showPrompt('An unexpected browser error occurred.');
        }
    });

    window.addEventListener('unhandledrejection', function (event) {
        event.preventDefault();
        showPrompt('An unexpected browser operation failed.');
    });

    if (window.fetch) {
        var originalFetch = window.fetch;
        window.fetch = function () {
            var requestUrl = arguments[0] instanceof Request
                ? arguments[0].url
                : arguments[0];
            var responsePromise = originalFetch.apply(this, arguments);
            return responsePromise.then(function (response) {
                if (
                    response.status >= 500 &&
                    !isProblemReportRequest(requestUrl)
                ) {
                    showPrompt('A background request returned a server error.');
                }
                return response;
            });
        };
    }

    if (window.XMLHttpRequest) {
        var originalOpen = XMLHttpRequest.prototype.open;
        XMLHttpRequest.prototype.open = function (method, url) {
            this.__problemReportRequestUrl = url;
            return originalOpen.apply(this, arguments);
        };

        var originalSend = XMLHttpRequest.prototype.send;
        XMLHttpRequest.prototype.send = function () {
            this.addEventListener('loadend', function () {
                if (
                    this.status >= 500 &&
                    !isProblemReportRequest(this.responseURL || this.__problemReportRequestUrl)
                ) {
                    showPrompt('A background request returned a server error.');
                }
            });
            return originalSend.apply(this, arguments);
        };
    }

    var reportForm = document.querySelector('[data-problem-report-form]');
    if (reportForm) {
        try {
            var draft = JSON.parse(window.sessionStorage.getItem(draftKey) || 'null');
            window.sessionStorage.removeItem(draftKey);
            if (draft) {
                var pageField = reportForm.elements.namedItem('page_path');
                var descriptionField = reportForm.elements.namedItem('description');
                if (pageField && !pageField.value) {
                    pageField.value = sanitizePath(draft.pagePath || '/');
                }
                if (descriptionField && !descriptionField.value) {
                    descriptionField.value = safeSummaries.indexOf(draft.summary) !== -1
                        ? draft.summary
                        : 'An unexpected website error occurred.';
                }
            }
        } catch (_error) {
            window.sessionStorage.removeItem(draftKey);
        }
    }
})();

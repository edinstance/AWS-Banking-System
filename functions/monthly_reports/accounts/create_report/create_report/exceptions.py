class ReportGenerationError(Exception):
    """Raised when PDF generation fails."""


class ReportTemplateError(Exception):
    """Raised when the Jinja2 template is missing or invalid."""


class ReportUploadError(Exception):
    """Raised when uploading to S3 fails."""

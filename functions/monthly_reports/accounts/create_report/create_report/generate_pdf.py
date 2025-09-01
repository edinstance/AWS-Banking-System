import io
import os
from datetime import datetime, timezone

from aws_lambda_powertools import Logger
from jinja2 import Environment, FileSystemLoader, TemplateNotFound, select_autoescape
from xhtml2pdf import pisa

from .exceptions import ReportGenerationError, ReportTemplateError


def generate_transactions_pdf(event: dict, logger: Logger) -> bytes:
    current_dir = os.path.dirname(os.path.abspath(__file__))
    env = Environment(
        loader=FileSystemLoader(current_dir),
        autoescape=select_autoescape(["html", "xml"]),
    )

    try:
        template = env.get_template("template.html")
    except TemplateNotFound as e:
        logger.error("Template 'template.html' not found")
        raise ReportTemplateError("Missing template: template.html") from e

    html_out = template.render(
        accountId=event["accountId"],
        statementPeriod=event["statementPeriod"],
        transactions=event["transactions"],
        accountBalance=event["accountBalance"],
        generationDate=datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC"),
    )

    pdf_buffer = io.BytesIO()
    pisa_status = pisa.CreatePDF(io.StringIO(html_out), dest=pdf_buffer)

    if pisa_status.err:
        logger.error("xhtml2pdf failed to generate PDF")
        raise ReportGenerationError("Error generating PDF")

    pdf_buffer.seek(0)
    pdf_bytes = pdf_buffer.getvalue()

    logger.debug("PDF generated (%d bytes).", len(pdf_bytes))
    return pdf_bytes

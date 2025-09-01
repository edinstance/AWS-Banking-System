import pytest
from unittest.mock import patch, MagicMock
from functions.monthly_reports.accounts.create_report.create_report.generate_pdf import (
    generate_transactions_pdf,
)
from functions.monthly_reports.accounts.create_report.create_report.exceptions import (
    ReportGenerationError,
    ReportTemplateError,
)


class TestGenerateTransactionsPDF:
    """Test cases for the generate_transactions_pdf function."""

    @pytest.fixture
    def sample_event(self):
        """Sample event data for testing."""
        return {
            "accountId": "test-account-123",
            "statementPeriod": "2024-01",
            "transactions": [
                {
                    "id": "txn-1",
                    "amount": 100.00,
                    "description": "Test transaction 1",
                    "date": "2024-01-15",
                },
                {
                    "id": "txn-2",
                    "amount": -50.00,
                    "description": "Test transaction 2",
                    "date": "2024-01-20",
                },
            ],
            "accountBalance": 1500.00,
        }

    @pytest.fixture
    def mock_logger(self):
        """Mock logger for testing."""
        return MagicMock()

    @pytest.fixture
    def mock_template_content(self):
        """
        Return a mock HTML Jinja2 template used for rendering account transaction statements in tests.
        
        The template includes placeholders expected by generate_transactions_pdf:
        - accountId, statementPeriod, accountBalance, generationDate
        - an iterable `transactions` where each item exposes `id`, `amount`, `description` and `date`.
        
        Returns:
            str: Multiline HTML template string suitable for Jinja2 rendering in tests.
        """
        return """
        <html>
        <head><title>Account Statement</title></head>
        <body>
            <h1>Account Statement</h1>
            <p>Account ID: {{ accountId }}</p>
            <p>Statement Period: {{ statementPeriod }}</p>
            <p>Account Balance: {{ accountBalance }}</p>
            <p>Generated: {{ generationDate }}</p>
            <table>
                <tr><th>ID</th><th>Amount</th><th>Description</th><th>Date</th></tr>
                {% for transaction in transactions %}
                <tr>
                    <td>{{ transaction.id }}</td>
                    <td>{{ transaction.amount }}</td>
                    <td>{{ transaction.description }}</td>
                    <td>{{ transaction.date }}</td>
                </tr>
                {% endfor %}
            </table>
        </body>
        </html>
        """

    def test_successful_pdf_generation(
        self, sample_event, mock_logger, mock_template_content
    ):
        """Test successful PDF generation."""
        with patch("os.path.dirname") as mock_dirname:
            mock_dirname.return_value = "/mock/path"

            # Mock the Jinja2 Environment and template
            with patch(
                "functions.monthly_reports.accounts.create_report.create_report.generate_pdf.Environment"
            ) as mock_env:
                mock_template = MagicMock()
                mock_template.render.return_value = "<html><body>Test PDF</body></html>"
                mock_env_instance = MagicMock()
                mock_env_instance.get_template.return_value = mock_template
                mock_env.return_value = mock_env_instance

                # Mock xhtml2pdf
                with patch("xhtml2pdf.pisa.CreatePDF") as mock_pisa:
                    mock_pisa.return_value.err = False

                    # Mock tempfile
                    with patch("tempfile.NamedTemporaryFile") as mock_tempfile:
                        mock_tempfile_instance = MagicMock()
                        mock_tempfile_instance.name = "/tmp/test.pdf"
                        mock_tempfile.return_value.__enter__.return_value = (
                            mock_tempfile_instance
                        )
                        mock_tempfile.return_value.__exit__.return_value = None

                        # Call the function
                        result = generate_transactions_pdf(sample_event, mock_logger)

                        # Verify template was rendered with correct data
                        mock_template.render.assert_called_once()
                        call_args = mock_template.render.call_args[1]
                        assert call_args["accountId"] == sample_event["accountId"]
                        assert (
                            call_args["statementPeriod"]
                            == sample_event["statementPeriod"]
                        )
                        assert call_args["transactions"] == sample_event["transactions"]
                        assert (
                            call_args["accountBalance"]
                            == sample_event["accountBalance"]
                        )
                        assert "generationDate" in call_args

                        # Verify PDF generation was called
                        mock_pisa.assert_called_once()

                        # Verify result is bytes
                        assert isinstance(result, bytes)

    def test_template_not_found_error(self, sample_event, mock_logger):
        """Test handling of template not found error."""
        with patch("os.path.dirname") as mock_dirname:
            mock_dirname.return_value = "/mock/path"

            # Mock Jinja2 to raise TemplateNotFound
            with patch(
                "functions.monthly_reports.accounts.create_report.create_report.generate_pdf.Environment"
            ) as mock_env:
                from jinja2 import TemplateNotFound

                mock_env_instance = MagicMock()
                mock_env_instance.get_template.side_effect = TemplateNotFound(
                    "template.html", "template.html"
                )
                mock_env.return_value = mock_env_instance

                # Call the function and expect ReportTemplateError
                with pytest.raises(
                    ReportTemplateError, match="Missing template: template.html"
                ):
                    generate_transactions_pdf(sample_event, mock_logger)

                # Verify error was logged
                mock_logger.error.assert_called_with(
                    "Template 'template.html' not found"
                )

    def test_pdf_generation_error(
        self, sample_event, mock_logger, mock_template_content
    ):
        """Test handling of PDF generation error."""
        with patch("os.path.dirname") as mock_dirname:
            mock_dirname.return_value = "/mock/path"

            # Mock the Jinja2 Environment and template
            with patch(
                "functions.monthly_reports.accounts.create_report.create_report.generate_pdf.Environment"
            ) as mock_env:
                mock_template = MagicMock()
                mock_template.render.return_value = "<html><body>Test PDF</body></html>"
                mock_env_instance = MagicMock()
                mock_env_instance.get_template.return_value = mock_template
                mock_env.return_value = mock_env_instance

                # Mock xhtml2pdf to return an error
                with patch("xhtml2pdf.pisa.CreatePDF") as mock_pisa:
                    mock_pisa.return_value.err = True

                    # Call the function and expect ReportGenerationError
                    with pytest.raises(
                        ReportGenerationError, match="Error generating PDF"
                    ):
                        generate_transactions_pdf(sample_event, mock_logger)

                    # Verify error was logged
                    mock_logger.error.assert_called_with(
                        "xhtml2pdf failed to generate PDF"
                    )

    def test_empty_transactions(self, mock_logger, mock_template_content):
        """Test PDF generation with empty transactions list."""
        event_with_empty_transactions = {
            "accountId": "test-account-123",
            "statementPeriod": "2024-01",
            "transactions": [],
            "accountBalance": 1500.00,
        }

        with patch("os.path.dirname") as mock_dirname:
            mock_dirname.return_value = "/mock/path"

            # Mock the Jinja2 Environment and template
            with patch(
                "functions.monthly_reports.accounts.create_report.create_report.generate_pdf.Environment"
            ) as mock_env:
                mock_template = MagicMock()
                mock_template.render.return_value = (
                    "<html><body>Empty PDF</body></html>"
                )
                mock_env_instance = MagicMock()
                mock_env_instance.get_template.return_value = mock_template
                mock_env.return_value = mock_env_instance

                # Mock xhtml2pdf
                with patch("xhtml2pdf.pisa.CreatePDF") as mock_pisa:
                    mock_pisa.return_value.err = False

                    # Mock tempfile
                    with patch("tempfile.NamedTemporaryFile") as mock_tempfile:
                        mock_tempfile_instance = MagicMock()
                        mock_tempfile_instance.name = "/tmp/test.pdf"
                        mock_tempfile.return_value.__enter__.return_value = (
                            mock_tempfile_instance
                        )
                        mock_tempfile.return_value.__exit__.return_value = None

                        # Call the function
                        result = generate_transactions_pdf(
                            event_with_empty_transactions, mock_logger
                        )

                        # Verify template was rendered with empty transactions
                        mock_template.render.assert_called_once()
                        call_args = mock_template.render.call_args[1]
                        assert call_args["transactions"] == []

                        # Verify result is bytes
                        assert isinstance(result, bytes)

    def test_large_transactions_list(self, mock_logger, mock_template_content):
        """Test PDF generation with a large number of transactions."""
        large_transactions = [
            {
                "id": f"txn-{i}",
                "amount": 100.00 + i,
                "description": f"Transaction {i}",
                "date": "2024-01-15",
            }
            for i in range(100)
        ]

        event_with_large_transactions = {
            "accountId": "test-account-123",
            "statementPeriod": "2024-01",
            "transactions": large_transactions,
            "accountBalance": 1500.00,
        }

        with patch("os.path.dirname") as mock_dirname:
            mock_dirname.return_value = "/mock/path"

            # Mock the Jinja2 Environment and template
            with patch(
                "functions.monthly_reports.accounts.create_report.create_report.generate_pdf.Environment"
            ) as mock_env:
                mock_template = MagicMock()
                mock_template.render.return_value = (
                    "<html><body>Large PDF</body></html>"
                )
                mock_env_instance = MagicMock()
                mock_env_instance.get_template.return_value = mock_template
                mock_env.return_value = mock_env_instance

                # Mock xhtml2pdf
                with patch("xhtml2pdf.pisa.CreatePDF") as mock_pisa:
                    mock_pisa.return_value.err = False

                    # Mock tempfile
                    with patch("tempfile.NamedTemporaryFile") as mock_tempfile:
                        mock_tempfile_instance = MagicMock()
                        mock_tempfile_instance.name = "/tmp/test.pdf"
                        mock_tempfile.return_value.__enter__.return_value = (
                            mock_tempfile_instance
                        )
                        mock_tempfile.return_value.__exit__.return_value = None

                        # Call the function
                        result = generate_transactions_pdf(
                            event_with_large_transactions, mock_logger
                        )

                        # Verify template was rendered with all transactions
                        mock_template.render.assert_called_once()
                        call_args = mock_template.render.call_args[1]
                        assert len(call_args["transactions"]) == 100

                        # Verify result is bytes
                        assert isinstance(result, bytes)

    def test_generation_date_format(
        self, sample_event, mock_logger, mock_template_content
    ):
        """Test that generation date is properly formatted."""
        with patch("os.path.dirname") as mock_dirname:
            mock_dirname.return_value = "/mock/path"

            # Mock the Jinja2 Environment and template
            with patch(
                "functions.monthly_reports.accounts.create_report.create_report.generate_pdf.Environment"
            ) as mock_env:
                mock_template = MagicMock()
                mock_template.render.return_value = "<html><body>Test PDF</body></html>"
                mock_env_instance = MagicMock()
                mock_env_instance.get_template.return_value = mock_template
                mock_env.return_value = mock_env_instance

                # Mock xhtml2pdf
                with patch("xhtml2pdf.pisa.CreatePDF") as mock_pisa:
                    mock_pisa.return_value.err = False

                    # Mock tempfile
                    with patch("tempfile.NamedTemporaryFile") as mock_tempfile:
                        mock_tempfile_instance = MagicMock()
                        mock_tempfile_instance.name = "/tmp/test.pdf"
                        mock_tempfile.return_value.__enter__.return_value = (
                            mock_tempfile_instance
                        )
                        mock_tempfile.return_value.__exit__.return_value = None

                        # Call the function
                        generate_transactions_pdf(sample_event, mock_logger)

                        # Verify generation date format
                        mock_template.render.assert_called_once()
                        call_args = mock_template.render.call_args[1]
                        generation_date = call_args["generationDate"]

                        # Check that it matches the expected format: YYYY-MM-DD HH:MM:SS UTC
                        import re

                        pattern = r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2} UTC$"
                        assert re.match(pattern, generation_date) is not None

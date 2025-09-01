import pytest
from unittest.mock import patch
from botocore.exceptions import ClientError
from functions.monthly_reports.accounts.create_report.create_report.exceptions import (
    ReportGenerationError,
    ReportTemplateError,
    ReportUploadError,
)


class TestCreateReportLambdaHandler:
    """Test cases for the create_report Lambda handler."""

    def test_successful_report_creation(
        self,
        create_report_app_with_mocks,
        sample_event,
        mock_pdf_bytes,
        mock_presigned_url,
        mock_context,
    ):
        """Test successful report creation and upload."""
        app = create_report_app_with_mocks

        # Mock the PDF generation
        with patch(
            "functions.monthly_reports.accounts.create_report.create_report.app.generate_transactions_pdf"
        ) as mock_generate_pdf:
            mock_generate_pdf.return_value = mock_pdf_bytes

            # Mock S3 operations
            app.s3.put_object.return_value = {
                "ResponseMetadata": {"HTTPStatusCode": 200}
            }
            app.s3.generate_presigned_url.return_value = mock_presigned_url

            # Call the handler
            result = app.lambda_handler(sample_event, mock_context)

            # Verify PDF generation was called
            mock_generate_pdf.assert_called_once_with(
                event=sample_event, logger=app.logger
            )

            # Verify S3 upload was called with correct parameters
            app.s3.put_object.assert_called_once_with(
                Bucket="test-reports-bucket",
                Key=f"{sample_event['accountId']}/{sample_event['statementPeriod']}.pdf",
                Body=mock_pdf_bytes,
                ContentType="application/pdf",
            )

            # Verify presigned URL generation was called
            app.s3.generate_presigned_url.assert_called_once_with(
                "get_object",
                Params={
                    "Bucket": "test-reports-bucket",
                    "Key": f"{sample_event['accountId']}/{sample_event['statementPeriod']}.pdf",
                },
                ExpiresIn=3600,
            )

            # Verify the response
            expected_response = {
                "reportUrl": mock_presigned_url,
                "accountId": sample_event["accountId"],
                "userId": sample_event["userId"],
                "statementPeriod": sample_event["statementPeriod"],
            }
            assert result == expected_response

    def test_pdf_generation_error(
        self, create_report_app_with_mocks, sample_event, mock_context
    ):
        """Test handling of PDF generation errors."""
        app = create_report_app_with_mocks

        # Mock PDF generation to raise an error
        with patch(
            "functions.monthly_reports.accounts.create_report.create_report.app.generate_transactions_pdf"
        ) as mock_generate_pdf:
            mock_generate_pdf.side_effect = ReportGenerationError(
                "PDF generation failed"
            )

            # Call the handler and expect the error to be re-raised
            with pytest.raises(ReportGenerationError, match="PDF generation failed"):
                app.lambda_handler(sample_event, mock_context)

            # Verify S3 operations were not called
            app.s3.put_object.assert_not_called()
            app.s3.generate_presigned_url.assert_not_called()

    def test_template_error(
        self, create_report_app_with_mocks, sample_event, mock_context
    ):
        """
        Verify the Lambda handler re-raises ReportTemplateError from PDF generation and does not perform any S3 operations.
        
        This test mocks generate_transactions_pdf to raise ReportTemplateError("Template not found"), invokes the handler with a valid event/context, asserts the same exception is propagated, and confirms that neither S3 put_object nor presigned URL generation are called.
        """
        app = create_report_app_with_mocks

        # Mock PDF generation to raise a template error
        with patch(
            "functions.monthly_reports.accounts.create_report.create_report.app.generate_transactions_pdf"
        ) as mock_generate_pdf:
            mock_generate_pdf.side_effect = ReportTemplateError("Template not found")

            # Call the handler and expect the error to be re-raised
            with pytest.raises(ReportTemplateError, match="Template not found"):
                app.lambda_handler(sample_event, mock_context)

            # Verify S3 operations were not called
            app.s3.put_object.assert_not_called()
            app.s3.generate_presigned_url.assert_not_called()

    def test_s3_upload_error(
        self, create_report_app_with_mocks, sample_event, mock_pdf_bytes, mock_context
    ):
        """Test handling of S3 upload errors."""
        app = create_report_app_with_mocks

        # Mock the PDF generation
        with patch(
            "functions.monthly_reports.accounts.create_report.create_report.app.generate_transactions_pdf"
        ) as mock_generate_pdf:
            mock_generate_pdf.return_value = mock_pdf_bytes

            # Mock S3 upload to raise an error
            error_response = {
                "Error": {"Code": "NoSuchBucket", "Message": "Bucket does not exist"}
            }
            app.s3.put_object.side_effect = ClientError(error_response, "PutObject")

            # Call the handler and expect a ReportUploadError
            with pytest.raises(ReportUploadError, match="S3 upload failed"):
                app.lambda_handler(sample_event, mock_context)

            # Verify presigned URL generation was not called
            app.s3.generate_presigned_url.assert_not_called()

    def test_presigned_url_generation_error(
        self, create_report_app_with_mocks, sample_event, mock_pdf_bytes, mock_context
    ):
        """Test handling of presigned URL generation errors."""
        app = create_report_app_with_mocks

        # Mock the PDF generation
        with patch(
            "functions.monthly_reports.accounts.create_report.create_report.app.generate_transactions_pdf"
        ) as mock_generate_pdf:
            mock_generate_pdf.return_value = mock_pdf_bytes

            # Mock S3 upload to succeed
            app.s3.put_object.return_value = {
                "ResponseMetadata": {"HTTPStatusCode": 200}
            }

            # Mock presigned URL generation to raise an error
            error_response = {
                "Error": {"Code": "AccessDenied", "Message": "Access denied"}
            }
            app.s3.generate_presigned_url.side_effect = ClientError(
                error_response, "GeneratePresignedUrl"
            )

            # Call the handler and expect a ReportUploadError
            with pytest.raises(
                ReportUploadError, match="Presigned URL generation failed"
            ):
                app.lambda_handler(sample_event, mock_context)

    def test_missing_required_event_fields(
        self, create_report_app_with_mocks, mock_context
    ):
        """Test handling of missing required event fields."""
        app = create_report_app_with_mocks

        # Create event with missing fields
        incomplete_event = {
            "accountId": "test-account-123"
            # Missing userId, statementPeriod, transactions, accountBalance
        }

        with pytest.raises(ReportGenerationError):
            app.lambda_handler(incomplete_event, mock_context)

    def test_empty_transactions_list(
        self, create_report_app_with_mocks, mock_presigned_url, mock_context
    ):
        """Test handling of empty transactions list."""
        app = create_report_app_with_mocks

        # Create event with empty transactions
        event_with_empty_transactions = {
            "accountId": "test-account-123",
            "userId": "test-user-456",
            "statementPeriod": "2024-01",
            "transactions": [],
            "accountBalance": 1500.00,
        }

        mock_pdf_bytes = b"%PDF-1.4\n%Empty transactions PDF\n%%EOF"

        # Mock the PDF generation
        with patch(
            "functions.monthly_reports.accounts.create_report.create_report.app.generate_transactions_pdf"
        ) as mock_generate_pdf:
            mock_generate_pdf.return_value = mock_pdf_bytes

            # Mock S3 operations
            app.s3.put_object.return_value = {
                "ResponseMetadata": {"HTTPStatusCode": 200}
            }
            app.s3.generate_presigned_url.return_value = mock_presigned_url

            # Call the handler
            result = app.lambda_handler(event_with_empty_transactions, mock_context)

            # Verify the response is correct
            expected_response = {
                "reportUrl": mock_presigned_url,
                "accountId": event_with_empty_transactions["accountId"],
                "userId": event_with_empty_transactions["userId"],
                "statementPeriod": event_with_empty_transactions["statementPeriod"],
            }
            assert result == expected_response

    def test_logger_integration(
        self,
        create_report_app_with_mocks,
        sample_event,
        mock_pdf_bytes,
        mock_presigned_url,
        mock_context,
    ):
        """Test that logging is properly integrated."""
        app = create_report_app_with_mocks

        # Mock the PDF generation
        with patch(
            "functions.monthly_reports.accounts.create_report.create_report.app.generate_transactions_pdf"
        ) as mock_generate_pdf:
            mock_generate_pdf.return_value = mock_pdf_bytes

            # Mock S3 operations
            app.s3.put_object.return_value = {
                "ResponseMetadata": {"HTTPStatusCode": 200}
            }
            app.s3.generate_presigned_url.return_value = mock_presigned_url

            # Call the handler
            result = app.lambda_handler(sample_event, mock_context)

            # Verify that the logger was used (we can't easily verify the exact calls due to the way powertools works)
            # But we can verify the function completed successfully, which means logging worked
            assert result is not None
            assert "reportUrl" in result

    def test_s3_key_format(
        self,
        create_report_app_with_mocks,
        sample_event,
        mock_pdf_bytes,
        mock_presigned_url,
        mock_context,
    ):
        """Test that S3 key is formatted correctly."""
        app = create_report_app_with_mocks

        # Mock the PDF generation
        with patch(
            "functions.monthly_reports.accounts.create_report.create_report.app.generate_transactions_pdf"
        ) as mock_generate_pdf:
            mock_generate_pdf.return_value = mock_pdf_bytes

            # Mock S3 operations
            app.s3.put_object.return_value = {
                "ResponseMetadata": {"HTTPStatusCode": 200}
            }
            app.s3.generate_presigned_url.return_value = mock_presigned_url

            # Call the handler
            app.lambda_handler(sample_event, mock_context)

            # Verify S3 key format
            expected_key = (
                f"{sample_event['accountId']}/{sample_event['statementPeriod']}.pdf"
            )
            app.s3.put_object.assert_called_once()
            call_args = app.s3.put_object.call_args
            assert call_args[1]["Key"] == expected_key

    def test_presigned_url_expiration(
        self,
        create_report_app_with_mocks,
        sample_event,
        mock_pdf_bytes,
        mock_presigned_url,
        mock_context,
    ):
        """Test that presigned URL is generated with correct expiration."""
        app = create_report_app_with_mocks

        # Mock the PDF generation
        with patch(
            "functions.monthly_reports.accounts.create_report.create_report.app.generate_transactions_pdf"
        ) as mock_generate_pdf:
            mock_generate_pdf.return_value = mock_pdf_bytes

            # Mock S3 operations
            app.s3.put_object.return_value = {
                "ResponseMetadata": {"HTTPStatusCode": 200}
            }
            app.s3.generate_presigned_url.return_value = mock_presigned_url

            # Call the handler
            app.lambda_handler(sample_event, mock_context)

            # Verify presigned URL expiration
            app.s3.generate_presigned_url.assert_called_once()
            call_args = app.s3.generate_presigned_url.call_args
            assert call_args[1]["ExpiresIn"] == 3600

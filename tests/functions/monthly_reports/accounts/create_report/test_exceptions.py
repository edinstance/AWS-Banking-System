import pytest
from functions.monthly_reports.accounts.create_report.create_report.exceptions import (
    ReportGenerationError,
    ReportTemplateError,
    ReportUploadError,
)


class TestReportExceptions:
    """Test cases for the custom exceptions used in the create_report module."""

    def test_report_generation_error(self):
        """Test ReportGenerationError exception."""
        error_message = "PDF generation failed"
        error = ReportGenerationError(error_message)

        assert str(error) == error_message
        assert isinstance(error, Exception)
        assert isinstance(error, ReportGenerationError)

    def test_report_template_error(self):
        """Test ReportTemplateError exception."""
        error_message = "Template not found"
        error = ReportTemplateError(error_message)

        assert str(error) == error_message
        assert isinstance(error, Exception)
        assert isinstance(error, ReportTemplateError)

    def test_report_upload_error(self):
        """Test ReportUploadError exception."""
        error_message = "S3 upload failed"
        error = ReportUploadError(error_message)

        assert str(error) == error_message
        assert isinstance(error, Exception)
        assert isinstance(error, ReportUploadError)

    def test_exception_inheritance(self):
        """Test that all custom exceptions inherit from Exception."""
        exceptions = [ReportGenerationError, ReportTemplateError, ReportUploadError]

        for exception_class in exceptions:
            assert issubclass(exception_class, Exception)

    def test_exception_uniqueness(self):
        """Test that all exceptions are unique classes."""
        exceptions = [ReportGenerationError, ReportTemplateError, ReportUploadError]

        for i, exception_class in enumerate(exceptions):
            for j, other_exception_class in enumerate(exceptions):
                if i != j:
                    assert exception_class != other_exception_class

    def test_exception_with_empty_message(self):
        """Test exceptions with empty messages."""
        empty_message = ""

        generation_error = ReportGenerationError(empty_message)
        template_error = ReportTemplateError(empty_message)
        upload_error = ReportUploadError(empty_message)

        assert str(generation_error) == empty_message
        assert str(template_error) == empty_message
        assert str(upload_error) == empty_message

    def test_exception_with_none_message(self):
        """Test exceptions with None messages."""
        none_message = None

        generation_error = ReportGenerationError(none_message)
        template_error = ReportTemplateError(none_message)
        upload_error = ReportUploadError(none_message)

        assert str(generation_error) == "None"
        assert str(template_error) == "None"
        assert str(upload_error) == "None"

    def test_exception_with_long_message(self):
        """Test exceptions with long messages."""
        long_message = "A" * 1000

        generation_error = ReportGenerationError(long_message)
        template_error = ReportTemplateError(long_message)
        upload_error = ReportUploadError(long_message)

        assert str(generation_error) == long_message
        assert str(template_error) == long_message
        assert str(upload_error) == long_message

    def test_exception_with_special_characters(self):
        """Test exceptions with special characters in messages."""
        special_message = "Error with special chars: !@#$%^&*()_+-=[]{}|;':\",./<>?"

        generation_error = ReportGenerationError(special_message)
        template_error = ReportTemplateError(special_message)
        upload_error = ReportUploadError(special_message)

        assert str(generation_error) == special_message
        assert str(template_error) == special_message
        assert str(upload_error) == special_message

    def test_exception_with_unicode_characters(self):
        """Test exceptions with unicode characters in messages."""
        unicode_message = "Error with unicode: 你好世界 🌍"

        generation_error = ReportGenerationError(unicode_message)
        template_error = ReportTemplateError(unicode_message)
        upload_error = ReportUploadError(unicode_message)

        assert str(generation_error) == unicode_message
        assert str(template_error) == unicode_message
        assert str(upload_error) == unicode_message

    def test_exception_raising_and_catching(self):
        """Test that exceptions can be raised and caught properly."""
        error_message = "Test error message"

        # Test ReportGenerationError
        with pytest.raises(ReportGenerationError) as exc_info:
            raise ReportGenerationError(error_message)
        assert str(exc_info.value) == error_message

        # Test ReportTemplateError
        with pytest.raises(ReportTemplateError) as exc_info:
            raise ReportTemplateError(error_message)
        assert str(exc_info.value) == error_message

        # Test ReportUploadError
        with pytest.raises(ReportUploadError) as exc_info:
            raise ReportUploadError(error_message)
        assert str(exc_info.value) == error_message

    def test_exception_in_except_block(self):
        """Test that exceptions work properly in except blocks."""

        def function_that_raises_generation_error():
            raise ReportGenerationError("Generation failed")

        def function_that_raises_template_error():
            raise ReportTemplateError("Template failed")

        def function_that_raises_upload_error():
            raise ReportUploadError("Upload failed")

        # Test catching and re-raising
        with pytest.raises(ReportGenerationError) as exc_info:
            try:
                function_that_raises_generation_error()
            except ReportGenerationError as e:
                assert str(e) == "Generation failed"
                # Re-raise to test it works
                raise
        assert str(exc_info.value) == "Generation failed"

        with pytest.raises(ReportTemplateError) as exc_info:
            try:
                function_that_raises_template_error()
            except ReportTemplateError as e:
                assert str(e) == "Template failed"
                raise
        assert str(exc_info.value) == "Template failed"

        with pytest.raises(ReportUploadError) as exc_info:
            try:
                function_that_raises_upload_error()
            except ReportUploadError as e:
                assert str(e) == "Upload failed"
                raise
        assert str(exc_info.value) == "Upload failed"

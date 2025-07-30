import pytest

from monthly_reports.responses import create_response


class TestResponses:

    @pytest.mark.parametrize(
        "status,expected_code",
        [
            ("COMPLETED", 200),
            ("TIMEOUT_CONTINUATION", 202),
            ("ERROR_NO_CONTINUATION_QUEUE", 500),
            ("CRITICAL_ERROR", 500),
            ("UNKNOWN_STATUS", 500),
        ],
    )
    def test_create_response_status_codes(self, mock_logger, status, expected_code):
        metrics = {
            "processed_count": 1,
            "failed_starts_count": 0,
            "skipped_count": 0,
            "already_exists_count": 0,
        }
        result = create_response(metrics, status, mock_logger)

        assert result
        assert result.get("statusCode") == expected_code

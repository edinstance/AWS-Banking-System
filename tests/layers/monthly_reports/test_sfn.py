import uuid
from unittest.mock import patch

import pytest
from botocore.exceptions import ClientError

from monthly_reports.sfn import start_sfn_execution_with_retry


class TestStartExecution:

    def test_success(self, mock_logger, magic_mock_sfn_client):

        input_id = str(uuid.uuid4())

        result = start_sfn_execution_with_retry(
            magic_mock_sfn_client,
            "test-state-machine-arn",
            "test-input",
            {"id": input_id},
            mock_logger,
        )

        assert result == "processed"
        assert magic_mock_sfn_client.start_execution.call_count == 1

    def test_execution_already_exists(self, mock_logger, magic_mock_sfn_client):

        magic_mock_sfn_client.start_execution.side_effect = ClientError(
            {"Error": {"Code": "ExecutionAlreadyExistsException"}}, "StartExecution"
        )

        input_id = str(uuid.uuid4())

        result = start_sfn_execution_with_retry(
            magic_mock_sfn_client,
            "test-state-machine-arn",
            "test-input",
            {"id": input_id},
            mock_logger,
        )

        assert result == "already_exists"

    @pytest.mark.parametrize(
        "error_code", ["ThrottlingException", "ServiceUnavailable", "InternalFailure"]
    )
    def test_retryable_error_success_on_retry(
        self, mock_logger, magic_mock_sfn_client, error_code
    ):
        with patch("time.sleep"):

            magic_mock_sfn_client.start_execution.side_effect = [
                ClientError(
                    error_response={"Error": {"Code": error_code}},
                    operation_name="StartExecution",
                ),
                None,
            ]

            input_id = str(uuid.uuid4())

            result = start_sfn_execution_with_retry(
                magic_mock_sfn_client,
                "test-state-machine-arn",
                "test-execution",
                {"id": input_id},
                mock_logger,
            )

            assert result == "processed"
            assert magic_mock_sfn_client.start_execution.call_count == 2

    @pytest.mark.parametrize(
        "error_code", ["ThrottlingException", "ServiceUnavailable", "InternalFailure"]
    )
    def test_retryable_error_max_retries_exceeded(
        self, mock_logger, magic_mock_sfn_client, error_code, mocker
    ):
        with patch("time.sleep") as mock_sleep:

            client_error = ClientError(
                error_response={"Error": {"Code": error_code}},
                operation_name="StartExecution",
            )
            magic_mock_sfn_client.start_execution.side_effect = client_error

            input_id = str(uuid.uuid4())

            with pytest.raises(ClientError):
                start_sfn_execution_with_retry(
                    magic_mock_sfn_client,
                    "test-state-machine-arn",
                    "test-execution",
                    {"id": input_id},
                    mock_logger,
                    max_retries=3,
                )

            assert magic_mock_sfn_client.start_execution.call_count == 3
            assert mock_sleep.call_count == 2

    def test_non_retryable_error(self, mock_logger, magic_mock_sfn_client):
        client_error = ClientError(
            error_response={"Error": {"Code": "InvalidParameterValue"}},
            operation_name="StartExecution",
        )
        magic_mock_sfn_client.start_execution.side_effect = client_error

        input_id = str(uuid.uuid4())

        with pytest.raises(ClientError):
            start_sfn_execution_with_retry(
                magic_mock_sfn_client,
                "test-state-machine-arn",
                "test-execution",
                {"id": input_id},
                mock_logger,
            )

        assert magic_mock_sfn_client.start_execution.call_count == 1
        mock_logger.error.assert_called_once()

    def test_custom_max_retries(self, mock_logger, magic_mock_sfn_client, mocker):
        with patch("time.sleep") as mock_sleep:
            client_error = ClientError(
                error_response={"Error": {"Code": "ThrottlingException"}},
                operation_name="StartExecution",
            )
            magic_mock_sfn_client.start_execution.side_effect = client_error

            input_id = str(uuid.uuid4())

            with pytest.raises(ClientError):
                start_sfn_execution_with_retry(
                    magic_mock_sfn_client,
                    "test-state-machine-arn",
                    "test-execution",
                    {"id": input_id},
                    mock_logger,
                    max_retries=2,
                )

            assert magic_mock_sfn_client.start_execution.call_count == 2
            assert mock_sleep.call_count == 1

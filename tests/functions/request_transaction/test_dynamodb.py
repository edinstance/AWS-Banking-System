import uuid
from unittest.mock import patch, MagicMock


class TestDynamoDBInteractions:
    def test_table_initialization_with_environment_variable(
        self, app_with_mocked_table
    ):
        """
        Verify that the DynamoDB table resource is properly initialised when the TRANSACTIONS_TABLE_NAME environment variable is set.

        Asserts that the table attribute is not None and that the table name matches the expected test value.
        """
        assert app_with_mocked_table.table is not None
        assert (
            app_with_mocked_table.TRANSACTIONS_TABLE_NAME == "test-transactions-table"
        )

    def test_lambda_handler_with_uninitialized_table(self, app_without_table):
        """
        Test that the Lambda handler returns a 500 error and logs an error message when the DynamoDB table resource is not initialised.

        Asserts that the response indicates a server configuration error and verifies that an error log about the missing DynamoDB table resource is generated.
        """
        mock_context = MagicMock()
        mock_context.aws_request_id = "test-request-id"
        mock_context.function_name = "test-function"

        with patch.object(app_without_table, "logger") as mock_logger:
            mock_logger.inject_lambda_context.return_value = lambda f: f

            response = app_without_table.lambda_handler(
                {
                    "httpMethod": "POST",
                    "path": "/transactions",
                },
                mock_context,
            )

            assert response["statusCode"] == 500
            assert "Server configuration error" in response["body"]

            mock_logger.error.assert_called_with(
                "DynamoDB table resource is not initialized"
            )

    #

    def test_lambda_handler_with_initialized_table(self, app_with_mocked_table):
        """
        Test that the Lambda handler returns a 400 error when the Idempotency-Key header is missing, even if the DynamoDB table is initialised.

        Verifies that the response contains an appropriate error message and that the DynamoDB table resource remains available on the application instance.
        """
        mock_context = MagicMock()
        mock_context.aws_request_id = "test-request-id"
        mock_context.function_name = "test-function"

        with patch.object(app_with_mocked_table, "logger") as mock_logger:
            mock_logger.inject_lambda_context.return_value = lambda f: f

            event = {
                "httpMethod": "POST",
                "path": "/transactions",
                "headers": {},
                "requestContext": {
                    "authorizer": {"claims": {"sub": str(uuid.uuid4())}}
                },
            }

            response = app_with_mocked_table.lambda_handler(event, mock_context)

            assert response["statusCode"] == 400
            assert "Idempotency-Key header is required" in response["body"]

            assert app_with_mocked_table.table is not None

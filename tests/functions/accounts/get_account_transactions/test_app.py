import json
import uuid
from unittest.mock import patch

import pytest
from aws_lambda_powertools.event_handler.exceptions import (
    InternalServerError,
)
from botocore.exceptions import ClientError

from functions.accounts.get_account_transactions.get_account_transactions.app import (
    lambda_handler,
)
from functions.accounts.get_account_transactions.get_account_transactions.exceptions import (
    ValidationError,
)


class TestGetAccountTransactionsAPI:

    def test_get_account_transactions_success(
        self, valid_get_transactions_event, mock_context
    ):
        account_id = valid_get_transactions_event["pathParameters"]["account_id"]

        with patch(
            "functions.accounts.get_account_transactions.get_account_transactions.app.table"
        ) as mock_table:
            mock_table.query.return_value = {
                "Items": [
                    {
                        "id": str(uuid.uuid4()),
                        "accountId": account_id,
                        "amount": "100.50",
                        "type": "DEPOSIT",
                        "description": "Test transaction",
                        "status": "COMPLETED",
                        "createdAt": "2023-01-01T12:00:00Z",
                    }
                ]
            }

            response = lambda_handler(valid_get_transactions_event, mock_context)
            response_body = json.loads(response["body"])

            assert response["statusCode"] == 200
            assert "transactions" in response_body
            assert len(response_body["transactions"]) == 1
            assert response_body["transactions"][0]["accountId"] == account_id

    def test_get_account_transactions_with_period_param(
        self, valid_get_transactions_event, mock_context
    ):
        account_id = valid_get_transactions_event["pathParameters"]["account_id"]
        valid_get_transactions_event["queryStringParameters"] = {"period": "2023-01"}

        with patch(
            "functions.accounts.get_account_transactions.get_account_transactions.app.table"
        ) as mock_table:
            mock_table.query.return_value = {
                "Items": [
                    {
                        "id": str(uuid.uuid4()),
                        "accountId": account_id,
                        "amount": "100.50",
                        "type": "DEPOSIT",
                        "description": "Test transaction",
                        "status": "COMPLETED",
                        "createdAt": "2023-01-15T12:00:00Z",
                    }
                ]
            }

            response = lambda_handler(valid_get_transactions_event, mock_context)
            response_body = json.loads(response["body"])

            assert response["statusCode"] == 200
            assert "transactions" in response_body
            assert len(response_body["transactions"]) == 1

    def test_get_account_transactions_with_date_range_params(
        self, valid_get_transactions_event, mock_context
    ):
        account_id = valid_get_transactions_event["pathParameters"]["account_id"]
        valid_get_transactions_event["queryStringParameters"] = {
            "start": "2023-01-01",
            "end": "2023-01-31",
        }

        with patch(
            "functions.accounts.get_account_transactions.get_account_transactions.app.table"
        ) as mock_table:
            mock_table.query.return_value = {
                "Items": [
                    {
                        "id": str(uuid.uuid4()),
                        "accountId": account_id,
                        "amount": "100.50",
                        "type": "DEPOSIT",
                        "description": "Test transaction",
                        "status": "COMPLETED",
                        "createdAt": "2023-01-15T12:00:00Z",
                    }
                ]
            }

            response = lambda_handler(valid_get_transactions_event, mock_context)
            response_body = json.loads(response["body"])

            assert response["statusCode"] == 200
            assert "transactions" in response_body
            assert len(response_body["transactions"]) == 1

    def test_get_account_transactions_validation_error(
        self, valid_get_transactions_event, mock_context
    ):
        with patch(
            "functions.accounts.get_account_transactions.get_account_transactions.app.table"
        ) as mock_table:
            mock_table.query.side_effect = ValidationError("Invalid date range")

            response = lambda_handler(valid_get_transactions_event, mock_context)

            assert response["statusCode"] == 400
            response_body = json.loads(response["body"])
            assert "Invalid date range" in response_body["message"]

    def test_get_account_transactions_client_error(
        self, valid_get_transactions_event, mock_context
    ):
        """Test handling of DynamoDB client errors"""
        error_response = {
            "Error": {"Code": "InternalServerError", "Message": "Internal server error"}
        }
        with patch(
            "functions.accounts.get_account_transactions.get_account_transactions.app.table"
        ) as mock_table:
            mock_table.query.side_effect = ClientError(error_response, "Query")

            response = lambda_handler(valid_get_transactions_event, mock_context)

            assert response["statusCode"] == 500
            response_body = json.loads(response["body"])
            assert "Internal server error" in response_body["message"]

    def test_get_account_transactions_general_exception(
        self, valid_get_transactions_event, mock_context
    ):
        with patch(
            "functions.accounts.get_account_transactions.get_account_transactions.app.table"
        ) as mock_table:
            mock_table.query.side_effect = Exception("Unexpected error")

            response = lambda_handler(valid_get_transactions_event, mock_context)

            assert response["statusCode"] == 500
            response_body = json.loads(response["body"])
            assert "Internal server error" in response_body["message"]


class TestGetAccountTransactionsStepFunctions:

    def test_step_functions_request_success(self, step_functions_event, mock_context):
        account_id = step_functions_event["accountId"]

        with patch(
            "functions.accounts.get_account_transactions.get_account_transactions.app.table"
        ) as mock_table:
            mock_table.query.return_value = {
                "Items": [
                    {
                        "id": str(uuid.uuid4()),
                        "accountId": account_id,
                        "amount": "100.50",
                        "type": "DEPOSIT",
                        "description": "Test transaction",
                        "status": "COMPLETED",
                        "createdAt": "2023-01-01T12:00:00Z",
                    }
                ]
            }

            response = lambda_handler(step_functions_event, mock_context)

            assert "transactions" in response
            assert len(response["transactions"]) == 1
            assert response["transactions"][0]["accountId"] == account_id
            assert response["accountId"] == account_id

    def test_step_functions_request_missing_account_id(self, mock_context):
        event = {"someOtherField": "value"}

        with patch(
            "functions.accounts.get_account_transactions.get_account_transactions.app.table"
        ) as mock_table:
            mock_table.query.return_value = {"Items": []}

            response = lambda_handler(event, mock_context)

            assert response["statusCode"] == 400
            response_body = json.loads(response["body"])
            assert "Missing accountId" in response_body["error"]

    def test_step_functions_request_exception(self, step_functions_event, mock_context):
        with patch(
            "functions.accounts.get_account_transactions.get_account_transactions.app.table"
        ) as mock_table:
            mock_table.query.side_effect = Exception("Database error")

            response = lambda_handler(step_functions_event, mock_context)

            assert response["statusCode"] == 500
            response_body = json.loads(response["body"])
            assert "Database error" in response_body["error"]


class TestLambdaHandlerConfiguration:

    def test_lambda_handler_missing_table_configuration(self, mock_context):
        with patch(
            "functions.accounts.get_account_transactions.get_account_transactions.app.table",
            None,
        ):
            event = {"httpMethod": "GET", "path": "/accounts/123/transactions"}

            with pytest.raises(InternalServerError) as exc_info:
                lambda_handler(event, mock_context)

            assert "Server configuration error" in str(exc_info.value)

    def test_transactions_table_not_initialized(
        self, mock_context, step_functions_event
    ):
        """
        Ensure the handler raises InternalServerError with the exact message "Server configuration error"
        when the transactions table is not initialised and a Step Functions-style event is received.
        
        This patches the app.table to None, invokes the lambda_handler with a step functions event,
        and asserts that an InternalServerError is raised with the precise error message.
        """
        with patch(
            "functions.accounts.get_account_transactions.get_account_transactions.app.table",
            None,
        ):
            with pytest.raises(InternalServerError) as exc_info:
                lambda_handler(step_functions_event, mock_context)

            assert str(exc_info.value) == "Server configuration error"

    def test_table_initialization_with_environment_variables(
        self, get_account_transactions_app_with_mocked_tables
    ):
        assert get_account_transactions_app_with_mocked_tables.table is not None

        assert (
            get_account_transactions_app_with_mocked_tables.TRANSACTIONS_TABLE_NAME
            == "test-transactions-table"
        )

import json
import uuid
from unittest.mock import patch

import pytest
from aws_lambda_powertools.event_handler.exceptions import (
    UnauthorizedError,
    InternalServerError,
)
from botocore.exceptions import ClientError

from functions.accounts.get_accounts.get_accounts.app import lambda_handler
from tests.functions.accounts.get_accounts.conftest import TEST_USER_ID


class TestGetAccount:
    def test_get_account_success(
        self, valid_get_account_event, mock_context, mock_auth
    ):
        account_id = valid_get_account_event["pathParameters"]["account_id"]

        with patch(
            "functions.accounts.get_accounts.get_accounts.app.table"
        ) as mock_table:
            mock_table.get_item.return_value = {
                "Item": {
                    "id": account_id,
                    "userId": TEST_USER_ID,
                    "accountId": account_id,
                    "amount": "100.50",
                    "type": "DEPOSIT",
                    "description": "Test account",
                    "status": "COMPLETED",
                    "createdAt": "2023-01-01T12:00:00Z",
                }
            }

            response = lambda_handler(valid_get_account_event, mock_context)
            response_body = json.loads(response["body"])

            assert response["statusCode"] == 200
            assert response_body["accountId"] == account_id
            assert response_body["userId"] == TEST_USER_ID

    def test_get_account_client_error(
        self, valid_get_account_event, mock_context, mock_auth
    ):
        error_response = {
            "Error": {"Code": "InternalServerError", "Message": "Internal server error"}
        }
        with patch(
            "functions.accounts.get_accounts.get_accounts.app.table"
        ) as mock_table:
            mock_table.get_item.side_effect = ClientError(error_response, "Query")

            response = lambda_handler(valid_get_account_event, mock_context)

            assert response["statusCode"] == 500
            response_body = json.loads(response["body"])
            assert "Internal server error" in response_body["message"]

    def test_get_account_value_error(
        self, valid_get_account_event, mock_context, mock_auth
    ):
        with patch(
            "functions.accounts.get_accounts.get_accounts.app.table"
        ) as mock_table:
            mock_table.get_item.side_effect = ValueError("Invalid account ID")

            response = lambda_handler(valid_get_account_event, mock_context)

            assert response["statusCode"] == 400
            response_body = json.loads(response["body"])
            assert "Invalid account id" in response_body["message"]


class TestGetAccounts:
    def test_get_accounts_success(self, valid_get_event, mock_context, mock_auth):
        with patch(
            "functions.accounts.get_accounts.get_accounts.app.table"
        ) as mock_table:
            mock_table.query.return_value = {
                "Items": [
                    {
                        "id": str(uuid.uuid4()),
                        "userId": TEST_USER_ID,
                        "accountId": str(uuid.uuid4()),
                        "amount": "100.50",
                        "type": "DEPOSIT",
                        "description": "Test account",
                        "status": "COMPLETED",
                        "createdAt": "2023-01-01T12:00:00Z",
                    }
                ]
            }

            response = lambda_handler(valid_get_event, mock_context)
            response_body = json.loads(response["body"])

            assert response["statusCode"] == 200
            assert response_body[0]["userId"] == TEST_USER_ID

            mock_table.query.assert_called_once_with(
                IndexName="UserIdIndex",
                KeyConditionExpression="userId = :userId",
                ExpressionAttributeValues={":userId": TEST_USER_ID},
            )

    def test_get_accounts_auth_error(self, valid_get_event, mock_context):
        auth_error = UnauthorizedError("Authentication failed")
        with patch("functions.accounts.get_accounts.get_accounts.app.table"), patch(
            "functions.accounts.get_accounts.get_accounts.app.authenticate_request"
        ) as mock_auth:
            mock_auth.side_effect = auth_error

            response = lambda_handler(valid_get_event, mock_context)

            assert response["statusCode"] == 401
            response_body = json.loads(response["body"])
            assert response_body["message"] == "Authentication failed"

    def test_get_accounts_client_error(self, valid_get_event, mock_context, mock_auth):
        error_response = {
            "Error": {"Code": "InternalServerError", "Message": "Internal server error"}
        }
        with patch(
            "functions.accounts.get_accounts.get_accounts.app.table"
        ) as mock_table:
            mock_table.query.side_effect = ClientError(error_response, "Query")

            response = lambda_handler(valid_get_event, mock_context)

            assert response["statusCode"] == 500
            response_body = json.loads(response["body"])
            assert "Internal server error" in response_body["message"]


class TestConfig:
    def test_accounts_table_not_initialized(self, mock_context, valid_get_event):
        with patch("functions.accounts.get_accounts.get_accounts.app.table", None):
            with pytest.raises(InternalServerError) as exc_info:
                lambda_handler(valid_get_event, mock_context)

            assert str(exc_info.value) == "Server configuration error"

    def test_table_initialization_with_environment_variables(
        self, get_accounts_app_with_mocked_tables
    ):
        assert get_accounts_app_with_mocked_tables.accounts_table is not None

        assert (
            get_accounts_app_with_mocked_tables.ACCOUNTS_TABLE_NAME
            == "test-accounts-table"
        )

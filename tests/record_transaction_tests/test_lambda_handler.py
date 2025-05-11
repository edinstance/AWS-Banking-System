import json
import uuid
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from importlib import reload
from unittest.mock import patch, MagicMock

from functions.record_transactions import app


class TestLambdaHandler:
    """Test cases for the lambda_handler function."""

    def test_successful_transaction_creation(self, app_with_mocked_table):
        """Test the successful creation of a new transaction."""
        # Create a mock context
        mock_context = MagicMock()
        mock_context.aws_request_id = "test-request-id"

        # Create a valid idempotency key
        idempotency_key = str(uuid.uuid4())
        account_id = str(uuid.uuid4())

        # Create a valid request event
        event = {
            "headers": {
                "Idempotency-Key": idempotency_key
            },
            "body": json.dumps({
                "accountId": account_id,
                "amount": 100.50,
                "type": "DEPOSIT",
                "description": "Test transaction"
            })
        }

        # Call the lambda handler
        response = app_with_mocked_table.lambda_handler(event, mock_context)

        # Verify the response
        assert response["statusCode"] == 201
        response_body = json.loads(response["body"])
        assert "transactionId" in response_body
        assert response_body["message"] == "Transaction recorded successfully!"
        assert response_body["status"] == "COMPLETED"
        assert "timestamp" in response_body
        assert response_body["idempotencyKey"] == idempotency_key

        # Verify the transaction was saved in DynamoDB
        transactions = app_with_mocked_table.table.scan()["Items"]
        assert len(transactions) == 1
        transaction = transactions[0]
        assert transaction["accountId"] == account_id
        assert transaction["amount"] == Decimal("100.5")
        assert transaction["type"] == "DEPOSIT"
        assert transaction["description"] == "Test transaction"
        assert transaction["idempotencyKey"] == idempotency_key

    def test_idempotent_request(self, app_with_mocked_table):
        """Test handling of an idempotent request (same idempotency key)."""
        # Create a mock context
        mock_context = MagicMock()
        mock_context.aws_request_id = "test-request-id"

        # Create a valid idempotency key and account id
        idempotency_key = str(uuid.uuid4())
        account_id = str(uuid.uuid4())

        # Create a test transaction with the idempotency key
        now = datetime.now(timezone.utc)
        future_expiration = int((now + timedelta(days=7)).timestamp())

        transaction_item = {
            "id": "existing-transaction-id",
            "createdAt": now.isoformat(),
            "accountId": account_id,
            "amount": Decimal("100.0"),
            "type": "CREDIT",
            "idempotencyKey": idempotency_key,
            "idempotencyExpiration": future_expiration,
            "status": "COMPLETED"
        }

        # Insert the item directly into the table
        app_with_mocked_table.table.put_item(Item=transaction_item)

        # Create a request event with the same idempotency key
        event = {
            "headers": {
                "Idempotency-Key": idempotency_key
            },
            "body": json.dumps({
                "accountId": account_id,
                "amount": 200.75,
                "type": "CREDIT",
                "description": "Different transaction"
            })
        }

        # Call the lambda handler
        response = app_with_mocked_table.lambda_handler(event, mock_context)

        # Verify the response
        assert response["statusCode"] == 201
        response_body = json.loads(response["body"])
        assert response_body["transactionId"] == "existing-transaction-id"
        assert response_body["idempotent"] is True

        # Verify no new transaction was created
        transactions = app_with_mocked_table.table.scan()["Items"]
        assert len(transactions) == 1

    def test_missing_idempotency_key(self, app_with_mocked_table):
        """Test handling of a request without an idempotency key."""
        # Create a mock context
        mock_context = MagicMock()
        mock_context.aws_request_id = "test-request-id"



        # Create a request event without an idempotency key
        event = {
            "headers": {},
            "body": json.dumps({
                "accountId": "test-account-123",
                "amount": 100.50,
                "type": "CREDIT",
                "description": "Test transaction"
            })
        }

        # Call the lambda handler
        response = app_with_mocked_table.lambda_handler(event, mock_context)

        # Verify the response
        assert response["statusCode"] == 400
        response_body = json.loads(response["body"])
        assert "error" in response_body
        assert "Idempotency-Key header is required" in response_body["error"]
        assert "suggestion" in response_body
        assert "example" in response_body

    def test_invalid_idempotency_key_format(self, app_with_mocked_table):
        """Test handling of a request with an invalid idempotency key format."""
        # Create a mock context
        mock_context = MagicMock()
        mock_context.aws_request_id = "test-request-id"

        account_id = str(uuid.uuid4())

        # Create a request event with an invalid idempotency key (too short)
        event = {
            "headers": {
                "Idempotency-Key": "short"
            },
            "body": json.dumps({
                "accountId": account_id,
                "amount": 100.50,
                "type": "CREDIT",
                "description": "Test transaction"
            })
        }

        # Call the lambda handler
        response = app_with_mocked_table.lambda_handler(event, mock_context)

        # Verify the response
        assert response["statusCode"] == 400
        response_body = json.loads(response["body"])
        assert "error" in response_body
        assert "Idempotency-Key must be between 10 and 64 characters" in response_body["error"]

        # Test with a key that's too long
        event["headers"]["Idempotency-Key"] = "x" * 65
        response = app_with_mocked_table.lambda_handler(event, mock_context)
        assert response["statusCode"] == 400
        response_body = json.loads(response["body"])
        assert "Idempotency-Key must be between 10 and 64 characters" in response_body["error"]

    def test_non_uuid_idempotency_key(self, app_with_mocked_table):
        """Test handling of a request with a non-UUID idempotency key."""
        # Create a mock context
        mock_context = MagicMock()
        mock_context.aws_request_id = "test-request-id"

        account_id = str(uuid.uuid4())

        # Create a request event with a non-UUID idempotency key
        event = {
            "headers": {
                "Idempotency-Key": "not-a-uuid-but-long-enough-12345"
            },
            "body": json.dumps({
                "accountId": account_id,
                "amount": 100.50,
                "type": "CREDIT",
                "description": "Test transaction"
            })
        }

        # Call the lambda handler
        response = app_with_mocked_table.lambda_handler(event, mock_context)

        # Verify the response
        assert response["statusCode"] == 400
        response_body = json.loads(response["body"])
        assert "error" in response_body
        assert "Idempotency-Key must be a valid UUID" in response_body["error"]
        assert "example" in response_body

    def test_invalid_json_in_request_body(self, app_with_mocked_table):
        """Test handling of a request with invalid JSON in the body."""
        # Create a mock context
        mock_context = MagicMock()
        mock_context.aws_request_id = "test-request-id"

        # Create a request event with invalid JSON in the body
        event = {
            "headers": {
                "Idempotency-Key": str(uuid.uuid4())
            },
            "body": "{invalid json"
        }

        # Call the lambda handler
        response = app_with_mocked_table.lambda_handler(event, mock_context)

        # Verify the response
        assert response["statusCode"] == 400
        response_body = json.loads(response["body"])
        assert "error" in response_body
        assert "Invalid JSON format in request body" in response_body["error"]

    def test_validation_errors(self, app_with_mocked_table):
        """Test handling of validation errors in transaction data."""
        # Create a mock context
        mock_context = MagicMock()
        mock_context.aws_request_id = "test-request-id"

        # Create a request event with missing required fields
        event = {
            "headers": {
                "Idempotency-Key": str(uuid.uuid4())
            },
            "body": json.dumps({
                # Missing accountId
                "amount": 100.50,
                "type": "CREDIT"
            })
        }

        # Call the lambda handler
        response = app_with_mocked_table.lambda_handler(event, mock_context)

        # Verify the response
        assert response["statusCode"] == 400
        response_body = json.loads(response["body"])
        assert "error" in response_body
        assert "Missing required fields" in response_body["error"]

        # Test with an invalid transaction type
        event["body"] = json.dumps({
            "accountId": "test-account-123",
            "amount": 100.50,
            "type": "INVALID_TYPE"
        })

        response = app_with_mocked_table.lambda_handler(event, mock_context)
        assert response["statusCode"] == 400
        response_body = json.loads(response["body"])
        assert "Invalid transaction type" in response_body["error"]

    def test_database_error_during_idempotency_check(self, app_with_mocked_table):
        """Test handling of database errors during idempotency check."""
        # Create a mock context
        mock_context = MagicMock()
        mock_context.aws_request_id = "test-request-id"

        account_id = str(uuid.uuid4())

        # Create a valid request event
        event = {
            "headers": {
                "Idempotency-Key": str(uuid.uuid4())
            },
            "body": json.dumps({
                "accountId": account_id,
                "amount": 100.50,
                "type": "CREDIT",
                "description": "Test transaction"
            })
        }

        # Mock check_existing_transaction to raise an exception
        with patch.object(app_with_mocked_table, 'check_existing_transaction') as mock_check:
            mock_check.side_effect = Exception("Database error")

            # Call the lambda handler
            response = app_with_mocked_table.lambda_handler(event, mock_context)

            # Verify the response
            assert response["statusCode"] == 500
            response_body = json.loads(response["body"])
            assert "error" in response_body
            assert "Unable to verify transaction uniqueness" in response_body["error"]

    def test_database_error_during_save(self, app_with_mocked_table):
        """Test handling of database errors during transaction save."""
        # Create a mock context
        mock_context = MagicMock()
        mock_context.aws_request_id = "test-request-id"

        account_id = str(uuid.uuid4())

        # Create a valid request event
        event = {
            "headers": {
                "Idempotency-Key": str(uuid.uuid4())
            },
            "body": json.dumps({
                "accountId": account_id,
                "amount": 100.50,
                "type": "DEPOSIT",
                "description": "Test transaction"
            })
        }

        # Mock save_transaction to raise an exception
        with patch.object(app_with_mocked_table, 'save_transaction') as mock_save:
            mock_save.side_effect = Exception("Failed to save")

            # Call the lambda handler
            response = app_with_mocked_table.lambda_handler(event, mock_context)

            # Verify the response
            assert response["statusCode"] == 500
            response_body = json.loads(response["body"])
            assert "error" in response_body
            assert "Failed to process transaction" in response_body["error"]

    def test_unhandled_exception(self, app_with_mocked_table):
        """Test handling of unhandled exceptions."""
        # Create a mock context
        mock_context = MagicMock()
        mock_context.aws_request_id = "test-request-id"

        account_id = str(uuid.uuid4())

        # Create a valid request event
        event = {
            "headers": {
                "Idempotency-Key": str(uuid.uuid4())
            },
            "body": json.dumps({
                "accountId": account_id,
                "amount": 100.50,
                "type": "DEPOSIT",
                "description": "Test transaction"
            })
        }

        # Mock a function to raise an unexpected exception
        with patch.object(app_with_mocked_table, 'validate_transaction_data') as mock_validate:
            mock_validate.side_effect = RuntimeError("Unexpected error")

            # Call the lambda handler
            response = app_with_mocked_table.lambda_handler(event, mock_context)

            # Verify the response
            assert response["statusCode"] == 500
            response_body = json.loads(response["body"])
            assert "error" in response_body
            assert "Internal server error" in response_body["error"]

    def test_table_not_initialized(self, monkeypatch):
        """Test handling when the DynamoDB table is not initialized."""
        # Ensure TRANSACTIONS_TABLE_NAME is not set
        monkeypatch.delenv("TRANSACTIONS_TABLE_NAME", raising=False)

        # Reload app to clear the table
        reload(app)

        # Create a mock context
        mock_context = MagicMock()
        mock_context.aws_request_id = "test-request-id"

        account_id = str(uuid.uuid4())

        # Create a valid request event
        event = {
            "headers": {
                "Idempotency-Key": str(uuid.uuid4())
            },
            "body": json.dumps({
                "accountId": account_id,
                "amount": 100.50,
                "type": "CREDIT",
                "description": "Test transaction"
            })
        }

        # Call the lambda handler
        response = app.lambda_handler(event, mock_context)

        # Verify the response
        assert response["statusCode"] == 500
        response_body = json.loads(response["body"])
        assert "error" in response_body
        assert "Server configuration error" in response_body["error"]

    def test_deposit_transaction(self, monkeypatch, dynamo_table):
        """Test the successful creation of a DEPOSIT transaction."""
        table_name = dynamo_table
        monkeypatch.setenv("TRANSACTIONS_TABLE_NAME", table_name)

        # Reload app to use the mocked table
        reload(app)

        # Create a mock context
        mock_context = MagicMock()
        mock_context.aws_request_id = "test-request-id"

        # Create a valid idempotency key and account id
        idempotency_key = str(uuid.uuid4())
        account_id = str(uuid.uuid4())

        # Create a valid request event for a DEBIT transaction
        event = {
            "headers": {
                "Idempotency-Key": idempotency_key
            },
            "body": json.dumps({
                "accountId": account_id,
                "amount": 50.25,
                "type": "DEPOSIT",
                "description": "Test deposit transaction"
            })
        }

        # Call the lambda handler
        response = app.lambda_handler(event, mock_context)

        # Verify the response
        assert response["statusCode"] == 201
        response_body = json.loads(response["body"])
        assert "transactionId" in response_body
        assert response_body["message"] == "Transaction recorded successfully!"

        # Verify the transaction was saved in DynamoDB
        transactions = app.table.scan()["Items"]
        assert len(transactions) == 1
        transaction = transactions[0]
        assert transaction["accountId"] == account_id
        assert transaction["amount"] == Decimal("50.25")
        assert transaction["type"] == "DEPOSIT"

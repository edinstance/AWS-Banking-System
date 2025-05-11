from datetime import datetime, timezone, timedelta
from decimal import Decimal
from unittest.mock import patch

import pytest
from botocore.exceptions import ClientError


class TestCheckExistingTransaction:
    def test_existing_transaction_found(self, app_with_mocked_table):
        """Test successful retrieval of an existing transaction."""
        # Create a test transaction with an idempotency key
        idempotency_key = "test-idempotency-key"
        now = datetime.now(timezone.utc)
        future_expiration = int((now + timedelta(days=7)).timestamp())

        transaction_item = {
            "id": "test-transaction-id",
            "createdAt": now.isoformat(),
            "accountId": "test-account",
            "amount": Decimal("100.0"),
            "type": "CREDIT",
            "idempotencyKey": idempotency_key,
            "idempotencyExpiration": future_expiration
        }

        # Insert the item directly into the table
        app_with_mocked_table.table.put_item(Item=transaction_item)

        # Call the function
        result = app_with_mocked_table.check_existing_transaction(idempotency_key)

        # Verify the result
        assert result is not None
        assert result["id"] == "test-transaction-id"
        assert result["idempotencyKey"] == idempotency_key

    def test_no_transaction_found(self, app_with_mocked_table):
        """
        Tests that querying with a non-existent idempotency key returns None, indicating no transaction is found.
        """
        # Call the function with a non-existent key
        result = app_with_mocked_table.check_existing_transaction("non-existent-key")

        # Verify the result
        assert result is None

    def test_expired_transaction(self, app_with_mocked_table):
        """
        Tests that an expired transaction is not returned by check_existing_transaction.
        
        Inserts a transaction with an idempotency expiration timestamp in the past and
        verifies that the function returns None, indicating expired transactions are
        ignored.
        """
        # Create a test transaction with an expired idempotency key
        idempotency_key = "expired-idempotency-key"
        now = datetime.now(timezone.utc)
        past_expiration = int((now - timedelta(days=1)).timestamp())  # Expired 1 day ago

        transaction_item = {
            "id": "expired-transaction-id",
            "createdAt": now.isoformat(),
            "accountId": "test-account",
            "amount": Decimal("100.0"),
            "type": "CREDIT",
            "idempotencyKey": idempotency_key,
            "idempotencyExpiration": past_expiration
        }

        # Insert the item directly into the table
        app_with_mocked_table.table.put_item(Item=transaction_item)

        # Call the function
        result = app_with_mocked_table.check_existing_transaction(idempotency_key)

        # Verify the result (should be None since it's expired)
        assert result is None

    def test_client_error_handling(self, app_with_mocked_table):
        """Test error handling when a DynamoDB client raises an error."""
        # Mock the table.query method to raise a ClientError
        with patch.object(app_with_mocked_table.table, 'query') as mock_query:
            error_response = {
                "Error": {
                    "Code": "ProvisionedThroughputExceededException",
                    "Message": "Rate exceeded"
                }
            }
            mock_query.side_effect = ClientError(error_response, "Query")

            # Mock the logger to capture log messages
            with patch.object(app_with_mocked_table.logger, 'error') as mock_error:
                with patch.object(app_with_mocked_table.logger, 'warning') as mock_warning:
                    # Call the function and expect it to raise the exception
                    with pytest.raises(ClientError):
                        app_with_mocked_table.check_existing_transaction("test-key")

                    # Verify logging
                    mock_error.assert_called_once()
                    mock_warning.assert_called_once()

    def test_other_client_error(self, app_with_mocked_table):
        """
        Tests that check_existing_transaction raises a ClientError and logs an error when a non-throughput DynamoDB ClientError occurs.
        
        Simulates a ResourceNotFoundException from DynamoDB and verifies that the error is logged, no warning is issued, and the exception is propagated.
        """
        # Mock the table.query method to raise a different ClientError
        with patch.object(app_with_mocked_table.table, 'query') as mock_query:
            error_response = {
                "Error": {
                    "Code": "ResourceNotFoundException",
                    "Message": "Table not found"
                }
            }
            mock_query.side_effect = ClientError(error_response, "Query")

            # Mock the logger to capture log messages
            with patch.object(app_with_mocked_table.logger, 'error') as mock_error:
                with patch.object(app_with_mocked_table.logger, 'warning') as mock_warning:
                    # Call the function and expect it to raise the exception
                    with pytest.raises(ClientError):
                        app_with_mocked_table.check_existing_transaction("test-key")

                    # Verify logging
                    mock_error.assert_called_once()
                    mock_warning.assert_not_called()


class TestSaveTransaction:
    def test_successful_save(self, app_with_mocked_table):
        """
        Tests that a transaction is saved successfully and can be retrieved from the database.
        
        Creates a sample transaction, saves it using the application's save method, and verifies
        that the transaction is present in the mocked database table.
        """
        # Create a test transaction
        transaction_id = "test-save-id"
        transaction_item = {
            "id": transaction_id,
            "createdAt": datetime.now(timezone.utc).isoformat(),
            "accountId": "test-account",
            "amount": Decimal("200.0"),
            "type": "CREDIT"
        }

        # Call the function
        result = app_with_mocked_table.save_transaction(transaction_item)

        # Verify the result
        assert result is True

        # Verify the item was saved by retrieving it
        response = app_with_mocked_table.table.get_item(
            Key={"id": transaction_id}
        )

        assert "Item" in response
        assert response["Item"]["id"] == transaction_id

    def test_throughput_exceeded_error(self, app_with_mocked_table):
        """
        Tests that save_transaction raises an exception with an appropriate message and logs an error when a ProvisionedThroughputExceededException occurs during a DynamoDB save operation.
        """
        # Mock the table.put_item method to raise a ClientError
        with patch.object(app_with_mocked_table.table, 'put_item') as mock_put_item:
            error_response = {
                "Error": {
                    "Code": "ProvisionedThroughputExceededException",
                    "Message": "Rate exceeded"
                }
            }
            mock_put_item.side_effect = ClientError(error_response, "PutItem")

            # Mock the logger to capture log messages
            with patch.object(app_with_mocked_table.logger, 'error') as mock_error:
                # Call the function and expect it to raise the specific exception
                with pytest.raises(Exception) as exc_info:
                    app_with_mocked_table.save_transaction({"id": "test-id"})

                # Verify the exception message
                assert "Service temporarily unavailable due to high load" in str(exc_info.value)

                # Verify logging
                mock_error.assert_called_once()

    def test_resource_not_found_error(self, app_with_mocked_table):
        """Test handling of ResourceNotFoundException."""
        # Mock the table.put_item method to raise a ClientError
        with patch.object(app_with_mocked_table.table, 'put_item') as mock_put_item:
            error_response = {
                "Error": {
                    "Code": "ResourceNotFoundException",
                    "Message": "Table not found"
                }
            }
            mock_put_item.side_effect = ClientError(error_response, "PutItem")

            # Mock the logger to capture log messages
            with patch.object(app_with_mocked_table.logger, 'error') as mock_error:
                # Call the function and expect it to raise the specific exception
                with pytest.raises(Exception) as exc_info:
                    app_with_mocked_table.save_transaction({"id": "test-id"})

                # Verify the exception message
                assert "Transaction database configuration error" in str(exc_info.value)

                # Verify logging
                mock_error.assert_called_once()

    def test_other_client_error(self, app_with_mocked_table):
        """
        Tests that save_transaction raises an exception and logs an error when a non-specific
        ClientError (such as InternalServerError) occurs during a database save operation.
        """
        # Mock the table.put_item method to raise a ClientError
        with patch.object(app_with_mocked_table.table, 'put_item') as mock_put_item:
            error_response = {
                "Error": {
                    "Code": "InternalServerError",
                    "Message": "Internal error"
                }
            }
            mock_put_item.side_effect = ClientError(error_response, "PutItem")

            # Mock the logger to capture log messages
            with patch.object(app_with_mocked_table.logger, 'error') as mock_error:
                # Call the function and expect it to raise the specific exception
                with pytest.raises(Exception) as exc_info:
                    app_with_mocked_table.save_transaction({"id": "test-id"})

                # Verify the exception message
                assert "Database error: InternalServerError" in str(exc_info.value)

                # Verify logging
                mock_error.assert_called_once()

import datetime
import uuid
from decimal import Decimal
from unittest.mock import patch, MagicMock

import pytest
from botocore.exceptions import ClientError

from functions.process_transactions.process_transactions.exceptions import (
    TransactionSystemError,
    BusinessLogicError,
)
from functions.process_transactions.process_transactions.transaction_helpers import (
    update_transaction_status,
    process_single_transaction,
)


@pytest.fixture
def transaction_helpers_valid_event():
    return {
        "dynamodb": {
            "NewImage": {
                "accountId": {"S": str(uuid.uuid4())},
                "userId": {"S": str(uuid.uuid4())},
                "id": {"S": str(uuid.uuid4())},
                "idempotencyKey": {"S": str(uuid.uuid4())},
                "type": {"S": "DEPOSIT"},
                "amount": {"N": "100"},
            }
        }
    }


class TestUpdateTransactionStatus:
    def test_update_transaction_status_success(
        self, mock_logger, magic_mock_transactions_table
    ):
        idempotency_key = str(uuid.uuid4())

        update_transaction_status(
            idempotency_key=idempotency_key,
            status="PROCESSED",
            logger=mock_logger,
            transactions_table=magic_mock_transactions_table,
        )

        magic_mock_transactions_table.update_item.assert_called_once_with(
            Key={"idempotencyKey": idempotency_key},
            UpdateExpression="SET #status = :status",
            ExpressionAttributeNames={"#status": "status"},
            ExpressionAttributeValues={":status": "PROCESSED"},
        )

    def test_update_transaction_status_with_processed_at(
        self, mock_logger, magic_mock_transactions_table
    ):
        idempotency_key = str(uuid.uuid4())
        processed_at = datetime.datetime.now(datetime.UTC).isoformat()

        update_transaction_status(
            idempotency_key=idempotency_key,
            status="PROCESSED",
            logger=mock_logger,
            transactions_table=magic_mock_transactions_table,
            processed_at=processed_at,
        )

        magic_mock_transactions_table.update_item.assert_called_once_with(
            Key={"idempotencyKey": idempotency_key},
            UpdateExpression="SET #status = :status, processedAt = :processedAt",
            ExpressionAttributeNames={"#status": "status"},
            ExpressionAttributeValues={
                ":status": "PROCESSED",
                ":processedAt": processed_at,
            },
        )

    def test_update_transaction_status_with_failure_reason(
        self, mock_logger, magic_mock_transactions_table
    ):
        idempotency_key = str(uuid.uuid4())
        failure_reason = "Insufficient funds"

        update_transaction_status(
            idempotency_key=idempotency_key,
            status="FAILED",
            logger=mock_logger,
            transactions_table=magic_mock_transactions_table,
            failure_reason=failure_reason,
        )

        magic_mock_transactions_table.update_item.assert_called_once_with(
            Key={"idempotencyKey": idempotency_key},
            UpdateExpression="SET #status = :status, failureReason = :failureReason",
            ExpressionAttributeNames={"#status": "status"},
            ExpressionAttributeValues={
                ":status": "FAILED",
                ":failureReason": failure_reason,
            },
        )

    def test_update_transaction_status_table_not_initialized(self, mock_logger):
        idempotency_key = str(uuid.uuid4())

        with pytest.raises(TransactionSystemError) as exception_info:
            update_transaction_status(
                idempotency_key=idempotency_key,
                status="PROCESSED",
                logger=mock_logger,
                transactions_table=None,
            )

        assert exception_info.type is TransactionSystemError
        assert str(exception_info.value) == "Transactions table not configured"

    def test_update_transaction_status_client_error(
        self, mock_logger, magic_mock_transactions_table
    ):
        magic_mock_transactions_table.update_item.side_effect = ClientError(
            {"Error": {"Code": "ValidationException", "Message": "Invalid table"}},
            "UpdateItem",
        )
        idempotency_key = str(uuid.uuid4())

        with pytest.raises(TransactionSystemError) as exception_info:
            update_transaction_status(
                idempotency_key=idempotency_key,
                status="PROCESSED",
                logger=mock_logger,
                transactions_table=magic_mock_transactions_table,
            )

        assert exception_info.type is TransactionSystemError
        assert "Failed to update transaction status: " in str(exception_info.value)


class TestProcessSingleTransaction:

    @patch(
        "functions.process_transactions.process_transactions.transaction_helpers.update_transaction_status"
    )
    @patch(
        "functions.process_transactions.process_transactions.transaction_helpers.update_account_balance"
    )
    @patch(
        "functions.process_transactions.process_transactions.transaction_helpers.get_account_balance"
    )
    @patch(
        "functions.process_transactions.process_transactions.transaction_helpers.check_user_owns_account"
    )
    @patch(
        "functions.process_transactions.process_transactions.transaction_helpers.check_account_exists_in_database"
    )
    @patch(
        "functions.process_transactions.process_transactions.transaction_helpers.validate_transaction_data"
    )
    def test_process_single_transaction_deposit_success(
        self,
        mock_validate_transaction_data,
        mock_check_account_exists,
        mock_check_user_owns_account,
        mock_get_account_balance,
        mock_update_account_balance,
        mock_update_transaction_status,
        transaction_helpers_valid_event,
        mock_logger,
        magic_mock_transactions_table,
        magic_mock_accounts_table,
    ):
        mock_validate_transaction_data.return_value = {
            "account_id": "account123",
            "user_id": "user123",
            "amount": Decimal("100"),
            "transaction_type": "DEPOSIT",
            "transaction_id": "txn123",
            "idempotency_key": "key123",
        }
        mock_check_account_exists.return_value = True
        mock_check_user_owns_account.return_value = True
        mock_get_account_balance.return_value = Decimal("500")

        process_single_transaction(
            transaction_helpers_valid_event,
            mock_logger,
            magic_mock_accounts_table,
            magic_mock_transactions_table,
        )

        mock_update_account_balance.assert_called_once_with(
            "account123", Decimal("600"), mock_logger, magic_mock_accounts_table
        )
        mock_update_transaction_status.assert_called_once()

    @patch(
        "functions.process_transactions.process_transactions.transaction_helpers.update_transaction_status"
    )
    @patch(
        "functions.process_transactions.process_transactions.transaction_helpers.update_account_balance"
    )
    @patch(
        "functions.process_transactions.process_transactions.transaction_helpers.get_account_balance"
    )
    @patch(
        "functions.process_transactions.process_transactions.transaction_helpers.check_user_owns_account"
    )
    @patch(
        "functions.process_transactions.process_transactions.transaction_helpers.check_account_exists_in_database"
    )
    @patch(
        "functions.process_transactions.process_transactions.transaction_helpers.validate_transaction_data"
    )
    def test_process_single_transaction_withdrawal_success(
        self,
        mock_validate_transaction_data,
        mock_check_account_exists,
        mock_check_user_owns_account,
        mock_get_account_balance,
        transaction_helpers_valid_event,
        mock_logger,
    ):
        mock_accounts_table = MagicMock()
        mock_transactions_table = MagicMock()

        mock_validate_transaction_data.return_value = {
            "account_id": uuid.uuid4(),
            "user_id": uuid.uuid4(),
            "amount": Decimal("100"),
            "transaction_type": "WITHDRAWAL",
            "transaction_id": uuid.uuid4(),
            "idempotency_key": uuid.uuid4(),
        }
        mock_check_account_exists.return_value = True
        mock_check_user_owns_account.return_value = True
        mock_get_account_balance.return_value = Decimal("500")

        process_single_transaction(
            transaction_helpers_valid_event,
            mock_logger,
            mock_accounts_table,
            mock_transactions_table,
        )

    @patch(
        "functions.process_transactions.process_transactions.transaction_helpers.validate_transaction_data"
    )
    def test_process_single_transaction_validation_error(
        self,
        mock_validate_transaction_data,
        transaction_helpers_valid_event,
        mock_logger,
    ):
        mock_validate_transaction_data.side_effect = Exception("Validation failed")

        with pytest.raises(BusinessLogicError) as exception_info:
            process_single_transaction(
                transaction_helpers_valid_event, mock_logger, MagicMock(), MagicMock()
            )

        assert exception_info.type is BusinessLogicError
        assert "Invalid transaction data: Validation failed" in str(
            exception_info.value
        )

    @patch(
        "functions.process_transactions.process_transactions.transaction_helpers.check_account_exists_in_database"
    )
    @patch(
        "functions.process_transactions.process_transactions.transaction_helpers.validate_transaction_data"
    )
    def test_process_single_transaction_account_not_exists(
        self,
        mock_validate_transaction_data,
        mock_check_account_exists,
        transaction_helpers_valid_event,
        mock_logger,
    ):
        mock_validate_transaction_data.return_value = {
            "account_id": "account123",
            "user_id": "user123",
            "amount": Decimal("100"),
            "transaction_type": "DEPOSIT",
            "transaction_id": "txn123",
            "idempotency_key": "key123",
        }
        mock_check_account_exists.return_value = False

        with pytest.raises(BusinessLogicError) as exception_info:
            process_single_transaction(
                transaction_helpers_valid_event, mock_logger, MagicMock(), MagicMock()
            )

        assert exception_info.type is BusinessLogicError
        assert "Account account123 does not exist" in str(exception_info.value)

    @patch(
        "functions.process_transactions.process_transactions.transaction_helpers.check_user_owns_account"
    )
    @patch(
        "functions.process_transactions.process_transactions.transaction_helpers.check_account_exists_in_database"
    )
    @patch(
        "functions.process_transactions.process_transactions.transaction_helpers.validate_transaction_data"
    )
    def test_process_single_transaction_user_not_owns_account(
        self,
        mock_validate_transaction_data,
        mock_check_account_exists,
        mock_check_user_owns_account,
        transaction_helpers_valid_event,
        mock_logger,
    ):
        mock_validate_transaction_data.return_value = {
            "account_id": "account123",
            "user_id": "user123",
            "amount": Decimal("100"),
            "transaction_type": "DEPOSIT",
            "transaction_id": "txn123",
            "idempotency_key": "key123",
        }
        mock_check_account_exists.return_value = True
        mock_check_user_owns_account.return_value = False

        with pytest.raises(BusinessLogicError) as exception_info:
            process_single_transaction(
                transaction_helpers_valid_event, mock_logger, MagicMock(), MagicMock()
            )

        assert exception_info.type is BusinessLogicError
        assert "User user123 does not own account account123" in str(
            exception_info.value
        )

    @patch(
        "functions.process_transactions.process_transactions.transaction_helpers.get_account_balance"
    )
    @patch(
        "functions.process_transactions.process_transactions.transaction_helpers.check_user_owns_account"
    )
    @patch(
        "functions.process_transactions.process_transactions.transaction_helpers.check_account_exists_in_database"
    )
    @patch(
        "functions.process_transactions.process_transactions.transaction_helpers.validate_transaction_data"
    )
    def test_process_single_transaction_insufficient_funds(
        self,
        mock_validate_transaction_data,
        mock_check_account_exists,
        mock_check_user_owns_account,
        mock_get_account_balance,
        transaction_helpers_valid_event,
        mock_logger,
    ):
        mock_validate_transaction_data.return_value = {
            "account_id": "account123",
            "user_id": "user123",
            "amount": Decimal("100"),
            "transaction_type": "WITHDRAWAL",
            "transaction_id": "txn123",
            "idempotency_key": "key123",
        }
        mock_check_account_exists.return_value = True
        mock_check_user_owns_account.return_value = True
        mock_get_account_balance.return_value = Decimal("50")

        with pytest.raises(BusinessLogicError) as exception_info:
            process_single_transaction(
                transaction_helpers_valid_event, mock_logger, MagicMock(), MagicMock()
            )

        assert exception_info.type is BusinessLogicError
        assert "Insufficient funds. Current balance: 50, Withdrawal amount: 100" in str(
            exception_info.value
        )

    @patch(
        "functions.process_transactions.process_transactions.transaction_helpers.get_account_balance"
    )
    @patch(
        "functions.process_transactions.process_transactions.transaction_helpers.check_user_owns_account"
    )
    @patch(
        "functions.process_transactions.process_transactions.transaction_helpers.check_account_exists_in_database"
    )
    @patch(
        "functions.process_transactions.process_transactions.transaction_helpers.validate_transaction_data"
    )
    def test_process_single_transaction_invalid_transaction_type(
        self,
        mock_validate_transaction_data,
        mock_check_account_exists,
        mock_check_user_owns_account,
        mock_get_account_balance,
        transaction_helpers_valid_event,
        mock_logger,
    ):
        mock_validate_transaction_data.return_value = {
            "account_id": "account123",
            "user_id": "user123",
            "amount": Decimal("100"),
            "transaction_type": "INVALID",
            "transaction_id": "txn123",
            "idempotency_key": "key123",
        }
        mock_check_account_exists.return_value = True
        mock_check_user_owns_account.return_value = True
        mock_get_account_balance.return_value = Decimal("500")

        with pytest.raises(BusinessLogicError) as exception_info:
            process_single_transaction(
                transaction_helpers_valid_event, mock_logger, MagicMock(), MagicMock()
            )

        assert exception_info.type is BusinessLogicError
        assert "Unsupported transaction type: INVALID" in str(exception_info.value)

    @patch(
        "functions.process_transactions.process_transactions.transaction_helpers.get_account_balance"
    )
    @patch(
        "functions.process_transactions.process_transactions.transaction_helpers.check_user_owns_account"
    )
    @patch(
        "functions.process_transactions.process_transactions.transaction_helpers.check_account_exists_in_database"
    )
    @patch(
        "functions.process_transactions.process_transactions.transaction_helpers.validate_transaction_data"
    )
    def test_process_single_transaction_get_balance_error(
        self,
        mock_validate_transaction_data,
        mock_check_account_exists,
        mock_check_user_owns_account,
        mock_get_account_balance,
        transaction_helpers_valid_event,
    ):
        mock_logger = MagicMock()
        mock_validate_transaction_data.return_value = {
            "account_id": "account123",
            "user_id": "user123",
            "amount": Decimal("100"),
            "transaction_type": "DEPOSIT",
            "transaction_id": "txn123",
            "idempotency_key": "key123",
        }
        mock_check_account_exists.return_value = True
        mock_check_user_owns_account.return_value = True
        mock_get_account_balance.side_effect = Exception("Database error")

        with pytest.raises(TransactionSystemError) as exception_info:
            process_single_transaction(
                transaction_helpers_valid_event, mock_logger, MagicMock(), MagicMock()
            )

        assert exception_info.type is TransactionSystemError
        assert "Failed to retrieve account balance: Database error" in str(
            exception_info.value
        )

    @patch(
        "functions.process_transactions.process_transactions.transaction_helpers.update_account_balance"
    )
    @patch(
        "functions.process_transactions.process_transactions.transaction_helpers.get_account_balance"
    )
    @patch(
        "functions.process_transactions.process_transactions.transaction_helpers.check_user_owns_account"
    )
    @patch(
        "functions.process_transactions.process_transactions.transaction_helpers.check_account_exists_in_database"
    )
    @patch(
        "functions.process_transactions.process_transactions.transaction_helpers.validate_transaction_data"
    )
    def test_process_single_transaction_update_balance_error(
        self,
        mock_validate_transaction_data,
        mock_check_account_exists,
        mock_check_user_owns_account,
        mock_get_account_balance,
        mock_update_account_balance,
        transaction_helpers_valid_event,
        mock_logger,
    ):
        mock_validate_transaction_data.return_value = {
            "account_id": "account123",
            "user_id": "user123",
            "amount": Decimal("100"),
            "transaction_type": "DEPOSIT",
            "transaction_id": "txn123",
            "idempotency_key": "key123",
        }
        mock_check_account_exists.return_value = True
        mock_check_user_owns_account.return_value = True
        mock_get_account_balance.return_value = Decimal("500")
        mock_update_account_balance.side_effect = Exception("Database error")

        with pytest.raises(TransactionSystemError) as exception_info:
            process_single_transaction(
                transaction_helpers_valid_event, mock_logger, MagicMock(), MagicMock()
            )

        assert exception_info.type is TransactionSystemError
        assert "Failed to update account balance: Database error" in str(
            exception_info.value
        )

    @patch(
        "functions.process_transactions.process_transactions.transaction_helpers.update_transaction_status"
    )
    @patch(
        "functions.process_transactions.process_transactions.transaction_helpers.update_account_balance"
    )
    @patch(
        "functions.process_transactions.process_transactions.transaction_helpers.get_account_balance"
    )
    @patch(
        "functions.process_transactions.process_transactions.transaction_helpers.check_user_owns_account"
    )
    @patch(
        "functions.process_transactions.process_transactions.transaction_helpers.check_account_exists_in_database"
    )
    @patch(
        "functions.process_transactions.process_transactions.transaction_helpers.validate_transaction_data"
    )
    def test_process_single_transaction_update_status_error(
        self,
        mock_validate_transaction_data,
        mock_check_account_exists,
        mock_check_user_owns_account,
        mock_get_account_balance,
        mock_update_account_balance,
        mock_update_transaction_status,
        transaction_helpers_valid_event,
        mock_logger,
    ):
        mock_validate_transaction_data.return_value = {
            "account_id": "account123",
            "user_id": "user123",
            "amount": Decimal("100"),
            "transaction_type": "DEPOSIT",
            "transaction_id": "txn123",
            "idempotency_key": "key123",
        }
        mock_check_account_exists.return_value = True
        mock_check_user_owns_account.return_value = True
        mock_get_account_balance.return_value = Decimal("500")
        mock_update_transaction_status.side_effect = Exception("Database error")

        with pytest.raises(TransactionSystemError) as exception_info:
            process_single_transaction(
                transaction_helpers_valid_event, mock_logger, MagicMock(), MagicMock()
            )

        assert exception_info.type is TransactionSystemError
        assert (
            "Failed to update transaction status after processing: Database error"
            in str(exception_info.value)
        )

    @patch(
        "functions.process_transactions.process_transactions.transaction_helpers.check_account_exists_in_database"
    )
    @patch(
        "functions.process_transactions.process_transactions.transaction_helpers.validate_transaction_data"
    )
    def test_process_single_transaction_unexpected_error(
        self,
        mock_validate_transaction_data,
        mock_check_account_exists,
        transaction_helpers_valid_event,
        mock_logger,
    ):
        mock_validate_transaction_data.return_value = {
            "account_id": "account123",
            "user_id": "user123",
            "amount": Decimal("100"),
            "transaction_type": "DEPOSIT",
            "transaction_id": "txn123",
            "idempotency_key": "key123",
        }
        mock_check_account_exists.side_effect = Exception("Unexpected system error")

        with pytest.raises(TransactionSystemError) as exception_info:
            process_single_transaction(
                transaction_helpers_valid_event, mock_logger, MagicMock(), MagicMock()
            )

        assert exception_info.type is TransactionSystemError
        assert (
            "Unexpected error processing transaction: Unexpected system error"
            in str(exception_info.value)
        )

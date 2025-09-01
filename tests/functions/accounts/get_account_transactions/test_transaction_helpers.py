from unittest.mock import MagicMock, patch

from functions.accounts.get_account_transactions.get_account_transactions.transaction_helpers import (
    query_transactions,
)


class TestQueryTransactions:
    @patch(
        "functions.accounts.get_account_transactions.get_account_transactions.date_helpers.get_date_range"
    )
    def test_query_transactions_success(self, mock_get_date_range):
        mock_get_date_range.return_value = (
            "2024-06",
            "2024-06-01T00:00:00Z",
            "2024-06-30T23:59:59Z",
        )

        mock_logger = MagicMock()
        mock_table = MagicMock()
        mock_table.query.return_value = {"Items": [{"id": "txn1"}, {"id": "txn2"}]}

        result = query_transactions(
            table=mock_table,
            account_id="acc123",
            logger=mock_logger,
            period="2024-06",
        )

        mock_get_date_range.assert_called_once_with("2024-06", None, None)
        mock_logger.info.assert_called_once()
        mock_table.query.assert_called_once()
        assert result["statementPeriod"] == "2024-06"
        assert result["transactions"] == [{"id": "txn1"}, {"id": "txn2"}]

    @patch(
        "functions.accounts.get_account_transactions.get_account_transactions.date_helpers.get_date_range"
    )
    def test_query_transactions_descending(self, mock_get_date_range):
        mock_get_date_range.return_value = (
            "2024-07",
            "2024-07-01T00:00:00Z",
            "2024-07-31T23:59:59Z",
        )

        mock_logger = MagicMock()
        mock_table = MagicMock()
        mock_table.query.return_value = {"Items": []}

        result = query_transactions(
            table=mock_table,
            account_id="acc456",
            logger=mock_logger,
            period="2024-07",
            descending=True,
        )

        assert mock_table.query.call_args[1]["ScanIndexForward"] is False
        assert result["transactions"] == []

    @patch(
        "functions.accounts.get_account_transactions.get_account_transactions.date_helpers.get_date_range"
    )
    def test_query_transactions_no_items(self, mock_get_date_range):
        mock_get_date_range.return_value = (
            "2024-08",
            "2024-08-01T00:00:00Z",
            "2024-08-31T23:59:59Z",
        )

        mock_logger = MagicMock()
        mock_table = MagicMock()
        mock_table.query.return_value = {}  # no Items key

        result = query_transactions(
            table=mock_table,
            account_id="acc789",
            logger=mock_logger,
            period="2024-08",
        )

        assert result["transactions"] == []

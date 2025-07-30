import pytest

from functions.transactions.process_transactions.process_transactions.sqs import format_sqs_message


class TestSqsHelpers:

    def test_format_sqs_message_incorrect_type(self):

        with pytest.raises(ValueError) as exception_info:
            format_sqs_message("", "")

            assert exception_info.type == ValueError
            assert exception_info.value.args[0] == "Record must be a dictionary"
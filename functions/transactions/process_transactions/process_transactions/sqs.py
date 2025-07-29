import datetime


def format_sqs_message(record, error_message: str = ""):
    return {
        "originalRecord": record,
        "errorMessage": error_message,
        "timestamp": record.get("dynamodb", {}).get("ApproximateCreationDateTime"),
        "sequenceNumber": record.get("dynamodb", {}).get("SequenceNumber"),
    }


def get_message_attributes(
    error_type: str, environment_name: str, idempotency_key: str = None
) -> dict:
    base_attributes = {
        "Source": {"StringValue": "ProcessTransactions", "DataType": "String"},
        "Environment": {"StringValue": environment_name, "DataType": "String"},
        "Timestamp": {
            "StringValue": datetime.datetime.now(datetime.UTC).isoformat(),
            "DataType": "String",
        },
    }

    if error_type == "BusinessLogicError":
        base_attributes.update(
            {
                "ErrorType": {
                    "StringValue": "BusinessLogicError",
                    "DataType": "String",
                },
                "ErrorCategory": {"StringValue": "RECOVERABLE", "DataType": "String"},
                "HasIdempotencyKey": {
                    "StringValue": str(bool(idempotency_key)),
                    "DataType": "String",
                },
            }
        )
    elif error_type == "TransactionSystemError":
        base_attributes.update(
            {
                "ErrorType": {
                    "StringValue": "TransactionSystemError",
                    "DataType": "String",
                },
                "ErrorCategory": {
                    "StringValue": "SYSTEM_FAILURE",
                    "DataType": "String",
                },
                "RequiresRetry": {"StringValue": "true", "DataType": "String"},
            }
        )
    else:
        base_attributes.update(
            {
                "ErrorType": {"StringValue": "UnknownError", "DataType": "String"},
                "ErrorCategory": {
                    "StringValue": "SYSTEM_FAILURE",
                    "DataType": "String",
                },
                "RequiresRetry": {"StringValue": "true", "DataType": "String"},
            }
        )

    return base_attributes

import datetime


def format_sqs_message(record: dict, error_message: str = ""):
    """
    Format a DynamoDB stream record into the SQS message payload expected by downstream consumers.
    
    Constructs a dict containing the original input record, an optional error message, and two metadata fields extracted from the record's DynamoDB payload: the approximate creation timestamp and the sequence number.
    
    Parameters:
        record (dict): A DynamoDB stream record dictionary; must contain (or be able to yield) `dynamodb.ApproximateCreationDateTime` and `dynamodb.SequenceNumber` via nested keys.
        error_message (str): Optional error message to include in the formatted payload (default is empty string).
    
    Returns:
        dict: A dictionary with keys:
            - originalRecord: the unmodified input `record`.
            - errorMessage: the provided `error_message`.
            - timestamp: value of `record["dynamodb"]["ApproximateCreationDateTime"]` if present, otherwise None.
            - sequenceNumber: value of `record["dynamodb"]["SequenceNumber"]` if present, otherwise None.
    
    Raises:
        ValueError: If `record` is not a dictionary.
    """
    if not isinstance(record, dict):
        raise ValueError("Record must be a dictionary")
    return {
        "originalRecord": record,
        "errorMessage": error_message,
        "timestamp": record.get("dynamodb", {}).get("ApproximateCreationDateTime"),
        "sequenceNumber": record.get("dynamodb", {}).get("SequenceNumber"),
    }


def get_message_attributes(
    error_type: str, environment_name: str, idempotency_key: str = None
) -> dict:
    """
    Build SQS-compatible MessageAttributes for an error message based on error type and environment.
    
    Generates a dictionary suitable for SQS MessageAttributes containing:
    - Source: fixed to "ProcessTransactions".
    - Environment: the provided environment_name.
    - Timestamp: current UTC time in ISO 8601 format.
    Additional attributes vary by error_type:
    - "BusinessLogicError": marks ErrorType and ErrorCategory as recoverable and includes HasIdempotencyKey ("True"/"False") derived from whether idempotency_key is provided.
    - "TransactionSystemError": marks ErrorType and ErrorCategory as system failure and sets RequiresRetry to "true".
    - Any other value: treated as an unknown system failure and sets RequiresRetry to "true".
    
    Parameters:
        error_type (str): Type of error driving attribute selection (e.g. "BusinessLogicError", "TransactionSystemError").
        environment_name (str): Name of the deployment environment to include in attributes.
        idempotency_key (str | None): Optional idempotency key; presence is reported only for BusinessLogicError.
    
    Returns:
        dict: Mapping of SQS MessageAttributes where each attribute is a dict with `StringValue` and `DataType`.
    """
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

from botocore.exceptions import ClientError


def get_all_transactions(user_id, table, logger):
    try:
        response = table.query(
            IndexName="UserIdIndex",
            KeyConditionExpression="userId = :userId",
            ExpressionAttributeValues={":userId": user_id},
        )
        return response["Items"]
    except ClientError as e:
        logger.error(f"Error querying transactions: {e}")
        raise e


def get_transaction_by_id(user_id, transaction_id, table, logger):
    try:
        response = table.query(
            IndexName="TransactionIdIndex",
            KeyConditionExpression="id = :transaction_id",
            ExpressionAttributeValues={":transaction_id": transaction_id},
        )
        items = response.get("Items")

        item = items[0] if items else None

        if not item or item.get("userId") != user_id:
            raise ValueError("Invalid transaction ID or user ID")

        return item
    except ClientError as e:
        logger.error(f"Error getting transaction: {e}")
        raise e

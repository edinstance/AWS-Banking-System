from aws_lambda_powertools.event_handler.exceptions import NotFoundError, ForbiddenError
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

        if not item:
            raise NotFoundError("Transaction not found")
        if item.get("userId") != user_id:
            raise ForbiddenError("Access denied.")

        return item
    except ClientError as e:
        logger.error(f"Error getting transaction: {e}")
        raise e

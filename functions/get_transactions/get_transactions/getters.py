from aws_lambda_powertools.event_handler.exceptions import NotFoundError, ForbiddenError
from botocore.exceptions import ClientError


def get_all_transactions(user_id, table, logger):
    """
    Retrieve all transactions associated with a specific user from the database.
    
    Parameters:
        user_id (str): The unique identifier of the user whose transactions are to be retrieved.
    
    Returns:
        list: A list of transaction items belonging to the specified user.
    
    Raises:
        ClientError: If an error occurs during the database query operation.
    """
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
    """
    Retrieve a transaction by its ID, ensuring it belongs to the specified user.
    
    Raises:
        NotFoundError: If no transaction with the given ID exists.
        ForbiddenError: If the transaction does not belong to the specified user.
    
    Returns:
        dict: The transaction item if found and authorised.
    """
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

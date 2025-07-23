from aws_lambda_powertools.event_handler.exceptions import NotFoundError, ForbiddenError
from botocore.exceptions import ClientError


def get_all_accounts(user_id, table, logger):
    try:
        response = table.query(
            IndexName="UserIdIndex",
            KeyConditionExpression="userId = :userId",
            ExpressionAttributeValues={":userId": user_id},
        )
        return response["Items"]
    except ClientError as e:
        logger.error(f"Error querying accounts: {e}")
        raise e


def get_account_by_id(user_id, account_id, table, logger):
    try:
        response = table.get_item(Key={"accountId": account_id})
        item = response.get("Item")
        print(item)

        if not item:
            raise NotFoundError("Account not found")
        if item.get("userId") != user_id:
            raise ForbiddenError("Access denied.")

        return item
    except ClientError as e:
        logger.error(f"Error getting accounts: {e}")
        raise e

from botocore.exceptions import ClientError


def check_account_exists_in_database(account_id: str, table) -> bool:
    try:
        response = table.get_item(
            Key={"accountId": account_id}, ProjectionExpression="accountId"
        )
        return "Item" in response
    except ClientError:
        return False


def check_user_owns_account(account_id: str, user_id: str, table) -> bool:
    try:
        response = table.get_item(
            Key={"accountId": account_id},
            ProjectionExpression="accountId,userId",
        )
        if "Item" in response:
            return response["Item"].get("userId") == user_id
        return False
    except ClientError:
        return False

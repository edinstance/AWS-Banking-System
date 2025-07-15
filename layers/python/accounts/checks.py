from botocore.exceptions import ClientError


def check_account_exists_in_database(account_id: str, table) -> bool:
    """
    Check if an account with the specified account ID exists in the database table.
    
    Returns:
        bool: True if the account exists, False if it does not or if a database error occurs.
    """
    try:
        response = table.get_item(
            Key={"accountId": account_id}, ProjectionExpression="accountId"
        )
        return "Item" in response
    except ClientError:
        return False


def check_user_owns_account(account_id: str, user_id: str, table) -> bool:
    """
    Determine whether a given user is the owner of a specified account in the database.
    
    Returns:
        bool: True if the account exists and is owned by the specified user; otherwise, False.
    """
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

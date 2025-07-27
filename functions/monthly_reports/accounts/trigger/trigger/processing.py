from .start_execution import start_sfn_execution_with_retry


def process_account_batch(
    accounts_batch, statement_period, sfn_client, logger, state_machine_arn
):
    valid_accounts = []
    skipped_count = 0

    for account in accounts_batch:
        account_id = account.get("accountId")
        user_id = account.get("userId")

        if not all([account_id, user_id]):
            logger.warning(f"Skipping account with missing data: {account}")
            skipped_count += 1
            continue

        valid_accounts.append(
            {
                "accountId": account_id,
                "userId": user_id,
                "statementPeriod": statement_period,
            }
        )

    if not valid_accounts:
        logger.warning("No valid accounts in batch to process")
        return {"skipped": skipped_count}

    sf_input = {
        "accounts": valid_accounts,
        "statementPeriod": statement_period,
        "batchSize": len(valid_accounts),
    }

    account_ids = [acc["accountId"][:5] for acc in valid_accounts[:3]]
    execution_name = f"StmtBatch-{statement_period}-{'-'.join(account_ids)}"

    try:
        result = start_sfn_execution_with_retry(
            sfn_client, state_machine_arn, execution_name, sf_input, logger
        )

        if result == "processed":
            return {"processed": len(valid_accounts), "skipped": skipped_count}
        elif result == "already_exists":
            return {"already_exists": len(valid_accounts), "skipped": skipped_count}
        else:
            return {"failed_starts": len(valid_accounts), "skipped": skipped_count}

    except Exception as e:
        logger.error(f"Failed to start SF execution for batch: {e}")
        return {"failed_starts": len(valid_accounts), "skipped": skipped_count}


def chunk_accounts(accounts, chunk_size=10):
    for i in range(0, len(accounts), chunk_size):
        yield accounts[i : i + chunk_size]

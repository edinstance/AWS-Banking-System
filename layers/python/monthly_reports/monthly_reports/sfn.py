import json
import random
import time

from botocore.exceptions import ClientError


def start_sfn_execution_with_retry(
    sfn_client, state_machine_arn, execution_name, sf_input, logger, max_retries=3
):
    """
    Start an AWS Step Functions execution, retrying on transient service errors.

    Attempts to start the specified state machine execution using the provided Step Functions client.
    On transient errors (ThrottlingException, ServiceUnavailable, InternalFailure) the call is retried
    with exponential backoff plus jitter up to max_retries. If an execution with the same name already
    exists, the function returns immediately.

    Parameters:
        sf_input: The payload for the execution; will be JSON-serialized before being sent.
        max_retries (int): Maximum number of attempts (default 3). The function will perform up to
            `max_retries` calls before giving up.

    Returns:
        str: "processed" when the execution was started successfully, or "already_exists" if an
        execution with the same name already exists.

    Raises:
        botocore.exceptions.ClientError: Propagated when a non-retryable AWS error occurs or when
        the retry attempts are exhausted.
    """
    for attempt in range(max_retries):
        try:
            sfn_client.start_execution(
                stateMachineArn=state_machine_arn,
                name=execution_name,
                input=json.dumps(sf_input),
            )
            return "processed"
        except ClientError as e:
            error_code = e.response["Error"]["Code"]

            if error_code == "ExecutionAlreadyExistsException":
                logger.info(f"SF execution {execution_name} already exists. Skipping.")
                return "already_exists"

            if error_code in [
                "ThrottlingException",
                "ServiceUnavailable",
                "InternalFailure",
            ]:
                if attempt < max_retries - 1:
                    wait_time = (2**attempt) + random.uniform(0, 1)
                    logger.warning(
                        f"Retrying SF execution {execution_name} after {wait_time:.2f}s (attempt {attempt + 1}/{max_retries})"
                    )
                    time.sleep(wait_time)
                    continue
                else:
                    logger.error(
                        f"Max retries exceeded for SF execution {execution_name}: {e}"
                    )
            else:
                logger.error(
                    f"Non-retryable error for SF execution {execution_name}: {e}"
                )

            raise e

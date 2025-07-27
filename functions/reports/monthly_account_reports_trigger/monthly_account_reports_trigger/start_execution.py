import json
import random
import time
from botocore.exceptions import ClientError
from moto.stepfunctions.exceptions import ExecutionAlreadyExists


def start_sfn_execution_with_retry(
    sfn_client, state_machine_arn, execution_name, sf_input, logger, max_retries=3
):
    for attempt in range(max_retries):
        try:
            sfn_client.start_execution(
                stateMachineArn=state_machine_arn,
                name=execution_name,
                input=json.dumps(sf_input),
            )
            return "processed"
        except ExecutionAlreadyExists:
            logger.info(f"SF execution {execution_name} already exists. Skipping.")
            return "already_exists"
        except ClientError as e:
            error_code = e.response["Error"]["Code"]

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

# AWS-Banking-System

This project is a banking application backend built using
serverless architecture on Amazon Web Services (AWS). It leverages the AWS Serverless Application Model (SAM) for
defining, building, and deploying the necessary cloud resources.

## Project Overview

This application provides core functionalities for managing financial transactions, designed with scalability,
reliability, and modern cloud practices in mind. Key features and technologies include:

* **Serverless Functions:** AWS Lambda is used for handling business logic, such as recording transactions, ensuring
  that compute resources are only consumed when requests are being processed.
* **API Gateway:** Amazon API Gateway exposes the Lambda functions as secure and scalable HTTP APIs, allowing client
  applications to interact with the banking backend.
* **NoSQL Database:** Amazon DynamoDB, a fully managed NoSQL database, is used for persistent storage of transaction
  data, offering high availability and performance.
* **Idempotency:** Critical operations, like transaction recording, implement idempotency to prevent duplicate
  processing and ensure data integrity.
* **Infrastructure as Code (IaC):** The entire infrastructure is defined using AWS SAM templates [template.yml](template.yml). This
  allows for repeatable deployments, version control of infrastructure, and easier management of cloud resources.
* **Local Development & Testing:** The project is set up for efficient local development and testing using `sam local`
  and a local instance of DynamoDB (via Docker), enabling developers to iterate quickly before deploying to the cloud.

## Prerequisites

Before you begin setting up and running this project locally or deploying it, please ensure you have the following
installed and
configured on your system:

1. **Docker & Docker Compose:**
    * Required to run the local DynamoDB instance, Lambda's, and the API Gateway.
    * Installation guides:
        * Docker: [https://docs.docker.com/get-docker/](https://docs.docker.com/get-docker/)
        * Docker Compose is typically included with Docker Desktop. For Linux, it might be a separate
          installation: [https://docs.docker.com/compose/install/](https://docs.docker.com/compose/install/)
    * Ensure the Docker daemon is running before proceeding with the setup.

2. **AWS SAM CLI (Serverless Application Model Command Line Interface):**
    * Used to build, test, and locally run your serverless application.
    * Installation
      guide: [https://docs.aws.amazon.com/serverless-application-model/latest/developerguide/install-sam-cli.html](https://docs.aws.amazon.com/serverless-application-model/latest/developerguide/install-sam-cli.html)
    * Verify installation with `sam --version`.
    * This is also used to deploy the system.

3. **AWS CLI (Command Line Interface):**
    * Used to interact with AWS services, including creating the local DynamoDB table.
    * Installation guide: [https://aws.amazon.com/cli/](https://aws.amazon.com/cli/)
    * While full AWS credentials are not strictly required for interacting with DynamoDB Local, having the AWS CLI
      installed is necessary for the `aws dynamodb create-table` command. You can configure it with fake credentials
      for local use if preferred:
    * Credentials are needed for deploying the system to an AWS Account.

4. **Python (Version 3.12 or as specified in [template.yml](template.yml)):**
    * The runtime for the Lambda functions.
    * Download: [https://www.python.org/downloads/](https://www.python.org/downloads/)
    * It's highly recommended to use a virtual environment:
      ```shell
      python3 -m venv .venv
      source .venv/bin/activate  # On macOS/Linux
      # .venv\Scripts\activate   # On Windows
      ```

## Project Dependencies

Once your Python virtual environment is activated, you can initialize the project dependencies using the `make init` target:

```shell
make init
```

This will install the required Python packages for development, testing, and the Lambda function itself.

## Linting and Formatting

To lint and format the Python code in this project, you can use the `make lint`, `make lint-fix`, and `make format` targets:

- **Lint the code**:
  ```shell
  make lint
  ```

- **Fix linting issues**:
  ```shell
  make lint-fix
  ```

- **Format the code**:
  ```shell
  make format
  ```

- **Check linting for staged changes only**:
  ```shell
  make lint-diff
  ```

- **Check if the code is properly formatted**:
  ```shell
  make format-check
  ```

## Make Help 

You can also run `make` or `make help` to see all the options for make.

```shell
make
```

## Local Testing

To test the project locally, you can use the `make test` or `make test-cov-report` targets:

- **Run unit tests**:
  ```shell
  make test
  ```

- **Run unit tests with a coverage report**:
  ```shell
  make test-cov-report
  ```

## Setting Up System Locally

### Cognito

Cognito cannot be set up locally, so if you want to run the system locally you need to use a deployed version of cognito, see below for details on how to deploy cognito.

### DynamoDB

To set up DynamoDB for local testing, ensure Docker is running and use the following command:

```shell
docker compose up -d
```

You need to create the DynamoDB tables using this command, ensure Docker Compose has successfully started the DynamoDB
Local container before running this command.

### Setting up DynamoDB Local

Create the transactions table with idempotency support:

```shell
# Create the transactions table with:
# - idempotencyKey as the hash/partition key
# - A global secondary index on the transaction ID
# - Pay-per-request billing for automatic scaling
aws dynamodb create-table \
    --table-name transactions-table-dev \
    --attribute-definitions \
        AttributeName=idempotencyKey,AttributeType=S \
        AttributeName=id,AttributeType=S \
    --key-schema \
        AttributeName=idempotencyKey,KeyType=HASH \
    --global-secondary-indexes '[
        {
            "IndexName": "TransactionIdIndex",
            "KeySchema": [
                {"AttributeName": "id", "KeyType": "HASH"}
            ],
            "Projection": {"ProjectionType": "ALL"}
        }
    ]' \
    --billing-mode PAY_PER_REQUEST \
    --endpoint-url http://localhost:8000

# Verify the table was created
aws dynamodb list-tables --endpoint-url http://localhost:8000
```

This creates a DynamoDB table that:
- Uses `idempotencyKey` as the primary key to prevent duplicate transactions
- Has a global secondary index on `id` for looking up transactions by their ID
- Uses on-demand capacity for automatic scaling
- Stores all attributes in the secondary index (ProjectionType=ALL)

### Environment Variables

Then you need to set up the environment variables for the system, this can be done by copying
the [env.example.json](env.example.json) into an [env.json](env.json) file and then setting the correct environment
variables for your application.

### Running

Finally, you can now run the system using:

```shell
sam build
sam local start-api --docker-network sam-network --env-vars env.json 
```

## Deployment

This project uses the AWS Serverless Application Model (SAM) for deployments. The deployment configurations for
different environments (e.g., `dev`, `test`, `prod`) are managed in the `samconfig.toml` file.

### Prerequisites for Deployment

Ensure you have met all the items in the [Prerequisites](#prerequisites) section, especially:

* An active AWS Account.
* AWS CLI is configured with credentials that have sufficient permissions to create the resources defined in
  [template.yml](template.yml) (CloudFormation, S3, Lambda, API Gateway, DynamoDB, IAM roles, etc.).
* AWS SAM CLI installed.

### S3 Bucket for Artifacts

With the current config a managed SAM S3 bucket will be used; to use a different bucket, you can either set the bucket
in the [samconfig.toml](samconfig.toml) or by using the `--s3-bucket` flag in the deployment command.

### Build the Application

Before deploying, you need to build your application. This command packages your Lambda function code, resolves
dependencies, and creates deployment artifacts in the `.aws-sam/build` directory.

```shell
sam build
```

You can add the `--use-container` flag, and it is recommended to use it to ensure that the build environment closely
matches the Lambda runtime environment,
especially if the functions have compiled dependencies.

### Deploying to an Environment

You can deploy to any environment defined in the `samconfig.toml` (e.g., `dev`, `test`, `prod`).

To deploy to the **development (`dev`)** environment use this command and then follow the instructions:

```shell
sam deploy --config-env dev
```

To deploy updates to the **development (`dev`)** environment run the same command.

To deploy to the **production (`prod`)** environment:

```shell
sam deploy --config-env prod
```

To deploy to the **testing (`test`)** environment:

```shell
sam deploy --config-env test
```

**Deployment Process:**

* The SAM CLI will use the parameters defined in `samconfig.toml` for the specified environment.
* It uploads the built artifacts to the configured S3 bucket under the environment-specific prefix.
* It creates an AWS CloudFormation changeset, which is a preview of the changes.
* You will be prompted to review and confirm these changes before they are applied to your AWS environment (due to
  `confirm_changeset = true`). **Always review these changes carefully, especially for production deployments.**
* If confirmed, CloudFormation will create or update your stack and all associated resources.

### Verifying the Deployment

After a successful deployment (`CREATE_COMPLETE` or `UPDATE_COMPLETE` status):

1. **AWS CloudFormation Console:**
    * Navigate to the CloudFormation console in the AWS region you deployed to.
    * Select your stack (e.g., `banking-app-dev`).
    * Check the "Status," "Events," "Resources," and especially the **"Outputs"** tab. The "Outputs" tab will contain
      important information like your `BankingApiGatewayEndpoint`.
2. **Test the API Endpoint:**
    * Use a tool like `curl` or Postman to send requests to the `BankingApiGatewayEndpoint` obtained from the
      CloudFormation stack outputs.
    * Example (replace with your actual endpoint and a valid idempotency key):
     ```shell
     API_ENDPOINT="YOUR_API_GATEWAY_ENDPOINT_FROM_OUTPUTS"

    IDEMPOTENCY_KEY=$(uuidgen)
    ACCOUNT_ID=$(uuidgen)

    JSON_PAYLOAD=$(printf '{"accountId": "%s", "amount": 150.75, 
    "type": "DEPOSIT", "description": "Initial cloud deposit"}' "$
    ACCOUNT_ID")

    curl -X POST \
    -H "Content-Type: application/json" \
    -H "Idempotency-Key: $IDEMPOTENCY_KEY" \
    -d "$JSON_PAYLOAD" \
    "$API_ENDPOINT"
    ```

### Deleting a Deployed Environment

To remove all resources associated with a deployed environment, you can delete its CloudFormation stack.

**Caution:** This action is generally irreversible and will delete all resources created by the stack, including
DynamoDB tables (and their data, unless `DeletionPolicy: Retain` is set on the table resource).

Using SAM CLI:

```shell
# To delete the 'dev' environment stack
sam delete --config-env dev

# To delete the 'prod' environment stack (use extreme caution!)
# sam delete --config-env prod
```

You will be prompted for confirmation.

Monitor the deletion progress in the AWS CloudFormation console.

## Cognito

To deploy Cognito for managing users or for local testing of the system, you can either use the normal sam deploy above and reuse the Cognito user pool ID and client ID, or you can use the [cognito-template.yml](cognito-template.yml) to only deploy Cognito. The users used in this must be created either in Cognito or with a custom flow, as this API does not support creating users.

### Security Considerations

When deploying Cognito for production use:
* Ensure users are created through secure, audited processes
* Consider implementing user invitation flows rather than allowing self-registration
* Regularly review and rotate any temporary credentials used for user management

### Deploying just cognito

To deploy only cognito, you need to run:

```shell
sam build --template-file cognito-template.yml
```

and then to deploy it, you should run:

```shell
sam deploy --template-file cognito-template.yml --config-file samconfig.cognito.toml
```

finally to delete it, you should run:

```shell
sam delete --config-file samconfig.cognito.toml  
```
## API Idempotency Requirements

### Endpoints Requiring Idempotency Keys

The following endpoints require an `Idempotency-Key` header to prevent duplicate operations:

- `POST /save/transaction` - For recording financial transactions

### Generating Idempotency Keys

For endpoints that require idempotency keys, clients should generate their own UUID v4 keys:

**Python:**

```python
import uuid

idempotency_key = str(uuid.uuid4())
```

**Java:**

```java
import java.util.UUID;
String idempotencyKey = UUID.randomUUID().toString();
```

## TODO

* Move authentication logic in record transactions to a Lambda layer
* Add accounts to the system
* Refactor `record_transaction` to `request_transaction`
* Use DynamoDB Streams to update account balances after transactions
* Once an account is updated, notify the user using SES, SNS, or other channels
* Create a set of GraphQL APIs using AppSync
* Experiment with AppSync events
* Add an SQS queue
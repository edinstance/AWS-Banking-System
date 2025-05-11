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
* **Infrastructure as Code (IaC):** The entire infrastructure is defined using AWS SAM templates (`template.yaml`). This
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
      installed is necessary for the `aws dynamodb create-table` command. You can configure it with dummy credentials
      for local use if preferred:
    * Credentials are needed for deploying the system to an AWS Account.

4. **Python (Version 3.12 or as specified in `template.yaml`):**
    * The runtime for the Lambda functions.
    * Download: [https://www.python.org/downloads/](https://www.python.org/downloads/)
    * It's highly recommended to use a virtual environment:
      ```shell
      python3 -m venv .venv
      source .venv/bin/activate  # On macOS/Linux
      # .venv\Scripts\activate   # On Windows
      ```

5. **Project Dependencies:**
    * Once your Python virtual environment is activated, install the required Python packages:
      ```shell
      pip install -r tests/requirements.txt
      ```

## Linting and Formatting

To lint and format the python code in this project, you can use [Ruff](https://github.com/astral-sh/ruff). To setup Ruff install it using 
```shell

pip install -r dev-requirements.txt       
```

Then once installed, you can use 
```shell

ruff format && ruff check
```

## Local testing

To test this locally, you first need to set up dynamodb to run locally; it is currently set up to use Docker by running:

``` shell

docker compose up -d
```

### DynamoDB

You need to create the DynamoDB tables using this command, ensure Docker Compose has successfully started the DynamoDB
Local container before running this command.

```shell

 aws dynamodb create-table \
  --table-name transactions-table-dev \
  --attribute-definitions \
    AttributeName=id,AttributeType=S \
    AttributeName=createdAt,AttributeType=S \
    AttributeName=idempotencyKey,AttributeType=S \
  --key-schema \
    AttributeName=id,KeyType=HASH \
    AttributeName=createdAt,KeyType=RANGE \
  --global-secondary-indexes \
    'IndexName=IdempotencyKeyIndex,KeySchema=[{AttributeName=idempotencyKey,KeyType=HASH}],Projection={ProjectionType=ALL}' \
  --billing-mode PAY_PER_REQUEST \
  --endpoint-url http://localhost:8000
```

### Environment Variables

Then you need to set up the environment variables for the system, this can be done by copying
the [env.example.json](env.example.json) into an [env.json](env.json) file and then setting the correct environment
variables for your application.

### Running

Finally, you can now run the system using:

```shell

sam local start-api --docker-network sam-network --env-vars env.json 
```

## Deployment


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

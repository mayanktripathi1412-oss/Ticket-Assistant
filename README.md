# AI IT Support Assistant

A local Agentic AI project for **Project 3 - AI Operations Assistant Using Agentic AI**.

The goal is to build a basic assistant that can understand a user's IT support request, decide which tool is required, execute the right local tool, keep useful conversation state, and return a final user-friendly response.

This project demonstrates:

- Tool calling
- LangGraph agent routing
- Conversation state
- Conditional routing
- Multi-step workflows
- Local data sources
- Safety and validation checks

The assistant supports a fictional organization's IT helpdesk. It can search a knowledge base, look up employees, check system status, search existing tickets, and create new tickets.

No real enterprise system, API key, or external IT integration is required. All business data is stored locally in JSON files under `data/`.

## Business Scenario

The fictional organization needs an AI IT Support Assistant for common employee requests:

- Answer IT how-to questions from a local knowledge base.
- Check existing support tickets.
- Create new tickets when required information is available.
- Remember employee and issue details across a short conversation.
- Show which tools/actions were used where appropriate.

## Required Tools

| Tool | Purpose | Local data source |
| --- | --- | --- |
| `knowledge_search` | Searches the local IT knowledge base and returns matching articles. | `data/knowledge_base.json` |
| `ticket_search` | Searches existing support tickets and returns retrieved ticket status. | `data/tickets.json` |
| `ticket_create` | Creates a new support ticket and generates the next ticket ID. | `data/tickets.json` |

The project also includes supporting tools for `employee_lookup` and `system_status` so ticket creation and service-health requests feel realistic.

| Supporting tool | Purpose | Local data source |
| --- | --- | --- |
| `employee_lookup` | Validates employee name, employee ID, or email before ticket actions. | `data/employees.json` |
| `system_status` | Checks local service-health records for VPN, email, and Wi-Fi. | `data/system_status.json` |

The same tools can also use DynamoDB when `STORAGE_BACKEND=dynamodb`.

## LangGraph Workflow

The assistant uses `langgraph.graph.StateGraph` in [agent.py](/Users/mayanktripathi/Ticket-Assistant/it_assistant/agent.py). The workflow is compiled once when `ITSupportAgent` is created.

```text
User Query
  -> decide_intent
  -> conditional routing
      -> knowledge_search
      -> ticket_lookup
      -> ticket_creation
      -> issue_triage
      -> status_check
  -> generate_response
  -> END
```

LangGraph concepts demonstrated:

- State: `WorkflowState` carries the user request, intent, pending ticket details, pending issue details, employee record, tool history, related tickets, duplicate-ticket information, and final response.
- Nodes: `decide_intent`, `knowledge_search`, `ticket_lookup`, `ticket_creation`, `issue_triage`, `status_check`, and `generate_response`.
- Edges: all tool nodes route into `generate_response`, which routes to `END`.
- Conditional routing: `decide_intent` uses `_route_from_intent()` to choose the correct tool node.
- Tool execution: tool nodes call local JSON-backed functions from [tools.py](/Users/mayanktripathi/Ticket-Assistant/it_assistant/tools.py).
- Final response generation: `generate_response` formats raw tool results into a user-friendly answer.

## Agent Requirement Coverage

- Understand the user's request: `ITSupportAgent._classify_intent()` classifies each request as knowledge search, ticket lookup, ticket creation, or system status.
- Decide whether a tool is required: ticket creation checks for required employee information first. If it is missing, the agent stores pending state and asks a follow-up question before calling the creation tool.
- Select the appropriate tool: LangGraph conditional edges route from `decide_intent` to the correct tool node.
- Pass appropriate parameters to the tool: graph nodes extract search queries, employee names/emails, issue text, priority, and employee IDs before calling tools.
- Process the tool response: each tool returns a `ToolResult`, and the agent records it in `AgentState.tool_history`.
- Generate a final user-friendly response: the `generate_response` node converts raw JSON records into concise answers, ticket summaries, or ticket creation confirmations.

## Safety And Validation

The agent includes basic safeguards so it does not blindly execute actions:

- Required information validation: ticket creation requires issue details and a valid employee name, employee ID, or email before creating a ticket.
- Missing information handling: if details are missing, the graph stores pending state and asks a follow-up question.
- Duplicate prevention: before creating a ticket, the graph searches active tickets for the same employee and a similar issue. If one exists, it returns the retrieved ticket instead of creating another.
- Tool failure handling: graph tool nodes catch exceptions and return a graceful user-facing error instead of crashing.
- No invented ticket data: ticket lookup and duplicate responses only use records retrieved from `data/tickets.json`; ticket IDs are generated only by `ticket_create`.
- Retrieved versus generated content: responses label retrieved knowledge, ticket, and system-status data separately from generated recommendations.

## Setup

Requirements:

- Python 3.10 or newer
- `pip`

Install dependencies:

```bash
pip install -r requirements.txt
```

Dependencies:

- `langgraph` for workflow orchestration.
- `streamlit` for the recommended chat UI.
- `boto3` for optional DynamoDB integration on AWS.

## Run The CLI

One-off requests:

```bash
python3 app.py "How do I reset my VPN password?"
python3 app.py "Is email down?"
python3 app.py "What is the status of my laptop issue?"
python3 app.py "Create a ticket for Priya Nair: laptop will not connect to wifi"
```

Interactive mode:

```bash
python3 app.py
```

Interactive mode starts when no request is passed.

## Streamlit Interface

Run the recommended UI with:

```bash
streamlit run streamlit_app.py
```

The Streamlit app provides:

- Chat interface using `st.chat_message` and `st.chat_input`.
- Conversation history stored in `st.session_state.messages`.
- Clear conversation button that resets the agent, retained state, messages, and tool events.
- Tool/action visibility in the sidebar, including tool name, status, summary, record count or record ID, and error details when available.
- UI-level error handling so unexpected exceptions are shown as user-friendly errors instead of crashing the chat.

## AWS Deployment With Terraform And GitHub Actions

The recommended demo deployment is intentionally cost-conscious:

```text
GitHub push to main
  -> GitHub Actions
  -> Build Docker image
  -> Push image to Amazon ECR
  -> Deploy container to one EC2 instance through AWS Systems Manager
  -> Streamlit app runs on port 8501
  -> App uses DynamoDB for cloud data storage
```

This avoids ECS, Fargate, Application Load Balancer, NAT Gateway, and RDS for the demo.

Terraform creates:

- Amazon ECR repository for Docker images.
- Four DynamoDB tables: `KnowledgeBase`, `Employees`, `SystemStatus`, and `Tickets`.
- EC2 instance for the Streamlit app.
- Security group allowing Streamlit traffic on port `8501`.
- EC2 IAM role with SSM, ECR pull, and DynamoDB permissions.
- GitHub Actions IAM OIDC deploy role.
- ECR lifecycle policy that keeps only the last 5 images.

Deployment files:

```text
Dockerfile
.dockerignore
.github/workflows/deploy-aws.yml
infra/terraform/
  versions.tf
  variables.tf
  main.tf
  outputs.tf
  user_data.sh
  terraform.tfvars.example
```

### 1. Prerequisites

Install locally:

- Terraform 1.6 or newer
- AWS CLI
- Docker, only if you want to test the image locally

Configure AWS CLI:

```bash
aws configure
```

Your AWS user/role for Terraform needs permissions to create EC2, ECR, DynamoDB, IAM, SSM-related instance profile resources, and security groups.

### 2. Configure Terraform Variables

Copy the example file:

```bash
cp infra/terraform/terraform.tfvars.example infra/terraform/terraform.tfvars
```

Edit:

```text
infra/terraform/terraform.tfvars
```

Set:

```hcl
aws_region           = "us-east-1"
project_name         = "ticket-assistant"
environment          = "demo"
instance_type        = "t3.micro"
allowed_ingress_cidr = "YOUR_PUBLIC_IP/32"

github_owner  = "YOUR_GITHUB_USERNAME_OR_ORG"
github_repo   = "YOUR_REPOSITORY_NAME"
github_branch = "main"
```

For a safer demo, use your own public IP with `/32` instead of `0.0.0.0/0`.

If your AWS account already has a GitHub OIDC provider, set:

```hcl
create_github_oidc_provider = false
```

### 3. Create AWS Infrastructure

Run:

```bash
cd infra/terraform
terraform init
terraform fmt
terraform validate
terraform plan -out=tfplan
terraform apply tfplan
```

After apply, note the outputs:

```bash
terraform output
```

Important outputs:

- `app_url`
- `ec2_instance_id`
- `ecr_repository_url`
- `github_deploy_role_arn`
- `dynamodb_table_prefix`
- `github_actions_variables`

### 4. Seed DynamoDB Demo Data

From the project root:

```bash
python3 scripts/bootstrap_dynamodb.py --region us-east-1 --prefix ticket-assistant
```

This loads the current JSON demo data into the DynamoDB tables created by Terraform.

### 5. Add GitHub Repository Variables

In GitHub:

```text
Repository -> Settings -> Secrets and variables -> Actions -> Variables
```

Add:

```text
AWS_DEPLOY_ROLE_ARN=<terraform output github_deploy_role_arn>
EC2_INSTANCE_ID=<terraform output ec2_instance_id>
ECR_REPOSITORY_URL=<terraform output ecr_repository_url>
DYNAMODB_TABLE_PREFIX=<terraform output dynamodb_table_prefix>
```

The workflow uses GitHub OIDC, so do not add long-lived AWS access keys.

If you deploy outside `us-east-1`, update `AWS_REGION` in [.github/workflows/deploy-aws.yml](/Users/mayanktripathi/Ticket-Assistant/.github/workflows/deploy-aws.yml).

### 6. Deploy From GitHub Actions

Push to `main`:

```bash
git add .
git commit -m "Add AWS Terraform deployment"
git push origin main
```

GitHub Actions will:

1. Assume the Terraform-created AWS deploy role.
2. Log in to ECR.
3. Build the Docker image.
4. Push the image to ECR.
5. Use SSM Run Command to pull and restart the container on EC2.

You can also start the workflow manually from:

```text
GitHub -> Actions -> Deploy To AWS -> Run workflow
```

### 7. Open The Demo App

Use the Terraform output:

```bash
terraform -chdir=infra/terraform output app_url
```

Open the printed URL in a browser.

### 8. Cost Controls

This demo keeps cost low by using:

- One small EC2 instance.
- DynamoDB on-demand tables.
- No ECS/Fargate.
- No Application Load Balancer.
- No NAT Gateway.
- No RDS.
- ECR lifecycle cleanup after 5 images.

Stop or destroy resources when the demo is done:

```bash
terraform -chdir=infra/terraform destroy
```

## Local Data

The project uses JSON files to keep the implementation realistic but easy to run locally:

- `data/knowledge_base.json`: IT how-to articles and recommended steps.
- `data/employees.json`: employee records used for validation and stateful workflows.
- `data/system_status.json`: local service status records.
- `data/tickets.json`: existing and newly created support tickets.

Creating a ticket updates `data/tickets.json`. The tests copy these files into a temporary directory so test runs do not mutate the project seed data.

## DynamoDB Integration

The app supports two storage backends:

| Backend | Use case | Environment |
| --- | --- | --- |
| JSON | Local development and unit tests. | `STORAGE_BACKEND=json` or unset |
| DynamoDB | AWS demo deployment with cloud persistence. | `STORAGE_BACKEND=dynamodb` |

Repository code lives in [repositories.py](/Users/mayanktripathi/Ticket-Assistant/it_assistant/repositories.py). The agent workflow does not change between backends; the tools call a repository interface.

Default DynamoDB table names use this format:

```text
<DYNAMODB_TABLE_PREFIX>-KnowledgeBase
<DYNAMODB_TABLE_PREFIX>-Employees
<DYNAMODB_TABLE_PREFIX>-SystemStatus
<DYNAMODB_TABLE_PREFIX>-Tickets
```

Default prefix:

```text
ticket-assistant
```

Example table names:

```text
ticket-assistant-KnowledgeBase
ticket-assistant-Employees
ticket-assistant-SystemStatus
ticket-assistant-Tickets
```

Primary keys:

| Table | Partition key |
| --- | --- |
| `KnowledgeBase` | `article_id` |
| `Employees` | `employee_id` |
| `SystemStatus` | `service` |
| `Tickets` | `ticket_id` |

Create and seed DynamoDB tables from the local JSON files:

```bash
python3 scripts/bootstrap_dynamodb.py --region us-east-1 --prefix ticket-assistant
```

Run the app with DynamoDB:

```bash
export STORAGE_BACKEND=dynamodb
export AWS_REGION=us-east-1
export DYNAMODB_TABLE_PREFIX=ticket-assistant
streamlit run streamlit_app.py
```

See [.env.example](/Users/mayanktripathi/Ticket-Assistant/.env.example) for the supported environment variables.

For EC2 deployment, set the same environment variables in the Docker run command:

```bash
docker run -d \
  --name ticket-assistant \
  -p 8501:8501 \
  -e STORAGE_BACKEND=dynamodb \
  -e AWS_REGION=us-east-1 \
  -e DYNAMODB_TABLE_PREFIX=ticket-assistant \
  <ECR_IMAGE_URI>
```

Minimum IAM permissions for the EC2 instance role:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "dynamodb:Scan",
        "dynamodb:PutItem"
      ],
      "Resource": [
        "arn:aws:dynamodb:us-east-1:<ACCOUNT_ID>:table/ticket-assistant-KnowledgeBase",
        "arn:aws:dynamodb:us-east-1:<ACCOUNT_ID>:table/ticket-assistant-Employees",
        "arn:aws:dynamodb:us-east-1:<ACCOUNT_ID>:table/ticket-assistant-SystemStatus",
        "arn:aws:dynamodb:us-east-1:<ACCOUNT_ID>:table/ticket-assistant-Tickets"
      ]
    }
  ]
}
```

For this demo, DynamoDB tables are created with `PAY_PER_REQUEST` billing in [bootstrap_dynamodb.py](/Users/mayanktripathi/Ticket-Assistant/scripts/bootstrap_dynamodb.py). This avoids capacity planning and keeps cost tied to actual usage.

## Project Structure

```text
app.py                    CLI entrypoint
streamlit_app.py          Streamlit chat UI
Dockerfile                Container image for AWS deployment
.dockerignore             Excludes local files from Docker builds
.github/workflows/
  deploy-aws.yml          GitHub Actions AWS deployment workflow
.env.example              Example local/AWS storage configuration
.gitignore                Ignores local env and Python cache files
it_assistant/
  agent.py                Agent state, routing, and workflow logic
  models.py               Shared dataclasses
  repositories.py         JSON and DynamoDB repository implementations
  tools.py                Local tool implementations
data/
  employees.json          Employee directory
  knowledge_base.json     IT knowledge base
  system_status.json      Service health data
  tickets.json            Ticket database
tests/
  __init__.py
  test_agent.py           Unit tests for routing and workflows
  test_repositories.py    Unit tests for DynamoDB repository behavior
scripts/
  bootstrap_dynamodb.py   Creates and seeds DynamoDB tables
infra/terraform/
  README.md               Terraform deployment guide
  versions.tf             Terraform and AWS provider requirements
  variables.tf            Deployment variables
  main.tf                 AWS resources
  outputs.tf              Values for GitHub Actions and app URL
  user_data.sh            EC2 bootstrap script
  terraform.tfvars.example Example Terraform variable file
requirements.txt          Python dependencies
```

## Example Workflows

Knowledge search:

```text
User: How do I reset my VPN password?
Agent:
Retrieved knowledge article: Reset a VPN password
Retrieved information: Employees can reset VPN passwords through the self-service identity portal.
Generated recommendation based on the article:
1. Go to the identity reset portal.
2. Enter company email.
3. Approve MFA.
4. Set the new password.
```

Ticket lookup:

```text
User: What is the status of my laptop issue?
Agent:
Retrieved ticket information: Found 1 related ticket(s).
- IT-0001: VPN disconnects every hour [in_progress, medium]
```

Ticket creation with all required information:

```text
User: Create a ticket for Priya Nair: laptop will not connect to wifi
Agent:
1. Routes to employee_lookup to identify Priya.
2. Routes to ticket_search to check related tickets.
3. Routes to ticket_create with the detected issue.
4. Stores each step in state.
5. Returns a final ticket confirmation.
```

Ticket creation with missing information in interactive mode:

```text
User: My VPN is not working. Please raise a ticket.
Agent: Please provide the employee name or email so I can create the ticket.
User: Alex Morgan
Agent: Creates the ticket and confirms the generated ticket ID.
```

Conversation state across turns:

```text
User: I have a VPN issue.
Agent: What is your employee ID or company email?
User: EMP1024.
Agent: I found your profile: Jordan Lee (EMP1024). Would you like me to check existing tickets?
User: Yes.
Agent: Searches tickets using the stored issue and employee context, then returns matching ticket status.
```

The same `ITSupportAgent` instance keeps `pending_issue`, `employee`, `intent`, and `tool_history` in `AgentState` between turns. In interactive CLI mode, one agent instance is reused until the user exits.

## Error Handling

Tool execution is wrapped in the agent. If a local tool fails, the agent records the failure in `ToolResult.error` and returns a user-friendly error message instead of crashing the conversation.

The Streamlit UI also catches unexpected UI-level exceptions and shows a clear error message in the chat while preserving conversation history.

## Tests

```bash
python3 -m unittest
```

The test suite covers:

- Knowledge search routing.
- System-status routing.
- Ticket lookup routing.
- Multi-step ticket creation.
- Missing employee collection.
- Multi-turn issue triage state.
- Required issue validation.
- Duplicate ticket prevention.
- Tool failure handling.
- DynamoDB repository scan/write behavior using fake in-memory tables.

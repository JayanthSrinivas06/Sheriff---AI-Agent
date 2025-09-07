# Sheriff AI Agent: Conversational Delivery Tracking System

Sheriff AI is a sophisticated, voice-first AI agent designed to automate real-time delivery status inquiries. This system leverages a powerful stack, integrating a conversational AI platform (**Vapi**), a high-performance asynchronous web framework (**FastAPI**), and a flexible structured content backend (**Sanity.io**) to provide a seamless and intelligent user experience over the phone.

![Python](https://img.shields.io/badge/Python-3.9%2B-blue.svg)
![FastAPI](https://img.shields.io/badge/FastAPI-0.100%2B-green.svg)
![Vapi](https://img.shields.io/badge/AI_Agent-Vapi-purple.svg)
![Sanity.io](https://img.shields.io/badge/Database-Sanity.io-red.svg)

---

## Core Architecture

The system is built upon a decoupled, three-tier architecture, ensuring modularity, scalability, and maintainability. Each component is responsible for a distinct part of the operational logic.

![Architecture Diagram](https://raw.githubusercontent.com/JayanthSrinivas06/Sheriff-AI-Agent/main/imgs/Architecture.png)

**1. Conversational AI Layer (Vapi)**
Vapi serves as the advanced conversational frontend. It manages the entire lifecycle of the phone call, from receiving the call to terminating it. Its core responsibilities include:
* **Speech-to-Text (STT):** Transcribing the user's spoken words into text in real-time.
* **Natural Language Understanding (NLU):** The underlying Large Language Model (LLM) processes the transcribed text to discern user intent (e.g., `check_delivery_status`) and extract critical entities (e.g., the `tracking_id`).
* **Tool-Call Orchestration:** When the LLM determines that external data is required, Vapi initiates a `tool-call`. This is a programmatic function execution triggered by the AI, which sends a `POST` request to our FastAPI webhook service.
* **Text-to-Speech (TTS):** Synthesizing the final, data-enriched response from the LLM into natural-sounding speech for the user.

**2. Webhook Service Layer (FastAPI)**
This is the central nervous system of the project, an asynchronous API built with FastAPI that acts as the middleware between the conversational AI and the database.
* **Endpoint Logic:** The primary `/webhook` endpoint is engineered to handle incoming `POST` requests from Vapi's tool-calling mechanism.
* **Data Sanitization:** It implements robust input validation and normalization. For instance, the `normalize_tracking_id` function sanitizes the raw tracking number, stripping non-alphanumeric characters to ensure a high cache-hit ratio and prevent query injection.
* **Secure Data Fetching:** The service securely authenticates with the Sanity.io API using bearer tokens managed through environment variables. It dynamically constructs **GROQ (Graph-Relational Object Queries)** to fetch precise data from the persistence layer.
* **Structured Response Generation:** It formats the retrieved data into a structured JSON payload, providing a clear, predictable output for Vapi's LLM to consume and reason upon.

**3. Data Persistence Layer (Sanity.io)**
Sanity.io is utilized as a headless, API-first structured content platform, serving as the single source of truth for all delivery information.
* **Flexible Schema:** Sanity.io's schema-based modeling allows for defining a clear `delivery` document type with strongly-typed fields like `trackingNumber`, `status`, `customerName`, etc.
* **Powerful Query Language (GROQ):** GROQ provides a declarative and efficient way to query complex JSON documents, enabling precise data fetching with minimal overhead. The queries can project the data into the exact shape required by the FastAPI service.
* **Scalability & Real-time Sync:** As a fully managed service, Sanity.io handles all the database administration, scaling, and provides real-time data synchronization capabilities, which are crucial for a time-sensitive application like delivery tracking.

---

## AI Agent Configuration & Response Management

The "intelligence" of the Sheriff AI agent is defined within the Vapi dashboard, primarily through the system prompt and tool definitions. This is where the NLP behavior and response logic are configured.

### **System Prompt Configuration**

The system prompt is the foundational instruction set that governs the LLM's personality, goals, and constraints throughout the conversation.

* **Personality & Role:** Define the AI's persona.
    > "You are Sheriff AI, a friendly and efficient automated assistant for a logistics company. Your primary goal is to help customers track their deliveries. Be polite, concise, and professional."
* **Core Task & Tool Usage:** Instruct the AI on its main function and when to use its tools.
    > "When a user wants to know the status of their delivery, you must use the `get_delivery_status` tool. To do this, you need to ask them for their tracking number if they don't provide it upfront. Do not attempt to answer delivery questions without using the tool."
* **Response Handling:** Guide the AI on how to interpret the data returned from the FastAPI service and formulate a response.
    > "After the `get_delivery_status` tool returns data, present the information clearly. State the customer's name for confirmation, the current status, and the estimated delivery date. If the tool returns a 'not_found' error, inform the user that you couldn't find a delivery with that tracking number and ask them to double-check it. If any other error occurs, apologize for the technical difficulty and suggest trying again later."

### **Tool Definition**

In Vapi, you must explicitly define the `get_delivery_status` function that the LLM can call. This definition includes the function name, a description of what it does, and its parameters.

* **Function Name:** `get_delivery_status`
* **Description:** "Fetches the real-time status of a delivery using its tracking number."
* **Parameters:**
    * **Name:** `tracking_id`
    * **Type:** `string`
    * **Description:** "The tracking number provided by the customer. It might contain letters, numbers, spaces, or hyphens."
* **Webhook URL:** The public URL of your deployed FastAPI application (e.g., your AWS App Runner URL).

This structured configuration ensures that the Vapi LLM understands its capabilities, knows exactly when to call your FastAPI backend, what data to send, and how to intelligently handle the response it receives.

---

## System Workflow & Data Flow

A typical user interaction follows a precise, orchestrated sequence:

1.  **Initiation:** A customer dials the phone number associated with the Vapi agent.
2.  **Intent Recognition:** The Vapi agent engages the user, and its NLU model, guided by the system prompt, identifies the intent to check a delivery status and extracts the tracking number entity.
3.  **Tool-Call Trigger:** Vapi, recognizing the need to use the `get_delivery_status` tool, dispatches a `POST` request to the `/webhook` endpoint of the deployed FastAPI application. The request body contains the `toolCalls` payload (e.g., `{"toolCalls": [{"function": {"name": "get_delivery_status", "arguments": {"tracking_id": "ABC 123 XYZ"}}}]}`).
4.  **Server-Side Processing:** The FastAPI server receives the request. The `normalize_tracking_id` function processes `"ABC 123 XYZ"` into `"ABC123XYZ"`.
5.  **Database Query:** The server constructs a GROQ query (e.g., `*[_type == 'delivery' && trackingNumber == 'ABC123XYZ']{...}`) and sends it to the Sanity.io API.
6.  **Data Retrieval:** Sanity.io's query engine processes the request and returns the matching delivery document as a JSON object.
7.  **Response Formulation:** The FastAPI server packages the retrieved delivery details into a structured JSON response and sends it back to Vapi with a `200 OK` status. This completes the tool-call.
8.  **Conversational Response:** Vapi's LLM receives the data, follows the instructions in its system prompt to formulate a human-like sentence (e.g., "I've found your delivery for John Doe. It is currently in transit and is estimated to arrive tomorrow."), and the TTS engine vocalizes this response to the customer.

---

## Scalability and Reliability

The system is architected for high availability and elastic scalability.

* **Scalability:**
    * **Stateless Service:** The FastAPI application is stateless, allowing for effortless horizontal scaling behind a load balancer on platforms like AWS App Runner.
    * **Managed Components:** Vapi and Sanity.io are fully managed, serverless platforms that scale their own infrastructure automatically.

* **Reliability:**
    * **Decoupled Architecture:** The microservices-style architecture ensures that a failure in one component does not cascade into a total system outage.
    * **Asynchronous Processing:** FastAPI's async capabilities allow the server to efficiently manage a high number of concurrent connections, enhancing its resilience under load.
    * **Secure Configuration:** Sensitive credentials are managed via environment variables, aligning with Twelve-Factor App principles for secure deployments.

---

## Setup and Deployment

### **1. Setting Up the Sanity.io Backend**

Before running the application, you need a Sanity.io project to act as your database.

1.  **Install the Sanity CLI:** You'll need Node.js and npm installed.
    ```bash
    npm install -g @sanity/cli
    ```
2.  **Initialize a New Sanity Project:**
    ```bash
    sanity init
    ```
    * Follow the prompts to log in or create an account.
    * Choose to **Create new project**. Give it a name (e.g., `Sheriff AI Backend`).
    * Use the default dataset configuration (`production`).
    * When asked for a project template, select the **Clean project with no predefined schemas** option.

3.  **Define the Delivery Schema:**
    * Inside your new Sanity project folder, navigate to the `schemas` directory.
    * Create a new file named `delivery.js`.
    * Paste the following schema definition into the file. This tells Sanity what fields a "delivery" document will have.
        ```javascript
        // schemas/delivery.js
        export default {
          name: 'delivery',
          title: 'Delivery',
          type: 'document',
          fields: [
            {
              name: 'trackingNumber',
              title: 'Tracking Number',
              type: 'string',
              validation: (Rule) => Rule.required(),
            },
            {
              name: 'customerName',
              title: 'Customer Name',
              type: 'string',
              validation: (Rule) => Rule.required(),
            },
            {
              name: 'status',
              title: 'Status',
              type: 'string',
              options: {
                list: [
                  {title: 'Processing', value: 'processing'},
                  {title: 'In Transit', value: 'in_transit'},
                  {title: 'Delivered', value: 'delivered'},
                  {title: 'Delayed', value: 'delayed'},
                ],
              },
              validation: (Rule) => Rule.required(),
            },
            {
              name: 'estimatedDelivery',
              title: 'Estimated Delivery Date',
              type: 'date',
              options: {
                dateFormat: 'YYYY-MM-DD',
              },
            },
            {
              name: 'lastUpdated',
              title: 'Last Updated',
              type: 'datetime',
            },
          ],
        }
        ```
4.  **Register the Schema:**
    * Open the `schemas/schema.js` file (it may be named `schemas/index.js` in newer versions).
    * Import your new schema and add it to the `types` array.
        ```javascript
        // schemas/schema.js
        import createSchema from 'part:@sanity/base/schema-creator'
        import schemaTypes from 'all:part:@sanity/base/schema-type'

        import delivery from './delivery' // <-- Import the schema

        export default createSchema({
          name: 'default',
          types: schemaTypes.concat([
            delivery, // <-- Add it to the array
          ]),
        })
        ```
5.  **Deploy the Sanity Studio:**
    * From your Sanity project's root directory, run:
        ```bash
        sanity deploy
        ```
    * This will deploy a web-based management interface (the Sanity Studio) where you can add and manage delivery data. Once deployed, you can visit the provided URL and add a few sample deliveries to test with.

6.  **Get Your Credentials:**
    * **Project ID & Dataset:** Find these in your `sanity.json` file or at `manage.sanity.io`.
    * **API Token:** Go to `manage.sanity.io`, navigate to your project -> API -> Tokens. Create a new **Read Token**. This token is what the FastAPI server will use to fetch data.

### **2. Local Development**

1.  **Clone the Repository:**
    ```bash
    git clone [https://github.com/JayanthSrinivas06/Sheriff-AI-Agent.git](https://github.com/JayanthSrinivas06/Sheriff-AI-Agent.git)
    cd Sheriff-AI-Agent
    ```
2.  **Set Up Virtual Environment:**
    ```bash
    python -m venv venv
    source venv/bin/activate  # On Windows, use `venv\Scripts\activate`
    ```
3.  **Install Dependencies:**
    ```bash
    pip install -r requirements.txt
    ```
4.  **Configure Environment:**
    Create a `.env` file in the root directory and populate it with the credentials from the previous step:
    ```env
    SANITY_PROJECT_ID="your_project_id"
    SANITY_DATASET="your_dataset_name"
    SANITY_API_TOKEN="your_sanity_read_token"
    ```
5.  **Run the Server:**
    ```bash
    uvicorn server:app --reload
    ```
    The server will be running on `http://127.0.0.1:8000`. Use a tool like `ngrok` to expose this local endpoint to the internet for testing with Vapi.

### **3. Production Deployment (AWS App Runner)**

This application is container-ready. Deploying on a managed cloud service like AWS App Runner is highly recommended for scalability and ease of management.

1.  **Prerequisites:**
    * An AWS Account.
    * Docker installed on your local machine.
    * AWS CLI installed and configured (`aws configure`).

2.  **Containerize the Application:**
    * Create a `Dockerfile` in the root of your project with the following content:
        ```dockerfile
        # Use an official Python runtime as a parent image
        FROM python:3.11-slim

        # Set the working directory in the container
        WORKDIR /code

        # Copy the dependencies file to the working directory
        COPY ./requirements.txt /code/requirements.txt

        # Install any needed packages specified in requirements.txt
        RUN pip install --no-cache-dir --upgrade -r /code/requirements.txt

        # Copy the rest of the application code
        COPY ./ /code/

        # Command to run the application using uvicorn
        # It will be available on port 8000 inside the container
        CMD ["uvicorn", "server:app", "--host", "0.0.0.0", "--port", "8000"]
        ```

3.  **Build and Push the Image to Amazon ECR (Elastic Container Registry):**
    * **Create an ECR Repository:** Go to the AWS ECR console and create a new private repository (e.g., `sheriff-ai-agent`). Note the URI.
    * **Authenticate Docker to ECR:** Run the following command, replacing `region` and `aws_account_id` with your details.
        ```bash
        aws ecr get-login-password --region <your-region> | docker login --username AWS --password-stdin <your-aws-account-id>.dkr.ecr.<your-region>.amazonaws.com
        ```
    * **Build the Docker Image:**
        ```bash
        docker build -t sheriff-ai-agent .
        ```
    * **Tag the Image:** Tag your image with the ECR repository URI.
        ```bash
        docker tag sheriff-ai-agent:latest <your-aws-account-id>.dkr.ecr.<your-region>[.amazonaws.com/sheriff-ai-agent:latest](https://.amazonaws.com/sheriff-ai-agent:latest)
        ```
    * **Push the Image:**
        ```bash
        docker push <your-aws-account-id>.dkr.ecr.<your-region>[.amazonaws.com/sheriff-ai-agent:latest](https://.amazonaws.com/sheriff-ai-agent:latest)
        ```

4.  **Deploy using AWS App Runner:**
    * Navigate to the AWS App Runner console and click **Create service**.
    * For **Source**, select **Container registry** and **Amazon ECR**.
    * Browse for your ECR repository (`sheriff-ai-agent`) and the `latest` image tag.
    * On the **Configure service** page:
        * Give your service a name (e.g., `Sheriff-AI-Service`).
        * In the **Environment variables** section, add your Sanity credentials. This is the secure way to manage secrets.
            * `SANITY_PROJECT_ID` = `your_project_id`
            * `SANITY_DATASET` = `your_dataset_name`
            * `SANITY_API_TOKEN` = `your_sanity_read_token`
        * Set the **Port** to `8000`.
    * Review the configuration and click **Create & deploy**. App Runner will provision the infrastructure and deploy your container.

5.  **Final Step:** Once the deployment is successful, App Runner will provide a **Default domain** URL (e.g., `https://<some-id>.<region>.awsapprunner.com`). Copy this URL and paste it into the **Webhook URL** field for your `get_delivery_status` tool in the Vapi dashboard. Your agent is now live and ready to take calls.


---
<p align="center">
  Developed by <a href="https://github.com/JayanthSrinivas06">Jayanth Srinivas</a> • © 2025<br>
  Source: Coffee;<br>
  Tool: Dedication;
</p>

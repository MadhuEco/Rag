# Steps To Run the project

### Step1: Install requirements
        1) Run "pip install -r requirements.txt"


##### Create a .env file
        AZURE_OPENAI_API_KEY="api_key"
        AZURE_OPENAI_ENDPOINT="endpoint"
        AZURE_OPENAI_API_VERSION=2024-12-01-preview
        AZURE_OPENAI_CHAT_DEPLOYMENT=gpt-5.4-nano
        AZURE_OPENAI_EMBEDDING_DEPLOYMENT=text-embedding-3-small
### Step2: To Create Local Vector Database
        1) Run the ingets.py file, "python ingest.py"

### Step3: To Run Streamlit application
        2) Run "streamlit run app.py"

### Step4: To Run Unit test case.
        3) Run "pytest test.py -v"

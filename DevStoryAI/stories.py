# === Imports ===
from crewai import Agent, Task, Crew, Process, LLM
from crewai.tools import tool
from langchain_google_genai import ChatGoogleGenerativeAI, GoogleGenerativeAIEmbeddings
from langchain_pinecone import PineconeVectorStore
from langchain.chains import create_retrieval_chain
from langchain.chains.combine_documents import create_stuff_documents_chain
from langchain_core.prompts import ChatPromptTemplate
from github import Github
from pinecone import Pinecone
import os
import ast
from dotenv import load_dotenv # Import load_dotenv

# === Load environment variables from .env file ===
load_dotenv()

# === Dynamic Global Vars ===
repo_url = ""
token = ""

# === GitHub File Reader Tool ===
@tool("read_github_files")
def read_github_files(file_path: str):
    """
    Reads file contents from a GitHub repo.
    This tool accepts one file path at once.
    """
    global token, repo_url
    try:
        parts = repo_url.rstrip("/").replace(".git", "").split('/')
        owner, repo_name = parts[-2], parts[-1]

        g = Github(token)
        repo = g.get_repo(f"{owner}/{repo_name}")

        branch = repo.default_branch
        file = repo.get_contents(file_path, ref=branch)
        return file.decoded_content.decode("utf-8")
    except Exception as e:
        return f"Error: {str(e)}"

git_reader = read_github_files

# === Pinecone Setup ===
os.environ["PINECONE_API_KEY"] = os.getenv("PINECONE_API_KEY") # Load from .env
pinecone_env = "us-east-1" # This can also be moved to .env if it changes per environment

# === RAG Retriever Tool ===
@tool("retriever_tool")
def my_retriever_tool(question: str) -> str:
    "acts as json reteriever"
    pinecone_api_key = os.getenv("PINECONE_API_KEY") # Load from .env
    index_name = "git-test" # This can also be moved to .env if it changes per environment

    pc = Pinecone(api_key=pinecone_api_key, environment=pinecone_env)

    llm = ChatGoogleGenerativeAI(model="gemini-2.0-flash", api_key=os.getenv("GOOGLE_API_KEY_1")) # Load from .env
    embeddings = GoogleGenerativeAIEmbeddings(
        model="models/embedding-001",
        google_api_key=os.getenv("GOOGLE_API_KEY_1") # Load from .env
    )

    vectorstore = PineconeVectorStore(index_name=index_name, embedding=embeddings)
    retriever = vectorstore.as_retriever(search_type="similarity", search_kwargs={"k": 15})

    system_prompt = (
        "You are an expert Java backend developer for a Spring Boot project. "
        "The user has requested a feature change involving order details, specifically to retrieve all order details within a price range. "
        "Your task is to identify which classes are directly or indirectly affected by this change, including Controllers, Services, ServiceImpl, Repositories, and Entities. "
        "List the affected classes with their exact file paths. Do not include any unrelated classes or those not impacted by the requested feature change. "
        "Ensure there are no duplicates and do not include source code."
        "{context}"
    )

    prompt = ChatPromptTemplate.from_messages([
        ("system", system_prompt),
        ("human", "{input}"),
    ])

    Youtube_chain = create_stuff_documents_chain(llm, prompt)
    rag_chain = create_retrieval_chain(retriever, Youtube_chain)
    response = rag_chain.invoke({"input": question})
    return response["answer"]

tool_retriever = my_retriever_tool

llm = LLM(model='gemini/gemini-2.0-flash', api_key=os.getenv("GOOGLE_API_KEY_1"))
llm_new = LLM(model='gemini/gemini-2.0-flash', api_key=os.getenv("GOOGLE_API_KEY_2"))

# === Agent: Analyzer ===
project_analyzer_agent = Agent(
    role="Information Retrieval Expert",
    goal="Retrieve and list all impacted classes and their paths based on the user's query.",
    backstory=(
        "You are an information retrieval expert in a Java Spring Boot project. "
        "Given a user's query, you will retrieve relevant information about the impacted classes, "
        "analyze it, and refine the query if necessary to ensure complete results. "
        "Only list the class names and their paths without source code."
    ),
    tools=[tool_retriever],
    llm=llm_new,
    allow_delegation=False,
    verbose=True
)

query_response_task = Task(
    agent=project_analyzer_agent,
    description=(
        "Process the user's query: '{{user_query}}' by invoking the 'retriever_tool'. "
        "After retrieving initial results, analyze for missing information. "
        "Generate 1–2 refined queries if needed. "
        "Use 'retriever_tool' again with those queries, combine the results, remove duplicates, "
        "and return the final impacted classes and their file paths.\n\n"
        "Format your final answer like this:\n\n"
        "[\n"
        "\"path/to/Class1.java\",\n"
        "\"path/to/Class2.java\",\n"
        "... \n]"
    ),
    expected_output="The final output must be a valid Python list assignment containing file paths.",
    input={"user_query": "{{user_query}}"},
    output_file="project_output/paths.txt"
)

# === Agent: Multi-File Reader ===
class MultiFileReaderAgent(Agent):
    def run(self, input_data):
        file_paths = input_data.get("file_paths", [])
        if isinstance(file_paths, str):
            file_paths = ast.literal_eval(file_paths)

        all_code = ""
        for path in file_paths:
            code = git_reader(path)
            all_code += f"\n// FILE: {path}\n{code}\n"
        return all_code

file_reader_agent = MultiFileReaderAgent(
    role="Java File Reader",
    goal="Read Java files from GitHub and concatenate their content into a single output.",
    backstory="You fetch multiple Java source codes from GitHub and combine them.",
    tools=[git_reader],
    llm=llm,
    allow_delegation=False,
    verbose=True
)

file_reading_task = Task(
    agent=file_reader_agent,
    description=(
        "Given the Python list of file paths from the previous task, "
        "read each file's content from GitHub and combine them."
    ),
    expected_output="Concatenated Java source code from all file paths.",
    input={"file_paths": "{{query_response_task.output}}"},
    output_file="project_output/code.txt"
)

# === Agent: Tech Lead ===
tech_lead_agent = Agent(
    role="Tech Lead",
    goal="Generate comprehensive user stories for developers and testers based on code changes and user requirements.",
    backstory="You are a highly experienced Tech Lead in a software company, skilled at translating feature requests into actionable user stories.",
    tools=[git_reader],
    llm=llm,
    allow_delegation=False,
    verbose=True
)

generate_stories_task = Task(
    description=(
        "Analyze the content of the provided combined Java code file ('code_file_path') and the user request: '{{user_query}}'. "
        "Based on this analysis, generate two sets of user stories: one for developers and one for testers."
    ),
    agent=tech_lead_agent,
    expected_output="A string containing Developer and Tester user stories, clearly labeled.",
    input={
        "code_file_path": "{{file_reading_task.output}}",
        "user_query": "{{user_query}}"
    },
    output_file="project_output/stories.txt"
)

# === Crew Setup ===
project_analysis_crew = Crew(
    agents=[project_analyzer_agent, file_reader_agent, tech_lead_agent],
    tasks=[query_response_task, file_reading_task, generate_stories_task],
    process=Process.sequential
)

# === Entry Function for Streamlit ===
def run_story_generation(user_query: str, git_path: str, git_token: str) -> str:
    global repo_url, token
    repo_url = git_path
    token = git_token

    result = project_analysis_crew.kickoff(inputs={
        "user_query": user_query
    })
    return result
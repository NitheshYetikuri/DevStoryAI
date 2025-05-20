from dotenv import load_dotenv
import os
from crewai import Agent, Task, Crew, LLM, Process
from crewai_tools import FileReadTool

# Load environment variables from .env file
load_dotenv()

# Tool Initialization
file_read_tool = FileReadTool()

# LLMs with keys from environment variables
llm = LLM(
    model='gemini/gemini-2.0-flash',
    api_key=os.getenv("GEMINI_API_KEY_1")
)
llm_new = LLM(
    model='gemini/gemini-2.0-flash',
    api_key=os.getenv("GEMINI_API_KEY_2")
)
# -------------------- Agents --------------------

TL_agent = Agent(
    role="Team Lead",
    goal="Analyze stories and break them into clear development and testing tasks.",
    backstory="You're a tech-savvy Team Lead who understands both development and testing in Spring Boot applications. "
              "Your job is to read user stories from a file and assign specific tasks to the developer and tester based on the story requirements.",
    llm=llm_new,
    tools=[file_read_tool],
    allow_delegation=True,
    verbose=True
)

developer_agent = Agent(
    role="Backend Developer",
    goal="Generate Java Spring Boot code that meets the assigned user story requirements and code. Do not write test code.",
    backstory="You're a backend developer specialized in Java, Spring Boot, and JPA. "
              "Based on tasks assigned by the Team Lead and class information from a file, your responsibility is to implement only the backend logic.",
    llm=llm,
    allow_delegation=False,
    verbose=True
)

developer_approver_agent = Agent(
    role="Code Reviewer",
    goal="Evaluate and approve Java code submitted by the developer, ensuring it fulfills the user story and follows best practices.",
    backstory="You're a senior software architect who reviews Java Spring Boot code. "
              "You ensure correctness, alignment with the story, and coding standards before approval.",
    llm=llm_new,
    allow_delegation=False,
    verbose=True
)

tester_agent = Agent(
    role="QA Engineer",
    goal="Generate JUnit test cases based on the functionality implemented by the developer and tasks assigned by the Team Lead.",
    backstory="You're a software tester with deep understanding of backend systems. "
              "Using class data and the developer's code, you create high-quality JUnit test cases.",
    llm=llm,
    allow_delegation=False,
    verbose=True
)

tester_approver_agent = Agent(
    role="Test Case Reviewer",
    goal="Review the JUnit test cases to ensure they comprehensively validate the assigned functionality and follow best practices.",
    backstory="You're a seasoned QA lead who checks if JUnit test cases are sufficient, accurate, and aligned with the user story and implementation.",
    llm=llm_new,
    allow_delegation=False,
    verbose=True
)

# -------------------- Tasks --------------------

TL_task = Task(
    description="Read stories from the input file and assign tasks separately for development and testing. "
                "Ensure each task clearly refers to a specific story and includes enough detail for execution.",
    agent=TL_agent,
    tools=[file_read_tool],
    expected_output="Tasks assigned to developer and tester, indicating which story each task belongs to.",
    input={
        "user_stories": "{{myenv/output/stories.txt}}"
    }
)

developer_task = Task(
    description="Implement backend Java code using the information provided in the class definitions file and the Team Lead's assigned task and also consider reading the code files from input . "
                "Implement complete and production-ready Java backend code using the class details in the input files and the task from the Team Lead. "
                "The code must include correct package declarations and necessary imports as per `code.txt`. Do not include any test code",
    agent=developer_agent,
    tools=[file_read_tool],
    expected_output="Java code that implements the required functionality, without test logic.",
    context=[TL_task],
    input={
        "code": "{{project_output/code.txt}}"
    }
)

developer_approve_task = Task(
    description="Review the Java code written by the developer. Confirm if it meets the user story requirements and follows clean code practices. "
                "Provide either approval or specific revision feedback.",
    agent=developer_approver_agent,
    expected_output="Approval confirmation or feedback for changes to the developer code.",
    context=[TL_task, developer_task]
)

tester_task = Task(
    description="Generate detailed JUnit test cases for the backend functionality implemented by the developer and also consider reading the code files from input . "
                "Use the TL’s task assignment and developer code to understand what to test.",
    agent=tester_agent,
    tools=[file_read_tool],
    expected_output="A complete set of JUnit test cases validating the described functionality.",
    context=[TL_task, developer_task],
    input={
        "code": "{{project_output/code.txt}}"
    }
)

tester_approve_task = Task(
    description="Review the JUnit test cases for completeness, correctness, and alignment with the user story and implemented logic. "
                "Approve them or suggest necessary improvements.",
    agent=tester_approver_agent,
    expected_output="Approval confirmation for test cases or detailed feedback for improvement.",
    context=[TL_task, tester_task]
)

developer_write_task = Task(
    description="If the code generated by the developer is approved, write the approved Java code to the 'developer_code.txt' file.",
    agent=developer_agent,
    expected_output="Java code written to 'developer_code.txt'.",
    context=[developer_approve_task, developer_task],
    output_file="project_output/developer_code.txt",
    condition=lambda output: "approved" in output.lower()
)

tester_write_task = Task(
    description="If the test cases generated by the tester are approved, write the approved JUnit test cases to the 'tester_code.txt' file.",
    agent=tester_agent,
    expected_output="Test cases written to 'tester_code.txt'.",
    context=[tester_approve_task, tester_task],
    output_file="project_output/tester_code.txt",
    condition=lambda output: "approved" in output.lower()
)

# -------------------- Crew --------------------

stories_imple_crew = Crew(
    agents=[TL_agent, developer_agent, developer_approver_agent, tester_agent, tester_approver_agent],
    tasks=[TL_task, developer_task, developer_approve_task, tester_task, tester_approve_task, developer_write_task, tester_write_task],
    process=Process.sequential,
    verbose=True
)

# -------------------- Run function --------------------

def run_code_generation():
    development_report = stories_imple_crew.kickoff()
    return development_report

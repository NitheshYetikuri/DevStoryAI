# 🚀 DevStoryAI

DevStoryAI is an intelligent assistant that analyzes Java projects from GitHub, generates user stories based on natural language queries, and automatically creates production-ready Java code and JUnit tests using AI agents. It integrates CrewAI, LangChain, and Gemini models with a friendly Streamlit interface.

---

## 🌟 Features

* 🔍 Analyze Java codebases from GitHub.
* 🧠 Generate developer and tester user stories using natural language input.
* 👥 Assign tasks to specialized AI agents for story handling.
* 🧑‍💻 Generate backend Java (Spring Boot) code automatically.
* ✅ Produce JUnit test cases for each generated feature.
* ☁️ Store project analysis and results securely in AWS DynamoDB and S3.
* 📊 Powered by CrewAI, LangChain, and Google Gemini Pro & Flash.

---

## 🤖 AI Agents in DevStoryAI

DevStoryAI uses CrewAI to orchestrate a team of specialized AI agents. Each agent contributes to a specific stage in the project analysis, story generation, code development, and review pipeline.

### 🧩 Agent Execution Sequence

| Agent Name               | Role                     | Responsibility                                                                   |
| ------------------------ | ------------------------ | -------------------------------------------------------------------------------- |
| **ProjectAnalyzerAgent** | Impact Analysis Agent    | Identifies impacted Java classes in the GitHub repo based on the user query.     |
| **FileReaderAgent**      | Source Code Reader Agent | Fetches and reads the source code of impacted Java files from GitHub.            |
| **TechLeadAgent**        | Story Generator Agent    | Analyzes user query + source code to generate developer and tester user stories. |
| **TaskAssignerAgent**    | Task Assignment Agent    | Assigns generated stories to Developer and Tester agents.                        |
| **DeveloperAgent**       | Code Generation Agent    | Writes Spring Boot Java code for the assigned developer user story.              |
| **TesterAgent**          | Test Generation Agent    | Writes JUnit test cases for the assigned tester user story.                      |
| **ReviewerAgent**        | Code Review Agent        | Reviews code and test cases for logic, standards, and potential issues.          |

---

## 📁 Project Structure

```
DevStoryAI/
├── streamlit/
│   ├── main.py               # Streamlit UI
│   ├── java_analyzer.py      # GitHub fetch & metadata generation
│   ├── stories1.py           # CrewAI pipeline for generating user stories
│   ├── CodeGenerator.py      # CrewAI pipeline for generating code + tests
│
├── project_output/           # Output folder (renamed from myenv)
│   ├── code.txt              # Parsed Java structure
│   ├── stories.txt           # Generated user stories
│   ├── developer_code.txt    # Generated Java code (Spring Boot)
│   ├── tester_code.txt       # Generated JUnit test cases
│
├── README.md
└── requirements.txt
```

---

## ⚙️ Tech Stack

* **Frontend**: Streamlit
* **Backend**: Python
* **Orchestration**: CrewAI
* **LLMs**: Gemini 1.5 Pro, Gemini Flash (via LangChain)
* **Cloud**: AWS S3 (storage), AWS DynamoDB (metadata)
* **GitHub Access**: GitHub REST API v3 + Personal Access Token
* **Java Parser**: JavaParser via subprocess or APIs

---

## 🧰 Prerequisites

* Python 3.10+
* AWS credentials with access to DynamoDB and S3
* Gemini API keys (Pro and Flash)
* [uv](https://github.com/astral-sh/uv) (used instead of `pip`)

---

## 🚀 Getting Started

### 1. Clone the repo

```bash
git clone https://github.com/NitheshYetikuri/DevStoryAI.git
cd DevStoryAI
```

### 2. Set up virtual environment and install dependencies

```bash
uv venv
source .venv/bin/activate
uv pip install -r requirements.txt
```

### 3. Set credentials

Update AWS and Gemini credentials in .env for:

* `java_analyzer.py`
* `stories.py`
* `CodeGenerator.py`

### 4. Run the app

```bash
streamlit run main.py
```

---

## 🧭 Workflow

1. **Form Submission**:

   * Enter GitHub repo URL, token, user ID, and project name.
   * Repo is analyzed and JSON metadata is stored in S3 and DynamoDB.

2. **Story Generation**:

   * Ask a natural language query like *"What if I want to add login functionality?"*
   * CrewAI generates user stories and displays them.

3. **Code Generation**:

   * Click the "Generate Code" button.
   * DeveloperAgent writes code; TesterAgent generates tests.
   * Outputs are saved in `project_output/`.

---



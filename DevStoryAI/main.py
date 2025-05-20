import streamlit as st
import boto3
from dotenv import load_dotenv # Import load_dotenv
import os # Import os for environment variables

from java_analyzer import analyze_java_project
from stories import run_story_generation
from CodeGenerator import run_code_generation

# === Load environment variables from .env file ===
load_dotenv()

# === DynamoDB Setup ===
dynamodb = boto3.resource(
    'dynamodb',
    region_name=os.getenv('AWS_REGION'),
    aws_access_key_id=os.getenv('AWS_ACCESS_KEY_ID'),
    aws_secret_access_key=os.getenv('AWS_SECRET_ACCESS_KEY')
)
table = dynamodb.Table('project_details')

# === UI Setup ===
st.set_page_config(page_title="DevStoryAI", layout="centered")
st.title("🔍  DevStoryAI")

# === Phase 1: Form Submission ===
with st.form("project_form"):
    user_id = st.text_input("User ID")
    git_path = st.text_input("GitHub Repo URL")
    git_token = st.text_input("GitHub Token", type="password")
    project_name = st.text_input("Project Name")
    submitted = st.form_submit_button("Analyze")

if submitted:
    if user_id and git_path and git_token and project_name:
        with st.spinner("Analyzing project..."):
            s3_metadata_url = analyze_java_project(git_path, git_token, project_name, user_id)

            if s3_metadata_url:
                try:
                    table.put_item(
                        Item={
                            'ID': user_id,
                            'git_path': git_path,
                            'git_token': git_token,
                            'project_name': project_name,
                            'json_path': s3_metadata_url
                        }
                    )
                    st.success(f"✅ Project '{project_name}' analyzed successfully!")
                    st.markdown(f"📦 [View JSON Metadata]({s3_metadata_url})", unsafe_allow_html=True)

                    st.session_state["git_path"] = git_path
                    st.session_state["git_token"] = git_token
                    st.session_state["project_name"] = project_name
                    st.session_state["chat_ready"] = True
                except Exception as e:
                    st.error(f"❌ Error inserting into DynamoDB: {e}")
            else:
                st.error("❌ Project analysis failed.")
    else:
        st.warning("⚠️ Please fill all fields.")

# === Phase 2: Chat Interface + Code Generation ===
if st.session_state.get("chat_ready"):
    st.markdown("---")
    st.header("💬 Ask a Question")

    user_query = st.text_input("Ask your question about the project", key="user_query")
    if st.button("Get Impacted Classes and Stories"):
        with st.spinner("Processing your query with CrewAI..."):
            result = run_story_generation(
                user_query=user_query,
                git_path=st.session_state["git_path"],
                git_token=st.session_state["git_token"]
            )
            st.subheader("📄 AI-Generated Output")
            st.code(result, language='markdown')

    st.markdown("---")
    st.header("🛠️ Code Generation from Stories")

    if st.button("Assign Stories to Developers and Testers & Generate Code"):
        with st.spinner("Assigning stories and generating code & tests..."):
            codegen_report = run_code_generation()
            st.success("✅ Code generation completed!")
            st.subheader("📝 Code Generation Report")
            st.text(codegen_report)
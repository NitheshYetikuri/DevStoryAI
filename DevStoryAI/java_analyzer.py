import os
import json
import logging
from typing import Dict, List, Optional, Union
from javalang.parse import parse
from javalang.tree import (
    ClassDeclaration, InterfaceDeclaration, MethodDeclaration, FieldDeclaration,
    MemberReference, MethodInvocation, VariableDeclarator, Type, ClassCreator
)
from github import Github
import requests
import boto3
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

STANDARD_LIBRARIES = {'System', 'log', 'e'}

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Initialize boto3 S3 client with credentials from environment variables
s3_client = boto3.client(
    's3',
    region_name=os.getenv('AWS_REGION'),
    aws_access_key_id=os.getenv('AWS_ACCESS_KEY_ID'),
    aws_secret_access_key=os.getenv('AWS_SECRET_ACCESS_KEY')
)

def parse_java_file(file_content: str) -> Union[ClassDeclaration, InterfaceDeclaration]:
    """Parses the content of a Java file and returns the AST."""
    return parse(file_content)

def is_standard_library_call(method_call: str) -> bool:
    """Checks if a method call is a standard library call."""
    return any(method_call.startswith(lib) for lib in STANDARD_LIBRARIES)

def extract_method_calls(method_node: MethodDeclaration) -> List[str]:
    """Extracts method calls from a method node."""
    calls = []
    for _, child in method_node:
        if isinstance(child, MethodInvocation):
            method_call = child.member
            if child.qualifier:
                qualifier = child.qualifier
                if isinstance(qualifier, MemberReference):
                    qualifier = qualifier.member
                elif isinstance(qualifier, ClassCreator) and isinstance(qualifier.type, Type):
                    qualifier = qualifier.type.name
                method_call = f"{qualifier}.{method_call}"
            if not is_standard_library_call(method_call):
                calls.append(method_call)
    return calls

def get_type_name(type_node: Optional[Type]) -> Optional[str]:
    """Gets the name of a type node."""
    return type_node.name if isinstance(type_node, Type) else str(type_node) if type_node else None

def extract_relationships(tree: Union[ClassDeclaration, InterfaceDeclaration], file_path: str) -> List[Dict]:
    """Extracts relationships (class/interface definitions, attributes, methods, calls) from a Java AST."""
    relationships = []
    for _, node in tree:
        if isinstance(node, (ClassDeclaration, InterfaceDeclaration)):
            node_type = 'class' if isinstance(node, ClassDeclaration) else 'interface'
            name = node.name
            extends = [get_type_name(ext) for ext in node.extends] if hasattr(node, 'extends') and node.extends else None
            implements = [get_type_name(impl) for impl in node.implements] if hasattr(node, 'implements') and node.implements else []
            attributes = [
                {
                    'name': declarator.name,
                    'type': get_type_name(member.type),
                    'modifiers': list(member.modifiers)
                }
                for member in node.body if isinstance(member, FieldDeclaration)
                for declarator in member.declarators if isinstance(declarator, VariableDeclarator)
            ]
            methods = {
                member.name: {
                    'calls': extract_method_calls(member),
                    'parameters': [{'name': p.name, 'type': get_type_name(p.type), 'modifiers': list(p.modifiers)} for p in member.parameters],
                    'return_type': get_type_name(member.return_type),
                    'modifiers': list(member.modifiers)
                }
                for member in node.body if isinstance(member, MethodDeclaration)
            }

            relationships.append({
                'className': name,
                'type': node_type,
                'classPath': file_path,
                'extends': extends if extends else None,
                'implements': implements if implements else None,
                'attributes': attributes if attributes else None,
                'methods': methods if methods else None
            })
    return relationships

def save_relationships_to_local(relationships: List[Dict], local_file_path: str):
    """Saves the extracted relationships to a JSON file."""
    try:
        # Ensure the directory exists
        os.makedirs(os.path.dirname(local_file_path), exist_ok=True)
        with open(local_file_path, 'w') as f:
            json.dump(relationships, f, indent=4)
        logging.info(f"JSON metadata saved locally to: {local_file_path}")
    except Exception as e:
        logging.error(f"Error saving JSON metadata locally: {e}")

def find_java_files_in_github(repo_url, github_token):
    """
    Finds all .java files in a GitHub repository without cloning it locally using the PyGithub library.

    Args:
        repo_url (str): The URL of the GitHub repository (e.g., "https://github.com/owner/repo").
        github_token (str): Your GitHub personal access token.

    Returns:
        list: A list of file paths with the ".java" extension found in the repository,
              or None if an error occurred.
    """
    try:
        # Extract owner and repository name from the URL
        parts = repo_url.split("/")
        owner = parts[-2]
        repo_name = parts[-1].replace(".git", "")

        g = Github(github_token)
        repo = g.get_repo(f"{owner}/{repo_name}")

        java_files = []
        contents = repo.get_git_tree(repo.default_branch, recursive=True).tree
        for item in contents:
            if item.type == 'blob' and item.path.endswith('.java'):
                java_files.append(item.path)
        return java_files

    except Exception as e:
        logging.error(f"An error occurred while listing Java files: {e}")
        return None

def get_file_content(repo_url, file_path, github_token):
    """
    Retrieves the content of a file from a GitHub repository.

    Args:
        repo_url (str): The URL of the GitHub repository.
        file_path (str): The path to the file within the repository.
        github_token (str): Your GitHub personal access token.

    Returns:
        str: The content of the file, or None if an error occurs.
    """
    try:
        parts = repo_url.split("/")
        owner = parts[-2]
        repo_name = parts[-1].replace(".git", "")

        headers = {}
        if github_token:
            headers['Authorization'] = f'token {github_token}'

        # Construct the API URL to get the file contents.
        api_url = f"https://api.github.com/repos/{owner}/{repo_name}/contents/{file_path}"
        response = requests.get(api_url, headers=headers)
        response.raise_for_status()  # Raise an exception for bad status codes

        content = response.json()['content']
        # The content is base64 encoded, so decode it.
        import base64
        return base64.b64decode(content).decode('utf-8')

    except requests.exceptions.RequestException as e:
        logging.error(f"Error fetching {file_path} from GitHub: {e}")
        return None
    except Exception as e:
        logging.error(f"An unexpected error occurred: {e}")
        return None

def save_json_to_s3(user_id: str, local_output_path: str, project_name: str) -> Optional[str]:
    S3_BUCKET_NAME = os.getenv('S3_BUCKET_NAME')
    S3_PREFIX = os.getenv('S3_PREFIX')
    s3_prefix = f"{S3_PREFIX}{user_id}/{project_name}/"
    s3_key = os.path.join(s3_prefix, f"{project_name}_metadata.json")  # Use project_name in filename for clarity
    s3_url = f"https://{S3_BUCKET_NAME}.s3.amazonaws.com/{s3_key}"

    try:
        s3_client.upload_file(local_output_path, S3_BUCKET_NAME, s3_key)
        logging.info(f"Uploaded {local_output_path} to s3://{S3_BUCKET_NAME}/{s3_key}")
        return s3_url
    except Exception as e:
        logging.error(f"Error uploading {local_output_path} to S3: {e}")
        return None

def analyze_java_project(git_url: str, git_token: str,project_name: str, user_id: str) -> Optional[str]:
    """Analyzes a Java project directly from a GitHub repository."""

    local_output_base = os.getenv('LOCAL_OUTPUT_BASE')
    local_output_path = os.path.join(local_output_base, project_name, "relationship.json")

    java_files = find_java_files_in_github(git_url, git_token)
    if not java_files:
        logging.error("No Java files found or unable to list files.")
        return None

    all_relationships = []

    for file_path in java_files:
        try:
            file_content = get_file_content(git_url, file_path, git_token)
            if file_content:
                tree = parse_java_file(file_content)
                relationships = extract_relationships(tree, file_path)
                all_relationships.extend(relationships)
            else:
                logging.error(f"Could not retrieve content for {file_path}. Skipping.")

        except Exception as e:
            logging.error(f"Error processing {file_path}: {e}")

    if all_relationships:
        save_relationships_to_local(all_relationships, local_output_path)
        s3_url = save_json_to_s3(user_id, local_output_path, project_name)
        return s3_url
    else:
        logging.info("No relationships extracted.")
        return None



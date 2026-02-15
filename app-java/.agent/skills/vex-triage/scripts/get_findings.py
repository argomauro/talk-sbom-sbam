import os
import json
import requests
import sys

def get_project_uuid(base_url, api_key, name, version):
    url = f"{base_url}/api/v1/project?name={name}&version={version}"
    headers = {"X-Api-Key": api_key}
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        projects = response.json()
        if projects:
            return projects[0]['uuid']
    return None

def get_findings(base_url, api_key, project_uuid):
    url = f"{base_url}/api/v1/finding/project/{project_uuid}"
    headers = {"X-Api-Key": api_key}
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        return response.json()
    return []

if __name__ == "__main__":
    dt_url = os.getenv("DT_URL", "http://host.docker.internal:8081").rstrip("/")
    api_key = os.getenv("DT_API_KEY")
    project_name = os.getenv("CI_PROJECT_NAME", "app-java")
    project_version = os.getenv("CI_COMMIT_BRANCH", "main")

    if not api_key:
        print("Error: DT_API_KEY is not set.")
        sys.exit(1)

    uuid = get_project_uuid(dt_url, api_key, project_name, project_version)
    if not uuid:
        print(f"Error: Project {project_name}:{project_version} not found.")
        sys.exit(1)

    findings = get_findings(dt_url, api_key, uuid)
    print(json.dumps(findings, indent=2))

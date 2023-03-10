import os
from github import Github
from slugify import slugify


g = Github(os.environ['GITHUB_TOKEN'])
user = g.get_user()

def create_repo(repo_name: str, private: bool = False) -> str:
    """Create a new repository.
    """
    res = user.create_repo(repo_name, private=True)
    return res.ssh_url


def create_repo_name(company_name: str, project: str) -> str:
    company_name = slugify(company_name)
    project = slugify(project)
    return f"{company_name}_{project}"

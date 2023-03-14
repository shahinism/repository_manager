import sys
import os
from typing import Iterable
from datetime import datetime
from github import Github
from github.GithubException import UnknownObjectException
from slugify import slugify
from prompt_toolkit.shortcuts import yes_no_dialog, input_dialog
from git import Repo
from logzero import logger
import click


GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN")
if not GITHUB_TOKEN:
    logger.error("GITHUB_TOKEN environment variable is not set")
    sys.exit(1)

GITHUB_USER = Github(os.environ["GITHUB_TOKEN"]).get_user()

def get_or_create_repo(repo_name: str, private: bool = True) -> str:
    try:
        res = GITHUB_USER.get_repo(repo_name)
    except UnknownObjectException as e:
        if e.status == 404:
            res = create_repo(repo_name, private)
        else:
            raise e

    return res.ssh_url


def create_repo(repo_name: str, private: bool = True) -> Repo:
    """Create a new repository."""
    res = GITHUB_USER.create_repo(repo_name, private=private)
    return res


def create_repo_name(company_name: str, project: str) -> str:
    company_name = slugify(company_name)
    project = slugify(project)
    return f"{company_name}_{project}"


def is_git_repo(path: str) -> bool:
    """Check if a given path is a git repository."""
    return os.path.isdir(os.path.join(path, ".git"))


def find_git_repos(path: str) -> Iterable[str]:
    for sub in os.scandir(path):
        if not sub.is_dir():
            continue

        path = sub.path
        if is_git_repo(path):
            yield path
        else:
            yield from find_git_repos(path)


def set_remote(
    repo_path: str,
    remote_name: str,
    remote_url: str,
    fetch_params: str = "+refs/heads/*:refs/remotes/origin/*",
) -> None:
    repo = Repo(repo_path)
    with repo.config_writer() as writer:
        writer.set_value(f'remote "{remote_name}"', "url", remote_url)
        writer.set_value(f'remote "{remote_name}"', "fetch", fetch_params)
        writer.release()


def push_repo(repo_path: str, remote_name: str) -> None:
    repo = Repo(repo_path)
    remote = repo.remote(remote_name)
    remote.push(all=True, force=True)


def push_tags(repo_path: str, remote_name: str) -> None:
    repo = Repo(repo_path)
    remote = repo.remote(remote_name)
    for tag in repo.tags:
        logger.info(f"Pushing tag {tag.name} to {remote_name}")
        remote.push(tag.path, force=True)


def set_lock(repo_path: str, lock_name: str) -> None:
    with open(os.path.join(repo_path, ".git", lock_name), "w") as f:
        f.write(datetime.now().isoformat())


def lock_exists(repo_path: str, lock_name: str) -> bool:
    return os.path.exists(os.path.join(repo_path, ".git", lock_name))


def process_repos(path: str, remote_name: str, lock_name: str = "github_lock") -> None:
    for idx, repo in enumerate(find_git_repos(path)):
        if lock_exists(repo, lock_name):
            logger.info(f"Skipping {repo} as it is locked")
            continue

        process = yes_no_dialog(
            title="1) Continue processing?", text=f"Do you want to make {repo}?"
        ).run()
        if not process:
            continue

        company_name, project_name = repo.split("/")[-2:]

        company_name = input_dialog(
            title="Company Name",
            text=f"Please enter the company name for \n {repo}:",
            default=company_name,
        ).run()
        project_name = input_dialog(
            title="Project Name",
            text=f"Please enter the project name for \n {repo}:",
            default=project_name,
        ).run()

        repo_name = create_repo_name(company_name, project_name)

        logger.info(f"Creating {repo_name}")
        ssh_url = get_or_create_repo(repo_name, private=True)

        logger.info(f"Setting remote {remote_name} to {ssh_url}")
        set_remote(repo, remote_name, ssh_url)

        logger.info(f"Pushing {repo} to {remote_name}")
        push_repo(repo, remote_name)

        logger.info(f"Pushing tags to {remote_name}")
        push_tags(repo, remote_name)

        logger.info(f"Setting lock for {repo}")
        set_lock(repo, lock_name)


@click.command(name="Upload to GitHub", help="""

This command will find all git repositories in a given path and upload
them to GitHub. I needed to structure them based on the projects, so
it uses my personal convention, where all repositories, are located in
main project's root directory.

The command will create the GitHub repository based on the convention
(if it doesn't already exist).

It'll upload all of the local branches, and tags.

After processing is done, it'll create a `github_lock` file in the
`.git` folder, to prevent reprocessing.

To use it, you need to set `GITHUB_TOKEN` environment variable. You
can get it based on this documentation: https://bit.ly/3leBkHM

Make sure you enable the following scopes:

1. Repository: Read access to metadata.
2. Repository: Read and Write access to administration.

""")
@click.argument("path", type=click.Path(exists=True))
@click.option("r", "--remote-name", type=click.STRING, default="origin")
@click.option("l", "--lock-name", type=click.STRING, default="github_lock")
def main(path, remote_name, lock_name) -> None:
    process_repos(path, remote_name, lock_name)


if __name__ == "__main__":
    main()

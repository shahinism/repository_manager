import pytest
from app import create_repo_name


@pytest.mark.parametrize(
    "company,project,expected",
    [
        ["company", "project", "company_project"],
        ["Company", "Project", "company_project"],
        ["Green Company", "My Project", "green-company_my-project"],
    ],
)
def test_create_repo_name(company, project, expected):
    assert create_repo_name(company, project) == expected

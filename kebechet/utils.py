#!/usr/bin/env python3
# Kebechet
# Copyright(C) 2018, 2019, 2020 Fridolin Pokorny
#
# This program is free software: you can redistribute it and / or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program. If not, see <http://www.gnu.org/licenses/>.

"""Just some utility methods."""


import os
import logging
import tempfile
from ogr.services.base import BaseGitService
from contextlib import contextmanager
from tempfile import TemporaryDirectory
from urllib.parse import urljoin
from typing import TYPE_CHECKING, Optional
import git

from ogr.services.github import GithubService
from ogr.services.gitlab import GitlabService
from ogr.services.pagure import PagureService

if TYPE_CHECKING:
    from .manager import ManagerBase


_LOGGER = logging.getLogger(__name__)
APP_NAME = os.getenv("GITHUB_APP_NAME", "khebhut")


@contextmanager
def cwd(path: str):
    """Change working directory in a push-pop manner with context manager."""
    previous_dir = os.getcwd()
    try:
        os.chdir(path)
        yield previous_dir
    finally:
        os.chdir(previous_dir)


@contextmanager
def cloned_repo(manager: "ManagerBase", **clone_kwargs):
    """Clone the given Git repository and cd into it."""
    service_url = manager.service_url
    slug = manager.slug
    if service_url.startswith("https://"):
        service_url = service_url[len("https://") :]
    elif service_url.startswith("http://"):
        service_url = service_url[len("http://") :]
    else:
        # This is mostly internal error - we require service URL to have protocol explicitly set
        raise NotImplementedError

    if manager.installation:
        access_token = manager.token
        repo_url = f"https://{APP_NAME}:{access_token}@{service_url}/{slug}"
    else:
        repo_url = f"git@{service_url}:{slug}.git"

    with TemporaryDirectory() as repo_path, cwd(repo_path):
        _LOGGER.info(f"Cloning repository {repo_url} to {repo_path}")
        repo = git.Repo.clone_from(repo_url, repo_path, branch="master", **clone_kwargs)
        repo.config_writer().set_value(
            "user", "name", os.getenv("KEBECHET_GIT_NAME", "Kebechet")
        ).release()
        repo.config_writer().set_value(
            "user",
            "email",
            os.getenv("KEBECHET_GIT_EMAIL", "noreply+kebechet@redhat.com"),
        ).release()
        yield repo


def construct_raw_file_url(
    service_url: str,
    slug: str,
    file_name: str,
    service_type: str,
    branch: str = None,
) -> str:
    """Get URL to a raw file - useful for downloads of content."""
    branch = branch or "master"
    if service_type == "GITHUB":
        # TODO self hosted GitHub?
        url = f"https://raw.githubusercontent.com/{slug}/{branch}/{file_name}"
    elif service_type == "GITLAB":
        url = urljoin(service_url, f"{slug}/raw/{branch}/{file_name}")
    else:
        raise NotImplementedError

    return url


@contextmanager
def download_kebechet_config(
    service: BaseGitService, namespace: str, project: str, branch: Optional[str] = None
):
    """Get file containing contents of .thoth.yaml from a remote repository."""
    ogr_project = service.get_project(namespace=namespace, repo=project)
    if branch is None:
        branch = ogr_project.default_branch

    content = ogr_project.get_file_content(".thoth.yaml", ref=branch)

    with tempfile.TemporaryFile("w+") as f:
        f.write(content)
        f.seek(0)
        _LOGGER.info(content)
        yield f


def create_ogr_service(
    service_type: str,
    service_url: Optional[str] = None,
    token: Optional[str] = None,
    github_app_id: Optional[str] = None,
    github_private_key_path: Optional[str] = None,
):
    """Create a new OGR service for interacting with remote GitForges."""
    service_type = service_type.upper()
    if service_type == "GITHUB":
        ogr_service = GithubService(
            token=token,
            github_app_id=os.getenv("GITHUB_APP_ID"),
            github_private_key_path=os.getenv("GITHUB_PRIVATE_KEY_PATH"),
        )
    elif service_type == "GITLAB":
        ogr_service = GitlabService(token=token, instance_url=service_url)
    elif service_type == "PAGURE":
        ogr_service = PagureService(
            token=token,
            instance_url=service_url,
        )
    else:
        raise NotImplementedError(f"Kebechet cannot act on {service_type}")
    return ogr_service

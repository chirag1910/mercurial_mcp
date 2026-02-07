from fastmcp import FastMCP
from fastmcp.exceptions import ToolError
from fastmcp.prompts.prompt import Message, PromptMessage, TextContent
import asyncio
import os
import helpers

mcp = FastMCP("Mercurial MCP", mask_error_details=True)

HG_REPO_ROOT = os.environ.get("HG_REPO_ROOT")
TOKEN_LIMIT = int(os.environ.get("TOKEN_LIMIT", 4096)) # decrease in case client fails with unknown error

if not HG_REPO_ROOT:
    raise ValueError("HG_REPO_ROOT environment variable is not set")

if not os.path.exists(HG_REPO_ROOT) or not os.path.isdir(HG_REPO_ROOT):
    raise ValueError("HG_REPO_ROOT does not exist or is not a directory")

# get parent directory of HG_REPO_ROOT
CWD = os.path.dirname(HG_REPO_ROOT)


@mcp.tool()
async def get_file_at_commit(commit_hash: str, file_path: str, page: int = 1) -> dict:
    """
    Get the content of a file at a specific commit.

    Args:
        commit_hash: The hash of the commit.
        file_path: The absolute path of the file.
        page: The page number of the file content.

    Returns:
        Returns a dictionary with the content of the file at the given commit
        and meta information about the response/pagination.
    """
    try:
        relpath = os.path.relpath(file_path, CWD)
        command = f'hg cat {commit_hash} {relpath}'

        result = await helpers.run_command_async(command, CWD)
        return helpers.get_paginated_result(result, page, TOKEN_LIMIT)
    except Exception as e:
        raise ToolError(str(e))


@mcp.tool()
async def blame_file(file_path: str, page: int = 1) -> dict:
    """
    Blames/annotates the given file.

    Args:
        file_path: The absolute path of the file.
        page: The page number of the blame.

    Returns:
        Returns a dictionary with the result and meta information about
        the response/pagination.
        The result is a string where each line is of the form:
        <commit_hash>, <parent_commit_hash>, <author>, <date|age>, <line_content>
    """
    try:
        relpath = os.path.relpath(file_path, CWD)
        command = "hg annotate --template '{lines % \"{pad(node|short,12,left=true)}, {pad(p1node|short,12,left=true)}, {pad(fill(author|emailuser|lower,11)|firstline,11,left=true)}, {pad(date|age|short,13,left=true)}, {line}\"}'"

        command += f" {relpath}"

        result = await helpers.run_command_async(command, CWD)
        return helpers.get_paginated_result(result, page, TOKEN_LIMIT)
    except Exception as e:
        raise ToolError(str(e))


@mcp.tool()
async def log_commits(file_path: str = None, page: int = 1) -> dict:
    """
    Returns the log of commits. If file_path is provided, returns the log of commits for that file.

    Args:
        file_path: The absolute path of the file.
        page: The page number of the log.

    Returns:
        Returns a dictionary with the result containing the log of commits and
        meta information about the response/pagination.
    """
    try:
        command = "hg log"

        if file_path is not None:
            relpath = os.path.relpath(file_path, CWD)
            command += f" -f {relpath}"

        result = await helpers.run_command_async(command, CWD)
        return helpers.get_paginated_result(result, page, TOKEN_LIMIT)
    except Exception as e:
        raise ToolError(str(e))


@mcp.tool()
async def get_commit_summary(commit_hash: str, page: int = 1) -> dict:
    """
    Gets the summary of a commit.

    Args:
        commit_hash: The hash of the commit.
        page: The page number of the summary.

    Returns:
        Returns a dictionary with the result containing the summary of the commit and
        meta information about the response/pagination.
    """
    try:
        desc_task = asyncio.create_task(helpers.get_commit_desc(commit_hash, CWD))
        diff_task = asyncio.create_task(helpers.get_commit_diff(commit_hash, CWD))

        desc, diff = await asyncio.gather(desc_task, diff_task)
        result = f"""Description:\n{desc}\n\nDiff:\n{diff}"""

        return helpers.get_paginated_result(result, page, TOKEN_LIMIT)
    except Exception as e:
        raise ToolError(str(e))


@mcp.tool()
async def search_across_files(pattern: str, page: int = 1) -> dict:
    """
    Searches for a pattern across all files in the repository. However,
    could be slow for large repositories, so, use when necessary.

    Args:
        pattern: The regex to search for.
        page: The page number of the search results.

    Returns:
        Returns a dictionary with the result containing the list of files
        that contain the pattern along with the commit id and
        meta information about the response/pagination.
    """
    try:
        command = f"hg grep --all '{pattern}'"

        result = await helpers.run_command_async(command, CWD)
        return helpers.get_paginated_result(result, page, TOKEN_LIMIT)
    except Exception as e:
        raise ToolError(str(e))


@mcp.tool()
async def get_revision_summary_by_id(revision_id: str, page: int = 1) -> dict:
    """
    Gets the summary of revision/differential. Revisions/differentials are the
    code changes which aren't yet committed.

    Args:
        revision_id: The id of the revision; starts with 'D'
        page: The page number of the summary.

    Returns:
        Returns a dictionary with the result containing the summary of the revision and
        meta information about the response/pagination.
        The summary includes the title, description of the changes,
        test plan and other meta data. It doesn't include the actual code changes.
    """
    try:
        if not revision_id.startswith("D"):
            raise ValueError("Revision id must start with 'D'")

        revision_id = revision_id.replace("D", "")
        command = """echo '{"constraints": {"ids": [%s]}}' | arc call-conduit -- differential.revision.search""" % revision_id

        result = await helpers.run_command_async(command, CWD)
        return helpers.get_paginated_result(result, page, TOKEN_LIMIT)
    except Exception as e:
        raise ToolError(str(e))


@mcp.tool()
async def get_revision_changes_by_id(revision_id: str, page: int = 1) -> dict:
    """
    Gets the content of revision/differential. Revisions/differentials are the
    code changes which aren't yet committed.

    Args:
        revision_id: The id of the revision; starts with 'D'
        page: The page number of the changes.

    Returns:
        Returns a dictionary with the result containing the changes made as part of the revision and
        meta information about the response/pagination.
    """
    try:
        if not revision_id.startswith("D"):
            raise ValueError("Revision id must start with 'D'")

        command = f"arc export --revision {revision_id} --git"

        result = await helpers.run_command_async(command, CWD)
        return helpers.get_paginated_result(result, page, TOKEN_LIMIT)
    except Exception as e:
        raise ToolError(str(e))


@mcp.tool()
async def get_task_summary_by_id(task_id: str, page: int = 1) -> dict:
    """
    Gets the summary of task/maniphest. Tasks/maniphest includes
    the information of bugs, feature requests, etc. which are yet to
    be resolved.

    Args:
        task_id: The id of the task; starts with 'T'
        page: The page number of the summary.

    Returns:
        Returns a dictionary with the result containing the summary of the task and
        meta information about the response/pagination.
        The summary includes the title, description of the task and other meta data.
    """
    try:
        if not task_id.startswith("T"):
            raise ValueError("Task id must start with 'T'")

        task_id = task_id.replace("T", "")
        command = """echo '{"constraints": {"ids": [%s]}}' | arc call-conduit -- maniphest.search""" % task_id

        result = await helpers.run_command_async(command, CWD)
        return helpers.get_paginated_result(result, page, TOKEN_LIMIT)
    except Exception as e:
        raise ToolError(str(e))


@mcp.prompt()
def review_revision(revision_id: str) -> str:
    """
    Review the given revision/differential.
    """

    prompt = """
    You are a senior software engineer. Your task is to review {revision_id} revision/differential.
    Get and analyze the summary and changes of the revision/differential. Check if the changes are
    appropriate and make sense. If not, suggest changes. In case revision/differential is
    associated with a task/maniphest, get and analyze the summary of the task/maniphest and check
    if the changes are relevant/aligned with the task.

    Furthermore, review the changes against following parameters:
    - Syntax (as per Code Formatting)
    - Naming (of variables, methods, file names)
    - Comments (as per Documentation)
    - Code reuse (including refactoring opportunities)
    - Performance (of code and queries)
    - Security (is proper authorization added)
    - Migrations (are Online Schema Changes needed)
    """

    return PromptMessage(role="assistant", content=TextContent(type="text", text=prompt))


if __name__ == "__main__":
    mcp.run()
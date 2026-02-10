import asyncio
import os
import helpers
import json
from fastmcp import FastMCP
from fastmcp.exceptions import ToolError
from fastmcp.prompts.prompt import Message, PromptMessage, TextContent

mcp = FastMCP("Mercurial MCP", mask_error_details=True)

HG_REPO_ROOT = os.environ.get("HG_REPO_ROOT")
TOKEN_LIMIT = int(os.environ.get("TOKEN_LIMIT", 4096))

if not HG_REPO_ROOT:
    raise ValueError("HG_REPO_ROOT environment variable is not set")

if not os.path.exists(HG_REPO_ROOT) or not os.path.isdir(HG_REPO_ROOT):
    raise ValueError("HG_REPO_ROOT does not exist or is not a directory")

# CWD should be the repository root for mercurial commands
CWD = HG_REPO_ROOT

# Trust config for Mercurial to avoid ownership issues in Docker
TRUST_CONFIG = "--config trust.users=root --config trust.groups=root"


@mcp.tool()
async def get_file_at_commit(
    commit_hash: str, file_path: str, page: int = 1
) -> dict:
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
        relpath = helpers.get_relpath(file_path)
        command = f'hg {TRUST_CONFIG} cat -r {commit_hash} "{relpath}"'

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
        relpath = helpers.get_relpath(file_path)
        tpl = (
            "'{lines % \"{pad(node|short,12,left=true)}, "
            "{pad(p1node|short,12,left=true)}, "
            "{pad(fill(author|emailuser|lower,11)|firstline,11,left=true)}, "
            "{pad(date|age|short,13,left=true)}, {line}\"}'"
        )
        command = (
            f"hg {TRUST_CONFIG} annotate "
            f"--template {tpl} {relpath}"
        )

        result = await helpers.run_command_async(command, CWD)
        return helpers.get_paginated_result(result, page, TOKEN_LIMIT)
    except Exception as e:
        raise ToolError(str(e))


@mcp.tool()
async def log_commits(file_path: str = None, page: int = 1) -> dict:
    """
    Returns the log of commits. If file_path is provided, returns the log
    of commits for that file.

    Args:
        file_path: The absolute path of the file.
        page: The page number of the log.

    Returns:
        Returns a dictionary with the result containing the log of commits and
        meta information about the response/pagination.
    """
    try:
        command = f"hg {TRUST_CONFIG} log"

        if file_path is not None:
            relpath = helpers.get_relpath(file_path)
            command += f' -f "{relpath}"'

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
        desk_task_command = f"hg {TRUST_CONFIG} log -r {commit_hash} --template '{{desc}}'"
        diff_task_command = f"hg {TRUST_CONFIG} diff -c {commit_hash}"

        desc_task = asyncio.create_task(
            helpers.run_command_async(desk_task_command, CWD)
        )
        diff_task = asyncio.create_task(
            helpers.run_command_async(diff_task_command, CWD)
        )

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
        command = f"hg {TRUST_CONFIG} grep --all '{pattern}'"

        result = await helpers.run_command_async(command, CWD)
        return helpers.get_paginated_result(result, page, TOKEN_LIMIT)
    except Exception as e:
        raise ToolError(str(e))


@mcp.tool()
async def get_revision_summary_by_id(revision_id: str, page: int = 1) -> dict:
    """
    Gets the summary of revision/differential.

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
        command = (
            'echo \'{"constraints": {"ids": [%s]}}\' | '
            'arc call-conduit -- differential.revision.search'
        ) % revision_id

        result = await helpers.run_command_async(command, CWD)
        return helpers.get_paginated_result(result, page, TOKEN_LIMIT)
    except Exception as e:
        raise ToolError(str(e))


@mcp.tool()
async def get_revision_changes_by_id(revision_id: str, page: int = 1) -> dict:
    """
    Gets the content of revision/differential.

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
    Gets the summary of task/maniphest.

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
        command = (
            'echo \'{"constraints": {"ids": [%s]}}\' | '
            'arc call-conduit -- maniphest.search'
        ) % task_id

        result = await helpers.run_command_async(command, CWD)
        return helpers.get_paginated_result(result, page, TOKEN_LIMIT)
    except Exception as e:
        raise ToolError(str(e))


@mcp.tool()
async def get_revision_comments_by_id(revision_id: str, page: int = 1) -> dict:
    """
    Gets all comments/discussion on a revision/differential.

    Args:
        revision_id: The id of the revision; starts with 'D'
        page: The page number of the comments.
    """
    try:
        if not revision_id.startswith("D"):
            raise ValueError("Revision id must start with 'D'")

        numeric_id = revision_id.replace("D", "")

        command = (
            'echo \'{"ids": [%s]}\' | '
            'arc call-conduit -- differential.getrevisioncomments'
        ) % numeric_id

        result_temp = await helpers.run_command_async(command, CWD)
        data = json.loads(result_temp)
        comments = data.get("response", {}).get(numeric_id, [])

        phids = []
        result = []
        for comment_obj in comments:
            if comment_obj.get('content') is None:
                continue

            phids.append(comment_obj["authorPHID"])
            result.append({
                "dateCreated": comment_obj["dateCreated"],
                "authorPHID": comment_obj["authorPHID"],
                "content": comment_obj["content"]
            })

        username_mapping = await helpers.resolve_usernames(phids, CWD)
        for comment_obj in result:
            comment_obj["authorPHID"] = (
                username_mapping.get(comment_obj["authorPHID"], "Unknown")
            )

        return helpers.get_paginated_result(
            json.dumps(result, indent=2), page, TOKEN_LIMIT
        )

    except Exception as e:
        raise ToolError(str(e))


@mcp.tool()
async def get_task_comments_by_id(task_id: str, page: int = 1) -> dict:
    """
    Gets all comments/discussion on a task/maniphest.

    Args:
        task_id: The id of the task; starts with 'T'
        page: The page number of the comments.
    """
    try:
        if not task_id.startswith("T"):
            raise ValueError("Task id must start with 'T'")

        numeric_id = task_id.replace("T", "")

        command = (
            'echo \'{"ids": [%s]}\' | '
            'arc call-conduit -- maniphest.gettasktransactions'
        ) % numeric_id

        result_temp = await helpers.run_command_async(command, CWD)
        data = json.loads(result_temp)
        transactions = data.get("response", {}).get(numeric_id, [])

        phids = []
        result = []
        for comment_obj in transactions:
            if comment_obj.get("transactionType") != "core:comment":
                continue

            phids.append(comment_obj["authorPHID"])
            result.append({
                "dateCreated": comment_obj["dateCreated"],
                "authorPHID": comment_obj["authorPHID"],
                "comments": comment_obj["comments"]
            })

        username_mapping = await helpers.resolve_usernames(phids, CWD)
        for comment_obj in result:
            comment_obj["authorPHID"] = (
                username_mapping.get(comment_obj["authorPHID"], "Unknown")
            )

        return helpers.get_paginated_result(
            json.dumps(result, indent=2), page, TOKEN_LIMIT
        )

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

    return PromptMessage(
        role="assistant", content=TextContent(type="text", text=prompt)
    )


if __name__ == "__main__":
    mcp.run()
import asyncio
import re
import json

async def run_command_async(command: str, cwd: str) -> str:
    """
    Common method to run commands asynchronously.
    
    Args:
        command: The command to execute
        cwd: Working directory for the command
        
    Returns:
        Decoded stdout from the command
        
    Raises:
        Exception: If command fails with non-zero return code
    """
    try:
        process = await asyncio.create_subprocess_shell(
            command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=cwd
        )
        stdout, stderr = await process.communicate()
        
        if process.returncode != 0:
            raise Exception(stderr.decode().strip())
        
        return stdout.decode().strip()
    except Exception as e:
        raise Exception(str(e))

def get_page_boundaries(page, page_length):
    """
    Return the start and end indices for a given page.
    """
    start = (page - 1) * page_length
    end = page * page_length
    return start, end

def get_paginated_result(result: str, page: int, page_length: int):
    """
    Splits the result into pages based on the given page length.
    
    Args:
        result: The result to split into pages
        page: The page number to return
        page_length: The length of each page
    
    Returns:
        A dictionary containing the result, page number, total characters,
        and whether there are more pages
    """
    tokens = re.split(r'(\n)', result)

    # Remove empty tokens but keep newlines
    tokens = [token for token in tokens if token]

    if not tokens:
        return {
            "result": "",
            "total_chars": 0,
            "has_more": False
        }

    # Build pages by accumulating tokens until we hit the character limit
    # Stop early once we've found our target page
    current_page_num = 1
    current_page_content = []
    current_chars = 0
    target_page_content = ""
    has_more = False

    for i, token in enumerate(tokens):
        token_length = len(token)

        # If adding this token would exceed the limit, start a new page
        if current_chars + token_length > page_length and current_page_content:
            # Check if this is our target page
            if current_page_num == page:
                target_page_content = ''.join(current_page_content)
                # Check if there are more tokens (indicating more pages)
                has_more = i < len(tokens) - 1
                break
            
            # Move to next page
            current_page_num += 1
            current_page_content = []
            current_chars = 0

        # Add token to current page
        current_page_content.append(token)
        current_chars += token_length

    # Handle the last page or if we never hit the limit
    if not target_page_content:
        if current_page_num == page and current_page_content:
            target_page_content = ''.join(current_page_content)
            has_more = False
        elif page > current_page_num:
            target_page_content = ""
            has_more = False

    return {
        "result": target_page_content,
        "page": page,
        "total_chars": len(target_page_content),
        "has_more": has_more
    }

async def resolve_usernames(phids: list[str], cwd: str) -> dict[str, str]:
    """
    Resolves a list of PHIDs to usernames.

    Args:
        phids: List of PHIDs to resolve

    Returns:
        Dictionary mapping PHIDs to usernames
    """
    if not phids:
        return {}

    phids_json = ",".join([f'"{p}"' for p in set(phids)])

    command = f"""
    echo '{{"constraints": {{"phids": [{phids_json}]}}}}' \
    | arc call-conduit -- user.search
    """

    raw = await run_command_async(command, cwd)

    data = json.loads(raw)
    mapping = {}

    for user in data.get("response", {}).get("data", []):
        mapping[user["phid"]] = user["fields"]["username"]

    return mapping

def get_relpath(file_path: str) -> str:
    """
    Translates absolute path (possibly from host) to repository-relative path.
    """
    if not file_path:
        return None

    # If starts with HOST_REPO_ROOT, translate to relative
    if HOST_REPO_ROOT and file_path.startswith(HOST_REPO_ROOT):
        rel = os.path.relpath(file_path, HOST_REPO_ROOT)
        return rel

    # If starts with HG_REPO_ROOT, translate to relative
    if file_path.startswith(HG_REPO_ROOT):
        rel = os.path.relpath(file_path, HG_REPO_ROOT)
        return rel

    # Otherwise assume it might already be relative or from some other root
    return file_path

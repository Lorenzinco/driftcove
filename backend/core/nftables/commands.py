import importlib
import json
import re
from typing import Any

from backend.core.logger import logger as logging


class NftablesCommandError(RuntimeError):
    def __init__(self, command: str, error: str):
        super().__init__(f"nftables command failed: {command}\n{error}")
        self.command = command
        self.error = error


def _new_nft(*, json_output: bool = False, handle_output: bool = False):
    """Create a libnftables client only when a real nft operation is requested."""
    # The external binding is installed in the backend container, but not necessarily on
    # developer hosts. Lazy import keeps local test collection and skipped Docker tests usable.
    nftables_module = importlib.import_module("nftables")
    nft = getattr(nftables_module, "Nftables")()
    for method_name, value in (
        ("set_json_output", json_output),
        ("set_handle_output", handle_output),
        ("set_echo_output", False),
        ("set_stateless_output", False),
    ):
        method = getattr(nft, method_name, None)
        if method is not None:
            method(value)
    return nft


def _decode(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode(errors="replace")
    return str(value)


def nft_cmd(command: str, *, json_output: bool = False, handle_output: bool = False) -> str:
    nft = _new_nft(json_output=json_output, handle_output=handle_output)
    rc, out, err = nft.cmd(command)
    out_text = _decode(out)
    err_text = _decode(err)
    if rc != 0:
        raise NftablesCommandError(command, err_text or out_text)
    return out_text


def nft_try(command: str) -> None:
    try:
        nft_cmd(command)
    except Exception as exc:
        logging.debug("nftables command failed (ignored): %s -> %s", command, exc)




def nft_json(command: str) -> dict:
    out = nft_cmd(command, json_output=True)
    return json.loads(out or "{}")


def nft_list_text(command: str, *, handle_output: bool = False) -> str:
    try:
        return nft_cmd(command, handle_output=handle_output)
    except Exception:
        return ""


def slug(value: str) -> str:
    return "".join(ch if ch.isalnum() else "_" for ch in value)


def delete_rule_by_match(chain: str, pattern: str) -> None:
    out = nft_list_text(f"list chain inet dcv {chain}", handle_output=True)
    for line in out.splitlines():
        if re.search(pattern, line):
            match = re.search(r"handle\s+(\d+)", line)
            if match:
                nft_try(f"delete rule inet dcv {chain} handle {match.group(1)}")


def backup_table(family: str, table: str, fallback: str) -> str:
    out = nft_list_text(f"list table {family} {table}")
    return out if out.strip() else fallback


def restore_table(table_text: str, family: str, table: str) -> None:
    nft_try(f"delete table {family} {table}")
    nft_cmd(table_text)


def list_set_elements(set_name: str) -> list[Any]:
    try:
        data = nft_json(f"list set inet dcv {set_name}")
    except Exception as exc:
        logging.debug("nftables set query failed for %s: %s", set_name, exc)
        return []

    direct_set = data.get("set")
    if isinstance(direct_set, dict):
        return direct_set.get("elem", []) or []

    for item in data.get("nftables", []):
        set_data = item.get("set") if isinstance(item, dict) else None
        if isinstance(set_data, dict):
            return set_data.get("elem", []) or []
    return []


def element_tuple(element: Any) -> list[Any]:
    if isinstance(element, dict):
        value = element.get("elem", element.get("val", element))
    else:
        value = element
    return value if isinstance(value, list) else [value]


def table_rules() -> list[dict]:
    try:
        data = nft_json("list table inet dcv")
    except Exception:
        return []
    rules: list[dict] = []
    for item in data.get("nftables", []):
        rule = item.get("rule") if isinstance(item, dict) else None
        if isinstance(rule, dict):
            rules.append(rule)
    return rules


def expression_has_set(node: Any, name: str) -> bool:
    if isinstance(node, dict):
        if node.get("set") == name:
            return True
        lookup = node.get("lookup")
        if isinstance(lookup, dict) and (lookup.get("set") == name or lookup.get("name") == name):
            return True
        return any(expression_has_set(value, name) for value in node.values())
    if isinstance(node, list):
        return any(expression_has_set(value, name) for value in node)
    return False

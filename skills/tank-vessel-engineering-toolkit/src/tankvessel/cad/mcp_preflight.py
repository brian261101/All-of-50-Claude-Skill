"""Checklist helper for an MCP preflight; does not connect to MCP by itself."""
REQUIRED_PREFLIGHT = [
    "record MCP server name, version, source URL and license",
    "inspect tool names, descriptions, permissions and file scope",
    "confirm FreeCAD version and supported runtime",
    "test on a disposable scratch project",
    "verify saved FCStd exists and is non-empty",
    "verify STEP export exists and can be re-imported",
    "record tool errors and actual outputs",
]
def preflight_items():
    return list(REQUIRED_PREFLIGHT)

# Windows setup guide

## 1. Prepare the project

1. Install a supported FreeCAD release from the official distribution channel.
2. Install Git and a Python version compatible with your non-FreeCAD calculation code.
3. Create the project directory and copy the skill into `.claude/skills/tank-vessel-design/`.
4. Copy `src/tankvessel`, `tests`, `config` and `project_templates` into the project as needed.

## 2. Configure FreeCAD MCP safely

1. Choose a FreeCAD MCP server and inspect its current README, license, releases, issue tracker and required permissions.
2. Verify what each tool can do. A tool that executes arbitrary Python or shell commands may access files beyond the CAD project.
3. Use the server's documented Claude Code setup command and exact config schema. `config/mcp-config.example.json` is deliberately a placeholder and must not be used unchanged.
4. Restrict filesystem scope to the project/output folders where possible.
5. Test with a disposable model before opening a real project.
6. Do not install or run unknown MCP code with administrator privileges.

## 3. Start with a dry run

Ask Claude Code:

> Use the tank-vessel-design skill. Inspect the project and available MCP tools, but do not modify or delete existing files. Validate the design input template, report missing required data, and create a preliminary workflow plan. Do not perform code calculations yet.

## 4. FreeCAD Python environment

FreeCAD modules often are not importable from an unrelated system Python. Use the FreeCAD Python console, FreeCAD executable / macro mechanism, or the MCP server's documented bridge. Record FreeCAD version and export capabilities in the QA report.

## 5. Verify the MCP connection

Ask Claude Code to:
- list available FreeCAD tools;
- report their names and descriptions;
- create a simple disposable cylinder in a new scratch file;
- save and verify the file;
- export STEP and verify the export;
- report any failed step without claiming success.

## 6. Keep design and calculation modules separate

Run pure-Python tests for the calculation/input package independently from FreeCAD. Only validated calculation outputs may be used to size the production geometry. The initial toolkit deliberately blocks unimplemented code calculations.

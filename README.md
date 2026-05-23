# MicroAgent

Lightweight AI agent for llama.cpp. Designed for low-resource hardware.

## Setup

1. Run `start-server.bat` — starts llama-server with Gemma 4 E2B on port 8080
2. Run `start-agent.bat` — starts the agent CLI (auto-installs `requests` if needed)

## Features

- **Tools**: file read/write/append, list files, run shell commands
- **Memory**: persistent facts saved to `memory.json`
- **Auto-compaction**: summarizes old context when nearing the 6K token limit
- **Streaming**: responses stream token-by-token

## Commands

| Command       | Description                      |
|---------------|----------------------------------|
| `/help`       | Show commands                    |
| `/memory`     | View saved memories              |
| `/clear`      | Clear conversation, keep memory  |
| `/compact`    | Force context compaction         |
| `/tokens`     | Show context usage               |
| `/cd <path>`  | Change working directory         |
| `/quit`       | Exit                             |

## Tool Examples

Ask the agent things like:
- "List the files in C:\projects"
- "Read the file config.yaml"
- "Create a Python script that prints hello world"
- "Run `dir` in the current folder"
- "Remember that my project is in C:\myproject"
- "Notes to remember this is a small assistant made to run on a usb stick for portable uses."

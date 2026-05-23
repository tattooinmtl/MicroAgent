# MicroAgent

Lightweight AI agent for llama.cpp. Designed for low-resource hardware.
(Build on --
--Processor	Intel(R) Core(TM) i7-6560U CPU @ 2.20GHz   2.21 GHz
--Installed RAM	16.0 GB (15.9 GB usable)
--Storage	238 GB SSD W800S 256GB SSD
--Graphics Card	Intel(R) Iris(R) Graphics 540 (128 MB) 

Get the model used in this version here : https://huggingface.co/unsloth/gemma-4-E2B-it-GGUF

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

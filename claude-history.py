#!/usr/bin/env python3
"""
Claude Code Conversation History Viewer
A simple CLI tool to browse Claude Code conversation history
"""

import os
import sys
import json
import termios
import tty
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Optional, Tuple


# ANSI color codes
class Colors:
    BLUE = "\033[94m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    RED = "\033[91m"
    CYAN = "\033[96m"
    WHITE = "\033[97m"
    GRAY = "\033[90m"
    BOLD = "\033[1m"
    UNDERLINE = "\033[4m"
    END = "\033[0m"


# Constants
CLAUDE_DIR = Path.home() / ".claude" / "projects"
VERSION = "1.0.1"


class InteractiveMenu:
    """Simple interactive menu using arrow keys"""

    def __init__(self):
        self.selected_index = 0

    def get_key(self) -> str:
        """Get a single keypress"""
        fd = sys.stdin.fileno()
        old_settings = termios.tcgetattr(fd)
        try:
            tty.setraw(sys.stdin.fileno())
            key = sys.stdin.read(1)

            # Handle arrow keys (they send escape sequences)
            if key == "\x1b":  # ESC sequence
                key += sys.stdin.read(2)

            return key
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)

    def clear_screen(self):
        """Clear the terminal screen"""
        os.system("clear")

    def display_menu(self, items: List[str], title: str = "", paginate: bool = False, items_per_page: int = 10) -> int:
        """Display an interactive menu and return the selected index"""
        self.selected_index = 0
        current_page = 0
        total_items = len(items)

        # Calculate pagination if needed
        if paginate and total_items > items_per_page:
            total_pages = (total_items + items_per_page - 1) // items_per_page
        else:
            paginate = False
            total_pages = 1
            items_per_page = total_items

        while True:
            self.clear_screen()

            # Display title
            if title:
                print(f"{Colors.BOLD}{Colors.CYAN}{title}{Colors.END}")
                print("=" * len(title))
                print()

            # Display instructions
            if paginate:
                print(
                    f"{Colors.GRAY}Use ↑/↓ arrows to navigate, PgUp/PgDn for pages, Enter to select, 'q' to quit{Colors.END}"
                )
                print(f"{Colors.YELLOW}Page {current_page + 1}/{total_pages} (Total: {total_items} items){Colors.END}")
            else:
                print(
                    f"{Colors.GRAY}Use ↑/↓ arrows to navigate, Enter to select, 'q' to quit{Colors.END}"
                )
            print()

            # Calculate visible items range
            start_idx = current_page * items_per_page
            end_idx = min(start_idx + items_per_page, total_items)
            visible_items = items[start_idx:end_idx]

            # Display menu items
            for i, item in enumerate(visible_items):
                actual_index = start_idx + i
                if actual_index == self.selected_index:
                    print(f"{Colors.GREEN}▶ {item}{Colors.END}")
                else:
                    print(f"  {item}")

            # Get user input
            key = self.get_key()

            if key == "\x1b[A":  # Up arrow
                if self.selected_index > start_idx:
                    self.selected_index -= 1
                elif current_page > 0:
                    # Move to previous page, bottom item
                    current_page -= 1
                    self.selected_index = min((current_page + 1) * items_per_page - 1, total_items - 1)
            elif key == "\x1b[B":  # Down arrow
                if self.selected_index < min(end_idx - 1, total_items - 1):
                    self.selected_index += 1
                elif current_page < total_pages - 1:
                    # Move to next page, top item
                    current_page += 1
                    self.selected_index = current_page * items_per_page
            elif key == "\x1b[5~":  # Page Up
                if paginate and current_page > 0:
                    current_page -= 1
                    self.selected_index = current_page * items_per_page
            elif key == "\x1b[6~":  # Page Down
                if paginate and current_page < total_pages - 1:
                    current_page += 1
                    self.selected_index = current_page * items_per_page
            elif key == "\r" or key == "\n":  # Enter
                return self.selected_index
            elif key == "q" or key == "\x03":  # q or Ctrl+C
                self.clear_screen()
                print("Goodbye!")
                sys.exit(0)


class ClaudeHistoryViewer:
    """Main class for viewing Claude conversation history"""

    def __init__(self):
        self.menu = InteractiveMenu()
        self.projects_dir = CLAUDE_DIR

        # Check if Claude directory exists
        if not self.projects_dir.exists():
            print(
                f"{Colors.RED}Error: Claude projects directory not found at {self.projects_dir}{Colors.END}"
            )
            sys.exit(1)

    def get_projects(self) -> List[Tuple[str, Path]]:
        """Get list of projects with their paths"""
        projects = []

        for project_dir in sorted(self.projects_dir.iterdir()):
            if project_dir.is_dir():
                # Clean up project name for display
                # The directory name format is like: -Users-windy-coding-classum-classum-connect-backend
                # We need to convert it back to: /Users/windy/coding/classum/classum-connect-backend
                name = project_dir.name

                # Handle paths starting with -Users-
                if name.startswith("-Users-"):
                    # Remove the leading dash
                    name = name[1:]

                    # Split into parts
                    parts = name.split("-")

                    # Rebuild the path
                    path_parts = []
                    i = 0

                    # Handle /Users/username part
                    if len(parts) > 1 and parts[0] == "Users":
                        path_parts.append("/Users")
                        i = 1
                        # Next should be username
                        if i < len(parts):
                            path_parts.append(parts[i])
                            i += 1

                    # Process remaining parts more intelligently
                    # We'll track the depth and make educated guesses
                    depth = 2  # We're at /Users/username level

                    while i < len(parts):
                        part = parts[i]

                        # At depth 2-3, these are typically directory names
                        if depth <= 3 and part in [
                            "coding",
                            "Documents",
                            "Desktop",
                            "Downloads",
                            "Projects",
                        ]:
                            path_parts.append(part)
                            depth += 1
                        # Special handling for known nested structures
                        elif depth == 3 and part in ["kaggle", "analyze", "workspaces"]:
                            path_parts.append(part)
                            depth += 1
                        elif depth == 3 and part == "classum":
                            # classum is a directory, and the next "classum-connect-backend" is the project
                            path_parts.append(part)
                            remaining = "-".join(parts[i + 1 :])
                            if remaining:
                                path_parts.append(remaining)
                            break
                        elif depth == 4 and part in ["competitions"]:
                            path_parts.append(part)
                            depth += 1
                        elif depth == 5 and part in ["math"]:
                            path_parts.append(part)
                            depth += 1
                        else:
                            # This is likely the start of a hyphenated project name
                            remaining = "-".join(parts[i:])
                            path_parts.append(remaining)
                            break
                        i += 1

                    project_name = "/".join(path_parts)
                else:
                    # For other formats, just display as-is
                    project_name = name

                projects.append((project_name, project_dir))

        return projects

    def get_conversations(self, project_path: Path) -> List[Tuple[str, Path]]:
        """Get list of conversation files with dates"""
        conversations = []

        for jsonl_file in project_path.glob("*.jsonl"):
            # Skip swap files
            if jsonl_file.name.startswith("."):
                continue

            # Get file modification time
            mtime = datetime.fromtimestamp(jsonl_file.stat().st_mtime)
            date_str = mtime.strftime("%Y-%m-%d %H:%M")

            conversations.append((f"{date_str} - {jsonl_file.name}", jsonl_file, mtime))

        # Sort by date (newest first)
        conversations.sort(key=lambda x: x[2], reverse=True)

        return [(name, path) for name, path, _ in conversations]

    def parse_conversation(self, jsonl_path: Path) -> List[Dict]:
        """Parse JSONL file and extract conversation"""
        messages = []

        try:
            with open(jsonl_path, "r", encoding="utf-8") as f:
                for line in f:
                    if line.strip():
                        try:
                            data = json.loads(line)

                            # Extract message based on type
                            if data.get("type") == "user":
                                msg_content = data.get("message", {}).get("content", "")

                                # Handle both string and array content
                                if isinstance(msg_content, str):
                                    content = msg_content
                                elif isinstance(msg_content, list):
                                    # Extract ONLY text from content array (skip tool results)
                                    content_parts = []
                                    for item in msg_content:
                                        if isinstance(item, dict):
                                            # Only include text type, skip tool_result
                                            if item.get("type") == "text":
                                                text = item.get("text", "")
                                                if text:
                                                    content_parts.append(text)
                                        elif isinstance(item, str):
                                            content_parts.append(item)
                                    content = (
                                        "\n".join(content_parts)
                                        if content_parts
                                        else ""
                                    )
                                else:
                                    content = str(msg_content) if msg_content else ""

                                if content:
                                    messages.append(
                                        {
                                            "role": "user",
                                            "content": content,
                                            "timestamp": data.get("timestamp", ""),
                                        }
                                    )

                            elif data.get("type") == "assistant":
                                message = data.get("message", {})
                                content_list = message.get("content", [])

                                # Extract text from content array
                                text_content = ""
                                for content_item in content_list:
                                    if (
                                        isinstance(content_item, dict)
                                        and content_item.get("type") == "text"
                                    ):
                                        text_content += content_item.get("text", "")

                                if text_content:
                                    messages.append(
                                        {
                                            "role": "assistant",
                                            "content": text_content,
                                            "timestamp": data.get("timestamp", ""),
                                        }
                                    )

                            # Handle summary type messages
                            elif data.get("type") == "summary":
                                summary = data.get("summary", "")
                                if summary:
                                    messages.append(
                                        {
                                            "role": "summary",
                                            "content": f"[Summary: {summary}]",
                                            "timestamp": data.get("timestamp", ""),
                                        }
                                    )

                        except json.JSONDecodeError:
                            continue

        except Exception as e:
            print(f"{Colors.RED}Error reading file: {e}{Colors.END}")
            return []

        return messages

    def display_conversation(
        self, messages: List[Dict], project_name: str, file_name: str
    ):
        """Display the conversation content"""
        self.menu.clear_screen()

        # Display header
        print(f"{Colors.BOLD}{Colors.CYAN}Project: {project_name}{Colors.END}")
        print(f"{Colors.BOLD}{Colors.CYAN}File: {file_name}{Colors.END}")
        print("=" * 80)
        print()

        # Display messages
        for msg in messages:
            role = msg["role"]
            content = msg["content"]

            if role == "user":
                print(f"{Colors.GREEN}{Colors.BOLD}user:{Colors.END}")
                print(content)
                print()
            elif role == "assistant":
                print(f"{Colors.BLUE}{Colors.BOLD}assistant:{Colors.END}")
                print(content)
                print()
            elif role == "summary":
                print(f"{Colors.YELLOW}{content}{Colors.END}")
                print()

        # Wait for user to press any key
        print()
        print(f"{Colors.GRAY}Press any key to return to menu...{Colors.END}")
        self.menu.get_key()

    def run(self):
        """Main application loop"""
        while True:
            # Step 1: Select project
            projects = self.get_projects()

            if not projects:
                print(
                    f"{Colors.RED}No projects found in {self.projects_dir}{Colors.END}"
                )
                sys.exit(1)

            project_names = [name for name, _ in projects]
            # Enable pagination for project list if more than 15 items
            use_pagination = len(project_names) > 15
            selected_project_idx = self.menu.display_menu(
                project_names,
                "Select a Project",
                paginate=use_pagination,
                items_per_page=15
            )

            project_name, project_path = projects[selected_project_idx]

            # Step 2: Select conversation
            conversations = self.get_conversations(project_path)

            if not conversations:
                self.menu.clear_screen()
                print(
                    f"{Colors.YELLOW}No conversations found in this project{Colors.END}"
                )
                print(f"{Colors.GRAY}Press any key to continue...{Colors.END}")
                self.menu.get_key()
                continue

            conversation_names = [name for name, _ in conversations]
            # Enable pagination for conversation list if more than 10 items
            use_pagination = len(conversation_names) > 10
            selected_conv_idx = self.menu.display_menu(
                conversation_names,
                f"Select a Conversation from {project_name}",
                paginate=use_pagination,
                items_per_page=10
            )

            conv_name, conv_path = conversations[selected_conv_idx]

            # Step 3: Display conversation
            messages = self.parse_conversation(conv_path)

            if messages:
                self.display_conversation(messages, project_name, conv_path.name)
            else:
                self.menu.clear_screen()
                print(
                    f"{Colors.YELLOW}No messages found in this conversation{Colors.END}"
                )
                print(f"{Colors.GRAY}Press any key to continue...{Colors.END}")
                self.menu.get_key()


def main():
    """Main entry point"""
    # Handle command line arguments
    if len(sys.argv) > 1:
        if sys.argv[1] in ["--version", "-v"]:
            print(f"cchistory version {VERSION}")
            sys.exit(0)
        elif sys.argv[1] in ["--help", "-h"]:
            print("Claude Code Conversation History Viewer")
            print()
            print("Usage: cchistory")
            print()
            print("Interactive CLI tool to browse Claude Code conversation history")
            print()
            print("Options:")
            print("  -h, --help     Show this help message")
            print("  -v, --version  Show version information")
            sys.exit(0)

    # Run the viewer
    try:
        viewer = ClaudeHistoryViewer()
        viewer.run()
    except KeyboardInterrupt:
        print("\nGoodbye!")
        sys.exit(0)
    except Exception as e:
        print(f"{Colors.RED}Unexpected error: {e}{Colors.END}")
        sys.exit(1)


if __name__ == "__main__":
    main()

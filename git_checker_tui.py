#!/usr/bin/env python3

import os
import sys
import json
import subprocess
from collections import Counter
from pathlib import Path
from textual.app import App, ComposeResult
from textual.containers import VerticalScroll, Horizontal, Container
from textual.screen import ModalScreen
from textual.widgets import Header, Footer, Button, Checkbox, Input, Select, Static, Collapsible
from textual.reactive import reactive

CONFIG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "git_tui_config.json")

def setup_config():
    print("=== Configurazione Iniziale ===")
    folder = input("1. Inserisci la cartella da analizzare (es: ~/Desktop): ")
    folder = os.path.expanduser(folder)
    
    set_alias = input("2. Vuoi settare l'alias nel bashrc o zshrc per eseguirla tramite comando 'git-check'? (y/N): ")
    rc_file = ""
    
    if set_alias.lower() == 'y':
        rc_file = input("3. Inserisci il file di configurazione del terminale (es. ~/.zshrc): ")
        rc_file = os.path.expanduser(rc_file)
        script_path = os.path.abspath(__file__)
        alias_cmd = f"\n# Alias per Git Checker TUI\nalias git-check='python3 \"{script_path}\"'\n"
        
        try:
            with open(rc_file, 'a') as f:
                f.write(alias_cmd)
            print(f"[+] Alias aggiunto a {rc_file}")
        except Exception as e:
            print(f"[-] Errore durante il salvataggio dell'alias: {e}")

    config = {"folder": folder, "rc_file": rc_file}
    with open(CONFIG_FILE, 'w') as f:
        json.dump(config, f)
    
    print("[+] Configurazione salvata. Avvio TUI in corso...\n")
    return config

def get_config():
    if not os.path.exists(CONFIG_FILE):
        return setup_config()
    with open(CONFIG_FILE, 'r') as f:
        return json.load(f)

def get_git_folders(base_folder):
    git_folders = []
    if not os.path.exists(base_folder):
        return git_folders

    for root, dirs, files in os.walk(base_folder):
        if ".git" in dirs:
            dirs.remove(".git") 
            
            status = subprocess.run(
                ['git', 'status', '--porcelain', '-z'],
                cwd=root, capture_output=True, text=True
            )

            if status.stdout.strip():
                branches_out = subprocess.run(
                    ['git', 'branch', '--format=%(refname:short)'],
                    cwd=root, capture_output=True, text=True
                )
                branches = [(b, b) for b in branches_out.stdout.splitlines() if b]

                # -z separates entries with NUL and leaves paths unquoted; renames/copies
                # emit two NUL-terminated fields (new path, then old path).
                tokens = status.stdout.split('\0')
                changed_files = []
                i = 0
                while i < len(tokens):
                    entry = tokens[i]
                    if not entry:
                        i += 1
                        continue
                    file_status = entry[:2]
                    file_path = entry[3:]
                    i += 1
                    if file_status[0] in ('R', 'C'):
                        i += 1
                    changed_files.append({"status": file_status.strip(), "file": file_path})

                git_folders.append({
                    "name": os.path.basename(root),
                    "path": root,
                    "branches": branches,
                    "files": changed_files
                })

    name_counts = Counter(repo["name"] for repo in git_folders)
    for repo in git_folders:
        repo["duplicate"] = name_counts[repo["name"]] > 1

    return git_folders

def escape_markup(text):
    # Textual parses widget labels as console markup; a bare "[" from a
    # filesystem path or filename can be misread as a tag, so escape it.
    return text.replace("[", "\\[")

class RepoItem(Container):
    def __init__(self, repo_data, uid, **kwargs):
        super().__init__(**kwargs)
        self.repo_data = repo_data
        self.uid = uid

    def compose(self) -> ComposeResult:
        label = escape_markup(self.repo_data["name"])

        with Horizontal(classes="repo-row"):
            yield Checkbox(label, id=f"chk_{self.uid}", classes="repo-checkbox")
            yield Input(placeholder="Messaggio di commit...", id=f"msg_{self.uid}", classes="repo-msg")
            if self.repo_data["branches"]:
                yield Select(self.repo_data["branches"], prompt="Scegli Branch", id=f"br_{self.uid}", classes="repo-branch")
            else:
                yield Static("Nessun branch trovato", classes="repo-branch repo-no-branch")
            yield Button("Scarta", id=f"discard_{self.uid}", classes="repo-discard", variant="warning")

        if self.repo_data.get("duplicate"):
            yield Static(escape_markup(self.repo_data["path"]), classes="repo-path")

        files = self.repo_data.get("files", [])
        if files:
            with Collapsible(title=f"File modificati ({len(files)})", id=f"files_{self.uid}", collapsed=True):
                for i, f in enumerate(files):
                    yield Checkbox(
                        escape_markup(f"{f['status']:<3}{f['file']}"),
                        value=True,
                        id=f"file_{self.uid}_{i}",
                        classes="repo-file-checkbox"
                    )

class ConfirmDiscardScreen(ModalScreen[bool]):
    CSS = """
    ConfirmDiscardScreen {
        align: center middle;
    }
    #confirm-dialog {
        width: 70;
        height: auto;
        border: thick $error;
        background: $surface;
        padding: 1 2;
    }
    #confirm-buttons {
        height: 3;
        align: center middle;
        margin-top: 1;
    }
    #confirm-buttons Button {
        margin: 0 1;
    }
    """

    def __init__(self, repo_name, repo_path):
        super().__init__()
        self.repo_name = repo_name
        self.repo_path = repo_path

    def compose(self) -> ComposeResult:
        with Container(id="confirm-dialog"):
            yield Static(
                f"Scartare tutte le modifiche non committate in [b]{escape_markup(self.repo_name)}[/b]?\n"
                f"\\[{escape_markup(self.repo_path)}]\n\n"
                "Verranno eseguiti 'git reset --hard' e 'git clean -fd':\n"
                "le modifiche andranno perse e non saranno recuperabili.",
                id="confirm-message"
            )
            with Horizontal(id="confirm-buttons"):
                yield Button("Annulla", id="confirm-no", variant="primary")
                yield Button("Sì, scarta", id="confirm-yes", variant="error")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        self.dismiss(event.button.id == "confirm-yes")

class GitStatusTUI(App):
    CSS = """
    RepoItem {
        height: auto;
        margin-bottom: 1;
    }
    Horizontal {
        align: left middle;
    }
    .repo-row {
        height: 3;
    }
    .repo-checkbox { width: 20%; }
    .repo-msg { width: 38%; }
    .repo-branch { width: 24%; }
    .repo-discard { width: 16%; min-width: 10; }
    .repo-path {
        width: 100%;
        color: $text-muted;
        text-style: italic;
        padding-left: 1;
    }
    .repo-file-checkbox { width: 100%; }
    #action-bar {
        dock: bottom;
        height: 3;
        align: center middle;
        background: $boost;
    }
    Button { margin-right: 2; }
    """

    selected_count = reactive(0)

    def __init__(self, repos):
        super().__init__()
        self.repos = repos

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with VerticalScroll(id="repo-list"):
            if not self.repos:
                yield Static("[+] Nessun repository ha file da committare nella cartella analizzata.", id="no-repos")
            for idx, repo in enumerate(self.repos):
                yield RepoItem(repo, idx, id=f"row_{idx}")
        
        with Horizontal(id="action-bar"):
            yield Button("Esci", id="btn_exit", variant="error")
            yield Button("Committa Selezionati", id="btn_commit", variant="success")
            yield Button("Open Terminal", id="btn_terminal", variant="primary", disabled=True)

    def on_checkbox_changed(self, event: Checkbox.Changed) -> None:
        checked = self.query(".repo-checkbox")
        self.selected_count = sum(1 for c in checked if c.value)
        
        term_btn = self.query_one("#btn_terminal", Button)
        term_btn.disabled = self.selected_count != 1

    def on_button_pressed(self, event: Button.Pressed) -> None:
        button_id = event.button.id or ""

        if button_id == "btn_exit":
            self.exit()

        elif button_id == "btn_terminal":
            self.open_terminal()

        elif button_id == "btn_commit":
            self.commit_selected()

        elif button_id.startswith("discard_"):
            uid = int(button_id.removeprefix("discard_"))
            self.confirm_and_discard(uid)

    def open_terminal(self):
        selected_repo = None
        for row in self.query(RepoItem):
            chk = row.query_one(".repo-checkbox", Checkbox)
            if chk.value:
                selected_repo = row.repo_data
                break
        
        if selected_repo:
            cwd = selected_repo["path"]
            
            terminals = [
                ["x-terminal-emulator", "--working-directory", cwd],
                ["gnome-terminal", "--working-directory", cwd],
                ["konsole", "--workdir", cwd],
                ["xfce4-terminal", "--working-directory", cwd],
                ["alacritty", "--working-directory", cwd],
                ["kitty", "--directory", cwd]
            ]
            
            opened = False
            for cmd in terminals:
                try:
                    subprocess.Popen(
                        cmd, 
                        cwd=cwd, 
                        stdout=subprocess.DEVNULL, 
                        stderr=subprocess.DEVNULL
                    )
                    self.notify("Shell aperta in una nuova finestra!")
                    opened = True
                    break
                except FileNotFoundError:
                    continue
            
            if not opened:
                self.notify("Errore: Impossibile trovare un terminale compatibile.", severity="error")

    def commit_selected(self):
        any_committed = False
        for row in self.query(RepoItem):
            chk = row.query_one(".repo-checkbox", Checkbox)
            if chk.value:
                repo_data = row.repo_data
                msg_input = row.query_one(Input).value

                try:
                    branch_sel = row.query_one(Select).value
                except:
                    branch_sel = None

                if not msg_input:
                    msg_input = "Aggiornamento automatico"

                cwd = repo_data["path"]

                file_checks = list(row.query(".repo-file-checkbox"))
                if file_checks:
                    selected_files = [
                        repo_data["files"][i]["file"]
                        for i, cb in enumerate(file_checks) if cb.value
                    ]
                    if not selected_files:
                        self.notify(
                            f"Nessun file selezionato per {repo_data['name']}, salto.",
                            severity="warning"
                        )
                        continue
                    subprocess.run(['git', 'add', '--'] + selected_files, cwd=cwd)
                else:
                    subprocess.run(['git', 'add', '.'], cwd=cwd)

                subprocess.run(['git', 'commit', '-m', msg_input], cwd=cwd)

                if branch_sel and branch_sel != Select.BLANK:
                    subprocess.run(['git', 'push', 'origin', branch_sel], cwd=cwd)

                chk.value = False
                row.query_one(Input).value = ""
                any_committed = True

        if any_committed:
            self.notify("Commit e Push eseguiti per le cartelle selezionate!")

    def confirm_and_discard(self, uid):
        row = self.query_one(f"#row_{uid}", RepoItem)
        repo_data = row.repo_data

        def handle_result(confirmed: bool) -> None:
            if confirmed:
                self.discard_changes(row)

        self.push_screen(
            ConfirmDiscardScreen(repo_data["name"], repo_data["path"]),
            handle_result
        )

    def discard_changes(self, row):
        repo_data = row.repo_data
        cwd = repo_data["path"]
        subprocess.run(['git', 'reset', '--hard'], cwd=cwd)
        subprocess.run(['git', 'clean', '-fd'], cwd=cwd)
        self.notify(f"Modifiche scartate per {repo_data['name']}")
        row.remove()

if __name__ == "__main__":
    config = get_config()
    repos_with_changes = get_git_folders(config["folder"])
    
    app = GitStatusTUI(repos_with_changes)
    app.run()

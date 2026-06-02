#!/usr/bin/env python3

import os
import sys
import json
import subprocess
from pathlib import Path
from textual.app import App, ComposeResult
from textual.containers import VerticalScroll, Horizontal, Container
from textual.widgets import Header, Footer, Button, Checkbox, Input, Select, Static
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
                ['git', 'status', '--porcelain'], 
                cwd=root, capture_output=True, text=True
            )
            
            if status.stdout.strip(): 
                branches_out = subprocess.run(
                    ['git', 'branch', '--format=%(refname:short)'], 
                    cwd=root, capture_output=True, text=True
                )
                branches = [(b, b) for b in branches_out.stdout.splitlines() if b]
                
                git_folders.append({
                    "name": os.path.basename(root), 
                    "path": root, 
                    "branches": branches
                })
                
    return git_folders

class RepoItem(Container):
    def __init__(self, repo_data, **kwargs):
        super().__init__(**kwargs)
        self.repo_data = repo_data

    def compose(self) -> ComposeResult:
        with Horizontal():
            yield Checkbox(self.repo_data["name"], id=f"chk_{self.repo_data['name']}", classes="repo-checkbox")
            yield Input(placeholder="Messaggio di commit...", id=f"msg_{self.repo_data['name']}", classes="repo-msg")
            if self.repo_data["branches"]:
                yield Select(self.repo_data["branches"], prompt="Scegli Branch", id=f"br_{self.repo_data['name']}", classes="repo-branch")
            else:
                yield Static("Nessun branch trovato", classes="repo-no-branch")

class GitStatusTUI(App):
    CSS = """
    RepoItem {
        height: 3;
        margin-bottom: 1;
    }
    Horizontal {
        align: left middle;
    }
    .repo-checkbox { width: 25%; }
    .repo-msg { width: 45%; }
    .repo-branch { width: 25%; }
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
            for repo in self.repos:
                yield RepoItem(repo, id=f"row_{repo['name']}")
        
        with Horizontal(id="action-bar"):
            yield Button("Esci", id="btn_exit", variant="error")
            yield Button("Committa Selezionati", id="btn_commit", variant="success")
            yield Button("Open Terminal", id="btn_terminal", variant="primary", disabled=True)

    def on_checkbox_changed(self, event: Checkbox.Changed) -> None:
        checked = self.query(Checkbox)
        self.selected_count = sum(1 for c in checked if c.value)
        
        term_btn = self.query_one("#btn_terminal", Button)
        term_btn.disabled = self.selected_count != 1

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn_exit":
            self.exit()
        
        elif event.button.id == "btn_terminal":
            self.open_terminal()
            
        elif event.button.id == "btn_commit":
            self.commit_selected()

    def open_terminal(self):
        selected_repo = None
        for row in self.query(RepoItem):
            chk = row.query_one(Checkbox)
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
        for row in self.query(RepoItem):
            chk = row.query_one(Checkbox)
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
                subprocess.run(['git', 'add', '.'], cwd=cwd)
                subprocess.run(['git', 'commit', '-m', msg_input], cwd=cwd)
                
                if branch_sel and branch_sel != Select.BLANK:
                    subprocess.run(['git', 'push', 'origin', branch_sel], cwd=cwd)
                
                chk.value = False
                row.query_one(Input).value = ""
        
        self.notify("Commit e Push eseguiti per le cartelle selezionate!")

if __name__ == "__main__":
    config = get_config()
    repos_with_changes = get_git_folders(config["folder"])
    
    app = GitStatusTUI(repos_with_changes)
    app.run()

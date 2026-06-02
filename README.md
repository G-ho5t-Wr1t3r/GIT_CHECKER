# Git Checker TUI

Una comoda Text User Interface (TUI) per Linux che permette di scansionare ricorsivamente una cartella alla ricerca di repository Git con modifiche pendenti. Tramite questa interfaccia è possibile selezionare le repository, scrivere i messaggi di commit, scegliere il branch, eseguire il push e aprire direttamente un terminale nella cartella del progetto.

## Prerequisiti

Il progetto utilizza la libreria `textual` per generare l'interfaccia nel terminale. Tutte le dipendenze sono elencate nel file `requirements.txt`.

## Installazione

1. Clonare o scaricare questa repository sul computer.
2. (Opzionale ma consigliato) Creare un ambiente virtuale (tramite `venv` o `conda`).
3. Installare le dipendenze:
   ```bash
   pip install -r requirements.txt
   ```

## Configurazione Iniziale e Utilizzo

Al primo avvio, lo script (`git_checker_tui.py` o il nome che gli assegnato) chiederà di inserire:
- La cartella base da analizzare (es. `~/Desktop`).
- Il permesso di creare un alias automatico nel file `.bashrc` o `.zshrc`.

Queste configurazioni verranno salvate in un file JSON allo stesso livello dello script, così non sarà necessario reinserirle ai successivi avvii.

### ⚠️ Importante: Modifica dell'Alias (Virtual Environment)

Se al primo avvio hai fatto impostare l'alias automaticamente allo script, ti conviene **modificarlo subito** nel tuo file di configurazione (`~/.bashrc` o `~/.zshrc`) per assicurarti che attivi l'ambiente virtuale prima di eseguire l'interfaccia.

Ecco un esempio pratico utilizzando **Conda** (puoi fare lo stesso attivando un `venv` normale):

```bash
alias git-check='conda activate git_checker_venv; python3 "/var/home/gianny/Desktop/MY_CODING/GIT_CHECKER/git_checker_tui.py"; conda deactivate'
```

In questo modo, digitando il comando `git-check`, il sistema attiverà l'ambiente corretto, avvierà la TUI e disattiverà l'ambiente non appena l'interfaccia verrà chiusa, mantenendo pulita la sessione del terminale.

## Funzionalità della TUI

- **Ricerca Ricorsiva:** Trova in automatico tutte le sottocartelle che contengono una directory `.git` con cambiamenti (untracked o modified).
- **Selezione Multipla:** Contrassegna una o più repository su cui agire.
- **Commit & Push Veloce:** Inserire un messaggio, selezionare un branch dal menu a tendina e committare i selezionati in un solo colpo.
- **Open Terminal:** Aprire una shell di sistema distaccata direttamente nella root della repository selezionata, senza chiudere o bloccare la TUI.

## TODO
- [ ] Gestire conflitti e merge
- [ ] Implementare la scelta dei file da aggiungere, per ora fa git add .
- [ ] Inserire un box in cui mostrare l stacktrace dei comandi lanciati
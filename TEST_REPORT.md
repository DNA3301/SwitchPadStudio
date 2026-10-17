# SwitchPad Studio 3.0 — verifica del pacchetto

Stato: sorgenti e GUI verificati su Debian 13 / Python 3.13.5; **non** esecuzione hardware su Windows.

## Test positivi

- 16 casi `unittest` passati.
- Conversione e normalizzazione SDL -> Xbox, inversione Y, deadzone radiale e mapping pulsanti.
- Mappatura RAW e JoyCon HIDAPI hints.
- Mock di input SDL + mock driver vgamepad: emulatore XInput pubblica dati, si disattiva e rilascia report.
- Serializzazione, valori invalidi, recovery configurazione JSON corrotta.
- Rendering UI Tkinter delle 3 schede attraverso Xvfb (non è un test del sistema Windows).
- Compilazione bytecode e sintassi Python senza errori.

## Test non eseguibili qui

- Binding SDL Windows sul controller fisico Nintendo (USB e Bluetooth).
- Installazione del driver Windows ViGEmBus.
- Test reali rumble/guide/trigger su hardware Switch.
- Esecuzione nell'effettivo motore input di CONTROL Resonant.
- Compilazione `.exe` con PyInstaller in Windows (lo script esegue il build sul PC dell'utente).

Il programma non è dichiarato hardware-verified fino a conferma dell'utente.

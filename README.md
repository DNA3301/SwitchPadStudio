# SwitchPad Studio 4.0

Un ponte per usare i controller su **Windows 10/11 x64**: legge un pad USB o Bluetooth e lo presenta ai giochi come un **Xbox 360 virtuale (XInput)**. Include test degli input, rimappatura, correzione del drift e profili salvati per modello. Interfaccia in italiano; un controller sorgente alla volta.

**Compatibilità estesa, non una garanzia per ogni pad esistente.** Il controller deve essere leggibile da Windows e SDL2. Protocolli proprietari, driver mancanti, guasti hardware e alcuni modelli recenti richiedono supporto specifico. Le prove software completate sono descritte in [TEST_REPORT.md](TEST_REPORT.md); le famiglie nella tabella non sono tutte collaudate fisicamente.

## Download e avvio

1. Scarica il pacchetto Windows dalla pagina [Releases](https://github.com/DNA3301/SwitchPadStudio/releases), estrailo e avvia `SwitchPadStudio.exe`. Non occorre installare Python. L'eseguibile non è firmato digitalmente.
2. Collega il pad con un cavo dati oppure abbinalo nelle impostazioni Bluetooth di Windows.
3. Se manca **ViGEmBus**, usa il collegamento nella scheda **Diagnostica** alla [release ufficiale 1.22.0](https://github.com/nefarius/ViGEmBus/releases/tag/v1.22.0). Il driver viene installato separatamente, con il consenso dell'utente. Riavvia se richiesto.
4. Lascia **Automatico — primo controller disponibile**, oppure scegli il dispositivo dall'elenco. La modalità automatica preferisce un pad con mappatura SDL e mantiene quello attivo finché rimane collegato.
5. Aspetta **XINPUT ATTIVO**, verifica l'anteprima e apri **Test Windows** (`joy.cpl`). Avvia quindi il gioco e lascia l'app aperta, anche nell'area di notifica.

Se usi i sorgenti, scarica il repository come ZIP, estrailo e fai doppio clic su `AVVIA_SWITCHPAD.cmd`. Il primo avvio prepara Python 3.12 e le librerie in `.venv` e richiede Internet. Il setup ripacchetta vgamepad da un archivio ufficiale verificato tramite SHA256 senza eseguirne lo script driver; non usare un'installazione sorgenti diretta di vgamepad in alternativa. Puoi compilare l'EXE con `COMPILA_EXE_WINDOWS.cmd`.

**ViGEmBus è un progetto ritirato.** Valuta la [dichiarazione ufficiale di fine supporto](https://docs.nefarius.at/projects/ViGEm/End-of-Life/) prima di installarlo. L'app non installa driver in background. Senza il driver, lettura e diagnostica restano utilizzabili; l'uscita Xbox richiede il driver operativo e uno slot XInput libero (massimo quattro slot nel sistema).

## Quali controller può leggere

| Famiglia | Percorso disponibile |
| --- | --- |
| Xbox 360, Xbox One, Xbox Series, pad XInput | Mappatura SDL quando il driver Windows li espone; i pad Xbox fisici non sono esclusi per nome o VID/PID |
| DualShock 4, DualSense e pad compatibili PlayStation | Mappatura SDL quando supportata via USB/Bluetooth; in alternativa profilo RAW |
| Switch Pro, Joy-Con originali | SDL HIDAPI, inclusa combinazione Joy-Con quando disponibile |
| 8BitDo, Logitech, HORI, PowerA e altri | Mappatura SDL se disponibile nella modalità selezionata sul pad, oppure configurazione RAW |
| Pad USB generici / joystick DirectInput | Configurazione RAW di tasti, stick, D-pad e trigger quando SDL espone gli input |
| PS3, Switch 2, dispositivi proprietari o adattatori particolari | Supporto condizionato a driver/protocollo e SDL; nessuna promessa di compatibilità automatica |

Non sono implementati giroscopio, touchpad, adaptive trigger, NFC, macro, conversione tastiera/mouse o riparazione dei driver del pad. La vibrazione dipende dal dispositivo e dal backend SDL. Il sistema operativo deve già riuscire a comunicare con la periferica.

## Se il pad ha tasti o assi sbagliati

Apri **Profili e tasti**. Ogni modello ha un profilo identificato dal GUID SDL; USB e Bluetooth possono avere GUID diversi. Due pad identici condividono le impostazioni del modello, ma puoi scegliere separatamente l'istanza da usare.

- **Rimappatura logica:** scegli per ciascun tasto la destinazione Xbox, oppure `DISABLED`. Funziona sia con SDL sia con RAW. Su PlayStation, la posizione di Croce corrisponde normalmente ad A di Xbox; non servono etichette Nintendo.
- **Drift e direzioni:** regola la deadzone o inverti gli assi. In RAW puoi acquisire il centro lasciando gli stick a riposo e premendo **Calibra centro stick a riposo**. Dopo un cambio degli indici, ripeti la calibrazione.
- **Lettura RAW:** per un pad senza profilo SDL, o con profilo SDL errato, attiva **Usa lettura RAW**. Usa **Rileva** accanto a un comando, poi premi il tasto o muovi un solo asse. Il rilevamento mette temporaneamente in pausa l'uscita. Gli indici sono visibili anche in tempo reale; `-1` disattiva un'associazione.
- **D-pad:** configura un hat, quattro pulsanti, oppure due assi. Per un hat basta rilevare una direzione. Gli assi D-pad considerano X positivo a destra e Y positivo in basso; se necessario puoi scambiare le direzioni con la rimappatura logica.
- **Trigger:** scegli pulsanti digitali, assi `0 → 1`, `-1 → +1`, `+1 → -1`, oppure un asse condiviso. Nell'ultimo caso assegna lo stesso indice a LT e RT: positivo = LT, negativo = RT; l'hardware non permette di distinguere la pressione simultanea.
- Premi **Salva mappatura RAW** per confermare gli indici e abilitare l'uscita. Un profilo RAW nuovo non invia comandi al gioco prima della conferma. Per Switch Pro originale è disponibile un preset da verificare e salvare.
- **Esporta profilo / Importa profilo** permette di condividere una configurazione JSON. L'importazione riguarda il pad selezionato; un profilo RAW importato richiede una nuova conferma.

## Risoluzione dei problemi

**Nessun pad nell'elenco:** controlla prima `joy.cpl`, cavo dati, associazione Bluetooth e driver del produttore. Premi **Rileva**. Se il dispositivo è nascosto con HidHide, autorizza anche l'eseguibile dell'app a leggerlo. Alcune modalità di un pad multipiattaforma producono protocolli diversi: prova la modalità Windows indicata dal produttore.

**Gli input reagiscono ma il gioco non risponde:** verifica **XINPUT ATTIVO** e il dispositivo Xbox in `joy.cpl`. Riavvia il gioco dopo l'attivazione. Controlla gli altri controller collegati e gli slot XInput.

**Comandi doppi o menu instabili:** chiudi altri mapper attivi sullo stesso pad, come BetterJoy o DS4Windows. Se necessario disabilita Steam Input per il singolo gioco. Alcuni giochi leggono sia il pad fisico sia quello virtuale: l'opzione esterna [HidHide](https://docs.nefarius.at/projects/HidHide/Simple-Setup-Guide/) può nascondere il solo pad fisico ai giochi, lasciando questa app autorizzata a leggerlo. Il filtro interno dell'app evita di rileggere l'uscita virtuale, ma non nasconde il pad fisico ai giochi.

**Disconnessione:** l'uscita viene azzerata e rimossa, poi il programma cerca nuovamente il pad. La selezione manuale attende il modello scelto invece di prendere una periferica diversa. Alcuni giochi richiedono un riavvio dopo la riconnessione.

**La finestra non compare:** avvia `AVVIA_CONSOLE.cmd` o consulta `%APPDATA%\SwitchPadStudio\logs\session.log`. La chiusura può ridurre l'app nel tray: usa **Chiudi completamente** dall'icona per terminarla.

## Dati e funzionamento

Impostazioni e log restano in `%APPDATA%\SwitchPadStudio`. La migrazione delle impostazioni 3.x conserva le mappature RAW già salvate. Nessun account o servizio remoto è necessario durante l'utilizzo. Il setup dei sorgenti scarica le dipendenze; i pulsanti dei collegamenti aprono il browser. I report diagnostici vengono esportati solo su richiesta e possono contenere informazioni locali: esaminali prima di condividerli.

L'app usa SDL/pygame per leggere gli input e vgamepad/ViGEmClient per l'uscita. Non modifica la memoria dei giochi e non installa DLL nei giochi. L'obiettivo del ciclo è 120 Hz; non è una garanzia di latenza.

## Sviluppo e verifiche

Python x64 3.10–3.13; build verificata con 3.12.4. Comandi dalla cartella del progetto:

```powershell
python -m unittest discover -s tests -v
python -m compileall -q main.py switchpad tools tests
powershell.exe -NoProfile -ExecutionPolicy Bypass -File setup_windows.ps1 -BuildExe -NoLaunch
.\SwitchPadStudio.exe --verify-install .\build\exe-verification.json
```

Il test `--verify-install` apre in memoria le tre schede, verifica SDL e il bridge di identità senza creare un output Xbox e senza salvare impostazioni. I test unitari non richiedono un pad o ViGEmBus. `python tools/windows_smoke.py` è una verifica **facoltativa** su Windows con driver già installato: crea un output temporaneo senza pressioni di tasti, ne verifica lo stato neutro e il filtro anti-feedback, poi lo rimuove. Non equivale a una prova con un controller fisico.

Le dipendenze mantengono le rispettive licenze: [third_party/README.md](third_party/README.md). I sorgenti di questa applicazione permettono di ricompilare il pacchetto con librerie LGPL modificate; è consentita l'analisi necessaria a verificare tali modifiche, nei termini delle licenze delle librerie.

Riferimenti tecnici: [pygame Controller](https://www.pygame.org/docs/ref/sdl2_controller.html), [SDL Joystick](https://wiki.libsdl.org/SDL2/CategoryJoystick), [vgamepad](https://github.com/yannbouteiller/vgamepad), [ViGEmClient](https://github.com/nefarius/ViGEmClient).

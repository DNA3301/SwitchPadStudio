# SWITCHPAD STUDIO 3.0 — Controller Nintendo Switch -> Xbox per Windows

**Una vera applicazione desktop con interfaccia grafica.** Legge il controller Switch, converte in tempo reale pulsanti e assi e pubblica un *Xbox 360 controller virtuale* (XInput) sul PC. Rimane attiva in background durante il gioco, anche dopo aver chiuso la finestra nell'area di notifica.

Questa versione **sostituisce SwitchPadHelper 2.0**, che eseguiva soltanto diagnostica / apertura di software esterni. Non serve più utilizzare BetterJoy come motore di traduzione: SDL/pygame legge il pad; vgamepad/ViGEmBus emula Xbox.

## LA VIA PIÙ SEMPLICE (Windows 10/11, 64 bit)

1. **Chiudi CONTROL Resonant** (e BetterJoy, DS4Windows o altri mapper se li stai usando sullo stesso pad).
2. Estrai **tutto** lo ZIP in una cartella, ad esempio `C:\SwitchPadStudio`.
3. Collega e abbina il pad Switch tramite Bluetooth, oppure con un cavo USB per **dati**. Per i Joy-Con, abbina entrambi i controller.
4. Fai doppio clic su **`AVVIA_SWITCHPAD.cmd`**. Alla prima esecuzione il programma prepara automaticamente Python e le dipendenze con pip (richiede Internet); non occorre compilare né scrivere codice.
5. **Una volta soltanto:** se l'app mostra `Driver ViGEmBus mancante/non operativo`, installa il driver **dalla release ufficiale**: <https://github.com/nefarius/ViGEmBus/releases/tag/v1.22.0>. Esegui l'installer appropriato, accetta l'avviso UAC e riavvia Windows se richiesto. L'app **non** installa driver in background, per scelta di sicurezza. Questo driver è dismesso; leggi le avvertenze in fondo.
6. Riapri `AVVIA_SWITCHPAD.cmd`. Seleziona **Automatico — primo controller Switch**; l'emulazione parte da sola. Aspetta l'indicazione **XINPUT ATTIVO** (verde).
7. Premi **Test Windows** (`joy.cpl`): deve esserci anche un controller Xbox 360 virtuale. Controlla i pulsanti e gli stick nell'interfaccia dell'app.
8. **Solo ora apri CONTROL Resonant.** Lascia l'app attiva (puoi ridurla a icona nel tray). Se il gioco è lanciato da Steam ed esegue già la conversione, prova a *disabilitare Steam Input per questo gioco* per evitare due traduttori concorrenti.

**Dall'esecuzione successiva basta fare doppio clic su `AVVIA_SWITCHPAD.cmd`**. Se hai compilato l'eseguibile, puoi invece aprire direttamente `SwitchPadStudio.exe`.

### Come creare un unico vero `.exe` Windows

Fai doppio clic su **`COMPILA_EXE_WINDOWS.cmd`**. Lo script prepara un ambiente isolato, scarica PyInstaller e compila l'app **sul tuo PC Windows** in `SwitchPadStudio.exe`. Il file creato si può lanciare direttamente, senza Python installato. Con l'EXE è disponibile anche la funzione *Avvia con Windows* nella scheda Diagnostica.

**Nota:** questo archivio **non contiene un EXE precompilato**: l'ambiente usato per generare il pacchetto era Linux, senza SDK/build Windows e senza accesso Internet per scaricare il runtime Windows. Non sarebbe corretto spacciarti per collaudato un file che non è stato compilato ed eseguito su Windows. Il compilatore Windows è incluso e automatizzato; necessita di Internet la prima volta.

### Che cosa fa realmente

- **Input fisico:** `pygame._sdl2.controller` (SDL2 / HIDAPI), con modalità RAW configurabile per controller non riconosciuti come GameController.
- **Xbox virtuale:** `vgamepad.VX360Gamepad` tramite driver Windows **ViGEmBus**. Il controller virtuale rimane collegato mentre il motore è attivo e viene scollegato all'uscita.
- **Aggiornamenti:** ciclo di lettura/invio a 120 Hz (obiettivo; l'effettiva frequenza dipende dal sistema).
- **Hotplug:** ricerca periodica e riconnessione automatica dopo perdita/ritorno del pad. Mantiene la selezione del modello quando possibile.
- **Sicurezza:** nessuna modifica alla memoria del gioco, nessuna iniezione di DLL nel gioco, nessun driver nascosto e nessun input sintetico da tastiera. In caso di disconnessione azzera/rimuove il gamepad virtuale.
- **Configurazione:** deadzone radiale degli stick, layout ABXY in modalità Xbox/per posizione oppure Nintendo/per lettera, inversione assi, vibrazione dove supportata, mapping RAW personalizzato, avvio automatico Windows con EXE, icona tray.
- **Diagnostica:** indicatori stick/pulsanti/trigger in tempo reale, informazioni SDL, rilevazione slot XInput, controllo driver dal registro (solo indicativo), export report e log.
- **Dati:** impostazioni e log in `%APPDATA%\SwitchPadStudio\`.

## Pad supportati e limiti

**Switch Pro Controller originale (prima generazione):** SDL2 supporta controller Switch via USB o Bluetooth sulle configurazioni compatibili. È l'obiettivo principale dell'app.

**Joy-Con originali (L + R):** SDL2 include l'opzione HIDAPI di combinazione automatica come unico pad, impostata a `1`. L'effettiva disponibilità dipende da versione, firmware e modalità di collegamento; l'app non implementa un proprio protocollo Bluetooth.

**Controller di terze parti (PowerA, 8BitDo, HORI, altri):** quando SDL offre un profilo GameController possono funzionare normalmente. Se SDL riconosce solo un joystick RAW puoi selezionarlo manualmente, leggere gli indici dei tasti nella scheda *Profili e tasti* e modificarne la mappatura. Per i trigger RAW puoi scegliere *Assi* o *Pulsanti*. Non si promette compatibilità per ogni clone/firmware.

**Nintendo Switch 2 Pro / Joy-Con 2:** questa versione **non garantisce** supporto. L'accesso Bluetooth e l'inizializzazione HID Switch 2 richiedono implementazioni specifiche che SDL2/pygame 2.6.1 può non includere. Il pad eventualmente visibile fra i dispositivi RAW non è una conferma che i suoi report siano leggibili o correttamente interpretabili.

**Non implementati:** motion aiming/giroscopio, NFC, cattura, calibrazione IMU, riconoscimento batteria universale, mappature per ogni clone, combinazione proprietaria Joy-Con 2. L'HD rumble Switch non è equivalente alla normale vibrazione XInput; eventuale rumble supporta solo le funzioni consentite dal backend SDL.

## Risoluzione problemi specifici di CONTROL Resonant

**Windows vede il controller ma XINPUT non si accende:** leggi l'errore nell'app e vai in Diagnostica. Se manca ViGEmBus, installalo **solo dalla release ufficiale** e riavvia se necessario. Chiudi BetterJoy/DS4Windows per escludere conflitti. In `joy.cpl`, un pad Switch visibile non equivale a un Xbox virtuale funzionante.

**XINPUT ATTIVO ma il gioco non risponde:** *chiudi interamente il gioco*, assicurati che il virtuale sia già attivo in `joy.cpl`, poi riavvialo. Il gioco può enumerare i controller solo all'avvio; negli utenti con altri pad collegati gli slot XInput non sono necessariamente attribuibili in modo univoco. Verifica anche la modalità controller in gioco e Steam Input.

**Tasti doppi o menu che impazziscono:** disattiva Steam Input **per il singolo gioco** quando usi questo mapper, e non tenere aperti altri mapper per lo stesso pad. Se il titolo continua a leggere il pad fisico insieme al virtuale, usa facoltativamente **HidHide** (driver di terzi), configurandolo per nascondere **solo il pad fisico** ai giochi e autorizzare `SwitchPadStudio.exe` a leggere quel pad. Non nascondere il dispositivo virtuale; non manipolare le periferiche globali alla cieca. Guida ufficiale: <https://docs.nefarius.at/projects/HidHide/Simple-Setup-Guide/>.

**Gli stick reagiscono nell'app ma sembrano strani:** cambia *Deadzone* o *Inverti assi*. Con un clone RAW usa gli indici hardware mostrati in fondo alla scheda Profili. I trigger Switch Pro sono digitali, vengono convertiti in 0% / 100% dell'input Xbox.

**Il pad scompare dopo la sospensione/Bluetooth:** ricollegalo e aspetta la ricerca; se il gioco lo ignora nonostante la riconnessione, riavvia il gioco dopo aver ristabilito la connessione XInput.

**L'app non apre la GUI:** esegui il file `AVVIA_CONSOLE.cmd` e leggi l'errore, oppure invia `%APPDATA%\SwitchPadStudio\logs\session.log`.

## Sicurezza del driver legacy

ViGEmBus è **ritirato dal 2023** e non riceve più aggiornamenti. La release ufficiale `v1.22.0` ha rimosso l'auto-updater; alcune vecchie installazioni con updater legacy hanno un potenziale rischio legato ai domini scaduti. Leggi la dichiarazione originale: <https://docs.nefarius.at/projects/ViGEm/End-of-Life/>. Il nostro programma **non** forza il download/avvio di alcun pacchetto driver e non cambia la configurazione di sistema in modo silenzioso. Puoi decidere di non installarlo; in questo caso puoi comunque vedere la diagnostica del pad ma **l'emulazione Xbox non funzionerà**.

## Stato di verifica

- **16 test automatizzati superati** (conversione tasti e assi, deadzone, emulatore fittizio, on/off, impostazioni).
- **Prova grafica completata** con Tkinter su display virtuale Linux (pannello, profili, diagnostica).
- **Verifica sintattica Python completata.**
- **NON collaudato su Windows fisico**: driver ViGEmBus, pacchettizzazione con PyInstaller, lettura reale Switch via USB/Bluetooth e ingresso dentro CONTROL Resonant devono essere verificati sul PC dell'utente. Non è possibile garantire che funzioni senza quella verifica.

## File

- `AVVIA_SWITCHPAD.cmd` — avvia l'app, effettuando il setup automatico solo al primo utilizzo.
- `INSTALLA_E_AVVIA.cmd` — forza la reinstallazione/aggiornamento dipendenze.
- `COMPILA_EXE_WINDOWS.cmd` — crea `SwitchPadStudio.exe` sul PC Windows.
- `AVVIA_CONSOLE.cmd` — diagnostica errori di avvio.
- `main.py`, `switchpad/*.py` — codice completo dell'app.
- `requirements.txt`, `requirements-build.txt` — dipendenze dichiarate.
- `assets/switchpad.ico` — icona applicazione.
- `tests/*.py` — verifiche riproducibili con `python -m unittest discover -s tests -v`.

Fonti tecniche primarie:
- <https://www.pygame.org/docs/ref/sdl2_controller.html>
- <https://wiki.libsdl.org/SDL2/SDL_HINT_JOYSTICK_HIDAPI_COMBINE_JOY_CONS>
- <https://github.com/yannbouteiller/vgamepad>
- <https://github.com/nefarius/ViGEmBus/releases/tag/v1.22.0>
- <https://docs.nefarius.at/projects/ViGEm/End-of-Life/>
- <https://store.steampowered.com/app/3669870/CONTROL_Resonant/>

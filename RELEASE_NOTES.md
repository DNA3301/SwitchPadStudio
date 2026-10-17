# SwitchPad Studio 4.0.0-beta.1

Anteprima pubblica per Windows 10/11 x64 con compatibilità controller estesa.

- Selezione automatica per qualsiasi famiglia esposta da SDL; distinzione fra Xbox fisico e uscita virtuale.
- Profili per modello, importazione/esportazione JSON, rimappatura logica e lettura RAW forzabile.
- Rilevamento guidato di tasti/assi, calibrazione del centro stick, D-pad con hat, pulsanti o assi.
- Trigger digitali, assi con diverse polarità e trigger su asse condiviso.
- Rilascio degli input alla disconnessione e ripristino del pad selezionato alla riconnessione.
- Inizializzazione verificata dell'uscita neutra e filtro anti-feedback tramite identità SDL/PnP/XInput.
- Setup da sorgenti che verifica l'archivio originale vgamepad e non ne esegue l'installer driver obsoleto.
- EXE Windows senza Python da installare, con sorgenti e avvisi delle dipendenze nel pacchetto.

Verificati 64 test automatici su Windows, le tre schede dell'interfaccia, il pacchetto EXE, la creazione dell'output Xbox con il driver già installato e il filtro anti-feedback reale. Non erano collegati controller fisici: USB/Bluetooth, vibrazione e funzionamento nei singoli giochi richiedono ancora prove per modello. Non è una promessa di supporto a ogni pad esistente. ViGEmBus è un progetto ritirato ed è installato separatamente dall'utente.

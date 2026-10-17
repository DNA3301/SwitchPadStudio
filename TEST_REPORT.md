# SwitchPad Studio 4.0.0-beta.1 — verifica Windows

Data: 17 ottobre 2026. Sistema locale Windows 11 x64 (build 26300); Python 3.12.4, pygame 2.6.1 / SDL 2.28.4, vgamepad 0.1.0, PyInstaller 6.22.3.

## Esiti completati

- **64 test automatici PASS**, incluse le tre schede Tk reali con motore simulato, profili separati, salvataggio RAW atomico, migrazione 3.x, rimappatura, calibrazione del centro, diverse convenzioni dei trigger e D-pad.
- Selezione di famiglie Nintendo, PlayStation, Xbox e generiche mediante fixture; selezione manuale di pad identici, riconnessione con nuovo instance ID e rilascio degli input alla rimozione.
- Errore driver senza perdita della diagnostica e recupero dopo errore di lettura del pad simulato.
- Setup vgamepad: archivio ufficiale verificato tramite SHA256; runtime ripacchettato senza eseguire setup.py o distribuire MSI. Test di rifiuto archivio alterato, esclusione dei percorsi non consentiti e integrità dei file runtime.
- **Driver reale già installato:** creazione e rimozione dell'Xbox virtuale, query dello slot XInput nativo, uscita neutra verificata, riconoscimento del servizio ViGEmBus negli antenati PnP ed esclusione effettiva del virtuale dall'elenco ingressi. Riprodotto e corretto lo stato iniziale fuori centro del driver.
- **EXE Windows compilato e avviato:** verifica incorporata PASS di GUI (3 schede), SDL, DLL del bridge di identità, assenza di errori ed emulazione disattivata durante la verifica. Non salva impostazioni utente.
- Ispezione visiva locale della home, del pannello profili e della parte RAW scorrevole.
- Compilazione bytecode e controllo diff/whitespace. Nessun driver installato o aggiornato durante queste verifiche.

Il controllo driver reale è eseguito sui sorgenti; la verifica del pacchetto EXE avviene con uscita disattivata. Non è una prova di un gioco o di un pad fisico. Il workflow GitHub esegue test, compilazione EXE e controllo GUI/SDL; non installa ViGEmBus e non certifica hardware.

## Artefatto locale

`SwitchPadStudio.exe`, SHA256:

`b4852b06ce0cf8920e74d6d5446d3fd640697ad67f9d493093fb20e2f33627d7`

I checksum di ZIP Windows, sorgenti e EXE accompagnano la release. Il pacchetto contiene sorgenti ricompilabili e licenze delle dipendenze, senza log, impostazioni personali, ambienti Python o installer driver.

## Verifiche ancora aperte

- Controller fisici di ogni famiglia: firmware, USB/Bluetooth, vibrazione, trigger, combinazione Joy-Con e adattatori specifici.
- Ingresso nei singoli giochi, doppio input e configurazioni Steam Input/HidHide.
- Prova su una macchina Windows 10 pulita e su Windows 11 senza driver preinstallato. Il percorso di setup privo di driver viene verificato anche dal workflow su runner Windows.
- Firma digitale dell'eseguibile e compatibilità con protocolli proprietari recenti, inclusi dispositivi Switch 2.

## Riproduzione e rollback

Dalla cartella del progetto: `python -m unittest discover -s tests -v`; `python -m compileall -q main.py switchpad tools tests`; setup Windows con `-BuildExe -NoLaunch`; `SwitchPadStudio.exe --verify-install build/verification.json`; facoltativamente `python tools/windows_smoke.py` con ViGEmBus già installato.

Il commit iniziale `0154a2b` conserva i sorgenti originali 3.0. Per tornare alla versione precedente, usa una cartella separata e una copia delle impostazioni 3.x; non sovrascrivere impostazioni correnti senza backup. Nessuna prova software qui elencata implica compatibilità universale certificata.

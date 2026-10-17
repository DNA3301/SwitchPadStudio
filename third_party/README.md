# Componenti di terze parti

Il codice delle librerie non è modificato. Le licenze originali sono conservate in `licenses/` e accompagnano il pacchetto Windows. Il programma non contiene driver ViGEmBus o installer MSI; contiene il client utente ViGEmClient usato da vgamepad.

`tools/safe_vgamepad.py` ripacchetta esclusivamente i file runtime originali per Windows x64, senza eseguire `setup.py`, che nella distribuzione originale può avviare un installer driver obsoleto. Vengono esclusi gli MSI; viene ricreata solo la metadata della wheel. L'archivio PyPI 0.1.0 è verificato contro SHA256 `57f6bd01aec0c172947517fb782d150ef9b285f7f4d524c317374fa5c24a89de`. Il setup richiede wheel binarie per le altre dipendenze e non ripiega su script di installazione sorgenti.

| Componente | Versione della build locale | Licenza e sorgenti |
| --- | --- | --- |
| CPython e libreria standard | 3.12.4 | PSF e avvisi inclusi; [sorgenti](https://www.python.org/downloads/release/python-3124/) |
| pygame | 2.6.1 | LGPL 2.1 o successiva; [sorgenti](https://github.com/pygame/pygame/tree/2.6.1) |
| SDL2 | 2.28.4, dalla wheel pygame | zlib; [sorgenti](https://github.com/libsdl-org/SDL/tree/release-2.28.4) |
| vgamepad | 0.1.0 | MIT; [sorgenti](https://github.com/yannbouteiller/vgamepad/tree/v0.1.0) |
| ViGEmClient | DLL distribuita con vgamepad 0.1.0 | MIT; [sorgenti](https://github.com/nefarius/ViGEmClient) |
| pystray | 0.19.5 | LGPLv3; [sorgenti](https://github.com/moses-palmer/pystray/tree/v0.19.5) |
| Pillow e relative librerie incorporate | 12.3.0 | MIT-CMU e avvisi aggiuntivi nel file completo; [sorgenti](https://github.com/python-pillow/Pillow/tree/12.3.0) |
| six | 1.17.0 | MIT; [sorgenti](https://github.com/benjaminp/six/tree/1.17.0) |
| Tcl / Tk | 8.6.13 | BSD; [Tcl](https://github.com/tcltk/tcl/tree/core-8-6-13), [Tk](https://github.com/tcltk/tk/tree/core-8-6-13) |
| OpenSSL | 3.0.13, dal runtime Python | Apache 2.0; [sorgenti](https://github.com/openssl/openssl/tree/openssl-3.0.13) |
| PyInstaller bootloader | 6.22.3 | GPL con eccezione per il bootloader; [sorgenti](https://github.com/pyinstaller/pyinstaller/tree/v6.22.3) |

Il build hook di pygame include soltanto SDL2, escludendo i moduli audio, MIDI, font e codec immagine non necessari. Il runtime Python può includere zlib, libffi e il runtime Microsoft Visual C++; gli avvisi pertinenti sono nei file Python/Pillow e nel file del runtime Microsoft.

Per sostituire una libreria LGPL, prepara un ambiente Python, installa la versione modificata e ricompila usando il comando PyInstaller in `setup_windows.ps1`, saltando la reinstallazione delle dipendenze fissate in `requirements.txt`. I sorgenti dell'app e lo script di build sono inclusi nel repository. Le licenze delle dipendenze regolano i diritti su tali componenti; questo elenco non trasferisce la titolarità dell'app.

# Extension review evidence

`blinker-extension-comments.json` is the actual portable annotation exported through the installed Pocket KiView Chrome extension, not a hand-written substitute. Import the KERO folder through Local files, open `KERO.kicad_sch`, then use Comments → Import and export → Import. The note uses a local-workspace identity; it has not been rebound to a GitHub revision.

Executed on 2026-11-07:

- Imported the local folder: 126 previewable files; 642 other files listed without preview.
- Opened the wired blinker schematic and saved one drawing-level Issue / Info / Open annotation.
- Verified Issues (1) and “Annotation saved in the configured review store”.
- Exported the 1,145-byte JSON and preserved its exact downloaded bytes here.
- Entered and verified a [response directly on GitHub](https://github.com/wayri/KERO/issues/13#issuecomment-6709805248).

Additional verified UI interactions: the saved PCB rendered in 2D and 3D, the assembly BoM displayed 12 groups, and the VBAT-high PI companion opened with six plots, four tables and 2,652 properties. Its potential field and PCB overlay were visibly rendered, with “Source PCB verified by SHA-256”. The 3D view reported 14 linked models across 18 board objects and disclosed unsupported pad-shape omissions. Pointer probing and the thermal GUI remain unverified.

Repository discovery reported failure and the extension toolbar reported GitHub signed out. No extension-backed GitHub publication, PR compare gesture, cross-probe or thermal GUI interaction is claimed by this receipt. Those tasks remain tracked in [issue #13](https://github.com/wayri/KERO/issues/13). API/parser analysis checks are documented separately under `evidence/analysis/`.

The imported root design is the validated blinker. Its saved analysis must not be presented as evidence for the new encoder PCB.

================================================================================
           CELES ARCHIVAL PRESERVATION PACKET - VERSION 1.0
================================================================================

DATE OF CREATION: 2026
FORMAT PURPOSE:  Long-term document sovereignty and digital longevity.
LICENSE:         Server-Lab Open-Control License (SOCL) 1.0 (See LICENSE.txt)
OFFICIAL SITE:   https://celes.is-best.net/

--------------------------------------------------------------------------------
1. MISSION STATEMENT
--------------------------------------------------------------------------------
Celes was built to solve the "Digital Dark Age." Most modern document formats 
rely on complex, ever-changing browser engines (HTML/JS) or opaque binaries 
(PDF). Celes is a "hardened" markup language designed so that the story 
survives even if the software dies.

--------------------------------------------------------------------------------
2. THREE WAYS TO VIEW CELES DOCUMENTS
--------------------------------------------------------------------------------

METHOD A: THE HUMAN WAY (Emergency / Universal)
   Open any .celes file in the simplest text editor available (Notepad, Vim, 
   etc.). The content is stored in raw UTF-8 plain text. Even without a 
   renderer, a human can read the narrative and structure between the tags.
   *RECOOMENDED FOR: Absolute long-term recovery.*

METHOD B: THE PYTHON TOOLKIT (Archival / Technical)
   The reference implementation is written in pure Python for maximum logic 
   readability.
   - SCRIPT: Run 'celes_renderer.py' to parse the file.
   - EXE: For modern systems, a compiled executable is provided for 
     "plug-and-play" viewing without needing a Python environment.
   - INSTALL: `pip install celes-lang`
   *RECOMMENDED FOR: Distributing with archives and data-hoards.*

METHOD C: THE BROWSER EXTENSION (Everyday / Productivity)
   For modern web-based workflows, use the Celes Browser Extension. It 
   provides syntax highlighting and live previews within your browser.
   *RECOMMENDED FOR: Daily creation and reading.*

--------------------------------------------------------------------------------
3. FILE STRUCTURE & PORTABILITY
--------------------------------------------------------------------------------
To ensure 50-year accessibility, this archive follows a strict structure:

- /README.txt          : This instruction manual.
- /LICENSE.txt         : Rights to use, modify, and redistribute the software.
- /spec.txt            : The plain-text specification of the Celes language.
- /celes_renderer.py   : The source code (the "DNA") of the renderer.
- /celes_view.exe      : The compiled viewer for immediate use.
- /documents/          : Where the .celes narrative files are stored.
- /assets/             : Local sub-folder for media (images/audio/video).

Celes forbids external "Cloud" dependencies. Every asset must be local.

--------------------------------------------------------------------------------
4. THE "GRACEFUL DECAY" PRINCIPLE
--------------------------------------------------------------------------------
If you find that the /assets/ folder is missing or the media formats (like 
.jpg or .mp4) are no longer supported by your era's technology, the document 
will still render the text content perfectly. 

The information is the priority; the media is a transient enhancement. 
Nothing in Celes is "silently ignored"—the renderer will tell you exactly 
what is missing without breaking the rest of the file.

--------------------------------------------------------------------------------
5. LEGAL & REDISTRIBUTION
--------------------------------------------------------------------------------
Under the SOCL 1.0 license, you have the right to study, modify, and 
redistribute this software. You are encouraged to bundle the renderer 
(.py and .exe) directly with your data archives to ensure they stay paired 
for future generations.

"The story survives the software."
--------------------------------------------------------------------------------
Original Author: Sourasish Das
Project Repository: https://celes.is-best.net/
================================================================================
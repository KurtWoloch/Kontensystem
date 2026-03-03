## Answers to Open Questions

1. Should this be a rewrite of the C# tool, the Window Logger, or a new unified application?

I think it could be either a rewrite of the C# tool or a new unified application.
It should not be a rewrite of the Window Logger or the Checklisten programs, which both have been coded in VB5, which is outdated by now.
So some logic of the Window Logger and Checklisten programs could be preserved (and combined with that of the C# program), but taken to a new level.
For the C# program, there's also that old version which I hand-wrote, which had all the tasks hardcoded in it, but also supported some additional functions,
like loading in part of a Windowlog file and distill it (which would have made the retrocactive creation of parts of the Ablauf files easier),
but this functionality, sadly, got deleted by the AI while moving to the new architecture which reads the CSV files.
When analyzing the C# program, you may have noticed that on the form there are buttons for "Laden" (two of them), "Speichern" and "Tagessummen" which are now non-functional,
but the old code module may contain routines designed to service them. That code module is here:
C:\Users\kurt_\Betrieb\Kontenverwaltung\Tagesplanung_AI\Tagesplanung\Tagesplanung\Tagesplanung_Global_Old.cs
That's not to say that these routines have to be re-instated, but they may give insight on what things were once planned or half-heartedly implemented.
Also useful for that purpose may be old versions of the form files backed up in the following locations, all of which predate the RooCode based rewrite, having been stored on December 11th, 2024:
C:\Users\kurt_\Betrieb\Kontenverwaltung\FrmTagesplanung.Designer.cs.txt
C:\Users\kurt_\Betrieb\Kontenverwaltung\FrmTagesplanung.cs.txt
C:\Users\kurt_\Betrieb\Kontenverwaltung\Program.cs.txt
C:\Users\kurt_\Betrieb\Kontenverwaltung\Feiertag.cs.txt
C:\Users\kurt_\Betrieb\Kontenverwaltung\Tagesplanung_Global.cs.txt
"C:\Users\kurt_\Betrieb\Papa\Aufgaben zu Papa's Pflege ab 6.12.2022.txt" (contains many tasks I did for my father prior to and after his death, and a list of things yet to do)

2. GUI: Always-visible small widget (like Checklisten's one-item-at-a-time), system tray, or full window?

I'd say a mixture of that... I'd like a window which isn't full screen, so you can put it beside other windows if needed... similar to Checklisten, Tagesplanung or Window Logger as they start up.

3. How to handle the transition period — can it read existing CSV and gradually learn mappings?

Well, I think I'd like to start with compiling a "task master list" and then add things already in place for mapping them:
- The "Window Logger" code has many mappings in place to map existing window data to activities
- In addition to that, the python script "C:\Users\kurt_\.openclaw\workspace\kontensystem\windowlog_corrector.py" has additional mappings, trying to fill in some blanks left by Window Logger.
Some of those mapping may only work with looking ahead, but some may be translatable to additional mappings from window log into activities.
- The "Window Logger" code also fills the combo boxes with activities that can be selected.
- The existing Windowlog files probably contain some additional activities that have been entered into Window Logger directly (whose combo boxes all support free data entry).
- The Ablauf files contain many more activities that have been logged although they haven't been planned and don't appear in the CSV file.
- The existing YAML exception file might contain some additional activities not present in the regular CSV file
- The code file mentioned at question 1. may contain additional activities which have since been dropped from the CSV file
- The accounting system table "Aufwandserfassung" (in "Kontensystem 2021.mdb") might contain several more activities, or broader definitions encompassing more activity types
- The accounting system table "Tab_Aktionen", similarly, may contain additional activities which have been derived from the activities in "Aufwanderfassung".
- The accounting system table "Tab_Gewinnaktionen" may contain additional activities which were designed to be used when the Checklisten program showed "further activities according to priority list".
- The accounting system table "Tab_Wuensche" contains additional tasks (or ideas) which have been proposed and are subject for review. Most of them are outdated by now, but should at least be reviewed.
- Additional potential tasks are defined in the following files:
C:\Users\kurt_\Betrieb\Kontenverwaltung\Taskliste.txt
C:\Users\kurt_\Betrieb\Kontenverwaltung\Checklisten_Winlogger\KURTDOKU.txt (containing some additional checklists which weren't accounted for in the C# planning tool and its CSV file, like the list for doctor visits)
Since part of those are long lists (Windowlog files or KURTDOKU.txt) or hundreds of files (Ablauf files), it may be advisible to write Python scripts to parse those files for extracting the tasks,
and to have a sub-agent write those Python scripts, if applicable, after analyzing the structure of the respective file or database table.

Other data relevant for the task list:
- The accounting system table "Tab_Konten" contains a list of the currently valid accounts (in the accounting system for 2021).
Accounts are subject to change from year to year according to needs, for instance, up to 2018 there was an account "Eltern" and several accounts for relatives which in 2019 were re-structured to "Papa" and "Verwandte".

The master task list should have the following for each task, but not all fields 
- The task name
- The 6-character task code... not all of them have one, but some do, and for many at least the first 2 letters can be inferred
- A parent task if applicable (for instance, the morning routine task "Morgent.+Frst." as used in the Aufwandserfassung table is further broken up in the individual steps of the morning routine, varying by weekday)
- Priority setting
- Setting for a fixed time when the task is always supposed to start (can be redefined in the CSV file though)
- Reference to a document and page inside that document where this task is defined in detail - since the documents have long file names, they could be given a shorter number or code referencing an extra list
- Some kind of status info telling whether this is a currently executed task, if it's a draft, if it needs review, if it isn't properly documented yet, if the documentation is outdated etc.
It should be clearly defined how this status is expressed in the respective data field.

In addition to that (but that doesn't initially have to be in place) there is supposed to be a list of documentations where the tasks are being described.
The first documentation is the original document for "KURTDOKU.txt" which is a Word document. A more recent version of that is available at "I:\Daten\Lebenserhaltung\Lebensdokumentation 8.9.27.doc" (I is an external hard drive which only spins up on demand and may take a while to spin up)
All tasks appearing in KURTDOKU.txt are defined to be documented in that first documentation. For others, there are other documentations which will be added by and by, or they are still undocumented.

4. Should the accounting export format match the current Access DB structure exactly?

I'm not sure about that. There should be some kind of transition. Currently there's a huge backlog with the accounting system... the final calculations are due since July 2021, and the "Aufwanderfassung" is still stalled at January 23rd, 2023.
Given this backlog, however, the format of accounting system databases after 2023 (from 2024 on) may change, but they still should be able to take in the old Windowlog files, maybe after those have been converted in some way.
2026 would be another transition year since Windowlog, Planung and Ablauf files still exist until now (March 3rd, 2026), so compatibility should be maintained with those.
But in principle, one of the items on my to-do list actually was "converting the accounting system database to a task list", though I never in detail made plans how exactly to do this.

5. What about the YAML exceptions — are they still needed, or does the reactive model handle deviations naturally?

If there's an easy way to set them, I would like to be able to keep those or a similar system to define exceptions rather than changing each day's plan manually to accommodate for them.
They just have to defined and integrated better, for instance if there's information about an upcoming task "Besuch Augenarzt", the system should integrate the items from the "Arztbesuch" checklist there and schedule other items around that to make space for it.
The YAML exceptions just have been cumbersome in that for a single date, I had to think myself how this would affect other schedule items around it and add lines to the YAML file manually to accomodate those, always trying not to break the YAML syntax.
RooCode couldn't handle a task given to it with simply the information "I have this doctor visit at that date, please plan for it", but OpenClaw might be able to do this,
especially after it once gets defined how to handle a certain type of dates.
Current "special" upcoming dates are:
19.3.2026 14:30-16:00: CoP Operations Management (should be integrated in work day, but causes teleworking to at least last until 16:00 on that day)
8.4.2026 10:00-11:00: Mundhygiene (Dr. Salbrechter, Donaufelder Str.), causing me to brush my teeth before leaving, leave home early, then attend the work meeting "BKDD Standup Meeting" from that remote location from 11:00 to 11:15, then riding to the BRZ.
15.4.2026 9:00-10:00: Besuch Augenarzt (Dr. Graziadei, Brünner Str. / Frauenstiftg.), which would be a stop on the way to BRZ, causing me to leave home early (8:50 at the latest) but pack for BRZ before it, riding to BRZ after the visit

6. Phone/away-from-PC: manual selection only, or integrate with calendar/location?

Well, I never even thought it would be possible to integrate with calendar/location! In fact up until now all the planning and accounting system work only has been done on my home PC.
In some instances (for instance, on doing the quarterly "Friedhofstour") the "Ablauf" file has been transferred to my laptop, and I continued to edit it there while doing the tour.
Calendar could be integrated though if it can be accessed. The calendar is currently work-related though, with the primary phone being my company iPhone which contains all the work-related and also private dates (which are rare as seen above).
Location tracking... I would have to think about this. Most of the time I'm either at home, at the BRZ or on the way to there or home, or I'm talking a walk near home. It only rarely happens that I ride somewhere else.

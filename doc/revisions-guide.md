# Script Revisions: A Guide

This guide explains what script revisions are, where they fit in the life of a screenplay, and how to manage them in Trelby. It ends with a full walkthrough of a revision cycle on a made-up film.

## Contents

1. [What revisions are](#what-revisions-are)
2. [When revisions happen](#when-revisions-happen)
3. [The parts of the system](#the-parts-of-the-system)
4. [Walkthrough: two rounds of revisions on *Night Freight*](#walkthrough-two-rounds-of-revisions-on-night-freight)
5. [Reference: revision features in Trelby](#reference-revision-features-in-trelby)
6. [Tips and common mistakes](#tips-and-common-mistakes)
7. [Glossary](#glossary)

---

## What revisions are

While you're writing, every new version of a script is just a new **draft**. You rewrite freely, page numbers shift, scenes get renumbered, and you hand over a fresh copy each time. Nobody minds, because nobody depends on page 47 being page 47.

That changes once the script goes into **production**. Dozens of people work from the same script, and each of them builds their work on its page and scene numbers:

- The **assistant director** builds the shooting schedule from scene numbers ("Day 3: scenes 14, 15, 22").
- The **script supervisor** logs every take against a scene and page.
- **Departments** (props, wardrobe, locations, camera) mark up their copies with notes, breakdowns and budgets.
- **Actors** learn their lines from specific pages.

If you handed these people a freshly repaginated script after every change, every schedule, breakdown and marked-up copy would break. So production scripts are changed through **revisions**: a controlled way to change the script that

1. **keeps the page and scene numbers stable**, so existing paperwork stays valid;
2. **shows exactly what changed**, with a mark in the margin of each changed line;
3. **sends out only the changed pages**, printed on colored paper, which people swap into their existing copies.

Each round of changes is called a **revision**, and it's named after the color of paper its pages are printed on.

### The colors

The industry uses a standard order of colors (based on WGA practice):

| Revision | Color |
|---|---|
| Original production draft | White |
| 1st revision | Blue |
| 2nd revision | Pink |
| 3rd revision | Yellow |
| 4th revision | Green |
| 5th revision | Goldenrod |
| 6th revision | Buff |
| 7th revision | Salmon |
| 8th revision | Cherry |
| 9th revision | Double White |
| 10th revision | Double Blue |
| … | … |

After Cherry the cycle starts again with "Double" colors, then "Triple". Some productions change the order or skip colors, so always follow the production office's list if it has one.

The color does two jobs. On a desk it shows at a glance which pages are newest. In the page header (for example, `Pink Rev. 10/17/26`) it tells everyone which revision a page belongs to, even when it's printed in black and white.

---

## When revisions happen

A screenplay roughly goes through these stages:

```
 Writing drafts ──► Production draft ("White") ──► Revisions (Blue, Pink, ...) ──► Shooting
 (free rewriting)   (pages and scenes locked)     (only changed pages go out)
```

**During development**, while you write and rewrite with producers, a studio or a director, you make plain drafts. Don't use revisions here. Renumbering is harmless and revision marks would only clutter the page.

**At the start of pre-production**, the script is declared the **production draft** (also called the "White draft" or "shooting script"). At that point the **pages and scene numbers are locked**. This is the baseline everyone breaks down.

**Through pre-production and the shoot**, every change goes out as a revision. Typical reasons:

- A location falls through and a scene has to move.
- An actor is cast and dialogue is adjusted to fit them.
- The schedule or budget forces a scene to be cut or combined.
- A director's or actor's note during rehearsal.
- Legal clearance problems (a brand name, a real person's name).

A revision can be a single line or a dozen pages. Busy productions often issue several in a week.

**When there are too many revisions**, a production sometimes issues a new **full draft**: it unlocks the pages, repaginates, and starts a fresh baseline (often a "Double White" draft). That's a judgment call for the production office, not a rule.

---

## The parts of the system

Revisions rely on several features working together. Trelby has all of them.

### Locked pages and A-pages

When pages are **locked**, each page keeps its number however the text changes.

- If you **add** enough text that page 12 overflows, the extra text doesn't push page 13 onwards. It goes onto a new page **12A** (then 12B, and so on). Only 12 and 12A need to be reissued.
- If you **remove** text, the page just ends early. If a page loses all of its text, it's combined with the next one and labeled **16-17**, so the numbering doesn't skip without explanation.

### Locked scene numbers, A-scenes and OMITTED

When scene numbers are **locked**, each scene keeps its number.

- A new scene added after scene 12 becomes **12A** (then 12B). One added before scene 1 becomes **A1**.
- A scene that is cut doesn't disappear from the numbering. It's replaced by its heading reading **OMITTED**, keeping its number, so everyone knows scene 15 wasn't lost by mistake.
- A scene that is moved keeps its number.

### Revision marks

Every line containing changed text gets a **revision mark** in the right margin, usually an asterisk (`*`). Readers can scan a page and see exactly which lines to look at.

### The revision on each page

Each revised page carries its revision in the header, for example `Blue Rev. 10/17/26`. A page's revision is the **latest** revision of any change on it. So a page changed in Blue and again in Pink is a Pink page.

### Revised pages only

When a revision is issued, only the pages changed in **that** revision are printed and handed out, on that revision's color of paper.

---

## Walkthrough: two rounds of revisions on *Night Freight*

### The situation

*Night Freight* is a low-budget thriller. The writer has finished the shooting script, and pre-production starts Monday. Over the next two weeks, three things will happen:

1. The producer tells you the airport location fell through. Scene 7 has to move to a **train yard**, and you have to add a short **new scene** so the change makes sense.
2. The budget can't cover the helicopter, so **scene 15 is cut**.
3. A week later, the lead actor asks for a few lines to be **trimmed** in scene 22.

The first two changes go out as the **Blue** revision, and the third as **Pink**.

### Step 1: Lock the production draft

Open the script and make sure it's the version everyone will receive as the White draft.

1. Choose **Production > Lock pages**.
   Every page now keeps its number. The status bar shows `Page 1 / 104 (locked)`, and in the page views a small lock icon appears beside each page number.
2. Choose **Production > Lock scene numbers**.
   Every scene keeps its number, and a lock icon appears beside each scene heading.
3. Choose **Production > Show scene numbers**, so the numbers are shown on screen and printed. New scripts don't show them until you do.
4. Save, and export the White draft with **File > Export > PDF**. This is what goes to the whole team.

> **Why lock before any revision?** If the pages aren't locked, a change on page 12 can push text onto every page after it. All of those pages would then count as changed, and you'd have to reissue the whole back half of the script.

### Step 2: Start the Blue revision

1. Choose **Production > Revision mode**.
   Because no revision has been started yet, the **Revisions** dialog opens first.
2. In the dialog:
   - **Current revision:** *Blue* (the first revision; it's already selected).
   - **Date:** today's date is filled in. Change it to the date this revision will be issued if that's different.
   - **Revision mark:** leave it as `*`.
   - Leave **Show each revised page's revision above its header** turned on.
   - Make sure **Revision mode: mark changes** is checked.
3. Click **OK**.

The status bar now says `Blue revision` next to the page number. Everything you change from now on is marked as Blue.

### Step 3: Make the changes

**Rewrite scene 7 for the train yard.** Go to scene 7 and edit as you normally would. Change the heading to `EXT. TRAIN YARD - NIGHT` and rework the action.

As you type, each changed word is highlighted in blue on screen, and a `*` appears in the right margin of every line with a change. Words you didn't touch stay unhighlighted, even when your edits rewrap them onto another line. Deleting text also marks the line it was deleted from, so removed words still leave a mark. Changing an element's type (say, action into dialogue) marks the whole element.

**Add the new scene.** Put the cursor at the end of scene 7 and write the new scene: heading, action, dialogue. Because scene numbers are locked, it's numbered **7A** and doesn't renumber scenes 8 onwards. All of its text is marked Blue.

If the new material overflows page 23, the overflow goes onto a new page **23A**. Page 24 stays page 24.

**Cut scene 15.** Put the cursor anywhere in scene 15 and choose **Production > Omit scene**. The whole scene is replaced by a single heading reading **OMITTED**, still numbered 15 and marked Blue. When printed with scene numbers, it reads:

```
15   OMITTED                                                    15   *
```

You'd get the same result by selecting the whole scene and deleting it: once scene numbers are locked, Trelby leaves an OMITTED heading in its place automatically. If you change your mind, undo works as usual. If you **cut** a scene and **paste** it somewhere else, it takes its number back and the OMITTED heading goes away.

### Step 4: Check your work

Before issuing anything, review the revision:

- **On screen**, switch to a page view (**View > Page** or **View > Side by side**). Revised pages show `Blue Rev. 10/17/26` above the header, changed text is highlighted, and margin marks show the changed lines.
- **Production > Revision settings** lists the pages revised in the current revision, for example *"Pages revised in the current revision: 23, 23A, 31"*. Close the dialog with **Cancel** to change nothing.

Check that the list matches what you expect. A page you didn't mean to touch might mean an accidental keystroke: undo it with **Edit > Undo**. Undo is the only way to unmark a single change; there's no command to unmark one word.

### Step 5: Issue the Blue pages

1. Choose **Production > Export revised pages**.
2. Choose a file name, such as `Night Freight - Blue Pages.pdf`.

The PDF contains only the pages with Blue changes, each with its locked page number, `Blue Rev. 10/17/26` at the top, and asterisks beside the changed lines. The production office prints them on blue paper and hands them out. Everyone swaps them into their copy: page 23 replaces the old 23, page 23A goes in after it, and so on.

Many productions also send a short cover memo listing the revised pages and summarizing the changes. The Revision settings dialog's page list is handy for it.

Save the script. The marks, the revision and its date are saved in the `.trelby` file.

### Step 6: Start the Pink revision

A week later, the lead's notes on scene 22 come in.

1. Choose **Production > Revision settings**.
2. Set **Current revision** to *Pink*. Today's date is filled in for it.
3. Click **OK**. The status bar now says `Pink revision`.

Make the trims in scene 22. The changes are highlighted in pink. The Blue changes elsewhere keep their blue highlight: each change remembers the revision it was made in.

If scene 22 is on page 31, which already had Blue changes, page 31 now becomes a **Pink** page, because a page's revision is the latest one on it. That's correct: the new page 31 has to go out with the Pink pages.

### Step 7: Issue the Pink pages

Choose **Production > Export revised pages** again. This time you get only the pages with **Pink** changes. Page 23, which has only Blue changes, isn't included, because everyone already has it.

On page 31, both the Blue and the Pink changes carry asterisks by default. If your production wants asterisks only for the newest changes, turn on **Mark only the current revision's changes** in Revision settings. The page is still a Pink page, and the older Blue changes just lose their asterisks.

### Step 8: Wrap up the cycle

Repeat steps 6 and 7 (Yellow, Green, …) for as long as the production needs.

If the production decides to issue a fresh full draft:

1. Choose **Production > Clear revision marks**. Every mark is removed and every page is White again. You can undo this.
2. Choose **Production > Unlock pages** (and, if the production wants fully renumbered scenes, **Production > Unlock scene numbers**). This paginates the script normally again. OMITTED headings stay in the script as ordinary scenes after unlocking, so delete them first if the new draft shouldn't have them.
3. Export the new draft, then lock it again as the new baseline before the next round of revisions.

To stop marking changes for a while (to fix a typo you don't want flagged, for example), choose **Production > Revision mode** again to turn it off. Changes made then aren't marked, but existing marks stay with their text.

---

## Reference: revision features in Trelby

| Task | Where |
|---|---|
| Lock / unlock pages | **Production > Lock pages**, **Production > Unlock pages** |
| Show or hide scene numbers | **Production > Show scene numbers** |
| Lock / unlock scene numbers | **Production > Lock scene numbers**, **Production > Unlock scene numbers** |
| Replace a scene with OMITTED | **Production > Omit scene** (cursor in the scene) |
| Turn marking on or off | **Production > Revision mode** |
| Choose the revision, date, mark and display options | **Production > Revision settings** |
| Export only this revision's pages as a PDF | **Production > Export revised pages** |
| Remove all revision marks | **Production > Clear revision marks** |

**Revision settings dialog:**

- **Revision mode: mark changes**: the same switch as the menu item.
- **Current revision**: the color new changes are marked with: Blue, Pink, Yellow, … up to Triple Cherry.
- **Date**: the revision's issue date, printed in the page header. Each revision keeps its own date.
- **Revision mark**: the character printed in the margin (default `*`).
- **Show each revised page's revision above its header**: prints `Blue Rev. 10/17/26` (or similar) at the top right of each revised page.
- **Mark only the current revision's changes**: asterisks only for the newest revision; older changes still count for the pages' revisions.
- The dialog also lists the pages revised in the current revision.

**Putting the revision in your own header:** in **Script > Page headers**, use the `${REVISION}` variable, for example `${REVISION}   ${PAGE}.`. Trelby then doesn't add its own label above the header.

**Exchanging scripts with Final Draft:** **File > Export > Final Draft (FDX)** keeps the revision marks (as Final Draft revision sets) and the scene numbers. Importing an FDX file brings its revision marks back.

**What gets marked:**

| You… | Marked |
|---|---|
| type or paste new text | the new words |
| change part of a word | the whole word |
| delete text | the line where it was deleted |
| change an element's type | the whole element |
| omit or delete a locked scene | the OMITTED heading |
| change formatting (bold, italic…), notes, page or scene locks | nothing |

Marks stay with their words when text is rewrapped, moved, undone and redone, and they're saved with the script.

---

## Tips and common mistakes

- **Lock before the first revision.** If you revise an unlocked script, every page after a change can shift, and they'll all need reissuing.
- **One revision per batch of pages issued.** Start a new color each time pages go out, not each time you sit down to write. If changes come in before the Blue pages are sent, keep working in Blue.
- **Turn revision mode off for invisible fixes.** If you fix a typo that doesn't need reissuing, turn revision mode off first so it isn't marked. Everyone's copy keeps the typo until that page goes out again for another reason.
- **Don't delete OMITTED headings.** They explain the gap in the numbering. Deleting one removes that scene number for good.
- **Check the revised page list before exporting.** Unexpected pages usually mean an accidental change.
- **The paper color is your printer's job.** Trelby prints in black and white. The revision name in the header tells the production office which paper to print each page on.
- **Keep the old PDFs.** Archive each White, Blue and Pink export. They're the production's record of what was sent out when.

---

## Glossary

**A-page** – A page added after a locked page when text overflows it (12A, 12B…). Pages added before page 1 are A1, B1….

**A-scene** – A scene added after a locked scene (7A, 7B…), or before scene 1 (A1).

**Breakdown** – A department's list of what each scene needs (cast, props, wardrobe, locations), keyed to scene numbers.

**Locked pages / locked scene numbers** – Page and scene numbers fixed at the production draft, so that later changes don't renumber anything.

**OMITTED** – What a cut scene's heading reads once scene numbers are locked. It keeps the scene number so the gap is explained.

**Production draft / shooting script / White draft** – The version of the script that is locked and distributed at the start of production. All revisions are measured against it.

**Revision** – One round of changes to a locked script, named after the color of paper its pages are printed on.

**Revision mark** – The character (usually `*`) in the right margin of each line with a change.

**Revised pages** – The pages that contain changes from the current revision. Only these are printed and handed out.

**Revision mode** – In Trelby, the switch that makes your edits get marked with the current revision.

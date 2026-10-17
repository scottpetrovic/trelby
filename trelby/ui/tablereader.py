# the table read in the GUI: reading the current script aloud from the
# cursor, the narrator and each character in their own voice (see
# screenplay/tableread.py for what's read in which voice, and speech.py
# for the speaking). MyFrame has one TableReader (frame.reader), which
# reads one script at a time.
#
# the backend speaks each element on its own thread and says when it's
# done, which is passed to the GUI thread with wx.CallAfter, where the
# next one is started. the element being read gets the cursor and is
# highlighted (MyCtrl.readingLines). reading stops when the script is
# edited (MyCtrl.updateScreen calls checkScript), when another tab is
# selected, and on Escape. pausing stops the element being read, and
# resuming reads it again from its start.
#
# the voices are the ones assignVoices picks, apart from the ones chosen
# by hand in the side panel's Read aloud tab (readaloudview.py), which are
# kept in the script (sp.readAloud). that tab also plays a sample of a
# voice (preview), and shows what's being read: every change of state or
# element is passed on to frame.readerChanged.

import wx

import trelby
import trelby.screenplay.tableread as tableread
import trelby.speech as speech
import trelby.ui.fileio as fileio

STOPPED = 0
READING = 1
PAUSED = 2


class TableReader:
    def __init__(self, frame):
        self.frame = frame

        # speech.Backend, made the first time it's needed, and why there's
        # none if there isn't
        self.backend = None
        self.noBackendReason = None
        self.triedBackend = False

        # the name database's {name: (male count, female count)}, for
        # guessing the characters' genders, loaded the first time
        self.nameGenders = None

        self.state = STOPPED

        # the backend's voices (speech.Voices), asked for the first time
        # they're needed
        self.voiceList = None

        # whether a voice's sample is being played (see preview)
        self.previewing = False

        # the MyCtrl being read, what's read (tableread.Utterances), the
        # index of the one being read, and the voices (tableread.Cast)
        self.ctrl = None
        self.utts = []
        self.index = 0
        self.cast = None

        # what the script looked like when reading started (see
        # changeMarker)
        self.marker = None

        # increased for each utterance started and on every stop, so that
        # the end of one that's been stopped is ignored
        self.token = 0

    def isActive(self):
        return self.state != STOPPED

    def isReading(self):
        return self.state == READING

    # the backend, or None if there's none (see noBackendReason)
    def ensureBackend(self):
        if not self.triedBackend:
            self.triedBackend = True
            self.backend, self.noBackendReason = speech.systemBackend()

        return self.backend

    # the backend, or None after telling the user why there's none
    def getBackend(self):
        if not self.ensureBackend():
            self.showError(self.noBackendReason)

        return self.backend

    # the backend's voices. raises what the backend raises.
    def getVoices(self):
        if self.voiceList is None:
            self.voiceList = self.backend.voices()

        return self.voiceList

    # the voices for reading sp (a tableread.Cast): the ones chosen in it,
    # and assignVoices' for the rest. needs the backend; raises what
    # getVoices raises.
    def makeCast(self, sp):
        voices = self.getVoices()
        names = tableread.characters(sp)
        nameGenders = self.getNameGenders()
        genders = {n: tableread.guessGender(n, nameGenders) for n in names}

        return tableread.assignVoices(
            voices,
            names,
            genders,
            self.backend.defaultRate,
            sp.readAloud.usableChoices(voices),
        )

    def showError(self, msg):
        wx.MessageBox(
            _("Reading aloud isn't available.\n\n{}").format(msg),
            _("Read aloud"),
            wx.OK,
            self.frame,
        )

    # start reading ctrl's script from its cursor
    def start(self, ctrl):
        self.stop()

        backend = self.getBackend()

        if not backend:
            return

        sp = ctrl.sp

        try:
            cast = self.makeCast(sp)
        except Exception as e:
            self.showError(str(e) or e.__class__.__name__)

            return

        utts = tableread.utterances(sp)
        index = tableread.indexAt(utts, ctrl.ed.line)

        if index is None:
            wx.MessageBox(
                _("There's nothing to read after the cursor."),
                _("Read aloud"),
                wx.OK,
                self.frame,
            )

            return

        self.cast = cast
        self.ctrl = ctrl
        self.utts = utts
        self.index = index
        self.marker = changeMarker(ctrl)
        self.state = READING
        self.speakCurrent()

    def getNameGenders(self):
        if self.nameGenders is None:
            data = fileio.loadMaybeCompressedFile(
                trelby.__path__[0] + "/names.txt", self.frame
            )
            self.nameGenders = tableread.parseNameGenders(data or "")

        return self.nameGenders

    # start reading if nothing's being read, otherwise pause or resume
    def toggle(self, ctrl):
        if self.state == STOPPED:
            self.start(ctrl)
        else:
            self.pause()

    # pause, or resume if paused
    def pause(self):
        if self.state == READING:
            self.state = PAUSED
            self.token += 1
            self.backend.stop()
            self.notify()
        elif self.state == PAUSED:
            if self.checkScript(self.ctrl):
                self.state = READING
                self.speakCurrent()

    def stop(self):
        self.stopPreview()

        if self.state == STOPPED:
            return

        self.state = STOPPED
        self.token += 1

        if self.backend:
            self.backend.stop()

        ctrl = self.ctrl
        self.ctrl = None
        self.utts = []
        self.cast = None

        if ctrl:
            ctrl.readingLines = None
            ctrl.Refresh(False)

        self.notify()

    # the speaker of the element being read (None for the narrator), or
    # False if nothing's being read
    def currentSpeaker(self):
        if self.state == STOPPED:
            return False

        return self.utts[self.index].speaker

    # if reading ctrl's script, read the rest in its voices as they are
    # now, after a change to the ones chosen in it
    def recast(self, ctrl):
        if (self.state == STOPPED) or (ctrl is not self.ctrl):
            return

        try:
            self.cast = self.makeCast(ctrl.sp)
        except Exception:
            # the voices worked a moment ago; keep the old ones
            pass

    # say text in the given tableread.VoiceChoice, as a sample of the
    # voice, stopping any reading
    def preview(self, text, choice):
        self.stop()

        backend = self.getBackend()

        if not backend:
            return

        self.token += 1
        token = self.token
        self.previewing = True

        def onDone(completed, error):
            try:
                wx.CallAfter(self.onPreviewDone, token, error)
            except Exception:
                # the app is closing
                pass

        backend.speak(text, choice.voiceId, choice.rate, onDone)

    def onPreviewDone(self, token, error):
        if (token != self.token) or not self.previewing:
            return

        self.previewing = False

        if error:
            self.showError(error)

    def stopPreview(self):
        if self.previewing:
            self.previewing = False
            self.token += 1
            self.backend.stop()

    # tell the frame that the state or the element being read changed
    def notify(self):
        f = getattr(self.frame, "readerChanged", None)

        if f:
            f()

    # go to the next (step 1) or previous (-1) element, reading it if
    # reading, only showing it if paused
    def skip(self, step):
        if (self.state == STOPPED) or not self.checkScript(self.ctrl):
            return

        index = self.index + step

        if (index < 0) or (index >= len(self.utts)):
            return

        self.index = index

        if self.state == READING:
            self.speakCurrent()
        else:
            self.showCurrent()

    # called when the script in ctrl may have changed, and by the commands
    # here. stops reading if it was ctrl's script that changed (or was
    # replaced), and returns whether reading goes on.
    def checkScript(self, ctrl):
        if (self.state != STOPPED) and (ctrl is self.ctrl):
            if changeMarker(ctrl) != self.marker:
                self.stop()

        return self.state != STOPPED

    # put the cursor on the current utterance and highlight it
    def showCurrent(self):
        u = self.utts[self.index]
        ctrl = self.ctrl

        ctrl.readingLines = (u.start, u.end)
        ctrl.clearAutoComp()
        ctrl.ed.clearMark()
        ctrl.ed.gotoPos(u.start, 0)
        ctrl.makeLineVisible(u.end)
        ctrl.makeLineVisible(u.start)
        ctrl.updateScreen()
        self.notify()

    def speakCurrent(self):
        self.showCurrent()

        u = self.utts[self.index]
        choice = self.cast.voiceFor(u.speaker)

        self.token += 1
        token = self.token

        def onDone(completed, error):
            try:
                wx.CallAfter(self.onDone, token, completed, error)
            except Exception:
                # the app is closing
                pass

        self.backend.speak(u.text, choice.voiceId, choice.rate, onDone)

    # the backend is done with the utterance started with token
    def onDone(self, token, completed, error):
        if (token != self.token) or (self.state != READING):
            return

        if error:
            self.stop()
            self.showError(error)

            return

        if not completed or not self.checkScript(self.ctrl):
            return

        if self.index + 1 >= len(self.utts):
            self.stop()

            return

        self.index += 1
        self.speakCurrent()

    # stop, and let go of the engine, when the program closes
    def close(self):
        self.stop()

        if self.backend:
            self.backend.close()


# what changes when ctrl's script is edited, replaced or undone: every
# edit is recorded in the undo history (and the history is cleared by the
# few that aren't), and undo / redo move its current point
def changeMarker(ctrl):
    uh = ctrl.ed.undoHistory

    return (ctrl.sp, ctrl.ed, uh.last, uh.current, len(ctrl.sp.lines))

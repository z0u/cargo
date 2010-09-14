#
# Copyright 2009 Alex Fraser <alex@phatcore.com>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#

import GameLogic
from . import Utilities
from . import Actor

class _HUD(Actor.DirectorListener, Actor.ActorListener):
	'''The head-up display manages the 2D user interface that is drawn over the
	3D scene. This is a Singleton (see HUD instance below). This object
	maintains is state even if no HUD objects are attached to it.'''

	def __init__(self):
		'''Reset the internal state and detach all UI elements.'''
		self.DialogueText = ""
		self.DialogueBox = None
		self.CausedSuspension = False
		
		self.MessageBox = None
		
		self.LoadingScreenVisible = True
		self.LoadingScreen = None
		self.LoadingScreenCallers = set()
		
		self.Gauges = {}
		self.Filter = None
		self.FilterColour = None
		
		Utilities.SceneManager.Subscribe(self)
		Actor.Director.addListener(self)
	
	def Attach(self, owner):
		'''Attach a new user interface, e.g. at the start of a new scene.
		
		Hierarchy:
		 - Owner: The root of the HUD.
		   - DialogueBox: An object to display text on. Must have a Content
		                  property (String).
		   - LoadingScreen: The object to display when the game is loading. This
		                  must be visible by default. In state 1 it will show
		                  itself; in state 2 it will hide itself.
		   - Gauge:       Any number of gauge objects (see Gauge, below). Must
		                  have a Name property to distinguish itself from other
		                  gauges.'''
		Utilities.parseChildren(self, owner)
		self._UpdateDialogue()
		self._UpdateLoadingScreen()
		self._updateHealthGauge()
		self._updateFilter()
	
	def OnSceneEnd(self):
		self.__init__()
	
	def parseChild(self, child, type):
		if type == "DialogueBox":
			if self.DialogueBox:
				print("Warning: HUD already has a dialogue box.")
				return False
			self.DialogueBox = child
			return True
		if type == "MessageBox":
			if self.MessageBox:
				print("Warning: HUD already has a message box.")
				return False
			self.MessageBox = child
			return True
		elif type == "LoadingScreen":
			if self.LoadingScreen:
				print("Warning: HUD already has a loading screen.")
				return False
			self.LoadingScreen = child
			return True
		elif type == "Gauge":
			name = child['Name']
			if name in self.Gauges:
				print("Warning: duplicate gauge '%s'" % name)
				return False
			self.Gauges[name] = Gauge(child)
			return True
		elif type == 'Filter':
			if self.Filter:
				print("Warning: HUD already has a filter.")
				return False
			self.Filter = Filter(child)
			return True
		return False
	
	def showMessage(self, message):
		'''
		Display a message. This is non-modal: game play is not suspended, and
		return does not need to be pressed. The message will disappear after a
		short time.

		Parameters:
		message: The message to show.
		'''
		if self.MessageBox == None:
			return
		
		self.MessageBox['Content'] = message
	
	def _UpdateDialogue(self):
		if self.DialogueText == "":
			if self.DialogueBox['Content'] != "":
				self.DialogueBox['Content'] = ""
				if self.CausedSuspension:
					Actor.Director.ResumeUserInput()
		else:
			self.DialogueBox['Content'] = self.DialogueText
			if not Actor.Director.InputSuspended:
				Actor.Director.SuspendUserInput()
				self.CausedSuspension = True

	def ShowDialogue(self, message):
		'''
		Display a message. A button will be shown to encourage
		the player to press Return. No events are hooked up to
		the Return key, however: you must call HideDialogue
		manually.

		Parameters:
		message: The message to show. An empty string causes the box to be
		         hidden.
		'''
		self.DialogueText = message
		if self.DialogueBox:
			self._UpdateDialogue()
	
	def HideDialogue(self):
		self.DialogueText = ""
		if self.DialogueBox:
			self._UpdateDialogue()
	
	def GetGauge(self, name):
		if name in self.Gauges:
			return self.Gauges[name]
		else:
			return None
	
	def _UpdateLoadingScreen(self):
		if self.LoadingScreenVisible:
			Utilities.setState(self.LoadingScreen, 1)
		else:
			Utilities.setState(self.LoadingScreen, 2)
	
	def ShowLoadingScreen(self, caller):
		print("%s started loading." % caller)
		if len(self.LoadingScreenCallers) == 0:
			self.LoadingScreenVisible = True
			if self.LoadingScreen:
				self._UpdateLoadingScreen()
		self.LoadingScreenCallers.add(caller)
	
	def HideLoadingScreen(self, caller):
		self.LoadingScreenCallers.discard(caller)
		print("%s finished loading. %d remaining." % (caller,
			len(self.LoadingScreenCallers)))
		if len(self.LoadingScreenCallers) == 0:
			self.LoadingScreenVisible = False
			if self.LoadingScreen:
				self._UpdateLoadingScreen()
	
	def _updateHealthGauge(self):
		gauge = self.GetGauge("Health")
		if gauge == None:
			return
		
		actor = Actor.Director.getMainCharacter()
		if actor != None:
			gauge.Show()
			#gauge.SetFraction(actor.getHealth())
			gauge.SetFraction(actor.getOxygen(), 'Oxygen')
		else:
			gauge.Hide()
	
	def directorMainCharacterChanged(self, oldActor, newActor):
		if oldActor != None:
			oldActor.removeListener(self)
		if newActor != None:
			newActor.addListener(self)  
			self._updateHealthGauge()
			
	def actorHealthChanged(self, actor):
		self._updateHealthGauge()
		
	def actorOxygenChanged(self, actor):
		self._updateHealthGauge()
	
	def actorRespawned(self, actor, reason):
		if reason != None:
			self.showMessage(reason)
	
	def _updateFilter(self):
		if self.Filter == None:
			return
		if self.FilterColour == None:
			self.Filter.hide()
		else:
			self.Filter.show(self.FilterColour)
	
	def showFilter(self, hue, value, alpha):
		self.FilterColour = Filter.Colour(hue, value, alpha)
		self._updateFilter()

HUD = _HUD()

def CreateHUD(c):
	HUD.Attach(c.owner)

def ShowLoadingScreen(c):
	HUD.ShowLoadingScreen(c.owner)

def HideLoadingScreen(c):
	HUD.HideLoadingScreen(c.owner)

class Filter(Actor.Actor):
	ALPHA_STEP = 0.1
	VALUE_WIDTH = 660.0
	VALUE_STEP = 0.2
	HUE_WIDTH = 60.0
	
	S_HIDE = 1
	S_SHOW = 2
	
	class Colour:
		def __init__(self, hue, value, alpha):
			self.hue = hue
			self.value = value
			self.alpha = alpha
	
	def __init__(self, owner):
		Actor.Actor.__init__(self, owner)
	
	def hide(self):
		Utilities.setState(self.owner, Filter.S_HIDE)
	
	def show(self, colour):
		key = colour.hue * Filter.HUE_WIDTH
		key += (colour.value % Filter.VALUE_STEP) * Filter.HUE_WIDTH
		key += (colour.alpha % Filter.ALPHA_STEP) * Filter.VALUE_WIDTH
		key += 1.0
		self.owner['Frame'] = key
		Utilities.setState(self.owner, Filter.S_SHOW)

class Gauge(Actor.Actor):
	'''
	Displays a value on the screen between 0 and 1.
	
	Hierarchy:
	Owner
	  - Indicator
	
	Owner properties:
	Type: 'Gauge'
	Name: Key for accessing gauge through HUD.getGauge.
	
	Indicator properties:
	Type: 'Indicator'
	Name: Key for accessing indicator through SetFraction. If not set, the
		indicator can be accessed using the key None.
	Speed: The responsiveness to changes in value. 0 <= Speed <= 1.
	Frame [out]: The animation frame that displays a fraction, as a percentage.
		0 <= Frame <= 100.
	'''
	
	S_HIDDEN  = 1
	S_VISIBLE = 2
	S_HIDING  = 3
	
	class Indicator:
		def __init__(self, owner):
			self.Fraction = 0.0
			self.TargetFraction = 0.0
			self.owner = owner
		
		def update(self):
			self.Fraction = Utilities._lerp(self.Fraction, self.TargetFraction,
				self.owner['Speed'])
			self.owner['Frame'] = self.Fraction * 100.0

	def __init__(self, owner):
		Actor.Actor.__init__(self, owner)
		self.Indicators = {}
		Utilities.parseChildren(self, owner)
	
	def parseChild(self, child, type):
		if type == "Indicator":
			if 'Name' in child:
				self.Indicators[child['Name']] = self.Indicator(child)
			else:
				self.Indicators[None] = self.Indicator(child)
			return True
		return False
	
	def OnSceneEnd(self):
		for i in list(self.Indicators.values()):
			i.owner = None
		Actor.Actor.OnSceneEnd(self)
	
	def Show(self):
		Utilities.setState(self.owner, self.S_VISIBLE)
	
	def Hide(self):
		Utilities.setState(self.owner, self.S_HIDING)
	
	def SetFraction(self, fraction, name = None):
		self.Indicators[name].TargetFraction = fraction
	
	def Update(self, c):
		for i in list(self.Indicators.values()):
			i.update()
		for a in c.actuators:
			c.activate(a)

def UpdateGauge(c):
	'''
	Update the indicators of a gauge. This sets the Frame property of each
	indicator, and instructs them to update.
	
	Sensors:
	<any>: Should be in pulse mode.
	
	Actuators:
	<any>: Update the indicator animation according to the indicator's Frame
		property.
	'''
	gauge = c.owner['Actor']
	gauge.Update(c)

class Font:
	GlyphDict = None
	Owner = None
	LineHeight = 0.0
	TypingSpeed = 0.0
	KeyError = KeyError
	len = len
	
	def __init__(self, owner):
		self.owner = owner
		self.GlyphDict = {}
		for child in self.owner.children:
			charWidth = child['Width']
			self.GlyphDict[child['char']] = (child, charWidth)
		self.LineHeight = owner['LineHeight']
		self.TypingSpeed = owner['TypingSpeed']
	
	def DecodeEscapeSequence(self, text, start):
		'''
		Decode an escape sequence from a string. Escape sequences begin with
		a backslash. '\\' is decoded into a single backslash. A backslash
		followed by a pair of matching square brackets decodes into the string
		between the brackets. Anything else is illegal, and the key 'undefined'
		will be returned.

		Returns: the decoded glyph key and the length of the complete escape
		sequence.
		'''
		seqLen = 1
		key = None
		if text[start + 1] == '\\':
			key = '\\'
			seqLen = 2
		elif text[start + 1] == '[':
			try:
				end = text.index(']', start + 2)
				key = text[start + 2: end]
				seqLen = (end + 1) - start
			except ValueError:
				key = 'undefined'
				seqLen = 2
		else:
			key = 'undefined'
			seqLen = 1
			
		return key, seqLen
	
	def TextToGlyphTuples(self, text):
		'''
		Convert a string of text into glyph tuples. Escape sequences are
		converted. E.G the string '\[foo]' will be converted into one glyph with
		the name 'foo'.
		
		Returns: a list of glyph tuples.
		'''

		glyphString = []
		i = 0
		while i < self.len(text):
			char = text[i]
			seqLen = 1
			if char == '\\':
				char, seqLen = self.DecodeEscapeSequence(text, i)
			glyphString.append(self.GetGlyph(char))
			i = i + seqLen
		return glyphString
	
	def GetGlyph(self, char):
		'''
		Return the glyph tuple that matches 'char'. If no match is found, the
		'undefined' glyph is returned (typically a box).
		
		Returns: (glyph object, width of glyph)
		'''
		try:
			return self.GlyphDict[char]
		except self.KeyError:
			return self.GlyphDict['undefined']

_fonts = {}
def CreateFont(c):
	global _fonts
	_fonts[c.owner['FontName']] = Font(c.owner)

class TextRenderer:
	'''
	A TextRenderer is used to render glyphs from a Font. The object nominated as
	the owner acts as the caret (like the head of a typewriter). It must be the
	only child of the text canvas. The canvas can be any KX_GameObject: the
	caret will draw glyphs onto the canvas' XY-plane. In short, the hierarchy
	should look like this:
	
	  |- Canvas
	  |  |- Caret
	
	Canvas properties:
	str   Content:   The text to draw.
	str   Font:      The name of the font to use.
	float LineWidth  The width of the canvas in Blender units.
	
	Caret properties:
	(none)
	
	Call RenderText to draw the Content to the screen. Set Content to "" before
	rendering to clear the canvas.
	'''
	
	def __init__(self, caret):
		self.caret = caret
		self.canvas = caret.parent
		if self.canvas == None or (len(self.canvas.children) != 1):
			raise Exception("Error: Text renderer must be the only child of " +
				"another object.")
		self.Clear()
		
		Utilities.SceneManager.Subscribe(self)
	
	def OnSceneEnd(self):
		self.caret = None
		self.canvas = None
		Utilities.SceneManager.Unsubscribe(self)
	
	def Clear(self):
		for child in self.canvas.children:
			if child == self.caret:
				continue
			child.endObject()
		
		self.caretX = 0.0
		self.caretY = 0.0
		self.glyphString = None
		self.font = None
		self.softBreakPoint = 0
		self.hardBreakPoint = 0
		self.newLine = True
		self.delay = 0.0
		self.currentChar = 0
	
	def GetFont(self, name):
		try:
			self.font = _fonts[name]
		except AttributeError:
			raise AttributeError("Error: Can't find font \"%s\". Ensure the " +
				"font group is on a visible layer. Don't worry, it will hide " +
				"itself." % name)
	
	def FindNextBreakableChar(self, glyphString, start):
		for i in range(start, len(glyphString)):
			(glyph, width) = glyphString[i]
			if self.IsWhitespace(glyph['char']) or self.IsPunctuation(glyph['char']):
				return i
		#
		# No more breakable characters.
		#
		return len(glyphString)
	
	def FindNextBreakPoint(self, lineWidth, glyphString, start):
		"""Find the break point for a string of text. Always taken from
		the start of the line (only call this when starting a new
		line)."""
		totalWidth = 0.0
		for i in range(start, len(glyphString)):
			(glyph, width) = glyphString[i]
			totalWidth = totalWidth + width
			if totalWidth > lineWidth:
				return i
		#
		# No break required: string is not long enough.
		#
		return len(glyphString)
	
	def IsWhitespace(self, char):
		"""Check whether a character is whitespace. Special characters
		(like icons) are not considered to be whitespace."""
		if len(char) > 1:
			return False
		elif char == ' ':
			return True
		else:
			return False
	
	def IsPunctuation(self, char):
		"""Check whether a character is punctuation. Special characters
		(like icons) are considered to be punctuation."""
		if len(char) > 1:
			return True
		elif char in '.,!:;\'"&()[]<>*$#%~^_':
			return True
		else:
			return False
	
	def _RenderNextChar(self):
		if not self.canvas['Rendering']:
			return
		
		if self.currentChar >= len(self.glyphString):
			self.canvas['Rendering'] = False
			return
		
		if self.newLine:
			self.hardBreakPoint = self.FindNextBreakPoint(
				self.canvas['LineWidth'], self.glyphString, self.currentChar)
			self.newLine = False
	
		(glyph, width) = self.glyphString[self.currentChar]
		
		if self.currentChar == self.softBreakPoint:
			#
			# This glyph can have a line break before it. If the next
			# such character is beyond the end of the line, break now.
			#
			self.softBreakPoint = self.FindNextBreakableChar(self.glyphString,
				self.currentChar + 1)
			if self.softBreakPoint > self.hardBreakPoint:
				self.newLine = True
		
		if self.currentChar == self.hardBreakPoint:
			#
			# This glyph is beyond the end of the line. Break now.
			#
			self.newLine = True
			
		if self.newLine:
			#
			# New line; carriage return.
			#
			self.caretX = 0.0
			self.caretY = self.caretY - self.font.LineHeight
			if self.IsWhitespace(glyph['char']):
				#
				# Advance to next character.
				#
				return
		
		self.caret.position = [self.caretX + glyph['xOffset'],
			self.caretY + glyph['yOffset'], 0.0]
		glyphInstance = GameLogic.getCurrentScene().addObject(glyph,
			self.caret, 0)
		glyphInstance.setParent(self.canvas)
		if self.canvas['Instant']:
			Utilities.setState(glyphInstance, 4)
		else:
			self.delay = (self.font.TypingSpeed * width *
				glyph['DelayMultiplier'])
			Utilities.setState(glyphInstance, 3)
		
		self.caretX = self.caretX + width
	
	def RenderNextChar(self):
		'''
		Lay out a glyph. Each glyph accumulates a delay based on its width. This
		should be called repeatedly until canvas['Rendering'] is False.
		'''
		if self.delay > 0:
			self.delay = self.delay - 1
			return
		
		try:
			self._RenderNextChar()
		finally:
			self.currentChar = self.currentChar + 1
	
	def RenderText(self):
		'''
		Render the content onto the canvas.
		'''
		self.Clear()
		
		self.GetFont(self.canvas['Font'])
		self.glyphString = self.font.TextToGlyphTuples(self.canvas['Content'])
		self.softBreakPoint = self.FindNextBreakableChar(self.glyphString, 0)
		self.canvas['Rendering'] = True
		
		if self.canvas['Instant']:
			while self.canvas['Rendering']:
				self.RenderNextChar()

def RenderText(c):
	try:
		tr = c.owner['_TextRenderer']
	except KeyError:
		tr = TextRenderer(c.owner)
		c.owner['_TextRenderer'] = tr
	tr.RenderText()

def RenderNextChar(c):
	if not Utilities.allSensorsPositive(c):
		return
	
	tr = c.owner['_TextRenderer']
	tr.RenderNextChar()


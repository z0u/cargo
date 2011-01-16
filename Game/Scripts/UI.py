#
# Copyright 2009-2010 Alex Fraser <alex@phatcore.com>
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

import bxt
from bge import logic
from . import Utilities
from . import Actor

@bxt.types.singleton()
class HUD(Actor.DirectorListener, Actor.ActorListener):
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
		self.filter = None
		self.filterColour = None
		
		Utilities.SceneManager().Subscribe(self)
		Actor.Director().addListener(self)
	
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
			if self.filter:
				print("Warning: HUD already has a filter.")
				return False
			self.filter = Filter(child)
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
					Actor.Director().ResumeUserInput()
		else:
			self.DialogueBox['Content'] = self.DialogueText
			if not Actor.Director().InputSuspended:
				Actor.Director().SuspendUserInput()
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
			bxt.utils.set_state(self.LoadingScreen, 1)
		else:
			bxt.utils.set_state(self.LoadingScreen, 2)
	
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
		
		actor = Actor.Director().getMainCharacter()
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
		if self.filter == None:
			return
		if self.filterColour == None:
			self.filter.hide()
		else:
			self.filter.show(self.filterColour)
	
	def showFilter(self, colour):
		self.filterColour = colour
		self._updateFilter()
	
	def hideFilter(self):
		self.filterColour = None
		self._updateFilter()

@bxt.utils.owner
def CreateHUD(o):
	HUD().Attach(o)

@bxt.utils.owner
def ShowLoadingScreen(o):
	HUD().ShowLoadingScreen(o)

@bxt.utils.owner
def HideLoadingScreen(o):
	HUD().HideLoadingScreen(o)

class Filter(Actor.Actor):
	S_HIDE = 1
	S_SHOW = 2
	
	def __init__(self, owner):
		Actor.Actor.__init__(self, owner)
	
	def hide(self):
		self.owner.visible = False
	
	def show(self, colour):
		self.owner.color = colour
		self.owner.visible = True

class Gauge(Actor.Actor):
	'''
	Displays a value on the screen between 0 and 1.
	
	Hierarchy:
	Owner
	  - Indicator
	
	Owner properties:
	Type: 'Gauge'
	Name: Key for accessing gauge through HUD().getGauge.
	
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
			self.Fraction = bxt.math.lerp(self.Fraction, self.TargetFraction,
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
		bxt.utils.set_state(self.owner, self.S_VISIBLE)
	
	def Hide(self):
		bxt.utils.set_state(self.owner, self.S_HIDING)
	
	def SetFraction(self, fraction, name = None):
		self.Indicators[name].TargetFraction = fraction
	
	def Update(self, c):
		for i in list(self.Indicators.values()):
			i.update()
		for a in c.actuators:
			c.activate(a)

@bxt.utils.controller
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
		self.baselineOffset = owner['baselineOffset']
		self.bottomOffset = owner['bottomOffset']
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
		elif text[start + 1] == 'n':
			key = 'newline'
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

@bxt.utils.owner
def CreateFont(o):
	global _fonts
	_fonts[o['FontName']] = Font(o)

class TextRenderer:
	'''
	A TextRenderer is used to render glyphs from a Font. The object nominated as
	the owner is the canvas. The canvas can be any KX_GameObject: the glyphs
	will be drawn onto the canvas' XY-plane.
	
	Canvas properties:
	str   Content:   The text to draw.
	str   Font:      The name of the font to use.
	float LineWidth  The width of the canvas in Blender units.
	
	Call RenderText to draw the Content to the screen. Set Content to "" before
	rendering to clear the canvas.
	'''
	
	def __init__(self, canvas):
		self.canvas = canvas
		bxt.utils.set_default_prop(canvas, 'colour', 'black')
		bxt.utils.set_default_prop(canvas, 'valign', 'bottom')
		self.lastHash = None
		self.Clear()
		
		Utilities.SceneManager().Subscribe(self)
	
	def OnSceneEnd(self):
		self.canvas = None
		Utilities.SceneManager().Unsubscribe(self)
	
	def Clear(self):
		for child in self.canvas.children:
			child.endObject()
		
		self.glyphString = []
		self.font = None
		self.delay = 0.0
		self.currentChar = 0
		self.lines = 0
	
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
			if self.IsWhitespace(glyph['char']):
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
			if totalWidth > lineWidth or glyph['char'] == 'newline':
				return i
		#
		# No break required: string is not long enough.
		#
		return len(glyphString)
	
	def IsWhitespace(self, char):
		"""Check whether a character is whitespace. Special characters
		(like icons) are not considered to be whitespace."""
		if char == 'newline':
			return True
		elif char == ' ':
			return True
		else:
			return False
	
	def layOutText(self, glyphString):
		newLine = True
		softBreakPoint = self.FindNextBreakableChar(glyphString, 0)
		hardBreakPoint = 0
		self.glyphString = []
		x = 0.0
		y = 0.0
		
		for i, (glyph, width) in enumerate(glyphString):
			if newLine:
				hardBreakPoint = self.FindNextBreakPoint(
					self.canvas['LineWidth'], glyphString, i)
				newLine = False
				self.lines += 1
		
			if i == softBreakPoint:
				# This glyph can have a line break before it. If the next
				# such character is beyond the end of the line, break now.
				softBreakPoint = self.FindNextBreakableChar(glyphString,
					i + 1)
				if softBreakPoint > hardBreakPoint:
					newLine = True
			elif i == hardBreakPoint:
				# This glyph is beyond the end of the line. Break now.
				newLine = True
				
			if newLine:
				# New line; carriage return.
				x = 0.0
				y = y - self.font.LineHeight
				if self.IsWhitespace(glyph['char']):
					# Advance to next character.
					continue
			
			gx = x + glyph['xOffset']
			gy = y + glyph['yOffset']
			if self.canvas['valign'] == 'baseline':
				gy += self.font.baselineOffset
			else:
				gy += self.font.bottomOffset
			pos = (gx, gy)
			self.glyphString.append((glyph, width, pos))
			x += width
		
	def _RenderNextChar(self):
		if not self.canvas['Rendering']:
			return
		
		if self.currentChar >= len(self.glyphString):
			self.canvas['Rendering'] = False
			return
	
		glyph, width, pos = self.glyphString[self.currentChar]
		
		glyphInstance = logic.getCurrentScene().addObject(glyph,
			self.canvas, 0)
		glyphInstance.setParent(self.canvas)
		glyphInstance.color = bxt.render.parse_colour(self.canvas['colour'])
		glyphInstance.localPosition = [pos[0], pos[1], 0.0]
		
		if self.canvas['Instant']:
			bxt.utils.set_state(glyphInstance, 4)
		else:
			self.delay = (self.font.TypingSpeed * width *
				glyph['DelayMultiplier'])
			bxt.utils.set_state(glyphInstance, 3)
	
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
		h = hash(str(self.canvas['Content']))
		if h == self.lastHash:
			return
		self.lastHash = h
		
		self.Clear()
		
		self.GetFont(self.canvas['Font'])
		self.layOutText(self.font.TextToGlyphTuples(self.canvas['Content']))
		self.canvas['Rendering'] = True
		
		if self.canvas['Instant']:
			while self.canvas['Rendering']:
				self.RenderNextChar()

@bxt.utils.owner
def _getTextRenderer(o):
	try:
		tr = o['_TextRenderer']
	except KeyError:
		tr = TextRenderer(o)
		o['_TextRenderer'] = tr
	return tr

def RenderText():
	_getTextRenderer().RenderText()

@bxt.utils.all_sensors_positive
def RenderNextChar():
	_getTextRenderer().RenderNextChar()

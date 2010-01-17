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
import Utilities
import Actor

class _HUD(Utilities.SemanticGameObject):
	def __init__(self, owner):
		self.DialogueBox = None
		self.LoadingScreen = None
		Utilities.SemanticGameObject.__init__(self, owner)
		self.CausedSuspension = False
	
	def parseChild(self, child, type):
		if type == "DialogueBox":
			if self.DialogueBox:
				print "Warning: HUD already has a dialogue box."
			self.DialogueBox = child
			return True
		elif type == "LoadingScreen":
			if self.LoadingScreen:
				print "Warning: HUD already has a loading screen."
			self.LoadingScreen = child
			return True
		return False

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
		if message == "":
			self.HideDialogue()
		else:
			self.DialogueBox['Content'] = message
			if not Actor.Director.InputSuspended:
				Actor.Director.SuspendUserInput()
				self.CausedSuspension = True
	
	def HideDialogue(self):
		if self.DialogueBox['Content'] != "":
			self.DialogueBox['Content'] = ""
			if self.CausedSuspension:
				Actor.Director.ResumeUserInput()
	
	def ShowLoadingScreen(self):
		Utilities.setState(self.LoadingScreen, 1)
	
	def HideLoadingScreen(self):
		Utilities.setState(self.LoadingScreen, 2)

HUD = None
def CreateHUD(c):
	global HUD
	HUD = _HUD(c.owner)
	print "HUD created"

class Font:
	GlyphDict = None
	Owner = None
	LineHeight = 0.0
	TypingSpeed = 0.0
	KeyError = KeyError
	len = len
	
	def __init__(self, owner):
		self.Owner = owner
		self.GlyphDict = {}
		for child in self.Owner.children:
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


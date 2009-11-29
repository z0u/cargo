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
	Owner = None
	DialogueBox = None
	
	def __init__(self, owner):
		Utilities.SemanticGameObject.__init__(self, owner)
		self.CausedSuspension = False
	
	def parseChild(self, child, type):
		if type == "DialogueBox":
			if self.DialogueBox:
				print "Warning: HUD already has a dialogue box."
			self.DialogueBox = child
			return True

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
			raise Exception("Error: Text renderer must be the only child of another object.")
	
	def GetFont(self, name):
		try:
			return _fonts[name]
		except AttributeError:
			raise AttributeError("Error: Can't find font \"%s\". Ensure the font group is on a visible layer. Don't worry, it will hide itself." % name)
	
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
	
	def RenderText(self):
		'''
		Render the content onto the canvas.
		'''
		
		#
		# Clear the canvas.
		#
		for child in self.canvas.children:
			if child == self.caret:
				continue
			child.endObject()
		
		font = self.GetFont(self.canvas['Font'])
		
		x = 0.0
		y = 0.0
		z = 0.0
		glyphString = font.TextToGlyphTuples(self.canvas['Content'])
		softBreakPoint = self.FindNextBreakableChar(glyphString, 0)
		hardBreakPoint = 0
		newLine = True
		delay = 0.0
		scene = GameLogic.getCurrentScene()
		for i in range (0, len(glyphString)):
			#
			# Lay out the glyphs. Each glyph accumulates a delay based on its
			# width.
			#
			
			if newLine:
				hardBreakPoint = self.FindNextBreakPoint(
					self.canvas['LineWidth'], glyphString, i)
				newLine = False
		
			(glyph, width) = glyphString[i]
			
			if i == softBreakPoint:
				#
				# This glyph can have a line break before it. If the next
				# such character is beyond the end of the line, break now.
				#
				softBreakPoint = self.FindNextBreakableChar(glyphString, i + 1)
				if softBreakPoint > hardBreakPoint:
					newLine = True
			
			if i == hardBreakPoint:
				#
				# This glyph is beyond the end of the line. Break now.
				#
				newLine = True
				
			if newLine:
				#
				# New line; carriage return.
				#
				x = 0.0
				y = y - font.LineHeight
				if self.IsWhitespace(glyph['char']):
					continue
			
			self.caret.position = [x + glyph['xOffset'], y + glyph['yOffset'], z]
			glyphInstance = scene.addObject(glyph, self.caret, 0)
			glyphInstance.setParent(self.canvas)
			glyphInstance['Delay'] = delay
			delay = delay + (font.TypingSpeed * width * glyph['DelayMultiplier'])
			glyphInstance.state = 1<<1
			
			x = x + width

def RenderText(c):
	try:
		tr = c.owner['_TextRenderer']
	except KeyError:
		tr = TextRenderer(c.owner)
		c.owner['_TextRenderer'] = tr
	tr.RenderText()

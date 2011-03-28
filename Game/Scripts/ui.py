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

import weakref

import bge
from bge import logic

import bxt

class HUDState(metaclass=bxt.types.Singleton):
	def __init__(self):
		self.loaders = bxt.types.GameObjectSet()
		bxt.types.EventBus().addListener(self)

	def onEvent(self, evt):
		if evt.message == "StartLoading":
			self.loaders.add(evt.body)
		if evt.message == "FinishLoading":
			self.loaders.discard(evt.body)

	def getNumLoaders(self):
		return len(self.loaders)

class MessageBox(bxt.types.BX_GameObject, bge.types.KX_GameObject):
	_prefix = 'MB_'

	def __init__(self, old_owner):
		self.canvas = self.find_descendant([('template', 'TextCanvas_T')])
		if self.canvas.__class__ != Text:
			self.canvas = Text(self.canvas)

		bxt.types.EventBus().addListener(self)
		bxt.types.EventBus().replayLast(self, 'ShowMessage')

	def onEvent(self, evt):
		if evt.message == 'ShowMessage':
			self.setText(evt.body)

	def setText(self, text):
		if self['Content'] != text:
			self['Content'] = text
			self.canvas['Content'] = text

	@bxt.types.expose
	def clear(self):
		self['Content'] = ""
		self.canvas['Content'] = ""

class DialogueBox(bxt.types.BX_GameObject, bge.types.KX_GameObject):
	_prefix = 'DB_'

	def __init__(self, old_owner):
		self.canvas = self.find_descendant([('template', 'TextCanvas_T')])
		if self.canvas.__class__ != Text:
			self.canvas = Text(self.canvas)

		bxt.types.EventBus().addListener(self)
		bxt.types.EventBus().replayLast(self, 'ShowDialogue')

	def onEvent(self, evt):
		if evt.message == 'ShowDialogue':
			self.setText(evt.body)

	def setText(self, text):
		if text == None:
			text = ""

		if self['Content'] != text:
			self['Content'] = text
			self.canvas['Content'] = text

		if self['Content'] != text:
			if text == "":
				evt = bxt.types.Event("ResumePlay")
				bxt.types.EventBus().notify(evt)
			else:
				evt = bxt.types.Event("SuspendPlay")
				bxt.types.EventBus().notify(evt)

	@bxt.types.expose
	def clear(self):
		self['Content'] = ""
		self.canvas['Content'] = ""

class LoadingScreen(bxt.types.BX_GameObject, bge.types.KX_GameObject):
	_prefix = 'LS_'

	S_SHOW = 2
	S_HIDE = 3

	def __init__(self, old_owner):
		bxt.types.EventBus().addListener(self)
		bxt.types.EventBus().replayLast(self, 'StartLoading')
		self.set_state(LoadingScreen.S_SHOW)

	def onEvent(self, evt):
		if evt.message == 'StartLoading':
			self.set_state(LoadingScreen.S_SHOW)

	@bxt.types.expose
	def update(self):
		if HUDState().getNumLoaders() > 0:
			self.set_state(LoadingScreen.S_SHOW)
		else:
			self.set_state(LoadingScreen.S_HIDE)

class Filter(bxt.types.BX_GameObject, bge.types.KX_GameObject):
	S_HIDE = 1
	S_SHOW = 2
	
	def __init__(self, owner):
		bxt.types.EventBus().addListener(self)
		bxt.types.EventBus().replayLast(self, 'ShowFilter')

	def onEvent(self, evt):
		if evt.message == 'ShowFilter':
			self.show(evt.body)

	def show(self, colourString):
		if colourString == "" or colourString == None:
			self.visible = False
		else:
			colour = bxt.render.parse_colour(colourString)
			self.color = colour
			self.visible = True

class Indicator(bxt.types.BX_GameObject, bge.types.KX_GameObject):
	def __init__(self, old_owner):
		self.fraction = 0.0
		self.targetFraction = 0.0

		bxt.types.EventBus().addListener(self)
		bxt.types.EventBus().replayLast(self, self['event'])

	def onEvent(self, evt):
		if evt.message == self['event']:
			self.targetFraction = evt.body
			try:
				self.parent.indicatorChanged()
			except:
				print('Warning: indicator %s is not attached to a gauge.' %
						self.name)

	@bxt.types.expose
	def update(self):
		self.fraction = bxt.math.lerp(self.fraction, self.targetFraction,
			self['Speed'])
		self['Frame'] = self.fraction * 100.0

class Gauge(bxt.types.BX_GameObject, bge.types.KX_GameObject):	
	S_HIDDEN  = 1
	S_VISIBLE = 2
	S_HIDING  = 3

	def __init__(self, old_owner):
		for child in self.children:
			Indicator(child)

	def indicatorChanged(self):
		maximum = 0.0
		for child in self.children:
			if child.__class__ == Indicator:
				maximum = max(maximum, child.targetFraction)

		if maximum > 0.0:
			self.show()
		else:
			self.hide()

	def show(self):
		if not self.has_state(self.S_VISIBLE):
			self.set_state(self.S_VISIBLE)
	
	def hide(self):
		if self.has_state(self.S_VISIBLE):
			self.set_state(self.S_HIDING)

class Text(bxt.types.BX_GameObject, bge.types.KX_GameObject):
	'''
	A TextRenderer is used to render glyphs from a Font. The object nominated as
	the owner is the canvas. The canvas can be any KX_GameObject: the glyphs
	will be drawn onto the canvas' XY-plane.
	
	Canvas properties:
	str   Content:   The text to draw.
	str   Font:      The name of the font to use.
	float LineWidth  The width of the canvas in Blender units.
	
	Call render_text to draw the Content to the screen. Set Content to "" before
	rendering to clear the canvas.
	'''

	def __init__(self, old_owner):
		self.set_default_prop('Content', '')
		self.set_default_prop('colour', 'black')
		self.set_default_prop('valign', 'bottom')
		self.set_default_prop('LineWidth', 10.0)
		self.set_default_prop('Rendering', False)
		self.set_default_prop('Instant', False)
		self.set_default_prop('Font', 'Sans')
		self.lastHash = None
		self.clear()

	def clear(self):
		for child in self.children:
			child.endObject()

		self.glyphString = []
		self.delay = 0.0
		self.currentChar = 0
		self.lines = 0

	def text_to_glyphs(self, text):
		'''
		Convert a string of text into glyph tuples. Escape sequences are
		converted. E.G the string '\[foo]' will be converted into one glyph with
		the name 'foo'.
		
		Returns: a list of glyphs.
		'''

		glyphString = []
		i = 0
		while i < len(text):
			char = text[i]
			seqLen = 1
			if char == '\\':
				char, seqLen = self.decode_escape_sequence(text, i)
			glyphString.append(self.get_glyph(char))
			i = i + seqLen
		return glyphString

	def decode_escape_sequence(self, text, start):
		'''Decode an escape sequence from a string. Escape sequences begin with
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

	def get_glyph(self, char):
		'''Return the glyph tuple that matches 'char'. If no match is found, the
		'undefined' glyph is returned (typically a box).

		Returns: glyph object
		'''
		font = self.get_font()
		glyphDict = font['_glyphDict']
		try:
			return glyphDict[char]
		except KeyError:
			return glyphDict['undefined']

	def get_font(self):
		font = logic.getCurrentScene().objectsInactive[self['Font']]
		if not '_glyphDict' in font:
			self.parse_font(font)
		return font

	def parse_font(self, font):
		glyphDict = {}
		for child in font.children:
			glyphDict[child['char']] = child
		font['_glyphDict'] = glyphDict

	def find_next_breakable_char(self, glyphString, start):
		for i in range(start, len(glyphString)):
			if self.is_whitespace(glyphString[i]['char']):
				return i
		#
		# No more breakable characters.
		#
		return len(glyphString)

	def find_next_break_point(self, lineWidth, glyphString, start):
		"""Find the break point for a string of text. Always taken from
		the start of the line (only call this when starting a new
		line)."""
		totalWidth = 0.0
		for i in range(start, len(glyphString)):
			glyph = glyphString[i]
			totalWidth = totalWidth + glyph['Width']
			if totalWidth > lineWidth or glyph['char'] == 'newline':
				return i
		#
		# No break required: string is not long enough.
		#
		return len(glyphString)

	def is_whitespace(self, char):
		"""Check whether a character is whitespace. Special characters
		(like icons) are not considered to be whitespace."""
		if char == 'newline':
			return True
		elif char == ' ':
			return True
		else:
			return False

	def lay_out_text(self, glyphString):
		newLine = True
		softBreakPoint = self.find_next_breakable_char(glyphString, 0)
		hardBreakPoint = 0
		self.glyphString = []
		x = 0.0
		y = 0.0
		font = self.get_font()

		for i, glyph in enumerate(glyphString):
			width = glyph['Width']
			if newLine:
				hardBreakPoint = self.find_next_break_point(
					self['LineWidth'], glyphString, i)
				newLine = False
				self.lines += 1

			if i == softBreakPoint:
				# This glyph can have a line break before it. If the next
				# such character is beyond the end of the line, break now.
				softBreakPoint = self.find_next_breakable_char(glyphString,
					i + 1)
				if softBreakPoint > hardBreakPoint:
					newLine = True
			elif i == hardBreakPoint:
				# This glyph is beyond the end of the line. Break now.
				newLine = True

			if newLine:
				# New line; carriage return.
				x = 0.0
				y = y - font['lineHeight']
				if self.is_whitespace(glyph['char']):
					# Advance to next character.
					continue

			gx = x + glyph['xOffset']
			gy = y + glyph['yOffset']
			if self['valign'] == 'baseline':
				gy += font['baselineOffset']
			else:
				gy += font['bottomOffset']
			pos = (gx, gy)
			self.glyphString.append((glyph, width, pos))
			x += width

	def _render_next_char(self):
		if not self['Rendering']:
			return

		if self.currentChar >= len(self.glyphString):
			self['Rendering'] = False
			return

		font = self.get_font()

		glyph, width, pos = self.glyphString[self.currentChar]

		glyphInstance = logic.getCurrentScene().addObject(glyph,
			self, 0)
		glyphInstance.setParent(self)
		glyphInstance.color = bxt.render.parse_colour(self['colour'])
		glyphInstance.localPosition = [pos[0], pos[1], 0.0]

		if self['Instant']:
			bxt.utils.set_state(glyphInstance, 4)
		else:
			self.delay = (font['typingSpeed'] * width *
				glyph['DelayMultiplier'])
			bxt.utils.set_state(glyphInstance, 3)

	@bxt.types.expose
	def render_next_char(self):
		'''
		Lay out a glyph. Each glyph accumulates a delay based on its width. This
		should be called repeatedly until canvas['Rendering'] is False.
		'''
		if self.delay > 0:
			self.delay = self.delay - 1
			return

		try:
			self._render_next_char()
		finally:
			self.currentChar = self.currentChar + 1

	@bxt.types.expose
	def render(self):
		'''Render the content onto the canvas.'''

		h = hash(str(self['Content']))
		if h == self.lastHash:
			return
		self.lastHash = h

		self.clear()

		self.lay_out_text(self.text_to_glyphs(self['Content']))
		self['Rendering'] = True

		if self['Instant']:
			while self['Rendering']:
				self.render_next_char()

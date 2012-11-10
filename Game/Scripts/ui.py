#
# Copyright 2009-2012 Alex Fraser <alex@phatcore.com>
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

import time

import bge
import mathutils

import bat.bats
import bat.containers
import bat.event
import bat.render

import Scripts.inventory
import bat.impulse
import Scripts.director


class HUDState(metaclass=bat.bats.Singleton):
	def __init__(self):
		self.loaders = bat.containers.SafeSet()
		bat.event.EventBus().add_listener(self)

	def on_event(self, evt):
		if evt.message == "StartLoading":
			self.loaders.add(evt.body)
			bat.event.Event("ShowLoadingScreen", (True, None)).send()
		elif evt.message == "FinishLoading":
			self.loaders.discard(evt.body)
			if len(self.loaders) == 0:
				# Send event on next frame, to ensure shaders have been
				# compiled.
				bat.event.Event("ShowLoadingScreen", (False, None)).send(.001)


def test_input(c):
	if len(bge.logic.getSceneList()) > 1:
		c.owner.endObject()
		return

	# The owner has another controller that handles input. So we just send a
	# message so that the user input can do something useful!
	bat.event.Event('ShowDialogue', ("Ta-da! Please deliver this \[envelope] for me.",
			("Of course!", "I'm too sleepy..."))).send(5)

class DialogueBox(bat.impulse.Handler, bat.bats.BX_GameObject, bge.types.KX_GameObject):
	_prefix = 'DB_'

	# Animation layers
	L_DISPLAY = 0

	ARM_HIDE_FRAME = 1
	ARM_SHOW_FRAME = 8

	OPT_0_FRAME = 1
	OPT_1_FRAME = 3

	# States
	S_INIT = 1
	S_HIDE_UPDATE = 2
	S_SHOW_UPDATE = 3
	S_IDLE = 4

	# Time to wait before dialogue may be dismissed, in seconds per character.
	WAIT_TIME = 0.6 / 24.0

	def __init__(self, old_owner):
		self.canvas = bat.bats.mutate(self.childrenRecursive['Dlg_TextCanvas'])
		self.armature = self.childrenRecursive['Dlg_FrameArmature']
		self.frame = self.childrenRecursive['Dlg_Frame']

		self.response = self.children['ResponseBox']
		self.response_canvas = bat.bats.mutate(self.childrenRecursive['Rsp_TextCanvas'])
		self.response_armature = self.childrenRecursive['Rsp_FrameArmature']
		self.response_frame = self.childrenRecursive['Rsp_Frame']
		self.response_cursor = self.childrenRecursive['Rsp_OptionCursor']
		self.response_cursor_mesh = self.childrenRecursive['Rsp_OptionCursorMesh']
		self.button = self.childrenRecursive['Dlg_OKButton']

		self.options = None
		self.set_selected_option(None)
		self.options_time = 0
		self.options_visible = False
		self.set_state(DialogueBox.S_IDLE)

		bat.event.EventBus().add_listener(self)
		bat.event.EventBus().replay_last(self, 'ShowDialogue')

	def on_event(self, evt):
		if evt.message == 'ShowDialogue':
			if evt.body is None:
				self.hide()
			elif isinstance(evt.body, str):
				self.show(evt.body, None)
			else:
				text, options = evt.body
				self.show(text, options)

	def show(self, text, options):
		self.canvas.set_text(text)
		self.options = options
		delay = time.time() + len(text) * DialogueBox.WAIT_TIME
		self.hide_options()
		self.show_options_later(delay)

		start = self.armature.getActionFrame()
		self.armature.playAction('DialogueBoxBoing', start,
				DialogueBox.ARM_SHOW_FRAME, layer=DialogueBox.L_DISPLAY)
		self.frame.playAction('DB_FrameVis', start,
				DialogueBox.ARM_SHOW_FRAME, layer=DialogueBox.L_DISPLAY)

		# Frame is visible immediately; button is shown later.
		self.armature.setVisible(True, True)
		bat.impulse.Input().add_handler(self, 'DIALOGUE')

	def hide(self):
		self.canvas.set_text("")
		self.options = None
		self.hide_options()

		start = self.armature.getActionFrame()
		self.armature.playAction('DialogueBoxBoing', start,
			 	DialogueBox.ARM_HIDE_FRAME, layer=DialogueBox.L_DISPLAY)
		self.frame.playAction('DB_FrameVis', start,
				DialogueBox.ARM_HIDE_FRAME, layer=DialogueBox.L_DISPLAY)

		# Button is hidden immediately; frame is hidden later.
		self.button.visible = False
		# Frame is hidden at end of animation in hide_update.

		self.set_state(DialogueBox.S_HIDE_UPDATE)
		bat.impulse.Input().remove_handler(self)

	def show_options_later(self, delay):
		# Put this object into a state in which a sensor will fire every frame
		# until it's the right time to show the options.
		self.options_time = delay
		self.set_state(DialogueBox.S_SHOW_UPDATE)

	def show_options(self):
		if self.options is None:
			self.button.visible = True
			self.set_selected_option(None)
		else:
			self.set_selected_option(0)
			self.response_canvas.set_text("%s\n%s" % self.options)
			start = self.response_armature.getActionFrame()
			self.response_armature.playAction('DialogueBoxBoing', start,
					DialogueBox.ARM_SHOW_FRAME, layer=DialogueBox.L_DISPLAY)
			self.response_frame.playAction('DB_FrameVis', start,
					DialogueBox.ARM_SHOW_FRAME, layer=DialogueBox.L_DISPLAY)
			self.response_cursor_mesh.playAction('ButtonPulse', 1, 50,
					layer=DialogueBox.L_DISPLAY, play_mode=bge.logic.KX_ACTION_MODE_LOOP)
			# Frame is shown immediately.
			self.response.setVisible(True, True)
		self.options_visible = True

	def hide_options(self):
		if not self.options_visible:
			return
		self.set_selected_option(None)
		self.response_canvas.set_text("")
		start = self.response_armature.getActionFrame()
		self.response_armature.playAction('DialogueBoxBoing', start,
				DialogueBox.ARM_HIDE_FRAME, layer=DialogueBox.L_DISPLAY)
		self.response_frame.playAction('DB_FrameVis', start,
				DialogueBox.ARM_HIDE_FRAME, layer=DialogueBox.L_DISPLAY)
		self.response_cursor_mesh.stopAction(DialogueBox.L_DISPLAY)
		self.response_cursor.setVisible(False, True)
		# Frame is hidden at end of animation in hide_update.
		self.options_visible = False

	def set_selected_option(self, index):
		self.selected_option = index
		start = self.response_cursor.getActionFrame()
		if index == 1:
			end = DialogueBox.OPT_1_FRAME
		else:
			end = DialogueBox.OPT_0_FRAME
		self.response_cursor.playAction('Rsp_OptionCursorMove', start, end,
				layer=DialogueBox.L_DISPLAY)

	def can_handle_input(self, state):
		# Stop player from doing anything else while dialogue is up.
		return True

	def handle_input(self, state):
		if state.name == 'Movement':
			self.handle_movement(state)
		elif state.name == '1':
			self.handle_bt_1(state)
		elif state.name == '2':
			self.handle_bt_2(state)
		elif state.name == 'Switch':
			self.handle_switch(state)

	def handle_bt_1(self, state):
		'''Hide the dialogue, and inform listeners which option was chosen.'''
		if not self.options_visible:
			return

		if state.activated:
			bat.event.Event("DialogueDismissed", self.selected_option).send()
			self.hide()

	def handle_bt_2(self, state):
		'''Hide the dialogue, and suggest that the dialogue be skipped.'''
		if not self.options_visible:
			return

		if state.activated:
			bat.event.Event("DialogueDismissed", self.selected_option).send()
			bat.event.Event("DialogueCancelled").send()
			self.hide()

	def handle_switch(self, state):
		if state.direction > 0.1:
			self.switch_option(True)
		elif state.direction < -0.1:
			self.switch_option(False)

	def handle_movement(self, state):
		if state.direction.y > 0.1:
			self.switch_option(False)
		elif state.direction.y < -0.1:
			self.switch_option(True)

	def switch_option(self, nxt):
		if not self.options_visible or self.options is None:
			return
		# Only two options anyway.
		if nxt:
			self.set_selected_option(1)
		else:
			self.set_selected_option(0)

	@bat.bats.expose
	def show_update(self):
		if self.options_time < time.time():
			self.show_options()
			self.set_state(DialogueBox.S_IDLE)

	@bat.bats.expose
	def hide_update(self):
		if self.armature.getActionFrame() < 2:
			self.response.setVisible(False, True)
			self.armature.setVisible(False, True)
			self.set_state(DialogueBox.S_IDLE)


class Marker(bat.bats.BX_GameObject, bge.types.KX_GameObject):
	_prefix = 'Ma_'

	S_INIT = 1
	S_ACTIVE = 2
	S_INACTIVE = 3

	L_DISPLAY = 0

	target = bat.containers.weakprop("target")

	def __init__(self, old_owner):
		self.hide()

#		sce = bge.logic.getCurrentScene()
#		target = sce.objects['MarkerTest']
#		bat.event.WeakEvent('ShowMarker', target).send(5)
#		bat.event.WeakEvent('ShowMarker', None).send(200)

		bat.event.EventBus().add_listener(self)
		bat.event.EventBus().replay_last(self, 'ShowMarker')

	def on_event(self, evt):
		if evt.message == 'ShowMarker':
			print(evt)
			self.target = evt.body
			if evt.body is not None:
				self.show()
			else:
				self.hide()

	def show(self):
		self.set_state(Marker.S_ACTIVE)

	def hide(self):
		self.children['MarkerMesh'].visible = False
		self.set_state(Marker.S_INACTIVE)

	@bat.bats.expose
	def update(self):
		if self.target is None:
			self.set_state(Marker.S_INACTIVE)
			self.children['MarkerMesh'].visible = False
			return

		t_sce = bat.utils.get_scene(self.target)
		t_cam = t_sce.active_camera
		viewpos = mathutils.Vector(t_cam.getScreenPosition(self.target))
		#print("Viewpos", viewpos)

		cam = bge.logic.getCurrentScene().active_camera
		if cam.perspective:
			vec = cam.getScreenVect(viewpos.x, viewpos.y)
			#print("Vec", vec)
			pos_from = cam.worldPosition
			pos_through = pos_from - vec
		else:
			vec = cam.getAxisVect(-bat.bmath.ZAXIS)
			pos_from = viewpos.copy()
			pos_from.resize_3d()
			pos_from.x -= 0.5
			pos_from.y = (1.0 - pos_from.y) - 0.5
			aspect = (float(bge.render.getWindowWidth()) /
					float(bge.render.getWindowHeight()))
			pos_from.y /= aspect
			pos_from *= cam.ortho_scale
			pos_from = bat.bmath.to_world(cam, pos_from)
			pos_through = pos_from + vec
		#print("Ray", pos_from, pos_through)
		hitob, hitloc, _ = cam.rayCast(pos_through, pos_from, 100.0,
				"MarkerPlane", 0, 1, 0)

		#print("Hit", hitob, hitloc)
		if hitob is not None:
			self.worldPosition = hitloc
			self.children['MarkerMesh'].visible = True
		else:
			self.children['MarkerMesh'].visible = False


class LoadingScreen(bat.bats.BX_GameObject, bge.types.BL_ArmatureObject):
	_prefix = 'LS_'

	L_DISPLAY = 0

	def __init__(self, old_owner):
		# Default state (frame 1) is for everything to be shown.
		self.currently_shown = True

		# Send an event to say that loading has finished. This will trigger the
		# loading screen to hide itself, unless another object has already sent
		# a StartLoading message - in which case, we wait for that object to
		# finish loading too (see the HUDState class).
		bat.event.EventBus().add_listener(self)
		bat.event.Event("FinishLoading").send()

	def on_event(self, evt):
		if evt.message == 'ShowLoadingScreen':
			visible, cbEvent = evt.body
			self.show(visible, cbEvent)

	def show(self, visible, cbEvent):
		icon = self.children["LS_Icon"]
		blackout = self.children["LS_Blackout"]

		if visible and not self.currently_shown:
			# Show the frame immediately, but wait for the animation to finish
			# before showing the icon.
			def cb():
				if self.invalid or not self.currently_shown:
					return
				self.children["LS_Icon"].visible = True
				if cbEvent is not None:
					print("Sending delayed event", cbEvent)
					cbEvent.send(delay=2)
			blackout.visible = True
			self.playAction('LS_Hide_Arm', 16, 1, layer=LoadingScreen.L_DISPLAY)
			bat.anim.add_trigger_lt(self, LoadingScreen.L_DISPLAY, 2, cb)
			self.currently_shown = True

		elif not visible and self.currently_shown:
			# Hide the icon immediately, but wait for the animation to finish
			# before hiding the frame.
			def cb():
				if self.invalid or self.currently_shown:
					return
				self.children["LS_Blackout"].visible = False
				if cbEvent is not None:
					cbEvent.send(delay=2)
			icon.visible = False
			self.playAction('LS_Hide_Arm', 1, 16, layer=LoadingScreen.L_DISPLAY)
			bat.anim.add_trigger_gte(self, LoadingScreen.L_DISPLAY, 15, cb)
			self.currently_shown = False


class Filter(bat.bats.BX_GameObject, bge.types.KX_GameObject):
	S_HIDE = 1
	S_SHOW = 2

	def __init__(self, owner):
		bat.event.EventBus().add_listener(self)
		bat.event.EventBus().replay_last(self, 'ShowFilter')

	def on_event(self, evt):
		if evt.message == 'ShowFilter':
			self.show(evt.body)

	def show(self, colourString):
		if colourString == "" or colourString is None:
			self.visible = False
		else:
			colour = bat.render.parse_colour(colourString)
			self.color = colour
			self.visible = True


class Indicator(bat.bats.BX_GameObject, bge.types.KX_GameObject):
	def __init__(self, old_owner):
		self.fraction = 0.0
		self.targetFraction = 0.0

		bat.event.EventBus().add_listener(self)
		bat.event.EventBus().replay_last(self, self['event'])

	def on_event(self, evt):
		if evt.message == self['event']:
			self.targetFraction = evt.body
			try:
				self.parent.indicator_changed()
			except AttributeError:
				print('Warning: indicator %s is not attached to a gauge.' %
						self.name)

	@bat.bats.expose
	def update(self):
		self.fraction = bat.bmath.lerp(self.fraction, self.targetFraction,
			self['Speed'])
		frame = self.fraction * 100.0
		frame = min(max(frame, 0), 100)
		self['Frame'] = frame

#bat.event.Event("HealthSet", 1.0).send()
#bat.event.Event("OxygenSet", 1.0).send()
#bat.event.Event("TimeSet", 0.5).send()
#bat.event.Event("TimeSet", 0.0).send(50)
#bat.event.Event("TimeSet", 0.0).send(100)

__mode = 'Playing'
@bat.utils.all_sensors_positive
def test_game_mode():
	global __mode
	if __mode == 'Playing':
		__mode = 'Cutscene'
	else:
		__mode = 'Playing'
	bat.event.Event('GameModeChanged', __mode).send()

class Gauge(bat.bats.BX_GameObject, bge.types.KX_GameObject):
	S_INIT = 1
	S_VISIBLE = 2
	S_HIDING  = 3
	S_HIDDEN  = 4

	def __init__(self, old_owner):
		self.set_state(self.S_HIDDEN)
		self.force_hide = False

		for child in self.children:
			Indicator(child)

		bat.event.EventBus().add_listener(self)
		bat.event.EventBus().replay_last(self, 'GameModeChanged')

	def on_event(self, evt):
		if evt.message == 'GameModeChanged':
			self.force_hide = evt.body != 'Playing'
			self.indicator_changed()

	def indicator_changed(self):
		if self.force_hide:
			self.hide()
			return

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


class MapWidget(bat.bats.BX_GameObject, bge.types.KX_GameObject):
	_prefix = 'Map_'

	S_INIT = 1
	S_VISIBLE = 2
	S_HIDING  = 3
	S_HIDDEN  = 4

	def __init__(self, old_owner):
		self.set_state(self.S_HIDDEN)
		self.force_hide = False
		self.init_uv()
		self.scale = mathutils.Vector((100.0, 100.0))
		self.offset = mathutils.Vector((0.0, 0.0))
		self.zoom = 2.0

		bat.event.EventBus().add_listener(self)
		bat.event.EventBus().replay_last(self, 'GameModeChanged')
		bat.event.EventBus().replay_last(self, 'SetMap')

	def on_event(self, evt):
		if evt.message == 'GameModeChanged':
			if evt.body == 'Playing':
				self.show()
			else:
				self.hide()
		elif evt.message == 'SetMap':
			self.set_map(*evt.body)

	def set_map(self, file_name, scale, offset, zoom):
		'''Load a texture from an image file and display it as the map.'''
		canvas = self.children['MapPage']

		matid = bge.texture.materialID(canvas, 'MAMapPage')
		tex = bge.texture.Texture(canvas, matid)
		source = bge.texture.ImageFFmpeg(bge.logic.expandPath(file_name))

		tex.source = source
		tex.refresh(False)

		# Must be stored, or it will be freed.
		bge.logic.maptex = tex

		self.scale = scale
		self.offset = offset
		self.zoom = zoom

	@bat.bats.expose
	def update(self):
		player = Scripts.director.Director().mainCharacter
		if player is None:
			return

		pos = player.worldPosition
		orn = player.worldOrientation
		self.centre_page(pos)
		self.rotate_marker(orn)
		self.orient_horizon(orn)

	def init_uv(self):
		canvas = self.children['MapPage']

		# copy UV's to the second channel
		canvas.meshes[0].transform_uv(-1, mathutils.Matrix(), 1, 0)

	def centre_page(self, loc):
		# local copies for fast access
		zoom = self.zoom
		uv_offset = self.world_to_uv(loc.xy) * zoom
		uv_tx_neg = mathutils.Matrix.Translation((uv_offset[0] - 0.5, uv_offset[1] - 0.5, 0))
		uv_tx_pos = mathutils.Matrix.Translation((0.5, 0.5, 0))  # could make static
		uv_tx_scale = mathutils.Matrix.Scale(1.0 / zoom, 4)
		uv_tx_final = uv_tx_pos * uv_tx_scale * uv_tx_neg

		canvas = self.children['MapPage']

		# transform and copy from channel 1
		canvas.meshes[0].transform_uv(-1, uv_tx_final, 0, 1)

	def rotate_marker(self, orn):
		marker = self.children['MapDirection']
		marker.localOrientation = orn
		marker.alignAxisToVect(bat.bmath.ZAXIS)

	def orient_horizon(self, orn):
		hball = self.childrenRecursive['HorizonBall']
		hball.localOrientation = orn.inverted()

	def world_to_uv(self, loc2D):
		uvc = loc2D - self.offset
		uvc.x /= self.scale.x
		uvc.y /= self.scale.y
		return uvc

	def show(self):
		if not self.has_state(self.S_VISIBLE):
			self.set_state(self.S_VISIBLE)

	def hide(self):
		if self.has_state(self.S_VISIBLE):
			self.set_state(self.S_HIDING)


class Inventory(bat.bats.BX_GameObject, bge.types.KX_GameObject):
	'''Displays the current shells in a scrolling view on the side of the
	screen.'''

	_prefix = 'Inv_'

	FRAME_STEP = 0.5
	FRAME_EPSILON = 0.6
	FRAME_HIDE = 1.0
	FRAME_PREVIOUS = 51.0
	FRAME_CENTRE = 41.0
	FRAME_NEXT = 31.0

	BG_FRAME_SHOW = 11
	BG_FRAME_HIDE = 1

	S_UPDATING = 2
	S_IDLE = 3

	def __init__(self, old_owner):
		self.initialise_icon_pool()

		self.update_icons()
		self.hide()
		bat.event.EventBus().add_listener(self)
		bat.event.EventBus().replay_last(self, 'GameModeChanged')

	def on_event(self, evt):
		if evt.message == 'ShellChanged':
			if evt.body == 'new':
				self.update_icons()
			elif evt.body == 'next':
				self['targetFrame'] = Inventory.FRAME_NEXT
				self.set_state(Inventory.S_UPDATING)
			elif evt.body == 'previous':
				self['targetFrame'] = Inventory.FRAME_PREVIOUS
				self.set_state(Inventory.S_UPDATING)

		elif evt.message == 'GameModeChanged':
			if evt.body == 'Playing':
				self.show()
			else:
				self.hide()

	def show(self):
		self['targetFrame'] = Inventory.FRAME_CENTRE
		self.set_state(Inventory.S_UPDATING)

		background = self.scene.objects['I_Background']
		cfra = background.getActionFrame()
		background.playAction('I_BackgroundAction', cfra,
				Inventory.BG_FRAME_SHOW)

	def hide(self):
		self['targetFrame'] = Inventory.FRAME_HIDE
		self.set_state(Inventory.S_UPDATING)

		background = self.scene.objects['I_Background']
		cfra = background.getActionFrame()
		background.playAction('I_BackgroundAction', cfra,
				Inventory.BG_FRAME_HIDE)

	def set_item(self, index, shellName):
		hook = self.children['I_IconHook_' + str(index)]
		for icon in hook.children:
			self.release_icon(icon)

		if shellName is not None:
			icon = self.claim_icon(shellName)
			icon.setParent(hook)
			icon.localScale = (1.0, 1.0, 1.0)
			icon.localPosition = (0.0, 0.0, 0.0)
			icon.localOrientation.identity()

	def update_icons(self):
		equipped = Scripts.inventory.Shells().get_equipped()
		self.set_item(0, equipped)
		if equipped is None or len(Scripts.inventory.Shells().get_shells()) > 1:
			# Special case: if nothing is equipped, we still want to draw icons
			# for the next and previous shell - even if there is only one shell
			# remaining in the inventory.
			self.set_item(-2, Scripts.inventory.Shells().get_next(-2))
			self.set_item(-1, Scripts.inventory.Shells().get_next(-1))
			self.set_item(1, Scripts.inventory.Shells().get_next(1))
			self.set_item(2, Scripts.inventory.Shells().get_next(2))
		else:
			self.set_item(-2, None)
			self.set_item(-1, None)
			self.set_item(1, None)
			self.set_item(2, None)

	@bat.bats.expose
	def update_frame(self):
		if self['targetFrame'] > self['frame'] + Inventory.FRAME_EPSILON:
			self['frame'] += Inventory.FRAME_STEP
		elif self['targetFrame'] < self['frame'] - Inventory.FRAME_EPSILON:
			self['frame'] -= Inventory.FRAME_STEP
		elif not self['targetFrame'] == Inventory.FRAME_HIDE:
			self.update_icons()
			self['frame'] = self['targetFrame'] = Inventory.FRAME_CENTRE
			self.set_state(Inventory.S_IDLE)

	def initialise_icon_pool(self):
		'''Pre-create flyweight icons.'''
		pool = self.children['I_IconPool']
		for shellName in Scripts.inventory.Shells.SHELL_NAMES:
			for _ in range(5):
				icon = bge.logic.getCurrentScene().addObject(
						'Icon_%s_static' % shellName, pool)
				icon.setParent(pool)
				icon.localScale = (0.1, 0.1, 0.1)

	def claim_icon(self, shellName):
		pool = self.children['I_IconPool']
		icon = pool.children['Icon_%s_static' % shellName]
		icon.visible = True
		return icon

	def release_icon(self, icon):
		pool = self.children['I_IconPool']
		icon.setParent(pool)
		icon.localScale = (0.1, 0.1, 0.1)
		icon.localPosition = (0.0, 0.0, 0.0)
		icon.localOrientation.identity()
		icon.visible = False


class Text(bat.bats.BX_GameObject, bge.types.KX_GameObject):
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
		self.textwidth = 0.0
		self.textheight = 0.0
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
			elif char == '\n':
				# Literal newline.
				char = 'newline'
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
			# Escaped newline.
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
		font = bge.logic.getCurrentScene().objectsInactive[self['Font']]
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
		totalwidth = 0.0

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
			if x > totalwidth:
				totalwidth = x

		totalheight = -y + font['lineHeight']
		self.textwidth = totalwidth
		self.textheight = totalheight

	def _render_next_char(self):
		if not self['Rendering']:
			return

		if self.currentChar >= len(self.glyphString):
			self['Rendering'] = False
			return

		font = self.get_font()

		glyph, width, pos = self.glyphString[self.currentChar]

		glyphInstance = bge.logic.getCurrentScene().addObject(glyph,
			self, 0)
		glyphInstance.setParent(self)
		glyphInstance['StartVisible'] = self.visible
		glyphInstance.color = bat.render.parse_colour(self['colour'])
		glyphInstance.localPosition = [pos[0], pos[1], 0.0]

		if self['Instant']:
			bat.utils.set_state(glyphInstance, 4)
		else:
			self.delay = (font['typingSpeed'] * width *
				glyph['DelayMultiplier'])
			bat.utils.set_state(glyphInstance, 3)

	def set_text(self, text):
		self['Content'] = text

	def get_text(self):
		return self['Content']

	@bat.bats.expose
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

	@bat.bats.expose
	def render(self):
		'''
		Render the content onto the canvas. This is idempotent if the content
		hasn't changed.
		'''

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

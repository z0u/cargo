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

import Utilities
from Blender import Mathutils

MIN_VOLUME = 0.01

def PlayWithRandomPitch(c):
	'''
	Play a sound with a random pitch. The pitch range is defined by the
	controller's owner using the properties PitchMin and PitchMax.
	
	Sensors:
	<one>:  If positive and triggered, a sound will be played.
	
	Actuators:
	<one+>: Each will be played in turn.
	
	Controller properties:
	PitchMin: The minimum pitch (float).
	PitchMax: The maximum pitch (float).
	'''
	s = c.sensors[0]
	if not s.triggered or not s.positive:
		return
	o = c.owner
	
	#
	# Select an actuator.
	#
	a = c.actuators[o['SoundActIndex']]
	o['SoundActIndex'] = (o['SoundActIndex'] + 1) % len(c.actuators)
	
	#
	# Set the pitch and activate!
	#
	a.pitch = Utilities._lerp(o['PitchMin'], o['PitchMax'], Utilities.Random.next())
	c.activate(a)

def Fade(c, maxVolume = 1.0):
	'''
	Causes a sound to play a long as its inputs are active. On activation, the
	sound fades in; on deactivation, it fades out. The fade rate is determined
	by the owner's SoundFadeFac property (0.0 <= SoundFadeFac <= 1.0).
	
	Sensors:
	sAlways:  Fires every frame to provide the fading effect.
	<one+>:   If any are positive, the sound will turn on. Otherwise the sound
	          will turn off.
	
	Actuators:
	<one>:    A sound actuator.
	
	Controller properties:
	VolumeMult:    The maximum volume (as speed approaches infinity) (float).
	SoundFadeFac:  The response factor for the volume (float).
	'''
	o = c.owner
	maxVolume = maxVolume * o['VolumeMult']
	
	targetVolume = 0.0
	for s in c.sensors:
		if s.name == "sAlways":
			continue
		if s.positive:
			targetVolume = maxVolume
			break
	
	a = c.actuators[0]
	a.volume = Utilities._lerp(a.volume, targetVolume, o['SoundFadeFac'])
	if a.volume > MIN_VOLUME:
		c.activate(a)
	else:
		c.deactivate(a)

def ModulateByAngV(c):
	'''
	Change the pitch and volume of the sound depending on the angular velocity
	of the controller's owner.
	
	Sensors:
	sAlways:  Fires every frame to provide the fading effect.
	<others>: At least one other. If any are positive, the sound will turn on.
	          Otherwise the sound will turn off.
	
	Actuators:
	<one>:    A sound actuator.
	
	Controller properties:
	SoundModScale: The rate at which the pitch increases (float).
	PitchMin:      The minimum pitch (when speed = 0) (float).
	PitchMax:      The maximum pitch (as speed approaches infinity) (float).
	VolumeMult:    The maximum volume (as speed approaches infinity) (float).
	SoundFadeFac:  The response factor for the volume (float).
	'''
	o = c.owner
	angV = Mathutils.Vector(o.getAngularVelocity(False))
	speed = angV.magnitude
	
	factor = 0.0
	if speed > 0.0:
		#
		# To visualise this function, try it in gnuplot:
		# f(speed, a) =  1.0 - (1.0 / ((speed + (1.0 / a)) * a))
		# plot [0:100] f(x, 0.5)
		#
		a = o['SoundModScale']
		factor = 1.0 - (1.0 / ((speed + (1.0 / a)) * a))
	
	a = c.actuators[0]
	a.pitch = Utilities._lerp(o['PitchMin'], o['PitchMax'], factor)
	
	Fade(c, factor)
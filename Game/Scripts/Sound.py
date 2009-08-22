import Utilities

MIN_VOLUME = 0.01

def PlayWithRandomPitch(c):
	'''
	Play a sound with a random pitch. The pitch range is defined by the
	controller's owner using the properties PitchMin and PitchMax.
	
	Parameters:
	c: A python controller. The controller must have exactly one (sound)
	   actuator attached to it. The owning object of the controller must have
	   the properties PitchMin and PitchMax (floats).
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
	print "Playing with pitch %f" % a.pitch
	c.activate(a)

def Fade(c):
	'''
	Causes a sound to play a long as its inputs are active. On activation, the
	sound fades in; on deactivation, it fades out. The fade rate is determined
	by the owner's SoundFadeFac property (0.0 <= SoundFadeFac <= 1.0).
	
	Parameters:
	c: A python controller. The controller must have exactly one (sound)
	   actuator attached to it. It must have one sensor called 'sAlways' that
	   fires every frame (to provide the fade effect), and any number of other
	   sensors. If any of the other sensors is positive, the sound will play.
	'''
	targetVolume = 0.0
	for s in c.sensors:
		if s.name == "sAlways":
			continue
		if s.positive:
			targetVolume = 1.0
			break
	
	a = c.actuators[0]
	a.volume = Utilities._lerp(a.volume, targetVolume, c.owner['SoundFadeFac'])
	if a.volume > MIN_VOLUME:
		c.activate(a)
	else:
		c.deactivate(a)

import Utilities

MIN_VOLUME = 0.01

def Fade(c):
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

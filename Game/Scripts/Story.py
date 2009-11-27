
import Actor

class StoryCharacter(Actor.Actor):

	def __init__(self, owner):
		Actor.Actor.__init__(self, owner)
		self.NextStep = 0
		
		stepNames = []
		for attr in dir(self):
			if not callable(getattr(self, attr)):
				continue
			if attr.startswith('StoryStep'):
				stepNames.append(attr)
		stepNames.sort()
		self.Steps = [getattr(self, name) for name in stepNames]

	def Progress(self, controller):
		if self.NextStep >= len(self.Steps):
			return
		step = self.Steps[self.NextStep]
		if step(controller):
			self.NextStep = self.NextStep + 1
	
	#def StoryStepN(self, controller):
	#	trigger animation
	#	if trigger was successful:
	#		return true
	#	else:
	#		return false
	
	def SetActionPair(self, aArm, aMesh, actionPrefix, start, end, current):
		aArm.action = actionPrefix
		aMesh.action = actionPrefix + '_S'
		
		aArm.frameStart = aMesh.frameStart = start
		aArm.frameEnd = aMesh.frameEnd = end
		aArm.frame = aMesh.frame = current

def Progress(c):
	character = c.owner['Actor']
	character.Progress(c)

class Worm(StoryCharacter):
	def StoryStep1(self, c):
		s = c.sensors['sReturn']
		if s.positive and s.triggered:
			print "StoryStep1"
			aArm = c.actuators['aArmature']
			aMesh = c.actuators['aMesh']
			self.SetActionPair(aArm, aMesh, 'BurstOut', 1.0, 240.0, 1.0)
			c.activate(aArm)
			c.activate(aMesh)
			
			return True
		return False
		
	def StoryStep2(self, c):
		s = c.sensors['sReturn']
		if s.positive and s.triggered and self.Owner['ActionFrame'] >= 240.0:
			print "StoryStep2"
			return True
		return False

def CreateWorm(c):
	worm = Worm(c.owner)


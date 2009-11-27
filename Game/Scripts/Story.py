
import Actor
import UI

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
	
	def SetActionPair(self, c, aArmName, aMeshName, actionPrefix, start, end, current):
		aArm = c.actuators[aArmName]
		aMesh = c.actuators[aMeshName]
		aArm.action = actionPrefix
		aMesh.action = actionPrefix + '_S'
		
		aArm.frameStart = aMesh.frameStart = start
		aArm.frameEnd = aMesh.frameEnd = end
		aArm.frame = aMesh.frame = current
		
		c.activate(aArm)
		c.activate(aMesh)

def Progress(c):
	character = c.owner['Actor']
	character.Progress(c)

class Worm(StoryCharacter):
	def StoryStep1(self, c):
		s = c.sensors['sReturn']
		if s.positive and s.triggered:
			self.SetActionPair(c, 'aArmature', 'aMesh', 'BurstOut', 1.0, 75.0, 1.0)
			return True
		return False
		
	def StoryStep2(self, c):
		if self.Owner['ActionFrame'] >= 75.0:
			UI.HUD.ShowDialogue("Cargo?")
			return True
		return False
		
	def StoryStep3(self, c):
		s = c.sensors['sReturn']
		if s.positive and s.triggered:
			UI.HUD.HideDialogue()
			self.SetActionPair(c, 'aArmature', 'aMesh', 'BurstOut', 75, 240.0, 1.0)
			return True
		return False
		
	def StoryStep4(self, c):
		if self.Owner['ActionFrame'] >= 240.0:
			UI.HUD.ShowDialogue("Wake up, Cargo! I need you to deliver this letter for me.")
			return True
		return False
	
	def StoryStep5(self, c):
		s = c.sensors['sReturn']
		if s.positive and s.triggered:
			UI.HUD.HideDialogue()
			return True
		return False

def CreateWorm(c):
	worm = Worm(c.owner)


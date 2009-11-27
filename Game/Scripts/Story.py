
import Actor
import UI
import GameLogic
import Camera

#
# Step progression conditions. These determine whether a step may execute.
#
class CondSensor:
	def __init__(self, name):
		self.Name = name
	
	def Evaluate(self, c):
		s = c.sensors[self.Name]
		return s.positive and s.triggered

class CondPropertyGE:
	def __init__(self, name, value):
		self.Name = name
		self.Value = value
	
	def Evaluate(self, c):
		return c.owner[self.Name] >= self.Value

#
# Actions. These belong to and are executed by steps.
#
class ActGeneric:
	def __init__(self, f, *closure):
		self.Function = f
		self.Closure = closure
	
	def Execute(self, c):
		self.Function(*self.Closure)

class ActSuspend:
	def Execute(self, c):
		Actor.SuspendAction()

class ActResume:
	def Execute(self, c):
		Actor.ResumeAction()

class ActActionPair:
	def __init__(self, aArmName, aMeshName, actionPrefix, start, end):
		self.aArmName = aArmName
		self.aMeshName = aMeshName
		self.ActionPrefix = actionPrefix
		self.Start = start
		self.End = end
		
	def Execute(self, c):
		aArm = c.actuators[self.aArmName]
		aMesh = c.actuators[self.aMeshName]
		aArm.action = self.ActionPrefix
		aMesh.action = self.ActionPrefix + '_S'
		
		aArm.frameStart = aMesh.frameStart = self.Start
		aArm.frameEnd = aMesh.frameEnd = self.End
		aArm.frame = aMesh.frame = self.Start
		
		c.activate(aArm)
		c.activate(aMesh)

class ActShowDialogue:
	def __init__(self, message):
		self.Message = message
	
	def Execute(self, c):
		UI.HUD.ShowDialogue(self.Message)

class ActHideDialogue:
	def Execute(self, c):
		UI.HUD.HideDialogue()

class ActSetCamera:
	def __init__(self, camName, fac = None, instantCut = False):
		self.CamName = camName
		self.InstantCut = instantCut
		self.Fac = fac
	
	def Execute(self, c):
		try:
			cam = GameLogic.getCurrentScene().objects['OB' + self.CamName]
		except KeyError:
			print ("Warning: couldn't find camera %s. Not adding." %
				self.CamName)
			return
		Camera.AutoCamera.AddGoal(cam, True, self.Fac, self.InstantCut)

class ActRemoveCamera:
	def __init__(self, camName):
		self.CamName = camName
	
	def Execute(self, c):
		try:
			cam = GameLogic.getCurrentScene().objects['OB' + self.CamName]
		except KeyError:
			print ("Warning: couldn't find camera %s. Not removing." %
				self.CamName)
			return
		Camera.AutoCamera.RemoveGoal(cam)

#
# Steps. These are executed by Characters when their conditions are met and they
# are at the front of the queue.
#
class Step:
	def __init__(self):
		self.Conditions = []
		self.Actions = []
	
	def AddAction(self, action):
		self.Actions.append(action)
	
	def AddCondition(self, cond):
		self.Conditions.append(cond)
	
	def CanExecute(self, c):
		for condition in self.Conditions:
			if not condition.Evaluate(c):
				return False
		return True
	
	def Execute(self, c):
		for act in self.Actions:
			act.Execute(c)

class Character(Actor.Actor):

	def __init__(self, owner):
		Actor.Actor.__init__(self, owner)
		self.NextStep = 0
		self.Steps = []
	
	def NewStep(self):
		step = Step()
		self.Steps.append(step)
		return step

	def Progress(self, controller):
		if self.NextStep >= len(self.Steps):
			return
		step = self.Steps[self.NextStep]
		if step.CanExecute(controller):
			step.Execute(controller)
			self.NextStep = self.NextStep + 1

def Progress(c):
	character = c.owner['Actor']
	character.Progress(c)

def CreateWorm(c):
	worm = Character(c.owner)

	cam1 = 'WormCam1'
	cam2 = 'WormCam2'

	step = worm.NewStep()
	step.AddCondition(CondSensor('sReturn'))
	step.AddAction(ActSetCamera(cam1))
	step.AddAction(ActSuspend())
	step.AddAction(ActActionPair('aArmature', 'aMesh', 'BurstOut', 1.0, 75.0))
	
	step = worm.NewStep()
	step.AddCondition(CondPropertyGE('ActionFrame', 75.0))
	step.AddAction(ActShowDialogue("Cargo?"))
	
	step = worm.NewStep()
	step.AddCondition(CondSensor('sReturn'))
	step.AddAction(ActHideDialogue())
	step.AddAction(ActActionPair('aArmature', 'aMesh', 'BurstOut', 75.0, 240.0))
	
	step = worm.NewStep()
	step.AddCondition(CondPropertyGE('ActionFrame', 240.0))
	step.AddAction(ActShowDialogue("Wake up, Cargo! I need you to deliver this letter for me."))
	
	step = worm.NewStep()
	step.AddCondition(CondSensor('sReturn'))
	step.AddAction(ActResume())
	step.AddAction(ActHideDialogue())
	step.AddAction(ActRemoveCamera(cam1))


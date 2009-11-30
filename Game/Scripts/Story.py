
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
class ActSuspendInput:
	def Execute(self, c):
		Actor.Director.SuspendUserInput()

class ActResumeInput:
	def Execute(self, c):
		Actor.Director.ResumeUserInput()

class ActActionPair:
	def __init__(self, aArmName, aMeshName, actionPrefix, start, end, loop = False):
		self.aArmName = aArmName
		self.aMeshName = aMeshName
		self.ActionPrefix = actionPrefix
		self.Start = start
		self.End = end
		self.Loop = loop
		
	def Execute(self, c):
		aArm = c.actuators[self.aArmName]
		aMesh = c.actuators[self.aMeshName]
		aArm.action = self.ActionPrefix
		aMesh.action = self.ActionPrefix + '_S'
		
		aArm.frameStart = aMesh.frameStart = self.Start
		aArm.frameEnd = aMesh.frameEnd = self.End
		aArm.frame = aMesh.frame = self.Start
		
		if self.Loop:
			aArm.mode = aMesh.mode = GameLogic.KX_ACTIONACT_LOOPEND
		else:
			aArm.mode = aMesh.mode = GameLogic.KX_ACTIONACT_PLAY
		
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

class ActGeneric:
	def __init__(self, f, *closure):
		self.Function = f
		self.Closure = closure
	
	def Execute(self, c):
		self.Function(*self.Closure)

class ActGenericContext(ActGeneric):
	def Execute(self, c):
		self.Function(c, *self.Closure)

class ActDebug:
	def __init__(self, message):
		self.Message = message
	
	def Execute(self, c):
		print self.Message

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
	def SleepSnail(c, animate):
		snail = c.sensors['sNearSnail'].hitObject['Actor']
		snail.enterShell(animate)
	
	def WakeSnail(c, animate):
		snail = c.sensors['sNearSnail'].hitObject['Actor']
		snail.exitShell(animate)
	
	worm = Character(c.owner)
	
	step = worm.NewStep()
	step.AddAction(ActShowDialogue("Press Return to start."))
	
	step = worm.NewStep()
	step.AddCondition(CondSensor('sReturn'))
	step.AddAction(ActHideDialogue())
	step.AddAction(ActGeneric(UI.HUD.HideLoadingScreen))
	
	step = worm.NewStep()
	step.AddCondition(CondSensor('sReturn'))
	step.AddAction(ActSetCamera('WormCamera0'))
	step.AddAction(ActSuspendInput())
	step.AddAction(ActGenericContext(SleepSnail, False))
	step.AddAction(ActActionPair('aArmature', 'aMesh', 'BurstOut', 1.0, 75.0))
	
	step = worm.NewStep()
	step.AddCondition(CondPropertyGE('ActionFrame', 75.0))
	step.AddAction(ActShowDialogue("Cargo?"))
	
	step = worm.NewStep()
	step.AddCondition(CondSensor('sReturn'))
	step.AddAction(ActHideDialogue())
	step.AddAction(ActRemoveCamera('WormCamera0'))
	step.AddAction(ActSetCamera('WormCamera1'))
	step.AddAction(ActActionPair('aArmature', 'aMesh', 'BurstOut', 75.0, 180.0))
	
	step = worm.NewStep()
	step.AddCondition(CondPropertyGE('ActionFrame', 180.0))
	step.AddAction(ActShowDialogue("Wake up, Cargo!"))
	step.AddAction(ActActionPair('aArmature', 'aMesh', 'BurstOut', 181.0, 197.0, True))
	
	step = worm.NewStep()
	step.AddCondition(CondSensor('sReturn'))
	step.AddAction(ActActionPair('aArmature', 'aMesh', 'BurstOut', 181.0, 240.0))
	
	step = worm.NewStep()
	step.AddCondition(CondPropertyGE('ActionFrame', 205.0))
	step.AddAction(ActGenericContext(WakeSnail, True))
	step.AddAction(ActShowDialogue("Sleeping in, eh? Don't worry, I won't tell anyone."))
	
	step = worm.NewStep()
	step.AddCondition(CondSensor('sReturn'))
	step.AddAction(ActShowDialogue("Please deliver this letter to the lighthouse keeper."))
	
	step = worm.NewStep()
	step.AddCondition(CondSensor('sReturn'))
	step.AddAction(ActResumeInput())
	step.AddAction(ActHideDialogue())
	step.AddAction(ActRemoveCamera('WormCamera1'))


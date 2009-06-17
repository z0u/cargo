import Actor

class Shell(Actor.Actor):
	def __init__(self, owner, cameraGoal):
		Actor.Actor.__init__(self, owner)
		self.Snail = None
		self.CameraGoal = cameraGoal
	
	def CanSuspend(self):
		'''Only suspend if this shell is currently dynamic.
		No attached snail -> Dynamic.
		Being carried by snail -> Not dynamic.
		Occupied by snail -> Dynamic.'''
		if self.Owner['Carried']:
			return False
		elif self.Owner['Occupied']:
			return True
		else:
			return True
	
	def OnPickedUp(self, snail):
		'''Called when a snail picks up this shell.'''
		self.Snail = snail
		self.Owner['Carried'] = True
		self.Owner.state = 1<<2 # state 3
	
	def OnDropped(self):
		'''Called when a snail drops this shell.'''
		self.Snail = None
		self.Owner['Carried'] = False
		self.Owner.state = 1<<1 # state 2
	
	def OnPreEnter(self):
		'''Called when the snail starts to enter this shell
		(seveal frames before control is passed).'''
		#
		# Set a new goal for the camera, initialised to the
		# current camera position.
		#
		activeCam = self.Snail.Camera.Camera
		self.CameraGoal.worldPosition = activeCam.worldPosition
		self.CameraGoal.worldOrientation = activeCam.worldOrientation
		self.Snail.Camera.PushGoalParent(self.CameraGoal, fac = self.CameraGoal['SlowFac'])
		self.CameraGoal.state = 1<<1 # state 2
	
	def OnEntered(self):
		'''Called when a snail enters this shell (just after
		control is transferred).'''
		self.Owner.state = 1<<3 # state 4
	
	def OnExited(self):
		'''Called when a snail exits this shell (just after
		control is transferred).'''
		self.Owner.state = 1<<2 # state 3
	
	def OnPostExit(self):
		'''Called when the snail has finished its exit shell
		animation.'''
		self.Snail.Camera.PopGoalParent()
		self.CameraGoal.state = 1<<0 # state 1

def CreateShell(c):
	cameraGoal = c.sensors['sCameraGoal'].owner
	Shell(c.owner, cameraGoal)

def CreateNut(c):
	cameraGoal = c.sensors['sCameraGoal'].owner
	Shell(c.owner, cameraGoal)

def CreateWheel(c):
	cameraGoal = c.sensors['sCameraGoal'].owner
	Shell(c.owner, cameraGoal)

class BottleCap(Shell):
	def Drown(self, water):
		return False

def CreateBottleCap(c):
	cameraGoal = c.sensors['sCameraGoal'].owner
	BottleCap(c.owner, cameraGoal)

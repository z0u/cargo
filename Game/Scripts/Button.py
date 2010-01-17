import GameLogic
import Mathutils
import Utilities

class Button:
	def __init__(self, owner):
		self.Owner = owner
		owner['Button'] = self
		self.Down = False
		Utilities.SceneManager.Subscribe(self)
	
	def OnSceneEnd(self):
		self.Owner['Button'] = None
		self.Owner = None
		Utilities.SceneManager.Unsubscribe(self)

	def Accept(self, ob):
		return True

	def OnTouched(self, obsTouch, obsReset):
		down = False
		
		obs = set(obsTouch)
		if self.Down:
			obs.update(obsReset)
		
		for ob in obs:
			if self.Accept(ob):
				down = True
				break
		
		if self.Down == down:
			return
		
		self.Down = down
		if down:
			self.OnDown()
		else:
			self.OnUp()
	
	def OnUp(self):
		print 'ButtonUp'
		GameLogic.sendMessage('ButtonUp')
	
	def OnDown(self):
		print 'ButtonDown'
		GameLogic.sendMessage('ButtonDown')

class ToughButton(Button):
	def Accept(self, ob):
		vel = Mathutils.Vector(ob.getLinearVelocity())
		print vel.magnitude 
		return vel.magnitude >= self.Owner['MinSpeed']

def CreateButton(c):
	Button(c.owner)

def CreateToughButton(c):
	ToughButton(c.owner)

def OnTouched(c):
	s1 = c.sensors['sTouch']
	s2 = c.sensors['sTouchReset']
	c.owner['Button'].OnTouched(s1.hitObjectList, s2.hitObjectList)


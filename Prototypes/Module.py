def Init(cont):
	print "Init called"
	print cont.owner
	cont.owner['Foo'] = [1,2,3,4]

def Foo(cont):
	print "Foo called"
	print cont.owner['Foo']

print "Module loaded"
print

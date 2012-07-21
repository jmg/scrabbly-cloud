from juggernaut import Juggernaut


class RealTimeService(object):

    jug = Juggernaut()

    def publish(self, event, data):

    	try:
        	self.jug.publish(event, data)
        except:
        	pass

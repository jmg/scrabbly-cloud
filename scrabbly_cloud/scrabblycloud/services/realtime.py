from juggernaut import Juggernaut
from settings import ENABLE_REAL_TIME


class RealTimeService(object):

    jug = Juggernaut()

    def publish(self, event, data):

    	if not ENABLE_REAL_TIME:
    		return 
    		
    	try:
        	self.jug.publish(event, data)
        except:
        	pass

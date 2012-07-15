from juggernaut import Juggernaut


class RealTimeService(object):

    jug = Juggernaut()

    def publish(self, event, data):

        self.jug.publish(event, data)

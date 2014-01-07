# MQTTBrokerNodes model - produced from XML source

import types, time, logging

from . import topics

from .MQTTSubscriptionEngines import MQTTSubscriptionEngines
 
class MQTTBrokerNodes:

  def __init__(self):
    self.se = MQTTSubscriptionEngines()
    self.__clients = {}
    self.__publications = {} # for those that can't be delivered immediately
    self.__wills = {}

  def getClients(self):
    return self.__clients

  def reinit(self):
    self.__init__()

  def cleanSession(self, aClientid):
    "clear any outstanding subscriptions and publications"
    self.se.clearSubscriptions(aClientid)
    if aClientid in self.__publications.keys():
      del self.__publications[aClientid]

  def __sendQueued__(self, aClient):
     # if we have queued publications, send them
     if aClient.id in self.__publications.keys():
       for p in self.__publications[aClient.id]:
         self.__clients[aClient.id][3].publishArrived(p[0], p[1], p[2])
       del self.__publications[aClient.id]

  def connect(self, aClient, cleanstart=True):
    if aClient.id in self.__clients.keys() and self.__clients[aClient.id][2]:
      logging.info("[MQTT-3.1.0-2] Second connect packet")
      raise Exception("[MQTT-3.1.0-2] Second connect packet")
    self.__clients[aClient.id] = [cleanstart, time.clock(), True, aClient]
    if cleanstart:
      self.cleanSession(aClient.id)
    else:
      self.__sendQueued__(aClient)
      #if aClient.id in self.__publications.keys():
      #  for p in self.__publications[aClient.id]:
      #    self.__clients[aClient.id][3].publishArrived(p[0], p[1], p[2])
      #  del self.__publications[aClient.id]

  def connectWill(self, aClient, cleanstart,
                        willtopic, willQoS, willmsg, willRetain):
    self.__wills[aClient.id] = (willtopic, willQoS, willmsg, willRetain)
    self.connect(aClient, cleanstart)

  def terminate(self, aClientid):
    "Abrupt disconnect which also causes a will msg to be sent out"
    if aClientid in self.__clients.keys() and self.__clients[aClientid][2]:
      self.disconnect(aClientid)
      if aClientid in self.__wills.keys():
        willtopic, willQoS, willmsg, willRetain = self.__wills[aClientid]
        self.publish(aClientid, willtopic, willmsg, willQoS, willRetain)

  def disconnect(self, aClientid):
   if aClientid in self.__clients.keys():
     self.__clients[aClientid][3].connected = False
     if self.__clients[aClientid][0]: # cleanstart
       self.cleanSession(aClientid)
       del self.__clients[aClientid]
     else:
       self.__clients[aClientid][1] = time.clock()
       self.__clients[aClientid][2] = False # set to disconnected

  def disconnectAll(self):
    for c in self.__clients.keys()[:]:
      self.disconnect(c)

  def publish(self, aClientid, topic, message, qos, retained=False):
    """publish to all subscribed connected clients
       also to any disconnected non-cleanstart clients with qos in [1,2]
    """
    if retained:
      self.se.setRetained(topic, message, qos)
    for c in self.se.subscribers(topic):  # all subscribed clients
      # qos is lower of publication and subscription
      thisqos = []
      for x in self.se.qosOf(c, topic):
        if min(x, qos) not in thisqos:
          thisqos.append(min(x, qos))
      if c in self.__clients.keys() and self.__clients[c][2]: # is connected?
        #if rule.properties["OVERLAPPING_QOS"] == "MULTIPLE":
        #  for q in thisqos:
        #    self.__clients[c][3].publishArrived(topic, message, [q])
        #else:
        self.__clients[c][3].publishArrived(topic, message, thisqos)
      else:
        if 1 in thisqos or 2 in thisqos:
          #if rule.properties["OVERLAPPING_QOS"] == "MULTIPLE":
          #  if 0 in thisqos:
          #    thisqos.remove(0) # only qos 1 and 2 are persisted
          #  for q in thisqos:
          #    if c not in self.__publications.keys():
          #      self.__publications[c] = [(topic, message, [q])]
          #    else:
          #      self.__publications[c].append((topic, message, [q]))
          #else:
          if c not in self.__publications.keys():
            self.__publications[c] = [(topic, message, thisqos)]
          else:
            self.__publications[c].append((topic, message, thisqos))

  def __doRetained__(self, aClientid, topic, qos):
    if type(topic) != type([]):
      topic = [topic]
      qos = [qos]
    i = 0
    for t in topic: # t is a wildcard subscription topic
      topicsUsed = []
      for s in self.se.retainedTopics(): # s is a non-wildcard retained topic
        if s not in topicsUsed and topics.topicMatches(t, s):
          # topic has retained publication
          topicsUsed.append(s)
          (ret_msg, ret_qos) = self.se.retained(s)
          thisqos = min(ret_qos, qos[i])
          self.__clients[aClientid][3].publishArrived(s, ret_msg, [thisqos], True)
      i += 1

  def subscribe(self, aClientid, topic, qos):
    "send out retained publications"
    rc = self.se.subscribe(aClientid, topic, qos)
    self.__doRetained__(aClientid, topic, qos)
    #i = 0
    #for t in topic: # t is a wildcard subscription topic
    #  topicsUsed = []
    #  for s in self.se.retainedTopics(): # s is a non-wildcard retained topic
    #    if s not in topicsUsed and topics.topicMatches(t, s):
    #      # topic has retained publication
    #      topicsUsed.append(s)
    #      (ret_msg, ret_qos) = self.se.retained(s)
    #      thisqos = min(ret_qos, qos[i])
    #      self.__clients[aClientid][3].publishArrived(s, ret_msg, [thisqos], True)
    #  i += 1
    return rc

  def unsubscribe(self, aClientid, topic):
    self.se.unsubscribe(aClientid, topic)

  def subscriptions(self, aClientid=None):
    return self.se.subscriptions(aClientid)
 
if __name__ == "__main__":
  bn = MQTTBrokerNodes()

  class Clients:

    def __init__(self, anId):
     self.id = anId # required
     self.msgqueue = []

    def publishArrived(self, topic, msg, qos, retained=False):
      "required by broker node class"
      logging.debug(self.id, "publishArrived", repr((topic, msg, qos, retained)))
      self.msgqueue.append((topic, msg, qos))

  Client1 = Clients("Client1")

  bn.connect(Client1, False)
  bn.subscribe(Client1.id, "topic1", 1)
  bn.publish(Client1.id, "topic1", "message 1", 1)

  assert Client1.msgqueue.pop(0) == ("topic1", "message 1", [1])

  bn.publish(Client1.id, "topic2", "message 2", 1, retained=True)
  bn.subscribe(Client1.id, "topic2", 2)

  assert Client1.msgqueue.pop(0) == ("topic2", "message 2", [1])

  bn.subscribe(Client1.id, "#", 2)
  assert Client1.msgqueue.pop(0) == ("topic2", "message 2", [1])

  bn.subscribe(Client1.id, "#", 0)
  assert Client1.msgqueue.pop(0) == ("topic2", "message 2", [0])
  bn.unsubscribe(Client1.id, "#")

  bn.publish(Client1.id, "topic2/next", "message 3", 2, retained=True)
  bn.publish(Client1.id, "topic2/blah", "message 4", 1, retained=True)
  bn.subscribe(Client1.id, "topic2/+", 2)
  logging.debug(Client1.msgqueue)
  msg1 = Client1.msgqueue.pop(0)
  msg2 = Client1.msgqueue.pop(0)

  assert (msg1 == ("topic2/next", "message 3", [2]) and \
          msg2 == ("topic2/blah", "message 4", [1])) or \
         (msg2 == ("topic2/next", "message 3", [2]) and \
          msg1 == ("topic2/blah", "message 4", [1]))

  assert Client1.msgqueue == []

  bn.disconnect(Client1.id)

  Client2 = Clients("Client2")
  bn.connect(Client2)
  bn.publish(Client2.id, "topic2/a", "queued message 0", 0)
  bn.publish(Client2.id, "topic2/a", "queued message 1", 1)
  bn.publish(Client2.id, "topic2/a", "queued message 2", 2)

  bn.connect(Client1, False)
  assert Client1.msgqueue.pop(0) == ("topic2/a", "queued message 1", [1])
  assert Client1.msgqueue.pop(0) == ("topic2/a", "queued message 2", [2])

  bn.disconnect(Client1.id)
  bn.disconnect(Client2.id)

 
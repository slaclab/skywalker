class Valve(object):
	''' Valve simulator
	'''
	def __init__(self):
		self.OPN_LS = FALSE
		self.CLS_LS = TRUE
		self.OPN_OK = TRUE
		self._OPN_SW = FALSE
		self._moveStartTime
		self._moveDuration = 2 #seconds
	def valve_action_(self):
		"""
		Normally closed valve action
		"""
		elapsedTime = time.clock() - self._moveStartTime
		if elapsedTime >= self._moveDuration:
			if self._OPN_SW:
				self.OPN_LS = true
			else:
				self.CLS_LS = true
		else:
			self.OPN_LS = false
			self.CLS_LS = false
	@property
	def OPN_SW(self):
		return self._OPN_SW
	@OPEN_SW.setter
	def OPN_SW(self, value):
		"""Rising and falling edge detection"""
		if value != self._OPN_SW:
			"""Rising edge starts valve open"""
			self._OPN_SW = value
			self._moveStartTime = time.clock()


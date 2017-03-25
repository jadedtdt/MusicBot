
class User:

    """
        User keeps track of information about a user either for data science or for managing cooldowns to prevent abuse.
    """


    def __init__(self):
    	self.canPlay = True
    	self.canSkip = True
    	self.canPlayNow = True
    	self.canTagAdd = True


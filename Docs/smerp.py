class Smerp:
    """Smooth exponential average interpolation"""

    def __init__(self, current, target, speedFactor = 0.3, responsiveness = 0.06):
        """Create a new interpolator.
        Parameters:
        current:        The current value.
        target:         The target value.
        speedFactor:    How quickly the current value approaches the target.
        responsiveness: How quickly the current value changes direction."""
        self.current = current
        self.target = target
        # Set initial speed to zero. Use 'current' as the type.
        self.currentDelta = current * 0.0
        self.speedFactor = speedFactor
        self.responsiveness = responsiveness

    def nextValue(self):
        """For each time step, try to move toward the target by some fraction of
        the distance (as is the case for normal exponential averages). If this
        would result in a positive acceleration, take a second exponential
        average of the acceleration."""
        targetDelta = (self.target - self.current) * self.speedFactor
        if (targetDelta * targetDelta > self.currentDelta * self.currentDelta):
            self.currentDelta = self.currentDelta * (1.0 - self.responsiveness) +
                                targetDelta * self.responsiveness
        else:
            self.currentDelta = targetDelta
        self.current = self.current + self.currentDelta
        return self.current


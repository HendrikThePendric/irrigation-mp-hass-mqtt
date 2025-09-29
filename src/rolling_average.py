class RollingAverage:
    """A circular buffer that maintains a rolling average of values."""
    
    def __init__(self, size: int = 10) -> None:
        """Initialize the rolling average with the specified buffer size.
        
        Args:
            size: The size of the circular buffer (default: 10)
        """
        self._size = size
        self._buffer = [0.0] * size
        self._index = 0
        self._count = 0
        
    def add_value(self, value: float) -> None:
        """Add a new value to the circular buffer.
        
        Args:
            value: The new value to add
        """
        self._buffer[self._index] = value
        self._index = (self._index + 1) % self._size
        if self._count < self._size:
            self._count += 1
            
    def get_average(self) -> float:
        """Get the current rolling average.
        
        Returns:
            The average of all values currently in the buffer
        """
        if self._count == 0:
            return 0.0
        return sum(self._buffer[:self._count]) / self._count
        
    def is_full(self) -> bool:
        """Check if the buffer is full.
        
        Returns:
            True if the buffer has reached its maximum size
        """
        return self._count == self._size
        
    def clear(self) -> None:
        """Clear all values from the buffer."""
        self._buffer = [0.0] * self._size
        self._index = 0
        self._count = 0
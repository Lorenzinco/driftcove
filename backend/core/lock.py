from fasteners import ReaderWriterLock

# Create a global lock for the application
lock = ReaderWriterLock()
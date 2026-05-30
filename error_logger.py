"""
Error logging module for Pico W with circular buffer and file persistence.
Keeps track of errors in memory and persists them to a file with size limit.
"""

import os
from time import localtime, time

class ErrorLogger:
    def __init__(self, filename='error_log.txt', max_entries=100, max_file_size=50000):
        """
        Initialize the error logger.
        
        Args:
            filename: Name of the log file
            max_entries: Maximum entries to keep in circular buffer
            max_file_size: Maximum size of log file in bytes (~50KB)
        """
        self.filename = filename
        self.max_entries = max_entries
        self.max_file_size = max_file_size
        self.entries = []
        self.stats = {
            'total_errors': 0,
            'total_exceptions': 0,
            'start_time': time()
        }
        self._load_existing_log()
    
    def _format_timestamp(self):
        """Return formatted timestamp string"""
        tm = localtime()
        return "{:04d}-{:02d}-{:02d} {:02d}:{:02d}:{:02d}".format(
            tm[0], tm[1], tm[2], tm[3], tm[4], tm[5]
        )
    
    def _check_file_size(self):
        """Check if log file exceeds max size and reset if needed"""
        try:
            stat = os.stat(self.filename)
            file_size = stat[6]  # Size in bytes
            
            if file_size > self.max_file_size:
                # File too large, back it up and start fresh
                backup_name = self.filename + '.old'
                try:
                    os.remove(backup_name)
                except:
                    pass
                os.rename(self.filename, backup_name)
                print(f"[LOG] File size limit reached. Old log backed up to {backup_name}")
        except:
            pass  # File doesn't exist yet
    
    def _load_existing_log(self):
        """Load existing log entries from file (last 20 lines)"""
        try:
            if self.filename in os.listdir():
                with open(self.filename, 'r') as f:
                    lines = f.readlines()
                    # Load last 20 entries
                    for line in lines[-20:]:
                        line = line.strip()
                        if line:
                            self.entries.append(line)
        except Exception as e:
            print(f"[LOG] Could not load existing log: {e}")
    
    def log_error(self, category, message, detail=""):
        """
        Log an error message.
        
        Args:
            category: Category of error (e.g., "MQTT", "WIFI", "GARAGE")
            message: Main error message
            detail: Additional details (optional)
        """
        timestamp = self._format_timestamp()
        detail_str = f" | {detail}" if detail else ""
        entry = f"[{timestamp}] {category}: {message}{detail_str}"
        
        print(entry)  # Print to console
        
        # Add to circular buffer
        self.entries.append(entry)
        if len(self.entries) > self.max_entries:
            self.entries.pop(0)
        
        # Write to file
        self._write_to_file(entry)
        self.stats['total_errors'] += 1
    
    def log_exception(self, exception, location=""):
        """
        Log an exception with traceback.
        
        Args:
            exception: The exception object
            location: Where the exception occurred
        """
        timestamp = self._format_timestamp()
        exc_type = type(exception).__name__
        exc_msg = str(exception)
        
        entry = f"[{timestamp}] EXCEPTION in {location}: {exc_type}: {exc_msg}"
        
        print(entry)  # Print to console
        
        # Add to circular buffer
        self.entries.append(entry)
        if len(self.entries) > self.max_entries:
            self.entries.pop(0)
        
        # Write to file
        self._write_to_file(entry)
        self.stats['total_exceptions'] += 1
    
    def _write_to_file(self, entry):
        """Write a single entry to log file"""
        try:
            self._check_file_size()
            with open(self.filename, 'a') as f:
                f.write(entry + '\n')
        except Exception as e:
            print(f"[LOG] Could not write to file: {e}")
    
    def get_recent_errors(self, count=10):
        """Get the last N error entries"""
        return self.entries[-count:] if self.entries else []
    
    def print_stats(self):
        """Print logging statistics"""
        uptime = time() - self.stats['start_time']
        print("\n=== Error Logger Statistics ===")
        print(f"Total Errors: {self.stats['total_errors']}")
        print(f"Total Exceptions: {self.stats['total_exceptions']}")
        print(f"Uptime: {int(uptime)} seconds ({int(uptime/60)} minutes)")
        print(f"Entries in buffer: {len(self.entries)}")
        print("===============================\n")
    
    def dump_log_to_file(self, output_file='error_log_dump.txt'):
        """Dump full log to a separate file for download"""
        try:
            with open(output_file, 'w') as f:
                for entry in self.entries:
                    f.write(entry + '\n')
            print(f"[LOG] Full log dumped to {output_file}")
        except Exception as e:
            print(f"[LOG] Could not dump log: {e}")
    
    def clear_log(self):
        """Clear log file and buffer"""
        try:
            self.entries = []
            with open(self.filename, 'w') as f:
                f.write("")  # Truncate file
            print("[LOG] Log cleared")
        except Exception as e:
            print(f"[LOG] Could not clear log: {e}")
    
    def get_log_file_size(self):
        """Get current log file size in bytes"""
        try:
            if self.filename in os.listdir():
                stat = os.stat(self.filename)
                return stat[6]
        except:
            pass
        return 0


# Global instance
error_log = ErrorLogger()

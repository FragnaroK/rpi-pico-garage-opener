import gc
import machine
import time
from error_logger import error_log

class MemoryMonitor:
    """Monitor and manage memory usage on Pico W with Auto-Reboot"""
    
    def __init__(self, check_interval=60, warning_threshold=80, reboot_threshold=85):
        """
        Initialize memory monitor
        
        Args:
            check_interval: Check memory every N seconds
            warning_threshold: Trigger warning at N% usage
            reboot_threshold: Reboot board at N% usage
        """
        self.check_interval = check_interval
        self.warning_threshold = warning_threshold
        self.reboot_threshold = reboot_threshold
        self.last_check = 0
        self.peak_usage = 0
        self.gc_count = 0
        self.allocation_count = 0
        
    def get_memory_stats(self):
        """Get current memory statistics"""
        gc.collect()  # Collect garbage before checking
        
        mem_info = {}
        try:
            total = gc.mem_alloc() + gc.mem_free()
            allocated = gc.mem_alloc()
            mem_info['total'] = total
            mem_info['allocated'] = allocated
            mem_info['free'] = gc.mem_free()
            mem_info['usage_percent'] = (allocated / total) * 100
        except Exception:
            mem_info['error'] = 'Could not read memory stats'
        
        return mem_info
    
    def check_memory(self, current_time=None):
        """Check memory and perform actions based on thresholds"""
        if current_time is None:
            current_time = time.time()
        
        if current_time - self.last_check < self.check_interval:
            return
        
        self.last_check = current_time
        stats = self.get_memory_stats()
        
        if 'error' in stats:
            error_log.log_error("MEMORY", stats['error'])
            return
        
        usage = stats['usage_percent']
        
        # Update peak usage
        if usage > self.peak_usage:
            self.peak_usage = usage
            
        # 1. CRITICAL: Check for Reboot Threshold
        if usage >= self.reboot_threshold:
            error_log.log_error(
                "MEMORY_CRITICAL", 
                f"Rebooting! Usage: {usage:.1f}% exceeds limit of {self.reboot_threshold}%"
            )
            # Small delay to ensure the log is written/flushed if using a physical file
            time.sleep(0.5) 
            machine.reset()
        
        # 2. WARNING: Log warning and force GC
        elif usage > self.warning_threshold:
            error_log.log_error(
                "MEMORY_WARNING",
                f"Memory usage at {usage:.1f}%",
                f"Free: {stats['free']} bytes"
            )
            self.force_gc()
        
        # Regular stats logging
        error_log.log_error(
            "MEMORY_STATS",
            f"Usage: {usage:.1f}% | Free: {stats['free']} bytes"
        )
    
    def force_gc(self):
        """Force garbage collection"""
        gc.collect()
        self.gc_count += 1
        stats = self.get_memory_stats()
        error_log.log_error(
            "GC_COLLECTED",
            f"Garbage collection #{self.gc_count}",
            f"Free memory after GC: {stats['free']} bytes"
        )
    
    def print_diagnostics(self):
        """Print full memory diagnostics"""
        stats = self.get_memory_stats()
        print("\n=== Memory Diagnostics ===")
        if 'error' not in stats:
            print(f"Total Heap: {stats['total']} bytes")
            print(f"Allocated: {stats['allocated']} bytes")
            print(f"Free: {stats['free']} bytes")
            print(f"Usage: {stats['usage_percent']:.1f}%")
            print(f"Peak Usage: {self.peak_usage:.1f}%")
        print(f"GC Collections: {self.gc_count}")
        print("==========================\n")

# Global instance with your requested 85% reboot limit
memory_monitor = MemoryMonitor(check_interval=60, warning_threshold=80, reboot_threshold=85)
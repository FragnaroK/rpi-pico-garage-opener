import gc
import machine
import time
from runtime.error_logger import error_log

class MemoryMonitor:
    """Monitor and manage memory usage on Pico W with Auto-Reboot

    This version avoids forcing GC during every stats read to reduce noise
    and only logs full stats at a configurable interval.
    """

    def __init__(self, check_interval=60, warning_threshold=80, reboot_threshold=85, log_interval=300):
        self.check_interval = check_interval
        self.warning_threshold = warning_threshold
        self.reboot_threshold = reboot_threshold
        self.log_interval = log_interval
        self.last_check = 0
        self.peak_usage = 0
        self.gc_count = 0
        self._last_stats_log = 0

    def get_memory_stats(self):
        """Return memory stats without forcing GC (caller decides when to GC)."""
        mem_info = {}
        try:
            total = gc.mem_alloc() + gc.mem_free()
            allocated = gc.mem_alloc()
            free = gc.mem_free()
            mem_info['total'] = total
            mem_info['allocated'] = allocated
            mem_info['free'] = free
            mem_info['usage_percent'] = (allocated / total) * 100 if total else 0
        except Exception:
            mem_info['error'] = 'Could not read memory stats'

        return mem_info

    def check_memory(self, current_time=None):
        """Check memory and perform actions based on thresholds."""
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
        if usage > self.peak_usage:
            self.peak_usage = usage

        # Critical: reboot when above reboot_threshold
        if usage >= self.reboot_threshold:
            error_log.log_error(
                "MEMORY_CRITICAL",
                f"Rebooting! Usage: {usage:.1f}% exceeds limit of {self.reboot_threshold}%"
            )
            time.sleep(0.5)
            machine.reset()

        # Warning: try to free memory and log
        if usage > self.warning_threshold:
            error_log.log_error(
                "MEMORY_WARNING",
                f"Memory usage at {usage:.1f}%",
                f"Free: {stats['free']} bytes"
            )
            self.force_gc()

        # Periodic stats logging to avoid noisy logs
        if current_time - self._last_stats_log > self.log_interval:
            error_log.log_error(
                "MEMORY_STATS",
                f"Usage: {usage:.1f}% | Free: {stats['free']} bytes"
            )
            self._last_stats_log = current_time

    def force_gc(self):
        """Force garbage collection and log the result."""
        gc.collect()
        self.gc_count += 1
        stats = self.get_memory_stats()
        error_log.log_error(
            "GC_COLLECTED",
            f"Garbage collection #{self.gc_count}",
            f"Free memory after GC: {stats.get('free', 0)} bytes"
        )

    def print_diagnostics(self):
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


# Global instance with an 85% reboot limit and conservative logging
memory_monitor = MemoryMonitor(check_interval=60, warning_threshold=80, reboot_threshold=85, log_interval=300)
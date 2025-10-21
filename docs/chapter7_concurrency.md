# Chapter 7 — Concurrency & Threading: Safe Parallel Execution

This chapter covers how to safely run multiple operations in parallel without race conditions or data corruption.

## The Concurrency Problem

**Scenario**: Multiple threads need to generate images and audio simultaneously.

```
Thread 1: Generate audio for slides 1-3
Thread 2: Generate images for slides 1-3
Thread 3: Compose video from results

Problem: Threads write to shared state (checkpoint file) simultaneously
→ File corruption or lost updates
```

## Solution 1: File Locking

### The Lock Mechanism

```python
# agent/runs_safe.py

import fcntl
import os
import json
import tempfile

class SafeCheckpoint:
    def __init__(self, run_id: str):
        self.run_id = run_id
        self.checkpoint_path = f"workspace/runs/{run_id}.json"
        self.lock_path = f"workspace/runs/{run_id}.lock"
    
    def save_state(self, node: str, data: Dict) -> None:
        """Save state with file-level locking"""
        
        logger.debug("Acquiring lock for %s", self.run_id)
        
        # Open lock file (create if doesn't exist)
        lock_fd = os.open(
            self.lock_path,
            os.O_CREAT | os.O_WRONLY,
            0o666
        )
        
        try:
            # Acquire exclusive lock - blocks until available
            fcntl.flock(lock_fd, fcntl.LOCK_EX)
            logger.debug("Lock acquired for %s", self.run_id)
            
            # Now we have exclusive access
            # Read current checkpoint
            current = {}
            if os.path.exists(self.checkpoint_path):
                with open(self.checkpoint_path, 'r') as f:
                    current = json.load(f)
                logger.debug("Loaded checkpoint: %d nodes", len(current))
            
            # Update with new data
            current[node] = data
            current["updated_at"] = datetime.utcnow().isoformat()
            
            # Write to temp file
            temp_fd, temp_path = tempfile.mkstemp(
                dir="workspace/runs",
                prefix=f"{self.run_id}_"
            )
            
            try:
                with os.fdopen(temp_fd, 'w') as f:
                    json.dump(current, f, indent=2)
                
                # Atomic rename
                os.replace(temp_path, self.checkpoint_path)
                logger.debug("Checkpoint saved: %s", node)
            
            except Exception:
                if os.path.exists(temp_path):
                    os.unlink(temp_path)
                raise
        
        finally:
            # Always release lock
            fcntl.flock(lock_fd, fcntl.LOCK_UN)
            os.close(lock_fd)
            logger.debug("Lock released for %s", self.run_id)
    
    def load_state(self) -> Dict:
        """Load state (no locking needed for read)"""
        if not os.path.exists(self.checkpoint_path):
            return {}
        
        with open(self.checkpoint_path, 'r') as f:
            return json.load(f)
```

### File Locking Diagram

```
Thread 1                    Lock File        Thread 2
─────────                   ────────         ────────
save_state()                  ✗
  open()     ────────────→  OPEN
  flock(LOCK_EX) ────→   LOCKED ←──── attempting flock()
    (exclusive)               │       (BLOCKED)
    [write data]              │
    [atomic rename]           │
  flock(UNLOCK) ──────→   OPEN  ───→ flock() returns
                                      (can proceed)
```

### Why This Works

1. **Exclusive Lock**: Only one thread can hold it
2. **Blocking**: Other threads wait until released
3. **Atomic Operations**: Temp file + rename prevents corruption
4. **Finally Block**: Lock always released even on error

## Solution 2: Thread-Safe Collections

### Queue for Safe Communication

```python
# agent/parallel.py

from queue import Queue
from threading import Thread
import logging

class TaskQueue:
    """Thread-safe task distribution"""
    
    def __init__(self, max_workers: int = 4):
        self.task_queue = Queue()
        self.result_queue = Queue()
        self.max_workers = max_workers
        self.workers = []
    
    def start(self):
        """Start worker threads"""
        for i in range(self.max_workers):
            worker = Thread(
                target=self._worker_loop,
                name=f"Worker-{i}",
                daemon=False
            )
            worker.start()
            self.workers.append(worker)
            logger.info("Started worker thread: %s", worker.name)
    
    def _worker_loop(self):
        """Worker thread main loop"""
        while True:
            # Get task (blocks until available)
            task = self.task_queue.get()
            
            if task is None:  # Sentinel value to stop
                self.task_queue.task_done()
                break
            
            try:
                logger.debug("Processing task: %s", task.get("id"))
                result = self._execute_task(task)
                self.result_queue.put(result)
            
            except Exception as e:
                logger.error("Task failed: %s", e)
                self.result_queue.put({"error": str(e)})
            
            finally:
                self.task_queue.task_done()
    
    def _execute_task(self, task: Dict) -> Dict:
        """Execute single task"""
        task_type = task.get("type")
        
        if task_type == "generate_audio":
            return generate_audio_task(task)
        elif task_type == "generate_image":
            return generate_image_task(task)
        else:
            raise ValueError(f"Unknown task type: {task_type}")
    
    def submit_tasks(self, tasks: List[Dict]) -> None:
        """Submit tasks to queue"""
        for task in tasks:
            self.task_queue.put(task)
            logger.debug("Submitted task: %s", task.get("id"))
    
    def wait_completion(self) -> List[Dict]:
        """Wait for all tasks and collect results"""
        # Wait for queue to be empty
        self.task_queue.join()
        
        # Stop workers
        for _ in range(self.max_workers):
            self.task_queue.put(None)
        
        # Wait for workers to finish
        for worker in self.workers:
            worker.join()
        
        # Collect results
        results = []
        while not self.result_queue.empty():
            results.append(self.result_queue.get())
        
        logger.info("All tasks completed: %d results", len(results))
        return results
```

### Using Task Queue

```python
def generate_slides_parallel(slides: List[Dict]) -> List[Dict]:
    """Generate audio and images for all slides in parallel"""
    
    logger.info("Starting parallel generation for %d slides", len(slides))
    
    # Create task queue
    queue = TaskQueue(max_workers=4)
    queue.start()
    
    # Submit tasks
    tasks = []
    for slide in slides:
        tasks.append({
            "id": f"audio-{slide['id']}",
            "type": "generate_audio",
            "slide": slide
        })
        tasks.append({
            "id": f"image-{slide['id']}",
            "type": "generate_image",
            "slide": slide
        })
    
    queue.submit_tasks(tasks)
    
    # Wait for completion
    results = queue.wait_completion()
    
    logger.info("Completed %d asset generations", len(results))
    return results
```

### Queue Diagram

```
Main Thread              Queue              Worker Threads
───────────              ─────              ──────────────
submit(task1) ────→     [task1]
submit(task2) ────→     [task2]     ←──── Worker-1: get()
submit(task3) ────→     [task3]     ←──── Worker-2: get()
                         Empty

wait_completion()        [busy]       ──→ Worker-1: process
                                      ──→ Worker-2: process

result_queue.get() ←──  [result1]
result_queue.get() ←──  [result2]
result_queue.get() ←──  [result3]
```

## Solution 3: Lock Objects for Data

### Using Locks for Shared Data

```python
from threading import Lock, RLock
from dataclasses import dataclass

@dataclass
class SharedCounter:
    """Thread-safe counter"""
    value: int = 0
    _lock: Lock = Lock()
    
    def increment(self) -> int:
        with self._lock:
            self.value += 1
            return self.value
    
    def get(self) -> int:
        with self._lock:
            return self.value

class RateLimiter:
    """Thread-safe rate limiter"""
    
    def __init__(self, rate: float):
        self.rate = rate
        self.tokens = float(rate)
        self.last_update = time.time()
        self._lock = Lock()
    
    def wait_if_needed(self) -> None:
        """Block until token available"""
        with self._lock:
            now = time.time()
            elapsed = now - self.last_update
            
            # Replenish tokens
            self.tokens = min(
                self.rate,
                self.tokens + elapsed * self.rate
            )
            self.last_update = now
            
            # If insufficient tokens, wait
            if self.tokens < 1.0:
                wait_time = (1.0 - self.tokens) / self.rate
                logger.debug("Rate limit: waiting %.3f seconds", wait_time)
                time.sleep(wait_time)
                self.tokens = 0.0
            else:
                self.tokens -= 1.0

# Usage

counter = SharedCounter()

def worker_thread():
    for i in range(100):
        count = counter.increment()
        logger.debug("Worker incremented counter to %d", count)

threads = [Thread(target=worker_thread) for _ in range(4)]
for t in threads:
    t.start()
for t in threads:
    t.join()

print(f"Final count: {counter.get()}")  # Should be 400
```

## Solution 4: Thread-Local Storage

### Using Thread-Local Data

```python
import threading

# Create thread-local storage
_thread_local = threading.local()

def get_llm_adapter() -> LLMAdapter:
    """Get LLM adapter, cached per thread"""
    
    # Check if we already created one in this thread
    if not hasattr(_thread_local, 'llm_adapter'):
        logger.debug("Creating LLM adapter for thread: %s", threading.current_thread().name)
        _thread_local.llm_adapter = _create_llm_adapter()
    
    return _thread_local.llm_adapter

def get_logger(name: str) -> logging.Logger:
    """Get logger, one per thread"""
    if not hasattr(_thread_local, 'loggers'):
        _thread_local.loggers = {}
    
    if name not in _thread_local.loggers:
        _thread_local.loggers[name] = logging.getLogger(name)
    
    return _thread_local.loggers[name]

# Usage

def worker_thread(thread_id: int):
    adapter = get_llm_adapter()  # Each thread gets its own
    logger = get_logger("worker")
    
    logger.info("Worker %d using adapter: %s", thread_id, adapter)
    # Thread-local adapter won't be used by other threads
```

## Common Concurrency Pitfalls

### Pitfall 1: Race Conditions

```python
# ❌ NOT THREAD-SAFE
counter = 0

def increment():
    global counter
    counter += 1  # This is 3 operations: read, increment, write
                   # Thread A and B might both read 0, increment to 1

# ✅ THREAD-SAFE
counter = 0
lock = Lock()

def increment():
    global counter
    with lock:
        counter += 1  # Atomic within the lock
```

### Pitfall 2: Deadlock

```python
# ❌ DEADLOCK RISK
lock1 = Lock()
lock2 = Lock()

def thread1_func():
    with lock1:
        print("Thread 1 acquired lock1")
        time.sleep(0.1)
        with lock2:  # Waiting for lock2
            print("Thread 1 acquired lock2")

def thread2_func():
    with lock2:
        print("Thread 2 acquired lock2")
        time.sleep(0.1)
        with lock1:  # Waiting for lock1 - DEADLOCK!
            print("Thread 2 acquired lock1")

# ✅ PREVENT DEADLOCK
# Always acquire locks in the same order

def thread1_func():
    with lock1:
        with lock2:
            print("Thread 1")

def thread2_func():
    with lock1:
        with lock2:
            print("Thread 2")
```

### Pitfall 3: Lost Updates

```python
# ❌ NOT THREAD-SAFE (lost writes)
state = {"count": 0}

def read_modify_write():
    data = state  # Read
    data["count"] += 1  # Modify (in local var)
    state = data  # Write
    # If two threads do this, one update is lost

# ✅ THREAD-SAFE (atomic)
state = {"count": 0}
lock = Lock()

def read_modify_write():
    with lock:
        state["count"] += 1  # All three operations atomic
```

## Testing Concurrency

```python
# tests/test_concurrency.py

def test_concurrent_checkpoint_writes():
    """Test multiple threads writing checkpoints"""
    run_id = "test_concurrent"
    checkpoint = SafeCheckpoint(run_id)
    
    results = []
    
    def worker(thread_id: int):
        for i in range(100):
            checkpoint.save_state(f"node_{thread_id}", {"value": i})
            results.append(i)
    
    # Create 4 threads
    threads = [Thread(target=worker, args=(i,)) for i in range(4)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    
    # All writes should succeed
    assert len(results) == 400

def test_rate_limiter_concurrent():
    """Test rate limiter under concurrent load"""
    limiter = RateLimiter(rate=10.0)  # 10 requests/sec
    
    start = time.time()
    
    def worker():
        for _ in range(10):
            limiter.wait_if_needed()
    
    # 4 threads x 10 = 40 requests
    threads = [Thread(target=worker) for _ in range(4)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    
    elapsed = time.time() - start
    
    # Should take ~4 seconds (40 requests / 10 per sec)
    assert elapsed >= 3.8 and elapsed <= 4.5

def test_task_queue_ordering():
    """Test task queue processes all tasks"""
    queue = TaskQueue(max_workers=2)
    queue.start()
    
    tasks = [
        {"id": f"task_{i}", "type": "generate_audio"}
        for i in range(100)
    ]
    
    queue.submit_tasks(tasks)
    results = queue.wait_completion()
    
    assert len(results) == 100
```

## Best Practices

1. **Always use locks** for shared mutable state
2. **Minimize lock scope** - hold locks for shortest time
3. **Use thread-local storage** for thread-specific data
4. **Document thread safety** - which fields are protected
5. **Test with multiple threads** - concurrency bugs only appear under load
6. **Use high-level constructs** - Queue, ThreadPoolExecutor instead of raw Threads
7. **Never access shared state outside lock** - define critical sections clearly

## Performance Considerations

```python
# Measure contention

import timeit

def sequential():
    counter = SharedCounter()
    for _ in range(10000):
        counter.increment()

def concurrent():
    counter = SharedCounter()
    threads = [
        Thread(target=lambda: [counter.increment() for _ in range(2500)])
        for _ in range(4)
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

# Sequential is faster due to no lock contention
seq_time = timeit.timeit(sequential, number=1)
conc_time = timeit.timeit(concurrent, number=1)
print(f"Sequential: {seq_time:.3f}s, Concurrent: {conc_time:.3f}s")
```

## Next Steps

Learn about [comprehensive testing strategies](chapter8_testing_strategies.md) or
start [hands-on exercises](chapter9_getting_started.md)

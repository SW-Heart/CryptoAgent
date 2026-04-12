"""
Agent Request Queue with Result Caching

实现 Agent 调用队列，控制并发并缓存结果：
- 限制同时运行的 Agent 调用数量
- 缓存相似请求的结果 (TTL 5分钟)
- 防止重复调用
"""

import time
import hashlib
import threading
from collections import OrderedDict
from concurrent.futures import ThreadPoolExecutor, Future
from typing import Dict, Any, Callable, Optional
import requests

# ============= Configuration =============
MAX_CONCURRENT_AGENTS = 3  # 最大并发 Agent 数
CACHE_TTL = 300  # 缓存有效期 (5分钟)
CACHE_MAX_SIZE = 100  # 最大缓存条目数


# ============= Result Cache =============
class TTLCache:
    """带 TTL 的简单缓存"""
    
    def __init__(self, max_size: int = CACHE_MAX_SIZE, ttl: int = CACHE_TTL):
        self.cache: OrderedDict[str, tuple] = OrderedDict()  # {key: (value, expire_time)}
        self.max_size = max_size
        self.ttl = ttl
        self._lock = threading.Lock()
    
    def _make_key(self, user_id: str, prompt: str) -> str:
        """生成缓存 key (基于用户和提示的哈希)"""
        content = f"{user_id}:{prompt[:200]}"  # 只用前200字符
        return hashlib.md5(content.encode()).hexdigest()
    
    def get(self, user_id: str, prompt: str) -> Optional[Any]:
        """获取缓存结果"""
        key = self._make_key(user_id, prompt)
        with self._lock:
            if key in self.cache:
                value, expire_time = self.cache[key]
                if time.time() < expire_time:
                    # 移到末尾 (LRU)
                    self.cache.move_to_end(key)
                    return value
                else:
                    # 过期，删除
                    del self.cache[key]
            return None
    
    def set(self, user_id: str, prompt: str, value: Any):
        """设置缓存"""
        key = self._make_key(user_id, prompt)
        with self._lock:
            # 清理过期条目
            self._cleanup()
            
            # 检查大小限制
            while len(self.cache) >= self.max_size:
                self.cache.popitem(last=False)  # 删除最旧的
            
            self.cache[key] = (value, time.time() + self.ttl)
    
    def _cleanup(self):
        """清理过期条目"""
        now = time.time()
        expired = [k for k, (v, t) in self.cache.items() if t < now]
        for k in expired:
            del self.cache[k]


# ============= Request Queue =============
class AgentRequestQueue:
    """Agent 请求队列，控制并发"""
    
    def __init__(self, max_workers: int = MAX_CONCURRENT_AGENTS):
        self.executor = ThreadPoolExecutor(max_workers=max_workers)
        self.cache = TTLCache()
        self._pending: Dict[str, Future] = {}  # 防止重复请求
        self._lock = threading.Lock()
        print(f"[AgentQueue] Initialized with max_workers={max_workers}")
    
    def submit(
        self, 
        user_id: str, 
        prompt: str, 
        agent_url: str,
        session_id: str = None,
        use_cache: bool = True
    ) -> Future:
        """
        提交 Agent 请求到队列。
        
        Args:
            user_id: 用户 ID
            prompt: 提示内容
            agent_url: Agent API URL
            session_id: 会话 ID
            use_cache: 是否使用缓存
        
        Returns:
            Future 对象，可用 .result() 获取结果
        """
        # 检查缓存
        if use_cache:
            cached = self.cache.get(user_id, prompt)
            if cached:
                print(f"[AgentQueue] Cache hit for user {user_id[:8]}...")
                future = Future()
                future.set_result(cached)
                return future
        
        # 生成请求 key
        request_key = f"{user_id}:{hashlib.md5(prompt[:100].encode()).hexdigest()}"
        
        with self._lock:
            # 检查是否已有相同请求在执行
            if request_key in self._pending:
                existing = self._pending[request_key]
                if not existing.done():
                    print(f"[AgentQueue] Reusing pending request for user {user_id[:8]}...")
                    return existing
            
            # 提交新请求
            future = self.executor.submit(
                self._execute_request,
                user_id, prompt, agent_url, session_id, use_cache
            )
            self._pending[request_key] = future
        
        return future
    
    def _execute_request(
        self, 
        user_id: str, 
        prompt: str, 
        agent_url: str, 
        session_id: str,
        use_cache: bool
    ) -> dict:
        """执行实际的 Agent 请求"""
        print(f"[AgentQueue] Executing request for user {user_id[:8]}...")
        
        try:
            response = requests.post(
                agent_url,
                data={
                    "message": prompt,
                    "user_id": user_id,
                    "session_id": session_id or f"queue-{user_id[:8]}",
                    "stream": "False"
                },
                timeout=120
            )
            
            result = {
                "status_code": response.status_code,
                "content": response.text if response.status_code == 200 else None,
                "error": response.text if response.status_code != 200 else None
            }
            
            # 成功则缓存
            if use_cache and response.status_code == 200:
                self.cache.set(user_id, prompt, result)
            
            return result
            
        except Exception as e:
            print(f"[AgentQueue] Error executing request: {e}")
            return {"status_code": 500, "content": None, "error": str(e)}
    
    def get_stats(self) -> dict:
        """获取队列状态"""
        with self._lock:
            pending = sum(1 for f in self._pending.values() if not f.done())
        
        return {
            "pending_requests": pending,
            "cache_size": len(self.cache.cache),
            "max_workers": MAX_CONCURRENT_AGENTS
        }


# ============= Global Instance =============
_agent_queue: Optional[AgentRequestQueue] = None

def get_agent_queue() -> AgentRequestQueue:
    """获取全局 Agent 队列实例"""
    global _agent_queue
    if _agent_queue is None:
        _agent_queue = AgentRequestQueue()
    return _agent_queue

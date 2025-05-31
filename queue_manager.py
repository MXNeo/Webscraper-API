import asyncio
import json
import logging
import time
from typing import Dict, Any, Optional
from dataclasses import dataclass
from enum import Enum
import redis.asyncio as redis
import uuid

logger = logging.getLogger(__name__)

class JobStatus(Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"

@dataclass
class ScrapeJob:
    id: str
    url: str
    method: str  # "newspaper" or "scrapegraph"
    api_key: Optional[str] = None
    status: JobStatus = JobStatus.PENDING
    created_at: float = None
    started_at: Optional[float] = None
    completed_at: Optional[float] = None
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    
    def __post_init__(self):
        if self.created_at is None:
            self.created_at = time.time()

class QueueManager:
    def __init__(self, redis_url: str = "redis://localhost:6379"):
        self.redis_url = redis_url
        self.redis_client = None
        self.queue_name = "scrape_jobs"
        self.result_prefix = "job_result:"
        self.status_prefix = "job_status:"
        
    async def connect(self):
        """Connect to Redis"""
        try:
            self.redis_client = redis.from_url(self.redis_url)
            await self.redis_client.ping()
            logger.info("Connected to Redis successfully")
        except Exception as e:
            logger.warning(f"Redis connection failed: {e}. Running without queue.")
            self.redis_client = None
    
    async def disconnect(self):
        """Disconnect from Redis"""
        if self.redis_client:
            await self.redis_client.close()
    
    async def enqueue_job(self, url: str, method: str, api_key: Optional[str] = None) -> str:
        """Add a scraping job to the queue"""
        job_id = str(uuid.uuid4())
        job = ScrapeJob(
            id=job_id,
            url=url,
            method=method,
            api_key=api_key
        )
        
        if self.redis_client:
            try:
                # Add job to queue
                job_data = {
                    "id": job.id,
                    "url": job.url,
                    "method": job.method,
                    "api_key": job.api_key,
                    "created_at": job.created_at
                }
                await self.redis_client.lpush(self.queue_name, json.dumps(job_data))
                
                # Set initial status
                await self.redis_client.setex(
                    f"{self.status_prefix}{job_id}",
                    3600,  # 1 hour TTL
                    JobStatus.PENDING.value
                )
                
                logger.info(f"Job {job_id} enqueued for {method} scraping of {url}")
                return job_id
            except Exception as e:
                logger.error(f"Failed to enqueue job: {e}")
                # Fall back to immediate processing
                return None
        else:
            # No Redis, return None to indicate immediate processing
            return None
    
    async def dequeue_job(self, timeout: int = 10) -> Optional[ScrapeJob]:
        """Get the next job from the queue"""
        if not self.redis_client:
            return None
            
        try:
            # Blocking pop with timeout
            result = await self.redis_client.brpop(self.queue_name, timeout=timeout)
            if result:
                _, job_data = result
                job_dict = json.loads(job_data)
                
                job = ScrapeJob(
                    id=job_dict["id"],
                    url=job_dict["url"],
                    method=job_dict["method"],
                    api_key=job_dict.get("api_key"),
                    created_at=job_dict["created_at"],
                    status=JobStatus.PROCESSING,
                    started_at=time.time()
                )
                
                # Update status to processing
                await self.redis_client.setex(
                    f"{self.status_prefix}{job.id}",
                    3600,
                    JobStatus.PROCESSING.value
                )
                
                return job
        except Exception as e:
            logger.error(f"Failed to dequeue job: {e}")
        
        return None
    
    async def complete_job(self, job: ScrapeJob, result: Dict[str, Any]):
        """Mark job as completed with result"""
        job.status = JobStatus.COMPLETED
        job.completed_at = time.time()
        job.result = result
        
        if self.redis_client:
            try:
                # Store result
                await self.redis_client.setex(
                    f"{self.result_prefix}{job.id}",
                    3600,  # 1 hour TTL
                    json.dumps(result)
                )
                
                # Update status
                await self.redis_client.setex(
                    f"{self.status_prefix}{job.id}",
                    3600,
                    JobStatus.COMPLETED.value
                )
                
                logger.info(f"Job {job.id} completed successfully")
            except Exception as e:
                logger.error(f"Failed to store job result: {e}")
    
    async def fail_job(self, job: ScrapeJob, error: str):
        """Mark job as failed with error"""
        job.status = JobStatus.FAILED
        job.completed_at = time.time()
        job.error = error
        
        if self.redis_client:
            try:
                # Store error
                await self.redis_client.setex(
                    f"{self.result_prefix}{job.id}",
                    3600,
                    json.dumps({"error": error})
                )
                
                # Update status
                await self.redis_client.setex(
                    f"{self.status_prefix}{job.id}",
                    3600,
                    JobStatus.FAILED.value
                )
                
                logger.error(f"Job {job.id} failed: {error}")
            except Exception as e:
                logger.error(f"Failed to store job error: {e}")
    
    async def get_job_status(self, job_id: str) -> Optional[JobStatus]:
        """Get the status of a job"""
        if not self.redis_client:
            return None
            
        try:
            status = await self.redis_client.get(f"{self.status_prefix}{job_id}")
            if status:
                return JobStatus(status.decode())
        except Exception as e:
            logger.error(f"Failed to get job status: {e}")
        
        return None
    
    async def get_job_result(self, job_id: str) -> Optional[Dict[str, Any]]:
        """Get the result of a completed job"""
        if not self.redis_client:
            return None
            
        try:
            result = await self.redis_client.get(f"{self.result_prefix}{job_id}")
            if result:
                return json.loads(result.decode())
        except Exception as e:
            logger.error(f"Failed to get job result: {e}")
        
        return None
    
    async def get_queue_size(self) -> int:
        """Get the current queue size"""
        if not self.redis_client:
            return 0
            
        try:
            return await self.redis_client.llen(self.queue_name)
        except Exception as e:
            logger.error(f"Failed to get queue size: {e}")
            return 0

# Global queue manager instance
queue_manager = QueueManager() 
import os
import tempfile
import unittest

from frigate.headless.rate_limit import DistributedRateLimiter


class TestRateLimitAbuse(unittest.TestCase):
    def test_allows_within_limit_and_blocks_after_exceed(self):
        with tempfile.TemporaryDirectory() as td:
            path = os.path.join(td, "rate_limit.json")
            limiter = DistributedRateLimiter(
                limit_per_minute=2,
                state_path=path,
                block_base_sec=10,
                block_max_sec=60,
            )
            key = "tenant:t1|principal:p1|route:critical:POST:/v1/config/apply"
            self.assertTrue(limiter.allow(key, now_ts=120.0).allowed)
            self.assertTrue(limiter.allow(key, now_ts=121.0).allowed)
            denied = limiter.allow(key, now_ts=122.0)
            self.assertFalse(denied.allowed)
            self.assertEqual(denied.reason, "rate_limit_exceeded")
            self.assertGreaterEqual(denied.retry_after_sec, 10)

    def test_progressive_block_grows_on_repeated_abuse(self):
        with tempfile.TemporaryDirectory() as td:
            path = os.path.join(td, "rate_limit.json")
            limiter = DistributedRateLimiter(
                limit_per_minute=1,
                state_path=path,
                block_base_sec=5,
                block_max_sec=60,
            )
            key = "tenant:t1|principal:p1|route:critical:POST:/v1/config/apply"
            limiter.allow(key, now_ts=60.0)
            first = limiter.allow(key, now_ts=61.0)
            self.assertFalse(first.allowed)
            after_first = limiter.allow(key, now_ts=121.0)
            self.assertTrue(after_first.allowed)
            second = limiter.allow(key, now_ts=122.0)
            self.assertFalse(second.allowed)
            self.assertGreaterEqual(second.retry_after_sec, first.retry_after_sec)


if __name__ == "__main__":
    unittest.main()

from apps.service.replay import ReplayScheduler


def test_replay_deterministic_hash():
    scheduler_a = ReplayScheduler("ci_flake", speed=1.0, jitter=0.2, seed=42)
    scheduler_b = ReplayScheduler("ci_flake", speed=1.0, jitter=0.2, seed=42)
    hash_a = scheduler_a.schedule_hash(scheduler_a.build_schedule())
    hash_b = scheduler_b.schedule_hash(scheduler_b.build_schedule())
    assert hash_a == hash_b

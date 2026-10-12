from agents.protocols import RoutingTier, TaskMetadata, route


def execute(task: str | TaskMetadata, function, *args, provider=None, **kwargs):
    tier = route(task)
    if tier in {RoutingTier.DETERMINISTIC, RoutingTier.MONITORING}:
        if provider is not None:
            raise ValueError("AI providers are prohibited for deterministic tasks")
        return function(*args, **kwargs)
    if tier != RoutingTier.DETERMINISTIC and provider is None:
        raise ValueError("optional AI task requires an explicitly configured provider")
    return function(*args, **kwargs)

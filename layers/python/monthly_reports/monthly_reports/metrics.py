def initialize_metrics():
    """Initialize metrics dictionary"""
    return {
        "processed_count": 0,
        "failed_starts_count": 0,
        "skipped_count": 0,
        "already_exists_count": 0,
        "batches_processed": 0,
        "pages_processed": 0,
    }


def merge_metrics(target_metrics, source_metrics):
    """Merge metrics from source into target"""
    for key, value in source_metrics.items():
        if key in target_metrics:
            target_metrics[key] += value

def initialize_metrics():
    """
    Return a new metrics dictionary initialised with predefined counters.

    The returned dictionary contains the following integer counters, each set to 0:
    - "processed_count": total items processed
    - "failed_starts_count": items that failed to start processing
    - "skipped_count": items intentionally skipped
    - "already_exists_count": items found to already exist
    - "batches_processed": number of batches processed
    - "pages_processed": number of pages processed

    Returns:
        dict: A new dictionary with the metric keys initialised to 0.
    """
    return {
        "processed_count": 0,
        "failed_starts_count": 0,
        "skipped_count": 0,
        "already_exists_count": 0,
        "batches_processed": 0,
        "pages_processed": 0,
    }


def merge_metrics(target_metrics, source_metrics):
    """
    Merge numeric metrics from source_metrics into target_metrics in-place.

    For each key in source_metrics, if the key exists in target_metrics the source value is added to the target value. Keys present in source_metrics but not in target_metrics are ignored.

    Parameters:
        target_metrics (dict): Destination metrics mapping; mutated in-place. Expected to contain the keys to be updated.
        source_metrics (dict): Source metrics mapping whose numeric values will be added into target_metrics.
    """
    for key, value in source_metrics.items():
        if key in target_metrics:
            target_metrics[key] += value

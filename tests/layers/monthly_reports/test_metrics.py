import pytest

from monthly_reports.metrics import initialize_metrics, merge_metrics


class TestInitialiseMetrics:

    def test_initialise_metrics(self):
        metrics = initialize_metrics()

        assert metrics["processed_count"] == 0
        assert metrics["failed_starts_count"] == 0
        assert metrics["skipped_count"] == 0
        assert metrics["already_exists_count"] == 0
        assert metrics["batches_processed"] == 0
        assert metrics["pages_processed"] == 0


class TestMergeMetrics:
    @pytest.mark.parametrize(
        "test_case,target,source,expected,should_modify_target",
        [
            (
                "basic_merge",
                {"processed_count": 5, "failed_starts_count": 2, "skipped_count": 1},
                {"processed_count": 3, "failed_starts_count": 1, "skipped_count": 2},
                {"processed_count": 8, "failed_starts_count": 3, "skipped_count": 3},
                True,
            ),
            (
                "merge_zeros",
                {"processed_count": 5, "failed_starts_count": 2},
                {"processed_count": 0, "failed_starts_count": 0},
                {"processed_count": 5, "failed_starts_count": 2},
                False,
            ),
            (
                "empty_target",
                {"processed_count": 0, "pages_processed": 0},
                {"processed_count": 10, "pages_processed": 20},
                {"processed_count": 10, "pages_processed": 20},
                True,
            ),
            (
                "negative_values",
                {"processed_count": 10, "failed_starts_count": 5},
                {"processed_count": -3, "failed_starts_count": -2},
                {"processed_count": 7, "failed_starts_count": 3},
                True,
            ),
            (
                "partial_keys",
                {"processed_count": 5, "failed_starts_count": 2, "pages_processed": 0},
                {"processed_count": 3, "pages_processed": 10},
                {"processed_count": 8, "failed_starts_count": 2, "pages_processed": 10},
                True,
            ),
            (
                "unknown_keys",
                {"processed_count": 5},
                {"processed_count": 3, "unknown_key": 10, "another_unknown": 20},
                {"processed_count": 8},
                True,
            ),
            (
                "large_numbers",
                {"processed_count": 1000000, "batches_processed": 500},
                {"processed_count": 2000000, "batches_processed": 300},
                {"processed_count": 3000000, "batches_processed": 800},
                True,
            ),
            (
                "single_key",
                {"processed_count": 100, "failed_starts_count": 50},
                {"processed_count": 25},
                {"processed_count": 125, "failed_starts_count": 50},
                True,
            ),
            (
                "full_metrics",
                {
                    "processed_count": 100,
                    "failed_starts_count": 10,
                    "skipped_count": 5,
                    "already_exists_count": 15,
                    "batches_processed": 2,
                    "pages_processed": 50,
                },
                {
                    "processed_count": 50,
                    "failed_starts_count": 5,
                    "skipped_count": 3,
                    "already_exists_count": 8,
                    "batches_processed": 1,
                    "pages_processed": 25,
                },
                {
                    "processed_count": 150,
                    "failed_starts_count": 15,
                    "skipped_count": 8,
                    "already_exists_count": 23,
                    "batches_processed": 3,
                    "pages_processed": 75,
                },
                True,
            ),
        ],
    )
    def test_metrics_functionality(
        self, test_case, target, source, expected, should_modify_target
    ):
        original_target = target.copy()
        original_id = id(target)

        result = merge_metrics(target, source)

        assert result is None
        assert target == expected
        assert id(target) == original_id

        for key in source:
            if key not in original_target:
                assert key not in target

        if should_modify_target:
            assert target != original_target
        else:
            assert target == original_target

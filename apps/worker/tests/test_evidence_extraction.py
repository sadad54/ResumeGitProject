from proofhire_worker.intelligence.evidence_extraction import (
    MAX_FILE_CHARS,
    MAX_GROUP_CHARS,
    _group_files,
)


def test_small_files_stay_in_one_group():
    files = [("a.py", "x" * 100), ("b.py", "y" * 100)]
    groups = _group_files(files)
    assert len(groups) == 1
    assert len(groups[0]) == 2


def test_large_batch_splits_into_multiple_groups():
    files = [(f"file_{i}.py", "x" * (MAX_GROUP_CHARS // 2 + 10)) for i in range(4)]
    groups = _group_files(files)
    assert len(groups) > 1
    for group in groups:
        total = sum(len(c) for _, c in group)
        assert total <= MAX_GROUP_CHARS + MAX_FILE_CHARS  # one file may push over slightly


def test_single_huge_file_is_truncated():
    files = [("huge.py", "x" * (MAX_FILE_CHARS * 10))]
    groups = _group_files(files)
    assert len(groups) == 1
    assert len(groups[0][0][1]) == MAX_FILE_CHARS


def test_empty_input_produces_no_groups():
    assert _group_files([]) == []

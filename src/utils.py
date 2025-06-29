from typing import Collection


def get_exactly_one[T](collection: Collection[T]) -> T:
    if len(collection) != 1:
        raise ValueError("Collection must contain exactly one element.")
    return next(iter(collection))

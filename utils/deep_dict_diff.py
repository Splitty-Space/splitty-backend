def deep_dict_diff(old, new):
    diff = {}

    # Get all keys from both dictionaries
    all_keys = set(old.keys()).union(new.keys())

    for key in all_keys:
        value1 = old.get(key, None)
        value2 = new.get(key, None)

        # If both values are dictionaries, recurse
        if isinstance(value1, dict) and isinstance(value2, dict):
            nested_diff = deep_dict_diff(value1, value2)
            if nested_diff:  # Only add non-empty diffs
                diff[key] = nested_diff

        # If both values are lists, compare them element by element
        elif isinstance(value1, list) and isinstance(value2, list):
            if len(value1) != len(value2):
                diff[key] = {"old": value1, "new": value2}
            else:
                list_diff = {}
                for i in range(len(value1)):
                    item_diff = deep_dict_diff({f"{i}": value1[i]}, {f"{i}": value2[i]})
                    if item_diff:
                        list_diff.update(item_diff)
                if list_diff:
                    diff[key] = list_diff

        # If values are different, record the difference
        elif value1 != value2:
            diff[key] = {"old": value1, "new": value2}

    return diff
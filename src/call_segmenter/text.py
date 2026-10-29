import re

_TAG = re.compile(r"\[([A-Z_]+)\]")


def tag_tokens(text):
    return _TAG.sub(lambda m: " tag" + m.group(1).lower().replace("_", "") + " ", text)

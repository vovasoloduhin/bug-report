import re

MAX_TAGS = 10
MAX_LEN = 30

def parse_tags(raw):
    names = []
    for part in re.split(r"[,;\n]", raw or ""):
        name = " ".join(part.strip().lstrip("#").split()).lower()[:MAX_LEN]
        if name and name not in names:
            names.append(name)
    return names[:MAX_TAGS]

def set_tags(bug, names):
    from .models import Tag
    tags = [Tag.objects.get_or_create(team=bug.team, name=n)[0] for n in names]
    bug.tags.set(tags)

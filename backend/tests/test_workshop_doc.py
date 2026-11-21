# backend/tests/test_workshop_doc.py
import json
import re

from app.workshop.doc import SPEC_DOC
from app.workshop.spec import expand


def test_spec_doc_is_short_and_its_examples_expand():
    assert len(SPEC_DOC) <= 3500
    examples = re.findall(r"EXAMPLE \d[^\n]*\n(\{.*?\}\n)(?=\n|EXAMPLE|$)", SPEC_DOC, flags=re.S)
    assert len(examples) == 2
    for text in examples:
        result = expand(json.loads(text))
        assert result.parts and not result.notes

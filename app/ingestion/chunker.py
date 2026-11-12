import hashlib
from dataclasses import asdict, dataclass

from app.ingestion.parser import units

CHUNK_BYTES = 1800
POLICY = "tree-sitter-v1/utf8-1800-byte-chunks/rule-provenance-v1"


@dataclass(frozen=True)
class Chunk:
    chunk_id: str
    repository: str
    snapshot: str
    file: str
    symbol: str
    signature: str
    language: str
    start_line: int
    end_line: int
    start_byte: int
    end_byte: int
    ordinal: int
    parser_status: str
    text: str

    def metadata(self):
        data = asdict(self)
        del data["text"]
        return data


def chunks(repository, snapshot, file, text, structural=False):
    raw = text.encode("utf-8")
    language = "c" if file.endswith(".c") else "cpp"
    status = "ok"
    try:
        parsed = units(raw, language)
    except Exception:
        # The file remains usable as evidence even if a grammar/API fails.
        parsed = []
        status = "failed"
    ranges = []
    position = 0
    for unit in parsed:
        if unit.start_byte > position:
            ranges.append((position, unit.start_byte, "", ""))
        ranges.append((unit.start_byte, unit.end_byte, unit.symbol, unit.signature))
        position = unit.end_byte
    if position < len(raw):
        ranges.append((position, len(raw), "", ""))
    result = []
    for start, end, symbol, signature in ranges:
        ordinal = 0
        while start < end:
            # Complete syntactic functions are retained for code-aware analysis.
            # The existing model budget rejects oversized required evidence.
            stop = end if structural and symbol else min(start + CHUNK_BYTES, end)
            if stop < end:
                newline = raw.rfind(b"\n", start, stop)
                if newline > start:
                    stop = newline + 1
                while stop > start and (raw[stop] & 0xC0) == 0x80:
                    stop -= 1
            body = raw[start:stop].decode("utf-8")
            if body.strip():
                identity = f"{repository}\0{snapshot}\0{file}\0{symbol}\0{start}\0{stop}\0{ordinal}\0{body}"
                result.append(Chunk(hashlib.sha256(identity.encode()).hexdigest(), repository, snapshot,
                                    file, symbol, signature, language, raw[:start].count(b"\n") + 1,
                                    raw[:max(start, stop - 1)].count(b"\n") + 1,
                                    start, stop, ordinal, status, body))
            start = stop
            ordinal += 1
    return result, status

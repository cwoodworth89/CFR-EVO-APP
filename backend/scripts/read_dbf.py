"""Minimal streaming DBF reader — audits Addresses.dbf without GDAL/fiona.

Standalone scratch script (CLAUDE.md 3.2). Read-only; touches no project state.
"""
import struct, sys, collections

PATH = sys.argv[1] if len(sys.argv) > 1 else \
    r'backend/data/Property_Information/Addresses.dbf'


def open_dbf(path):
    f = open(path, 'rb')
    hdr = f.read(32)
    n_records = struct.unpack('<I', hdr[4:8])[0]
    hdr_len = struct.unpack('<H', hdr[8:10])[0]
    rec_len = struct.unpack('<H', hdr[10:12])[0]

    fields = []
    while True:
        d = f.read(32)
        if not d or d[0:1] in (b'\x0d', b''):
            break
        name = d[0:11].split(b'\x00')[0].decode('latin-1')
        ftype = d[11:12].decode('latin-1')
        flen = d[16]
        fields.append((name, ftype, flen))
    return f, n_records, hdr_len, rec_len, fields


def records(path, wanted=None):
    f, n, hdr_len, rec_len, fields = open_dbf(path)
    offsets, pos = {}, 1  # 1 = deletion flag byte
    for name, ftype, flen in fields:
        offsets[name] = (pos, flen)
        pos += flen
    f.seek(hdr_len)
    keys = wanted or [x[0] for x in fields]
    for _ in range(n):
        raw = f.read(rec_len)
        if len(raw) < rec_len:
            break
        if raw[0:1] == b'*':      # deleted record
            continue
        out = {}
        for k in keys:
            if k not in offsets:
                continue
            s, ln = offsets[k]
            out[k] = raw[s:s + ln].decode('latin-1').strip()
        yield out
    f.close()


if __name__ == '__main__':
    f, n, hdr_len, rec_len, fields = open_dbf(PATH)
    f.close()
    print(f'records in header: {n}')
    print(f'record length: {rec_len}  header length: {hdr_len}')
    print('fields:', ', '.join(f'{a}({b}{c})' for a, b, c in fields))

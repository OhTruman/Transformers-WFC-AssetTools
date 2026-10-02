"""Tiny ActionScript 2 (SWF DoAction / DoInitAction) disassembler for authored-UI evidence.

Resolves ActionPush operands (constant-pool strings, numbers, registers) and prints one op per line with
the byte offset, recursing into DefineFunction / DefineFunction2 bodies by indentation.
Used with gfxscan.py:  python as2dis.py <file.gfx> <sprite id | 'root'> [--init]
"""
import struct, sys, os

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import gfxscan  # noqa: E402

OPS = {0x04: 'NextFrame', 0x05: 'PrevFrame', 0x06: 'Play', 0x07: 'Stop', 0x0A: 'Add', 0x0B: 'Subtract', 0x0C: 'Multiply',
       0x0D: 'Divide', 0x0E: 'Equals', 0x0F: 'Less', 0x10: 'And', 0x11: 'Or', 0x12: 'Not', 0x13: 'StringEquals',
       0x17: 'Pop', 0x18: 'ToInteger', 0x1C: 'GetVariable', 0x1D: 'SetVariable', 0x20: 'SetTarget2', 0x21: 'StringAdd',
       0x22: 'GetProperty', 0x23: 'SetProperty', 0x24: 'CloneSprite', 0x25: 'RemoveSprite', 0x26: 'Trace', 0x34: 'GetTime',
       0x3A: 'Delete', 0x3B: 'Delete2', 0x3C: 'DefineLocal', 0x3D: 'CallFunction', 0x3E: 'Return', 0x3F: 'Modulo',
       0x40: 'NewObject', 0x41: 'DefineLocal2', 0x42: 'InitArray', 0x43: 'InitObject', 0x44: 'TypeOf', 0x45: 'TargetPath',
       0x46: 'Enumerate', 0x47: 'Add2', 0x48: 'Less2', 0x49: 'Equals2', 0x4A: 'ToNumber', 0x4B: 'ToString', 0x4C: 'PushDuplicate',
       0x4D: 'StackSwap', 0x4E: 'GetMember', 0x4F: 'SetMember', 0x50: 'Increment', 0x51: 'Decrement', 0x52: 'CallMethod',
       0x53: 'NewMethod', 0x54: 'InstanceOf', 0x55: 'Enumerate2', 0x60: 'BitAnd', 0x61: 'BitOr', 0x62: 'BitXor', 0x63: 'BitLShift',
       0x64: 'BitRShift', 0x65: 'BitURShift', 0x66: 'StrictEquals', 0x67: 'Greater', 0x68: 'StringGreater', 0x69: 'Extends',
       0x81: 'GotoFrame', 0x83: 'GetURL', 0x87: 'StoreRegister', 0x88: 'ConstantPool', 0x8B: 'SetTarget', 0x8C: 'GotoLabel',
       0x8E: 'DefineFunction2', 0x94: 'With', 0x96: 'Push', 0x99: 'Jump', 0x9A: 'GetURL2', 0x9B: 'DefineFunction', 0x9D: 'If',
       0x9E: 'Call', 0x9F: 'GotoFrame2', 0x2A: 'Throw', 0x2B: 'CastOp', 0x2C: 'ImplementsOp', 0x8F: 'Try'}

def _cstr(b, i):
    j = b.index(0, i); return b[i:j].decode('latin-1'), j + 1

def dis(d, pool=None, indent=0, out=None, base=0):
    out = [] if out is None else out
    pool = pool if pool is not None else []
    i = 0; ends = []
    while i < len(d):
        while ends and i >= ends[-1]: ends.pop(); indent -= 1
        op = d[i]; at = i; i += 1
        if op == 0:
            out.append('%s%5d End' % ('  ' * indent, base + at)); break
        ln = 0
        if op >= 0x80: ln = struct.unpack_from('<H', d, i)[0]; i += 2
        body = d[i:i + ln]
        name = OPS.get(op, 'op_%02X' % op); arg = ''
        if op == 0x88:
            n = struct.unpack_from('<H', body, 0)[0]; j = 2; pool[:] = []
            for _ in range(n): s, j = _cstr(body, j); pool.append(s)
            arg = '%d strings' % n
        elif op == 0x96:
            vals = []; j = 0
            while j < len(body):
                t = body[j]; j += 1
                if t == 0: s, j = _cstr(body, j); vals.append(repr(s))
                elif t == 1: vals.append('%g' % struct.unpack_from('<f', body, j)[0]); j += 4
                elif t == 2: vals.append('null')
                elif t == 3: vals.append('undefined')
                elif t == 4: vals.append('r%d' % body[j]); j += 1
                elif t == 5: vals.append('true' if body[j] else 'false'); j += 1
                elif t == 6:
                    hi, lo = struct.unpack_from('<II', body, j); vals.append('%g' % struct.unpack('<d', struct.pack('<II', lo, hi))[0]); j += 8
                elif t == 7: vals.append('%d' % struct.unpack_from('<i', body, j)[0]); j += 4
                elif t == 8: vals.append(repr(pool[body[j]]) if body[j] < len(pool) else 'c%d' % body[j]); j += 1
                elif t == 9:
                    k = struct.unpack_from('<H', body, j)[0]; vals.append(repr(pool[k]) if k < len(pool) else 'c%d' % k); j += 2
                else: vals.append('?%d' % t); break
            arg = ', '.join(vals)
        elif op in (0x99, 0x9D):
            off = struct.unpack_from('<h', body, 0)[0]; arg = '-> %d' % (base + i + ln + off)
        elif op == 0x8C: arg = repr(_cstr(body, 0)[0])
        elif op == 0x81: arg = str(struct.unpack_from('<H', body, 0)[0])
        elif op == 0x87: arg = 'r%d' % body[0]
        elif op in (0x9B, 0x8E):
            fname, j = _cstr(body, 0)
            n = struct.unpack_from('<H', body, j)[0]; j += 2
            params = []
            if op == 0x8E:
                j += 1 + 2  # register count, flags
                for _ in range(n): r = body[j]; p_, j = _cstr(body, j + 1); params.append('r%d:%s' % (r, p_))
            else:
                for _ in range(n): p_, j = _cstr(body, j); params.append(p_)
            size = struct.unpack_from('<H', body, j)[0]
            arg = 'function %s(%s) [%d bytes]' % (fname or '<anon>', ', '.join(params), size)
            out.append('%s%5d %s %s' % ('  ' * indent, base + at, name, arg))
            i += ln
            indent += 1; ends.append(i + size)
            continue
        out.append('%s%5d %s %s' % ('  ' * indent, base + at, name, arg))
        i += ln
    return out

def actions_for(path, sprite, init=False):
    import struct as st
    b = open(path, 'rb').read()
    if b[:3] in (b'CFX', b'CWS'):
        import zlib; b = b[:8] + zlib.decompress(b[8:])
    res = []
    def walk(start, end, sid):
        for code, d, off in gfxscan._tags(b, start, end):
            if code == 39:
                s = st.unpack_from('<H', d, 0)[0]; walk(off + 4, off + len(d), s)
            elif code == 12 and not init and str(sid) == str(sprite): res.append(d)
            elif code == 59 and init and str(st.unpack_from('<H', d, 0)[0]) == str(sprite): res.append(d[2:])
    walk(8 + gfxscan._rect_len(b, 8) + 4, len(b), 'root')
    return res

if __name__ == '__main__':
    path, sprite = sys.argv[1], sys.argv[2]
    for blk in actions_for(path, sprite, '--init' in sys.argv):
        print('\n'.join(dis(blk))); print('-----')

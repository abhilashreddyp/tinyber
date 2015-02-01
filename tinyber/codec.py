# -*- Mode: Python -*-

# base for python codecs.

class IndefiniteLength (Exception):
    pass

class ElementTooLarge (Exception):
    pass

class Underflow (Exception):
    pass

class UnexpectedType (Exception):
    pass

class ConstraintViolation (Exception):
    pass

class FLAG:
    UNIVERSAL   = 0x00
    STRUCTURED  = 0x20
    APPLICATION = 0x40
    CONTEXT     = 0x80

class TAG:
    BOOLEAN     = 0x01
    INTEGER     = 0x02
    BITSTRING   = 0x03
    OCTETSTRING = 0x04
    NULLTAG     = 0x05
    OID         = 0x06
    ENUMERATED  = 0x0A
    UTF8STRING  = 0x0C
    SEQUENCE    = 0x10 | FLAG.STRUCTURED
    SET         = 0x11 | FLAG.STRUCTURED

class Buf:

    def __init__ (self, data, pos=0, end=None):
        self.data = data
        self.pos = pos
        if end is None:
            end = len(data)
        self.end = end

    def pop_byte (self):
        if self.pos + 1 > self.end:
            raise Underflow (self)
        else:
            val = ord (self.data[self.pos])
            self.pos += 1
            return val

    def pop (self, nbytes):
        if self.pos + nbytes > self.end:
            raise Underflow (self)
        else:
            r = Buf (self.data, self.pos, self.pos + nbytes)
            self.pos += nbytes
            return r

    def pop_bytes (self, nbytes):
        if self.pos + nbytes > self.end:
            raise Underflow (self)
        else:
            result = self.data[self.pos:self.pos+nbytes]
            self.pos += nbytes
            return result

    def done (self):
        return self.pos == self.end

    def get_length (self):
        val = self.pop_byte()
        if val < 0x80:
            # one-byte length
            return val
        elif val == 0x80:
            raise IndefiniteLength (self)
        else:
            # get length of length
            lol = val & 0x7f
            if lol > 4:
                raise ElementTooLarge (self)
            else:
                n = 0
                while lol:
                    n = (n << 8) | self.pop_byte()
                return n

    def check (self, expected):
        tag = self.pop_byte()
        if tag != expected:
            raise UnexpectedType (tag, expected)

    def next (self, expected):
        self.check (expected)
        length = self.get_length()
        return self.pop (length)
        
    def get_integer (self, length):
        if length == 0:
            return 0
        else:
            n = self.pop_byte()
            length -= 1
            if n & 0x80:
                # negative
                n -= 0x100
            else:
                while length:
                    n = n << 8 | self.pop_byte()
                    length -= 1
                return n

    def next_INTEGER (self, min_val, max_val):
        self.check (TAG.INTEGER)
        r = self.get_integer (self.get_length())
        if min_val is not None and r < min_val:
            raise ConstraintViolation (r, min_val)
        if max_val is not None and r > max_val:
            raise ConstraintViolation (r, max_val)
        return r

    def next_OCTET_STRING (self, min_size, max_size):
        self.check (TAG.OCTETSTRING)
        r = self.pop_bytes (self.get_length())
        if min_size is not None and len(r) < min_size:
            raise ConstraintViolation (r, min_size)
        if max_size is not None and len(r) > max_size:
            raise ConstraintViolation (r, max_size)
        return r

    def next_BOOLEAN (self):
        self.check (TAG.BOOLEAN)
        return self.pop_byte() != 0

    def next_ENUMERATED (self):
        self.check (TAG.ENUMERATED)
        return self.get_integer (self.get_length())

    def next_APPLICATION (self):
        tag = self.pop_byte()
        if not tag & FLAG.APPLICAITON:
            raise UnexpectedType (self, tag)
        else:
            return tag & 0x1f, self.pop (self.get_length())

class EncoderContext:

    def __init__ (self, enc, tag):
        self.enc = enc
        self.tag = tag
        self.pos = enc.length

    def __enter__ (self):
        pass

    def __exit__ (self, t, v, tb):
        self.enc.emit_length (self.enc.length - self.pos)
        self.enc.emit (chr (self.tag))

class Encoder:

    def __init__ (self):
        self.r = []
        self.length = 0
        
    def emit (self, data):
        self.r.insert (0, data)
        self.length += len(data)

    def emit_length (self, n):
        if n < 0x80:
            self.emit (chr(n))
        else:
            r = []
            b0 = chr (0x80 | ((n-1) & 0x7f))
            while n:
                r.insert (0, chr (n & 0xff))
                n >>= 8
            r.insert (0, b0)
            self.emit (''.join (r))

    def TLV (self, tag):
        return EncoderContext (self, tag)

    def done (self):
        return ''.join (self.r)

    # base types

    # encode an integer, ASN1 style.
    # two's complement with the minimum number of bytes.
    def emit_integer (self, n):
        i = 0
        n0 = n
        byte = 0x80
        r = []
        while 1:
            n >>= 8
            if n0 == n:
                if n == -1 and ((not byte & 0x80) or i==0):
                    # negative, but high bit clear
                    r.insert (0, chr(0xff))
                    i = i + 1
                elif n == 0 and (byte & 0x80):
                    # positive, but high bit set
                    r.insert (0, chr(0x00))
                    i = i + 1
                break
            else:
                byte = n0 & 0xff
                r.insert (0, chr (byte))
                i += 1
                n0 = n
        self.emit (''.join (r))

    def emit_INTEGER (self, n):
        with self.TLV (TAG.INTEGER):
            self.emit_integer (n)

class SEQUENCE:

    __slots__ = ()

    def __init__ (self, **args):
        for k, v in args.iteritems():
            setattr (self, k, v)

    def __repr__ (self):
        r = []
        for name in self.__slots__:
            r.append ('%s=%r' % (name, getattr (self, name)))
        return '<%s %s>' % (self.__class__.__name__, ' '.join (r))

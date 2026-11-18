# ==================================================================================
#       Copyright (c) 2026 LASSE/UFPA - Universidade Federal do Pará
#       Licensed under the Apache License, Version 2.0
# ==================================================================================
"""
Workaround for PER encoding of recursive ASN.1 types in pycrate.

E2SM-RC RANParameter-STRUCTURE / RANParameter-LIST are recursive. pycrate reuses the
same SEQUENCE OF object at every nesting level, so encoding an inner level replaces the
outer object's ``_val`` and the outer loop in ``_CONSTRUCT_OF.__to_per_cont`` then reads
the wrong list (IndexError or silently wrong encoding). This patch iterates over a local
copy of the values and restores ``_val`` after each element.

Needed for the Slice-level PRB quota hierarchy of E2SM-RC v03.00 section 8.4.3.6
(1 -> 2 -> 3 -> 5 -> 6 -> 8 -> 9/10).
"""
from pycrate_asn1rt import asnobj_construct as _construct
from pycrate_asn1rt.err import ASN1NotSuppErr

_CONSTRUCT_OF = _construct._CONSTRUCT_OF


def _to_per_cont_recursion_safe(self, GEN, num, off=0, bl=None):
    vals = self._val
    bl_cur, bl_upd = 0, False
    if self._ENC_MAXLEN and bl is not None:
        bl_cur, bl_upd = bl[0], True
    for i in range(num):
        self._cont._val = vals[off + i]
        cont_per = self._cont._to_per()
        self._val = vals
        if self._ENC_MAXLEN:
            bl_cur += sum([v[2] for v in cont_per])
            if bl_cur > self._ENC_MAXLEN:
                raise ASN1NotSuppErr('{0}: encoding too long, {1} bytes'.format(
                    self.fullname(), bl_cur >> 3))
        GEN.extend(cont_per)
    if bl_upd:
        bl[0] = bl_cur


if not getattr(_CONSTRUCT_OF, '_lasse_recursion_fix', False):
    _CONSTRUCT_OF._CONSTRUCT_OF__to_per_cont = _to_per_cont_recursion_safe
    _CONSTRUCT_OF._lasse_recursion_fix = True

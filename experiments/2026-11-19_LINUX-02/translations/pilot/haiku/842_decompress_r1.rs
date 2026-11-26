// SPDX-License-Identifier: GPL-2.0-or-later
/*
 * 842 Software Decompression
 *
 * Copyright (C) 2015 Dan Streetman, IBM Corp
 *
 * Rust translation of lib/842/842_decompress.c.
 * See 842.h for details of the 842 compressed format.
 */

use core::ffi::{c_int, c_uint};
use core::ptr;

// ---------------------------------------------------------------------------
// Constants from 842.h
// ---------------------------------------------------------------------------

/* special templates */
const OP_REPEAT: u64 = 0x1B;
const OP_ZEROS: u64 = 0x1C;
const OP_END: u64 = 0x1E;

/* sw only template - not in the hw design */
const OP_SHORT_DATA: u64 = 0x1D;

/* additional bits of each op param */
const OP_BITS: u8 = 5;
const REPEAT_BITS: u8 = 6;
const SHORT_DATA_BITS: u8 = 3;
const I2_BITS: u8 = 8;
const I4_BITS: u8 = 9;
const I8_BITS: u8 = 8;
const CRC_BITS: u8 = 32;

const SHORT_DATA_BITS_MAX: u64 = 0x7;

/* Arbitrary values used to indicate action */
const OP_ACTION: u8 = 0x70;
const OP_ACTION_INDEX: u8 = 0x10;
const OP_ACTION_DATA: u8 = 0x20;
const OP_ACTION_NOOP: u8 = 0x40;
const OP_AMOUNT: u8 = 0x0f;
const OP_AMOUNT_0: u8 = 0x00;
const OP_AMOUNT_2: u8 = 0x02;
const OP_AMOUNT_4: u8 = 0x04;
const OP_AMOUNT_8: u8 = 0x08;

const D2: u8 = OP_ACTION_DATA | OP_AMOUNT_2;
const D4: u8 = OP_ACTION_DATA | OP_AMOUNT_4;
const D8: u8 = OP_ACTION_DATA | OP_AMOUNT_8;
const I2: u8 = OP_ACTION_INDEX | OP_AMOUNT_2;
const I4: u8 = OP_ACTION_INDEX | OP_AMOUNT_4;
const I8: u8 = OP_ACTION_INDEX | OP_AMOUNT_8;
const N0: u8 = OP_ACTION_NOOP | OP_AMOUNT_0;

/* the max of the regular templates - not including the special templates */
const OPS_MAX: usize = 0x1a;

// ---------------------------------------------------------------------------
// Constants from linux/sw842.h / errno (x86_64) / limits
// ---------------------------------------------------------------------------

const EINVAL: c_int = 22;
const ENOSPC: c_int = 28;
const EOVERFLOW: c_int = 75;

const UINT_MAX: u32 = u32::MAX;

// ---------------------------------------------------------------------------
// Constants from 842_decompress.c
// ---------------------------------------------------------------------------

/* rolling fifo sizes */
const I2_FIFO_SIZE: u64 = 2 * (1u64 << I2_BITS);
const I4_FIFO_SIZE: u64 = 4 * (1u64 << I4_BITS);
const I8_FIFO_SIZE: u64 = 8 * (1u64 << I8_BITS);

static DECOMP_OPS: [[u8; 4]; OPS_MAX] = [
    [D8, N0, N0, N0],
    [D4, D2, I2, N0],
    [D4, I2, D2, N0],
    [D4, I2, I2, N0],
    [D4, I4, N0, N0],
    [D2, I2, D4, N0],
    [D2, I2, D2, I2],
    [D2, I2, I2, D2],
    [D2, I2, I2, I2],
    [D2, I2, I4, N0],
    [I2, D2, D4, N0],
    [I2, D4, I2, N0],
    [I2, D2, I2, D2],
    [I2, D2, I2, I2],
    [I2, D2, I4, N0],
    [I2, I2, D4, N0],
    [I2, I2, D2, I2],
    [I2, I2, I2, D2],
    [I2, I2, I2, I2],
    [I2, I2, I4, N0],
    [I4, D4, N0, N0],
    [I4, D2, I2, N0],
    [I4, I2, D2, N0],
    [I4, I2, I2, N0],
    [I4, I4, N0, N0],
    [I8, N0, N0, N0],
];

struct Sw842Param {
    input: *const u8,
    bit: u8,
    ilen: u64,
    out: *mut u8,
    ostart: *mut u8,
    olen: u64,
}

impl Sw842Param {
    /// Number of bytes written so far (p->out - p->ostart).
    #[inline]
    fn written(&self) -> u64 {
        (self.out as usize - self.ostart as usize) as u64
    }
}

extern "C" {
    /// u32 crc32_be(u32 crc, const u8 *p, size_t len)
    fn crc32_be(crc: u32, p: *const u8, len: usize) -> u32;
}

/// WARN(cond, ...): logging is a no-op here; returns cond.
#[inline]
fn warn(cond: bool) -> bool {
    cond
}

/// Unaligned big-endian load helper.
#[inline(always)]
unsafe fn load<const N: usize>(p: *const u8) -> [u8; N] {
    ptr::read_unaligned(p as *const [u8; N])
}

/// Mask with the low `n` bits set (GENMASK_ULL(n - 1, 0)).
#[inline(always)]
fn low_mask(n: u8) -> u64 {
    if n >= 64 {
        u64::MAX
    } else {
        (1u64 << n) - 1
    }
}

unsafe fn split_next_bits(p: &mut Sw842Param, d: &mut u64, n: u8, s: u8) -> c_int {
    let mut tmp: u64 = 0;
    let mut ret: c_int;

    if n <= s {
        /* pr_debug("split_next_bits invalid n %u s %u\n", n, s); */
        return -EINVAL;
    }

    ret = next_bits(p, &mut tmp, n - s);
    if ret != 0 {
        return ret;
    }
    ret = next_bits(p, d, s);
    if ret != 0 {
        return ret;
    }
    *d |= tmp << s;
    0
}

unsafe fn next_bits(p: &mut Sw842Param, d: &mut u64, n: u8) -> c_int {
    let inp = p.input;
    let b = p.bit;
    /* u8 arithmetic, as in the C original (no overflow possible for n <= 64) */
    let bits = b.wrapping_add(n);

    if n > 64 {
        /* pr_debug("next_bits invalid n %u\n", n); */
        return -EINVAL;
    }

    /* split this up if reading > 8 bytes, or if we're at the end of
     * the input buffer and would read past the end
     */
    if bits > 64 {
        return split_next_bits(p, d, n, 32);
    } else if p.ilen < 8 && bits > 32 && bits <= 56 {
        return split_next_bits(p, d, n, 16);
    } else if p.ilen < 4 && bits > 16 && bits <= 24 {
        return split_next_bits(p, d, n, 8);
    }

    /* DIV_ROUND_UP(bits, 8) > p->ilen */
    if (bits as u64 + 7) / 8 > p.ilen {
        return -EOVERFLOW;
    }

    let v: u64 = if bits <= 8 {
        (*inp as u64) >> (8 - bits)
    } else if bits <= 16 {
        (u16::from_be_bytes(load::<2>(inp)) as u64) >> (16 - bits)
    } else if bits <= 32 {
        (u32::from_be_bytes(load::<4>(inp)) as u64) >> (32 - bits)
    } else {
        u64::from_be_bytes(load::<8>(inp)) >> (64 - bits)
    };

    *d = v & low_mask(n);

    p.bit = bits;

    if p.bit > 7 {
        let bytes = (p.bit / 8) as u64;
        p.input = p.input.add(bytes as usize);
        p.ilen -= bytes;
        p.bit %= 8;
    }

    0
}

unsafe fn do_data(p: &mut Sw842Param, n: u8) -> c_int {
    let mut v: u64 = 0;

    if (n as u64) > p.olen {
        return -ENOSPC;
    }

    let ret = next_bits(p, &mut v, n * 8);
    if ret != 0 {
        return ret;
    }

    let be = v.to_be_bytes();
    match n {
        /* write the low n bytes of v, big-endian */
        2 | 4 | 8 => {
            ptr::copy_nonoverlapping(be.as_ptr().add(8 - n as usize), p.out, n as usize);
        }
        _ => return -EINVAL,
    }

    p.out = p.out.add(n as usize);
    p.olen -= n as u64;

    0
}

unsafe fn do_index_impl(p: &mut Sw842Param, size: u8, bits: u8, fsize: u64) -> c_int {
    let total = p.written() & !7u64; /* round_down(p->out - p->ostart, 8) */
    let mut index: u64 = 0;
    let mut offset: u64;

    if (size as u64) > p.olen {
        return -ENOSPC;
    }

    let ret = next_bits(p, &mut index, bits);
    if ret != 0 {
        return ret;
    }

    offset = index * (size as u64);

    /* a ring buffer of fsize is used; correct the offset */
    if total > fsize {
        /* this is where the current fifo is */
        let mut section = total & !(fsize - 1); /* round_down(total, fsize) */
        /* the current pos in the fifo */
        let pos = total - section;

        /* if the offset is past/at the pos, we need to
         * go back to the last fifo section
         */
        if offset >= pos {
            section -= fsize;
        }

        offset += section;
    }

    if offset + size as u64 > total {
        /* pr_debug("index%x points past end\n", size); */
        return -EINVAL;
    }

    /* WARN(1, "__do_index invalid size") when size is not 2/4/8; the copy
     * below still happens, exactly as in the C original. */
    let _ = warn(size != 2 && size != 4 && size != 8);

    ptr::copy(p.ostart.add(offset as usize), p.out, size as usize);
    p.out = p.out.add(size as usize);
    p.olen -= size as u64;

    0
}

unsafe fn do_index(p: &mut Sw842Param, n: u8) -> c_int {
    match n {
        2 => do_index_impl(p, 2, I2_BITS, I2_FIFO_SIZE),
        4 => do_index_impl(p, 4, I4_BITS, I4_FIFO_SIZE),
        8 => do_index_impl(p, 8, I8_BITS, I8_FIFO_SIZE),
        _ => -EINVAL,
    }
}

unsafe fn do_op(p: &mut Sw842Param, o: u8) -> c_int {
    if (o as usize) >= OPS_MAX {
        return -EINVAL;
    }

    for i in 0..4 {
        let op = DECOMP_OPS[o as usize][i];

        let ret = match op & OP_ACTION {
            OP_ACTION_DATA => do_data(p, op & OP_AMOUNT),
            OP_ACTION_INDEX => do_index(p, op & OP_AMOUNT),
            OP_ACTION_NOOP => 0,
            /* pr_err("Internal error, invalid op %x\n", op); */
            _ => return -EINVAL,
        };

        if ret != 0 {
            return ret;
        }
    }

    0
}

/// sw842_decompress
///
/// Decompress the 842-compressed buffer of length `ilen` at `input`
/// to the output buffer `out`, using no more than `*olen` bytes.
///
/// Returns: 0 on success, negative errno on failure. `*olen` receives the
/// number of output bytes written on success, or 0 on error.
#[no_mangle]
pub unsafe extern "C" fn sw842_decompress(
    input: *const u8,
    ilen: c_uint,
    out: *mut u8,
    olen: *mut c_uint,
) -> c_int {
    let mut p = Sw842Param {
        input,
        bit: 0,
        ilen: ilen as u64,
        out,
        ostart: out,
        olen: *olen as u64,
    };

    let total = p.olen;

    *olen = 0;

    loop {
        let mut op: u64 = 0;

        let ret = next_bits(&mut p, &mut op, OP_BITS);
        if ret != 0 {
            return ret;
        }

        match op {
            OP_REPEAT => {
                let mut rep: u64 = 0;

                let ret = next_bits(&mut p, &mut rep, REPEAT_BITS);
                if ret != 0 {
                    return ret;
                }

                if p.written() < 8 {
                    /* no complete previous block */
                    return -EINVAL;
                }

                /* copy rep + 1 */
                rep += 1;

                if rep * 8 > p.olen {
                    return -ENOSPC;
                }

                while rep > 0 {
                    rep -= 1;
                    ptr::copy_nonoverlapping(p.out.sub(8), p.out, 8);
                    p.out = p.out.add(8);
                    p.olen -= 8;
                }
            }
            OP_ZEROS => {
                if 8 > p.olen {
                    return -ENOSPC;
                }

                ptr::write_bytes(p.out, 0, 8);
                p.out = p.out.add(8);
                p.olen -= 8;
            }
            OP_SHORT_DATA => {
                let mut bytes: u64 = 0;

                let ret = next_bits(&mut p, &mut bytes, SHORT_DATA_BITS);
                if ret != 0 {
                    return ret;
                }

                if bytes == 0 || bytes > SHORT_DATA_BITS_MAX {
                    return -EINVAL;
                }
                if bytes > p.olen {
                    return -ENOSPC;
                }

                while bytes > 0 {
                    bytes -= 1;

                    let mut tmp: u64 = 0;
                    let ret = next_bits(&mut p, &mut tmp, 8);
                    if ret != 0 {
                        return ret;
                    }

                    *p.out = tmp as u8;
                    p.out = p.out.add(1);
                    p.olen -= 1;
                }
            }
            OP_END => {
                /* end of stream; loop exits below */
            }
            _ => {
                /* use template */
                let ret = do_op(&mut p, op as u8);
                if ret != 0 {
                    return ret;
                }
            }
        }

        if op == OP_END {
            break;
        }
    }

    /*
     * crc(0:31) is saved in compressed data starting with the
     * next bit after End of stream template.
     */
    let mut crc: u64 = 0;
    let ret = next_bits(&mut p, &mut crc, CRC_BITS);
    if ret != 0 {
        return ret;
    }

    let written = total - p.olen;

    /*
     * Validate CRC saved in compressed data.
     */
    let calc = crc32_be(0, out as *const u8, written as usize);
    if crc != calc as u64 {
        /* pr_debug("CRC mismatch for decompression\n"); */
        return -EINVAL;
    }

    if written > UINT_MAX as u64 {
        return -ENOSPC;
    }

    *olen = written as c_uint;

    0
}

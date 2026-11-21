use core::ffi::{c_int, c_uint};
use core::ptr;

extern "C" {
    fn crc32_be(crc: u32, p: *const u8, len: usize) -> u32;
}

const EINVAL: c_int = 22;
const ENOSPC: c_int = 28;
const EOVERFLOW: c_int = 75;

const OP_REPEAT: u64 = 0x1B;
const OP_ZEROS: u64 = 0x1C;
const OP_END: u64 = 0x1E;
const OP_SHORT_DATA: u64 = 0x1D;

const OP_BITS: u8 = 5;
const REPEAT_BITS: u8 = 6;
const SHORT_DATA_BITS: u8 = 3;
const I2_BITS: u8 = 8;
const I4_BITS: u8 = 9;
const I8_BITS: u8 = 8;
const CRC_BITS: u8 = 32;

const SHORT_DATA_BITS_MAX: u64 = 0x7;

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

const OPS_MAX: usize = 0x1a;

const I2_FIFO_SIZE: u64 = 2 * (1 << I2_BITS);
const I4_FIFO_SIZE: u64 = 4 * (1 << I4_BITS);
const I8_FIFO_SIZE: u64 = 8 * (1 << I8_BITS);

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
    in_: *mut u8,
    bit: u8,
    ilen: u64,
    out: *mut u8,
    ostart: *mut u8,
    olen: u64,
}

unsafe fn split_next_bits(p: &mut Sw842Param, d: *mut u64, n: u8, s: u8) -> c_int {
    let mut tmp: u64 = 0;

    if n <= s {
        return -EINVAL;
    }

    let ret = next_bits(p, &mut tmp, n - s);
    if ret != 0 {
        return ret;
    }
    let ret = next_bits(p, d, s);
    if ret != 0 {
        return ret;
    }
    *d |= tmp << s;
    0
}

unsafe fn next_bits(p: &mut Sw842Param, d: *mut u64, n: u8) -> c_int {
    let inp = p.in_;
    let b = p.bit;
    let bits: u8 = b.wrapping_add(n);

    if n > 64 {
        return -EINVAL;
    }

    if bits > 64 {
        return split_next_bits(p, d, n, 32);
    } else if p.ilen < 8 && bits > 32 && bits <= 56 {
        return split_next_bits(p, d, n, 16);
    } else if p.ilen < 4 && bits > 16 && bits <= 24 {
        return split_next_bits(p, d, n, 8);
    }

    if ((bits as u64) + 7) / 8 > p.ilen {
        return -EOVERFLOW;
    }

    if bits <= 8 {
        *d = ((*inp) as u64) >> (8 - bits);
    } else if bits <= 16 {
        let v = u16::from_be(ptr::read_unaligned(inp as *const u16));
        *d = (v as u64) >> (16 - bits);
    } else if bits <= 32 {
        let v = u32::from_be(ptr::read_unaligned(inp as *const u32));
        *d = (v as u64) >> (32 - bits);
    } else {
        let v = u64::from_be(ptr::read_unaligned(inp as *const u64));
        *d = v >> (64 - bits);
    }

    let mask: u64 = if n == 0 { 0 } else { u64::MAX >> (64 - n) };
    *d &= mask;

    p.bit += n;

    if p.bit > 7 {
        let adv = (p.bit / 8) as usize;
        p.in_ = p.in_.wrapping_add(adv);
        p.ilen -= adv as u64;
        p.bit %= 8;
    }

    0
}

unsafe fn do_data(p: &mut Sw842Param, n: u8) -> c_int {
    let mut v: u64 = 0;

    if (n as u64) > p.olen {
        return -ENOSPC;
    }

    let ret = next_bits(p, &mut v, ((n as u32) * 8) as u8);
    if ret != 0 {
        return ret;
    }

    match n {
        2 => ptr::write_unaligned(p.out as *mut u16, (v as u16).to_be()),
        4 => ptr::write_unaligned(p.out as *mut u32, (v as u32).to_be()),
        8 => ptr::write_unaligned(p.out as *mut u64, v.to_be()),
        _ => return -EINVAL,
    }

    p.out = p.out.wrapping_add(n as usize);
    p.olen -= n as u64;

    0
}

unsafe fn do_index_impl(p: &mut Sw842Param, size: u8, bits: u8, fsize: u64) -> c_int {
    let diff = (p.out as usize).wrapping_sub(p.ostart as usize) as i64;
    let total: u64 = (diff & !7i64) as u64;
    let mut index: u64 = 0;

    if (size as u64) > p.olen {
        return -ENOSPC;
    }

    let ret = next_bits(p, &mut index, bits);
    if ret != 0 {
        return ret;
    }

    let mut offset: u64 = index.wrapping_mul(size as u64);

    if total > fsize {
        let mut section: u64 = total & !(fsize - 1);
        let pos: u64 = total - section;

        if offset >= pos {
            section = section.wrapping_sub(fsize);
        }

        offset = offset.wrapping_add(section);
    }

    if offset.wrapping_add(size as u64) > total {
        return -EINVAL;
    }

    ptr::copy(p.ostart.wrapping_add(offset as usize), p.out, size as usize);
    p.out = p.out.wrapping_add(size as usize);
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
            _ => return -EINVAL,
        };

        if ret != 0 {
            return ret;
        }
    }

    0
}

#[no_mangle]
pub extern "C" fn sw842_decompress(
    in_: *const u8,
    ilen: c_uint,
    out: *mut u8,
    olen: *mut c_uint,
) -> c_int {
    unsafe {
        let mut p = Sw842Param {
            in_: in_ as *mut u8,
            bit: 0,
            ilen: ilen as u64,
            out,
            ostart: out,
            olen: *olen as u64,
        };
        let mut ret: c_int;
        let mut op: u64 = 0;
        let mut rep: u64 = 0;
        let mut tmp: u64 = 0;
        let mut bytes: u64 = 0;
        let mut crc: u64 = 0;

        let total: u64 = p.olen;

        *olen = 0;

        loop {
            ret = next_bits(&mut p, &mut op, OP_BITS);
            if ret != 0 {
                return ret;
            }

            match op {
                OP_REPEAT => {
                    ret = next_bits(&mut p, &mut rep, REPEAT_BITS);
                    if ret != 0 {
                        return ret;
                    }

                    let d = (p.out as usize).wrapping_sub(p.ostart as usize) as isize;
                    if d < 8 {
                        return -EINVAL;
                    }

                    rep += 1;

                    if rep * 8 > p.olen {
                        return -ENOSPC;
                    }

                    while rep > 0 {
                        rep -= 1;
                        ptr::copy(p.out.wrapping_sub(8), p.out, 8);
                        p.out = p.out.wrapping_add(8);
                        p.olen -= 8;
                    }
                }
                OP_ZEROS => {
                    if 8 > p.olen {
                        return -ENOSPC;
                    }

                    ptr::write_bytes(p.out, 0, 8);
                    p.out = p.out.wrapping_add(8);
                    p.olen -= 8;
                }
                OP_SHORT_DATA => {
                    ret = next_bits(&mut p, &mut bytes, SHORT_DATA_BITS);
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
                        ret = next_bits(&mut p, &mut tmp, 8);
                        if ret != 0 {
                            return ret;
                        }
                        *p.out = tmp as u8;
                        p.out = p.out.wrapping_add(1);
                        p.olen -= 1;
                    }
                }
                OP_END => {}
                _ => {
                    ret = do_op(&mut p, op as u8);
                    if ret != 0 {
                        return ret;
                    }
                }
            }

            if op == OP_END {
                break;
            }
        }

        ret = next_bits(&mut p, &mut crc, CRC_BITS);
        if ret != 0 {
            return ret;
        }

        let written = total - p.olen;
        if crc != crc32_be(0, out as *const u8, written as usize) as u64 {
            return -EINVAL;
        }

        if written > c_uint::MAX as u64 {
            return -ENOSPC;
        }

        *olen = written as c_uint;

        0
    }
}

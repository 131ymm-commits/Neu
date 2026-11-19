use core::ffi::{c_int, c_uint};
use core::ptr;

extern "C" {
    fn crc32_be(crc: u32, p: *const u8, len: usize) -> u32;
}

// ---- Константы из 842.h ----

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

const OPS_MAX: u8 = 0x1a;

// ---- Коды ошибок ----

const EINVAL: c_int = 22;
const ENOSPC: c_int = 28;
const EOVERFLOW: c_int = 75;

// ---- Размеры кольцевых FIFO из 842_decompress.c ----

const I2_FIFO_SIZE: u64 = 2 * (1u64 << I2_BITS);
const I4_FIFO_SIZE: u64 = 4 * (1u64 << I4_BITS);
const I8_FIFO_SIZE: u64 = 8 * (1u64 << I8_BITS);

static DECOMP_OPS: [[u8; 4]; 26] = [
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

#[repr(C)]
struct SwParam {
    input: *const u8,
    bit: u8,
    ilen: u64,
    out: *mut u8,
    ostart: *mut u8,
    olen: u64,
}

// ---- Вспомогательные функции ----

fn round_down(x: u64, y: u64) -> u64 {
    x & !(y - 1)
}

fn div_round_up(n: u64, d: u64) -> u64 {
    (n + d - 1) / d
}

fn out_pos(p: &SwParam) -> u64 {
    (p.out as usize - p.ostart as usize) as u64
}

/// SAFETY: p должен быть валиден для чтения 2 байт.
unsafe fn read_be16(p: *const u8) -> u16 {
    u16::from_be(ptr::read_unaligned(p as *const u16))
}

/// SAFETY: p должен быть валиден для чтения 4 байт.
unsafe fn read_be32(p: *const u8) -> u32 {
    u32::from_be(ptr::read_unaligned(p as *const u32))
}

/// SAFETY: p должен быть валиден для чтения 8 байт.
unsafe fn read_be64(p: *const u8) -> u64 {
    u64::from_be(ptr::read_unaligned(p as *const u64))
}

/// SAFETY: p должен быть валиден для записи 2 байт.
unsafe fn write_be16(p: *mut u8, v: u16) {
    ptr::write_unaligned(p as *mut u16, v.to_be());
}

/// SAFETY: p должен быть валиден для записи 4 байт.
unsafe fn write_be32(p: *mut u8, v: u32) {
    ptr::write_unaligned(p as *mut u32, v.to_be());
}

/// SAFETY: p должен быть валиден для записи 8 байт.
unsafe fn write_be64(p: *mut u8, v: u64) {
    ptr::write_unaligned(p as *mut u64, v.to_be());
}

// ---- Разбор битового потока ----

fn split_next_bits(p: &mut SwParam, d: &mut u64, n: u8, s: u8) -> c_int {
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

fn next_bits(p: &mut SwParam, d: &mut u64, n: u8) -> c_int {
    let b = p.bit;
    let bits = b.wrapping_add(n);

    if n > 64 {
        return -EINVAL;
    }

    // Разбиваем чтение, если оно больше 8 байт или вышло бы за конец входа.
    if bits > 64 {
        return split_next_bits(p, d, n, 32);
    } else if p.ilen < 8 && bits > 32 && bits <= 56 {
        return split_next_bits(p, d, n, 16);
    } else if p.ilen < 4 && bits > 16 && bits <= 24 {
        return split_next_bits(p, d, n, 8);
    }

    if div_round_up(bits as u64, 8) > p.ilen {
        return -EOVERFLOW;
    }

    let inp = p.input;
    // SAFETY: div_round_up(bits, 8) <= ilen, поэтому читается не больше ilen байт.
    let mut val: u64 = unsafe {
        if bits <= 8 {
            (*inp >> (8 - bits)) as u64
        } else if bits <= 16 {
            (read_be16(inp) >> (16 - bits)) as u64
        } else if bits <= 32 {
            (read_be32(inp) >> (32 - bits)) as u64
        } else {
            read_be64(inp) >> (64 - bits)
        }
    };

    let mask: u64 = if n >= 64 { u64::MAX } else { (1u64 << n) - 1 };
    val &= mask;
    *d = val;

    p.bit += n;

    if p.bit > 7 {
        let adv = p.bit / 8;
        // SAFETY: adv не превышает ilen (проверено выше), смещение внутри входа.
        p.input = unsafe { p.input.add(adv as usize) };
        p.ilen -= adv as u64;
        p.bit %= 8;
    }

    0
}

// ---- Операции ----

fn do_data(p: &mut SwParam, n: u8) -> c_int {
    if (n as u64) > p.olen {
        return -ENOSPC;
    }

    let mut v: u64 = 0;
    let ret = next_bits(p, &mut v, n.wrapping_mul(8));
    if ret != 0 {
        return ret;
    }

    // SAFETY: n <= olen проверено, запись n байт в выходной буфер.
    unsafe {
        match n {
            2 => write_be16(p.out, v as u16),
            4 => write_be32(p.out, v as u32),
            8 => write_be64(p.out, v),
            _ => return -EINVAL,
        }
        p.out = p.out.add(n as usize);
    }
    p.olen -= n as u64;

    0
}

fn __do_index(p: &mut SwParam, size: u8, bits: u8, fsize: u64) -> c_int {
    let total = round_down(out_pos(p), 8);

    if (size as u64) > p.olen {
        return -ENOSPC;
    }

    let mut index: u64 = 0;
    let ret = next_bits(p, &mut index, bits);
    if ret != 0 {
        return ret;
    }

    let mut offset = index * (size as u64);

    // Кольцевой буфер размером fsize: корректируем смещение.
    if total > fsize {
        let mut section = round_down(total, fsize);
        let pos = total - section;

        if offset >= pos {
            section -= fsize;
        }

        offset += section;
    }

    if offset + (size as u64) > total {
        return -EINVAL;
    }

    // size всегда 2, 4 или 8 (вызывается только из do_index), поэтому
    // WARN в оригинале не срабатывает; отладочный вывод на результат не влияет.

    // SAFETY: offset + size <= total <= out - ostart, источник и приёмник не перекрываются;
    // запись size байт в выходной буфер проверена через olen.
    unsafe {
        ptr::copy_nonoverlapping(p.ostart.add(offset as usize), p.out, size as usize);
        p.out = p.out.add(size as usize);
    }
    p.olen -= size as u64;

    0
}

fn do_index(p: &mut SwParam, n: u8) -> c_int {
    match n {
        2 => __do_index(p, 2, I2_BITS, I2_FIFO_SIZE),
        4 => __do_index(p, 4, I4_BITS, I4_FIFO_SIZE),
        8 => __do_index(p, 8, I8_BITS, I8_FIFO_SIZE),
        _ => -EINVAL,
    }
}

fn do_op(p: &mut SwParam, o: u8) -> c_int {
    if o >= OPS_MAX {
        return -EINVAL;
    }

    for i in 0..4usize {
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

// ---- Экспортируемая функция ----

#[no_mangle]
pub extern "C" fn sw842_decompress(
    input: *const u8,
    ilen: c_uint,
    out: *mut u8,
    olen: *mut c_uint,
) -> c_int {
    // SAFETY: olen указывает на допустимый unsigned int (контракт вызова из C).
    let olen_init = unsafe { *olen } as u64;

    let mut p = SwParam {
        input,
        bit: 0,
        ilen: ilen as u64,
        out,
        ostart: out,
        olen: olen_init,
    };

    let total = p.olen;

    // SAFETY: olen валиден (см. выше).
    unsafe {
        *olen = 0;
    }

    let mut op: u64 = 0;
    loop {
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

                // Нет полного предыдущего блока.
                if out_pos(&p) < 8 {
                    return -EINVAL;
                }

                // Копируем rep + 1 раз.
                rep += 1;

                if rep * 8 > p.olen {
                    return -ENOSPC;
                }

                for _ in 0..rep {
                    // SAFETY: есть не менее 8 записанных байт перед out и 8 свободных
                    // байт впереди; источник [out-8, out) и приёмник [out, out+8) не перекрываются.
                    unsafe {
                        ptr::copy_nonoverlapping(p.out.sub(8), p.out, 8);
                        p.out = p.out.add(8);
                    }
                    p.olen -= 8;
                }
            }
            OP_ZEROS => {
                if 8 > p.olen {
                    return -ENOSPC;
                }

                // SAFETY: 8 байт свободны (проверено olen).
                unsafe {
                    ptr::write_bytes(p.out, 0, 8);
                    p.out = p.out.add(8);
                }
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

                    // SAFETY: место для байта проверено через olen.
                    unsafe {
                        *p.out = tmp as u8;
                        p.out = p.out.add(1);
                    }
                    p.olen -= 1;
                }
            }
            OP_END => {}
            _ => {
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

    // CRC(0:31) записан сразу после шаблона END.
    let mut crc: u64 = 0;
    let ret = next_bits(&mut p, &mut crc, CRC_BITS);
    if ret != 0 {
        return ret;
    }

    let used = total - p.olen;

    // SAFETY: out..out+used — уже записанные выходные данные.
    let calc = unsafe { crc32_be(0, out as *const u8, used as usize) } as u64;
    if crc != calc {
        return -EINVAL;
    }

    if used > u32::MAX as u64 {
        return -ENOSPC;
    }

    // SAFETY: olen валиден (см. выше).
    unsafe {
        *olen = used as c_uint;
    }

    0
}

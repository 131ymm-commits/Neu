#![allow(non_camel_case_types)]

use core::ffi::{c_int, c_long, c_uint, c_void};
use core::mem::size_of;
use core::ptr::{copy_nonoverlapping, null_mut, write_bytes};

// ---------------------------------------------------------------------------
// Непрозрачные типы ядра (используются только через указатели)
// ---------------------------------------------------------------------------

#[repr(C)]
pub struct device {
    _opaque: [u8; 0],
}

#[repr(C)]
pub struct file {
    _opaque: [u8; 0],
}

#[repr(C)]
pub struct task_struct {
    _opaque: [u8; 0],
}

#[repr(C)]
struct strarray {
    array: *mut *mut u8,
    n: usize,
}

// ---------------------------------------------------------------------------
// Константы
// ---------------------------------------------------------------------------

const GFP_KERNEL: c_uint = 0xcc0;
const ENOENT: c_int = 2;
const ENOMEM: c_int = 12;
const EINVAL: c_int = 22;
const PAGE_SIZE: usize = 4096;
const PATH_MAX: usize = 4096;
const MAX_ERRNO: usize = 4095;
const HEX_ASC: &[u8; 16] = b"0123456789abcdef";

const STRING_UNITS_2: c_uint = 1;
const STRING_UNITS_MASK: c_uint = 1;
const STRING_UNITS_NO_SPACE: c_uint = 1 << 30;
const STRING_UNITS_NO_BYTES: c_uint = 1 << 31;

const UNESCAPE_SPACE: c_uint = 1 << 0;
const UNESCAPE_OCTAL: c_uint = 1 << 1;
const UNESCAPE_HEX: c_uint = 1 << 2;
const UNESCAPE_SPECIAL: c_uint = 1 << 3;

const ESCAPE_SPACE: c_uint = 1 << 0;
const ESCAPE_SPECIAL: c_uint = 1 << 1;
const ESCAPE_NULL: c_uint = 1 << 2;
const ESCAPE_OCTAL: c_uint = 1 << 3;
const ESCAPE_NP: c_uint = 1 << 4;
const ESCAPE_HEX: c_uint = 1 << 5;
const ESCAPE_NA: c_uint = 1 << 6;
const ESCAPE_NAP: c_uint = 1 << 7;
const ESCAPE_APPEND: c_uint = 1 << 8;

// ---------------------------------------------------------------------------
// Внешние функции ядра
// ---------------------------------------------------------------------------

extern "C" {
    fn kmalloc(size: usize, flags: c_uint) -> *mut c_void;
    fn kcalloc(n: usize, size: usize, flags: c_uint) -> *mut c_void;
    fn kfree(p: *const c_void);
    fn kstrdup(s: *const u8, gfp: c_uint) -> *mut u8;
    fn kasprintf(gfp: c_uint, fmt: *const u8, ...) -> *mut u8;
    fn snprintf(buf: *mut u8, size: usize, fmt: *const u8, ...) -> c_int;
    fn get_options(s: *const u8, nints: c_int, ints: *mut c_int) -> *mut u8;
    fn hex_to_bin(ch: u8) -> c_int;
    fn memdup_user_nul(src: *const c_void, len: usize) -> *mut c_void;
    fn file_path(file: *mut file, buf: *mut u8, buflen: c_int) -> *mut u8;
    fn get_cmdline(task: *mut task_struct, buffer: *mut u8, buflen: c_int) -> c_int;
    fn __devres_alloc_node(
        release: unsafe extern "C" fn(*mut device, *mut c_void),
        size: usize,
        gfp: c_uint,
        nid: c_int,
        name: *const u8,
    ) -> *mut c_void;
    fn devres_add(dev: *mut device, res: *mut c_void);
    fn devres_free(res: *mut c_void);
    fn strlen(s: *const u8) -> usize;
    fn strcmp(a: *const u8, b: *const u8) -> c_int;
}

// ---------------------------------------------------------------------------
// Вспомогательные функции (макросы и встроенные функции ядра)
// ---------------------------------------------------------------------------

/// isodigit: '0'..'7'
#[inline]
fn isodigit(c: u8) -> bool {
    (b'0'..=b'7').contains(&c)
}

/// isspace: 9..13, 32, 160
#[inline]
fn isspace(c: u8) -> bool {
    matches!(c, 9..=13 | 32 | 160)
}

/// isprint: 32..126, 160..255
#[inline]
fn isprint(c: u8) -> bool {
    matches!(c, 32..=126 | 160..=255)
}

/// isascii: 0..127
#[inline]
fn isascii(c: u8) -> bool {
    c <= 127
}

#[inline]
fn hex_asc_hi(x: u8) -> u8 {
    HEX_ASC[((x & 0xf0) >> 4) as usize]
}

#[inline]
fn hex_asc_lo(x: u8) -> u8 {
    HEX_ASC[(x & 0x0f) as usize]
}

/// do_div(n, base): делит n на месте, возвращает остаток.
#[inline]
fn do_div(n: &mut u64, base: u32) -> u32 {
    let b = base as u64;
    let r = (*n % b) as u32;
    *n /= b;
    r
}

/// IS_ERR: адрес как беззнаковое не меньше (unsigned long)-4095.
#[inline]
fn is_err<T>(p: *const T) -> bool {
    (p as usize) >= (usize::MAX - (MAX_ERRNO - 1))
}

/// PTR_ERR
#[inline]
fn ptr_err<T>(p: *const T) -> c_long {
    p as usize as c_long
}

/// ERR_PTR
#[inline]
fn err_ptr<T>(e: c_long) -> *mut T {
    e as usize as *mut T
}

/// WARN_ON: журнал недоступен в core-only варианте (без ввода-вывода); возвращает cond.
#[inline]
fn warn_on(cond: bool) -> bool {
    cond
}

/// strchr(s, c) != NULL: для c == 0 совпадает с терминатором, как в C.
#[inline]
unsafe fn strchr_u8(mut s: *const u8, c: u8) -> bool {
    loop {
        let v = *s;
        if v == c {
            return true;
        }
        if v == 0 {
            return false;
        }
        s = s.add(1);
    }
}

/// __devres_alloc_node(release, size, gfp, -1, name) — devres_alloc
#[inline]
unsafe fn devres_alloc(
    release: unsafe extern "C" fn(*mut device, *mut c_void),
    size: usize,
    gfp: c_uint,
) -> *mut c_void {
    __devres_alloc_node(release, size, gfp, -1, b"devm_kfree_strarray\0".as_ptr())
}

// ---------------------------------------------------------------------------
// string_get_size
// ---------------------------------------------------------------------------

#[no_mangle]
pub extern "C" fn string_get_size(
    mut size: u64,
    mut blk_size: u64,
    units: c_uint,
    buf: *mut u8,
    len: c_int,
) -> c_int {
    const UNITS_10: [&[u8]; 9] = [
        b"\0", b"k\0", b"M\0", b"G\0", b"T\0", b"P\0", b"E\0", b"Z\0", b"Y\0",
    ];
    const UNITS_2: [&[u8]; 9] = [
        b"\0", b"Ki\0", b"Mi\0", b"Gi\0", b"Ti\0", b"Pi\0", b"Ei\0", b"Zi\0", b"Yi\0",
    ];
    const DIVISOR: [u32; 2] = [1000, 1024];
    const ROUNDING: [u32; 3] = [500, 50, 5];

    let units_base = (units & STRING_UNITS_MASK) as usize;
    let mut i: c_int = 0;
    let mut tmp = [0u8; 12];

    if blk_size == 0 {
        size = 0;
    }

    // Пути "goto out" в C пропускают весь этот блок.
    if size != 0 {
        let mut remainder: u32 = 0;
        let mut j: usize = 0;

        while (blk_size >> 32) != 0 {
            do_div(&mut blk_size, DIVISOR[units_base]);
            i += 1;
        }

        while (size >> 32) != 0 {
            do_div(&mut size, DIVISOR[units_base]);
            i += 1;
        }

        size = size.wrapping_mul(blk_size);

        while size >= DIVISOR[units_base] as u64 {
            remainder = do_div(&mut size, DIVISOR[units_base]);
            i += 1;
        }

        let mut sf_cap: u32 = size as u32;
        while sf_cap.wrapping_mul(10) < 1000 {
            sf_cap = sf_cap.wrapping_mul(10);
            j += 1;
        }

        if units_base == STRING_UNITS_2 as usize {
            remainder = remainder.wrapping_mul(1000);
            remainder >>= 10;
        }

        remainder = remainder.wrapping_add(ROUNDING[j]);
        if remainder >= 1000 {
            remainder -= 1000;
            size += 1;
        }

        if j != 0 {
            unsafe {
                snprintf(
                    tmp.as_mut_ptr(),
                    tmp.len(),
                    b".%03u\0".as_ptr(),
                    remainder as c_uint,
                );
            }
            tmp[j + 1] = 0;
        }
    }

    // out:
    let table: &[&[u8]; 9] = if units_base == 1 { &UNITS_2 } else { &UNITS_10 };
    let unit: *const u8 = if (i as usize) >= table.len() {
        b"UNK\0".as_ptr()
    } else {
        table[i as usize].as_ptr()
    };
    let sep: *const u8 = if units & STRING_UNITS_NO_SPACE != 0 {
        b"\0".as_ptr()
    } else {
        b" \0".as_ptr()
    };
    let bsuf: *const u8 = if units & STRING_UNITS_NO_BYTES != 0 {
        b"\0".as_ptr()
    } else {
        b"B\0".as_ptr()
    };

    unsafe {
        snprintf(
            buf,
            len as usize,
            b"%u%s%s%s%s\0".as_ptr(),
            size as c_uint,
            tmp.as_ptr(),
            sep,
            unit,
            bsuf,
        )
    }
}

// ---------------------------------------------------------------------------
// parse_int_array / parse_int_array_user
// ---------------------------------------------------------------------------

#[no_mangle]
pub extern "C" fn parse_int_array(buf: *const u8, _count: usize, array: *mut *mut c_int) -> c_int {
    unsafe {
        let mut nints: c_int = 0;
        get_options(buf, 0, &mut nints);
        if nints == 0 {
            return -ENOENT;
        }

        // kzalloc_objs(*ints, nints + 1) == kcalloc(nints + 1, sizeof(int), GFP_KERNEL)
        let ints = kcalloc(
            nints.wrapping_add(1) as usize,
            size_of::<c_int>(),
            GFP_KERNEL,
        ) as *mut c_int;
        if ints.is_null() {
            return -ENOMEM;
        }

        get_options(buf, nints.wrapping_add(1), ints);
        *array = ints;

        0
    }
}

#[no_mangle]
pub extern "C" fn parse_int_array_user(
    from: *const u8,
    count: usize,
    array: *mut *mut c_int,
) -> c_int {
    unsafe {
        let buf = memdup_user_nul(from as *const c_void, count) as *mut u8;
        if is_err(buf as *const u8) {
            return ptr_err(buf as *const u8) as c_int;
        }

        let ret = parse_int_array(buf, count, array);
        kfree(buf as *const c_void);
        ret
    }
}

// ---------------------------------------------------------------------------
// string_unescape
// ---------------------------------------------------------------------------

unsafe fn unescape_space(src: &mut *mut u8, dst: &mut *mut u8) -> bool {
    let p = *dst;
    let q = *src;
    let v = match *q {
        b'n' => b'\n',
        b'r' => b'\r',
        b't' => b'\t',
        b'v' => 0x0b,
        b'f' => 0x0c,
        _ => return false,
    };
    *p = v;
    *dst = p.add(1);
    *src = q.add(1);
    true
}

unsafe fn unescape_octal(src: &mut *mut u8, dst: &mut *mut u8) -> bool {
    let p = *dst;
    let start = *src;
    let mut q = start;

    if !isodigit(*q) {
        return false;
    }

    let mut num: u8 = *q & 7;
    q = q.add(1);
    while num < 32 && isodigit(*q) && (q as usize - start as usize) < 3 {
        num <<= 3;
        num += *q & 7;
        q = q.add(1);
    }

    *p = num;
    *dst = p.add(1);
    *src = q;
    true
}

unsafe fn unescape_hex(src: &mut *mut u8, dst: &mut *mut u8) -> bool {
    let p = *dst;
    let mut q = *src;

    if *q != b'x' {
        return false;
    }
    q = q.add(1);

    let digit = hex_to_bin(*q);
    q = q.add(1);
    if digit < 0 {
        return false;
    }
    let mut num: u8 = digit as u8;

    let digit2 = hex_to_bin(*q);
    if digit2 >= 0 {
        q = q.add(1);
        num = (num << 4) | (digit2 as u8);
    }

    *p = num;
    *dst = p.add(1);
    *src = q;
    true
}

unsafe fn unescape_special(src: &mut *mut u8, dst: &mut *mut u8) -> bool {
    let p = *dst;
    let q = *src;
    let v = match *q {
        b'"' => b'"',
        b'\\' => b'\\',
        b'a' => 7,
        b'e' => 27,
        _ => return false,
    };
    *p = v;
    *dst = p.add(1);
    *src = q.add(1);
    true
}

#[no_mangle]
pub extern "C" fn string_unescape(
    mut src: *mut u8,
    dst: *mut u8,
    size: usize,
    flags: c_uint,
) -> c_int {
    unsafe {
        let mut out = dst;
        let mut size = if size == 0 { usize::MAX } else { size };

        // while (*src && --size)
        while *src != 0 {
            size -= 1;
            if size == 0 {
                break;
            }

            if *src == b'\\' && *src.add(1) != 0 && size > 1 {
                src = src.add(1);
                size -= 1;

                if flags & UNESCAPE_SPACE != 0 && unescape_space(&mut src, &mut out) {
                    continue;
                }
                if flags & UNESCAPE_OCTAL != 0 && unescape_octal(&mut src, &mut out) {
                    continue;
                }
                if flags & UNESCAPE_HEX != 0 && unescape_hex(&mut src, &mut out) {
                    continue;
                }
                if flags & UNESCAPE_SPECIAL != 0 && unescape_special(&mut src, &mut out) {
                    continue;
                }

                *out = b'\\';
                out = out.add(1);
            }

            *out = *src;
            out = out.add(1);
            src = src.add(1);
        }

        *out = 0;

        out.offset_from(dst) as c_int
    }
}

// ---------------------------------------------------------------------------
// string_escape_mem
// ---------------------------------------------------------------------------

/// Буфер вывода: запись только при pos < cap, pos считает все байты (как указатель p в C).
struct EscBuf {
    base: *mut u8,
    pos: usize,
    cap: usize,
}

impl EscBuf {
    #[inline]
    unsafe fn put(&mut self, v: u8) {
        if self.pos < self.cap {
            *self.base.add(self.pos) = v;
        }
        self.pos += 1;
    }
}

unsafe fn escape_passthrough(c: u8, out: &mut EscBuf) -> bool {
    out.put(c);
    true
}

unsafe fn escape_space(c: u8, out: &mut EscBuf) -> bool {
    let to = match c {
        b'\n' => b'n',
        b'\r' => b'r',
        b'\t' => b't',
        11 => b'v',
        12 => b'f',
        _ => return false,
    };
    out.put(b'\\');
    out.put(to);
    true
}

unsafe fn escape_special(c: u8, out: &mut EscBuf) -> bool {
    let to = match c {
        b'\\' => b'\\',
        7 => b'a',
        27 => b'e',
        b'"' => b'"',
        _ => return false,
    };
    out.put(b'\\');
    out.put(to);
    true
}

unsafe fn escape_null(c: u8, out: &mut EscBuf) -> bool {
    if c != 0 {
        return false;
    }
    out.put(b'\\');
    out.put(b'0');
    true
}

unsafe fn escape_octal(c: u8, out: &mut EscBuf) -> bool {
    out.put(b'\\');
    out.put(((c >> 6) & 0x07) + b'0');
    out.put(((c >> 3) & 0x07) + b'0');
    out.put((c & 0x07) + b'0');
    true
}

unsafe fn escape_hex(c: u8, out: &mut EscBuf) -> bool {
    out.put(b'\\');
    out.put(b'x');
    out.put(hex_asc_hi(c));
    out.put(hex_asc_lo(c));
    true
}

#[no_mangle]
pub extern "C" fn string_escape_mem(
    src: *const u8,
    isz: usize,
    dst: *mut u8,
    osz: usize,
    flags: c_uint,
    only: *const u8,
) -> c_int {
    unsafe {
        let mut out = EscBuf {
            base: dst,
            pos: 0,
            cap: osz,
        };
        let is_dict = !only.is_null() && *only != 0;
        let is_append = flags & ESCAPE_APPEND != 0;

        let mut s = src;
        let mut left = isz;
        while left != 0 {
            left -= 1;
            let c = *s;
            s = s.add(1);

            let in_dict = is_dict && strchr_u8(only, c);

            if !(is_append || in_dict) && is_dict && escape_passthrough(c, &mut out) {
                continue;
            }
            if !(is_append && in_dict)
                && isascii(c)
                && isprint(c)
                && (flags & ESCAPE_NAP) != 0
                && escape_passthrough(c, &mut out)
            {
                continue;
            }
            if !(is_append && in_dict)
                && isprint(c)
                && (flags & ESCAPE_NP) != 0
                && escape_passthrough(c, &mut out)
            {
                continue;
            }
            if !(is_append && in_dict)
                && isascii(c)
                && (flags & ESCAPE_NA) != 0
                && escape_passthrough(c, &mut out)
            {
                continue;
            }

            if (flags & ESCAPE_SPACE) != 0 && escape_space(c, &mut out) {
                continue;
            }
            if (flags & ESCAPE_SPECIAL) != 0 && escape_special(c, &mut out) {
                continue;
            }
            if (flags & ESCAPE_NULL) != 0 && escape_null(c, &mut out) {
                continue;
            }
            // ESCAPE_OCTAL и ESCAPE_HEX всегда последними
            if (flags & ESCAPE_OCTAL) != 0 && escape_octal(c, &mut out) {
                continue;
            }
            if (flags & ESCAPE_HEX) != 0 && escape_hex(c, &mut out) {
                continue;
            }

            escape_passthrough(c, &mut out);
        }

        out.pos as c_int
    }
}

// ---------------------------------------------------------------------------
// kstrdup_quotable* и связанные
// ---------------------------------------------------------------------------

#[no_mangle]
pub extern "C" fn kstrdup_quotable(src: *const u8, gfp: c_uint) -> *mut u8 {
    unsafe {
        const FLAGS: c_uint = ESCAPE_HEX;
        const ESC: &[u8] = b"\x0c\n\r\t\x0b\x07\x1b\\\"\0";

        if src.is_null() {
            return null_mut();
        }
        let slen = strlen(src);

        let dlen = string_escape_mem(src, slen, null_mut(), 0, FLAGS, ESC.as_ptr()) as usize;
        let dst = kmalloc(dlen.wrapping_add(1), gfp) as *mut u8;
        if dst.is_null() {
            return null_mut();
        }

        warn_on(
            string_escape_mem(src, slen, dst, dlen, FLAGS, ESC.as_ptr()) as usize != dlen,
        );
        *dst.add(dlen) = 0;

        dst
    }
}

#[no_mangle]
pub extern "C" fn kstrdup_quotable_cmdline(task: *mut task_struct, gfp: c_uint) -> *mut u8 {
    unsafe {
        let buffer = kmalloc(PAGE_SIZE, GFP_KERNEL) as *mut u8;
        if buffer.is_null() {
            return null_mut();
        }

        let mut res = get_cmdline(task, buffer, (PAGE_SIZE - 1) as c_int) as isize;
        *buffer.offset(res) = 0;

        // Схлопываем хвостовые NUL; res указывает на последний не-NUL.
        res -= 1;
        while res >= 0 && *buffer.offset(res) == 0 {
            res -= 1;
        }

        // Межаргументные NUL -> пробелы.
        let mut i: isize = 0;
        while i <= res {
            if *buffer.offset(i) == 0 {
                *buffer.offset(i) = b' ';
            }
            i += 1;
        }

        let quoted = kstrdup_quotable(buffer, gfp);
        kfree(buffer as *const c_void);
        quoted
    }
}

#[no_mangle]
pub extern "C" fn kstrdup_quotable_file(file: *mut file, gfp: c_uint) -> *mut u8 {
    unsafe {
        if file.is_null() {
            return kstrdup(b"<unknown>\0".as_ptr(), gfp);
        }

        // 11 байт для " (deleted)"
        let temp = kmalloc(PATH_MAX + 11, GFP_KERNEL) as *mut u8;
        if temp.is_null() {
            return kstrdup(b"<no_memory>\0".as_ptr(), gfp);
        }

        let mut pathname = file_path(file, temp, (PATH_MAX + 11) as c_int);
        if is_err(pathname as *const u8) {
            pathname = kstrdup(b"<too_long>\0".as_ptr(), gfp);
        } else {
            pathname = kstrdup_quotable(pathname, gfp);
        }

        kfree(temp as *const c_void);
        pathname
    }
}

#[no_mangle]
pub extern "C" fn kstrdup_and_replace(src: *const u8, old: u8, new: u8, gfp: c_uint) -> *mut u8 {
    unsafe {
        let dst = kstrdup(src, gfp);
        if dst.is_null() {
            return null_mut();
        }
        strreplace(dst, old, new)
    }
}

// ---------------------------------------------------------------------------
// strarray
// ---------------------------------------------------------------------------

#[no_mangle]
pub extern "C" fn kasprintf_strarray(gfp: c_uint, prefix: *const u8, n: usize) -> *mut *mut u8 {
    unsafe {
        let names = kcalloc(n, size_of::<*mut u8>(), gfp) as *mut *mut u8;
        if names.is_null() {
            return null_mut();
        }

        let mut i: usize = 0;
        while i < n {
            let s = kasprintf(gfp, b"%s-%zu\0".as_ptr(), prefix, i);
            *names.add(i) = s;
            if s.is_null() {
                kfree_strarray(names, i);
                return null_mut();
            }
            i += 1;
        }

        names
    }
}

#[no_mangle]
pub extern "C" fn kfree_strarray(array: *mut *mut u8, n: usize) {
    unsafe {
        if array.is_null() {
            return;
        }

        let mut i: u32 = 0;
        while (i as usize) < n {
            kfree(*array.add(i as usize) as *const c_void);
            i = i.wrapping_add(1);
        }

        kfree(array as *const c_void);
    }
}

/// static-функция, передаётся C-коду как release-callback, поэтому имеет C ABI.
unsafe extern "C" fn devm_kfree_strarray(_dev: *mut device, res: *mut c_void) {
    let array = res as *mut strarray;
    kfree_strarray((*array).array, (*array).n);
}

#[no_mangle]
pub extern "C" fn devm_kasprintf_strarray(
    dev: *mut device,
    prefix: *const u8,
    n: usize,
) -> *mut *mut u8 {
    unsafe {
        let ptr = devres_alloc(devm_kfree_strarray, size_of::<strarray>(), GFP_KERNEL)
            as *mut strarray;
        if ptr.is_null() {
            return err_ptr(-(ENOMEM as c_long));
        }

        (*ptr).n = n;
        (*ptr).array = kasprintf_strarray(GFP_KERNEL, prefix, n);
        if (*ptr).array.is_null() {
            devres_free(ptr as *mut c_void);
            return err_ptr(-(ENOMEM as c_long));
        }

        devres_add(dev, ptr as *mut c_void);

        (*ptr).array
    }
}

// ---------------------------------------------------------------------------
// skip_spaces / strim / sysfs_streq / match_string / strreplace / memcpy_and_pad
// ---------------------------------------------------------------------------

#[no_mangle]
pub extern "C" fn skip_spaces(mut s: *const u8) -> *mut u8 {
    unsafe {
        while isspace(*s) {
            s = s.add(1);
        }
        s as *mut u8
    }
}

#[no_mangle]
pub extern "C" fn strim(s: *mut u8) -> *mut u8 {
    unsafe {
        let size = strlen(s);
        if size == 0 {
            return s;
        }

        let mut end: isize = size as isize - 1;
        while end >= 0 && isspace(*s.offset(end)) {
            end -= 1;
        }
        *s.offset(end + 1) = 0;

        skip_spaces(s)
    }
}

#[no_mangle]
pub extern "C" fn sysfs_streq(mut s1: *const u8, mut s2: *const u8) -> bool {
    unsafe {
        while *s1 != 0 && *s1 == *s2 {
            s1 = s1.add(1);
            s2 = s2.add(1);
        }

        if *s1 == *s2 {
            return true;
        }
        if *s1 == 0 && *s2 == b'\n' && *s2.add(1) == 0 {
            return true;
        }
        if *s1 == b'\n' && *s1.add(1) == 0 && *s2 == 0 {
            return true;
        }
        false
    }
}

#[no_mangle]
pub extern "C" fn match_string(
    array: *const *const u8,
    n: usize,
    string: *const u8,
) -> c_int {
    unsafe {
        let mut index: usize = 0;
        while index < n {
            let item = *array.add(index);
            if item.is_null() {
                break;
            }
            if strcmp(item, string) == 0 {
                return index as c_int;
            }
            index += 1;
        }
        -EINVAL
    }
}

#[no_mangle]
pub extern "C" fn __sysfs_match_string(
    array: *const *const u8,
    n: usize,
    str: *const u8,
) -> c_int {
    unsafe {
        let mut index: usize = 0;
        while index < n {
            let item = *array.add(index);
            if item.is_null() {
                break;
            }
            if sysfs_streq(item, str) {
                return index as c_int;
            }
            index += 1;
        }
        -EINVAL
    }
}

#[no_mangle]
pub extern "C" fn strreplace(str: *mut u8, old: u8, new: u8) -> *mut u8 {
    unsafe {
        let mut s = str;
        while *s != 0 {
            if *s == old {
                *s = new;
            }
            s = s.add(1);
        }
        str
    }
}

#[no_mangle]
pub extern "C" fn memcpy_and_pad(
    dest: *mut c_void,
    dest_len: usize,
    src: *const c_void,
    count: usize,
    pad: c_int,
) {
    unsafe {
        // memcpy/memset не входят в список внешних функций; используем эквивалентные
        // примитивы core (они лоуэрятся в те же memcpy/memset).
        let d = dest as *mut u8;
        let s = src as *const u8;
        if dest_len > count {
            copy_nonoverlapping(s, d, count);
            write_bytes(d.add(count), pad as u8, dest_len - count);
        } else {
            copy_nonoverlapping(s, d, dest_len);
        }
    }
}

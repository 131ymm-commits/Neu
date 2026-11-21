#![allow(non_snake_case)]
#![allow(non_camel_case_types)]
#![allow(clippy::missing_safety_doc)]

use core::ffi::{c_int, c_long, c_uint, c_ulong, c_void};

pub type gfp_t = c_uint;
pub const GFP_KERNEL: gfp_t = 0xcc0;

const EINVAL: c_int = 22;
const ENOMEM: c_int = 12;
const ENOENT: c_int = 2;
const PAGE_SIZE: usize = 4096;
const PATH_MAX: usize = 4096;
const MAX_ERRNO: c_ulong = 4095;

pub const STRING_UNITS_10: c_uint = 0;
pub const STRING_UNITS_2: c_uint = 1;
pub const STRING_UNITS_MASK: c_uint = 1 << 0;
pub const STRING_UNITS_NO_SPACE: c_uint = 1 << 30;
pub const STRING_UNITS_NO_BYTES: c_uint = 1 << 31;

pub const UNESCAPE_SPACE: c_uint = 1 << 0;
pub const UNESCAPE_OCTAL: c_uint = 1 << 1;
pub const UNESCAPE_HEX: c_uint = 1 << 2;
pub const UNESCAPE_SPECIAL: c_uint = 1 << 3;
pub const UNESCAPE_ANY: c_uint = UNESCAPE_SPACE | UNESCAPE_OCTAL | UNESCAPE_HEX | UNESCAPE_SPECIAL;
pub const UNESCAPE_ALL_MASK: c_uint = 0xf;

pub const ESCAPE_SPACE: c_uint = 1 << 0;
pub const ESCAPE_SPECIAL: c_uint = 1 << 1;
pub const ESCAPE_NULL: c_uint = 1 << 2;
pub const ESCAPE_OCTAL: c_uint = 1 << 3;
pub const ESCAPE_ANY: c_uint = ESCAPE_SPACE | ESCAPE_OCTAL | ESCAPE_SPECIAL | ESCAPE_NULL;
pub const ESCAPE_NP: c_uint = 1 << 4;
pub const ESCAPE_ANY_NP: c_uint = ESCAPE_ANY | ESCAPE_NP;
pub const ESCAPE_HEX: c_uint = 1 << 5;
pub const ESCAPE_NA: c_uint = 1 << 6;
pub const ESCAPE_NAP: c_uint = 1 << 7;
pub const ESCAPE_APPEND: c_uint = 1 << 8;
pub const ESCAPE_ALL_MASK: c_uint = 0x1ff;

#[repr(C)]
pub struct device {
    _private: [u8; 0],
}
#[repr(C)]
pub struct file {
    _private: [u8; 0],
}
#[repr(C)]
pub struct task_struct {
    _private: [u8; 0],
}

#[repr(C)]
struct strarray {
    array: *mut *mut u8,
    n: usize,
}

type DrRelease = unsafe extern "C" fn(dev: *mut device, res: *mut c_void);

extern "C" {
    fn kmalloc(size: usize, flags: gfp_t) -> *mut c_void;
    fn kcalloc(n: usize, size: usize, flags: gfp_t) -> *mut c_void;
    fn kfree(p: *const c_void);
    fn kstrdup(s: *const u8, gfp: gfp_t) -> *mut u8;
    fn kasprintf(gfp: gfp_t, fmt: *const u8, ...) -> *mut u8;
    fn snprintf(buf: *mut u8, size: usize, fmt: *const u8, ...) -> c_int;
    fn get_options(str: *const u8, nints: c_int, ints: *mut c_int) -> *mut u8;
    fn hex_to_bin(ch: u8) -> c_int;
    fn memdup_user_nul(src: *const c_void, len: usize) -> *mut c_void;
    fn file_path(file: *mut file, buf: *mut u8, buflen: c_int) -> *mut u8;
    fn get_cmdline(task: *mut task_struct, buffer: *mut u8, buflen: c_int) -> c_int;
    fn __devres_alloc_node(
        release: Option<DrRelease>,
        size: usize,
        gfp: gfp_t,
        nid: c_int,
        name: *const u8,
    ) -> *mut c_void;
    fn devres_add(dev: *mut device, res: *mut c_void);
    fn devres_free(res: *mut c_void);
    fn strlen(s: *const u8) -> usize;
    fn strcmp(a: *const u8, b: *const u8) -> c_int;
}

#[inline]
fn isprint(c: u8) -> bool {
    (32..=126).contains(&c) || c >= 160
}
#[inline]
fn isspace(c: u8) -> bool {
    (9..=13).contains(&c) || c == 32 || c == 160
}
#[inline]
fn isascii(c: u8) -> bool {
    c <= 127
}
#[inline]
fn isodigit(c: u8) -> bool {
    (b'0'..=b'7').contains(&c)
}
#[inline]
fn do_div(n: &mut u64, base: u32) -> u32 {
    let rem = (*n % base as u64) as u32;
    *n /= base as u64;
    rem
}
#[inline]
fn is_err<T>(p: *const T) -> bool {
    (p as usize as c_ulong) >= (MAX_ERRNO.wrapping_neg())
}
#[inline]
fn err_ptr<T>(e: c_long) -> *mut T {
    e as isize as usize as *mut T
}
#[inline]
fn ptr_err<T>(p: *const T) -> c_long {
    p as usize as isize as c_long
}

const HEX_ASC: &[u8; 16] = b"0123456789abcdef";

static UNITS_10: [&[u8]; 9] = [
    b"\0", b"k\0", b"M\0", b"G\0", b"T\0", b"P\0", b"E\0", b"Z\0", b"Y\0",
];
static UNITS_2: [&[u8]; 9] = [
    b"\0", b"Ki\0", b"Mi\0", b"Gi\0", b"Ti\0", b"Pi\0", b"Ei\0", b"Zi\0", b"Yi\0",
];
static UNITS_STR: [&[&[u8]; 9]; 2] = [&UNITS_10, &UNITS_2];
static DIVISOR: [u32; 2] = [1000, 1024];
static ROUNDING: [u32; 3] = [500, 50, 5];

#[no_mangle]
pub extern "C" fn string_get_size(
    mut size: u64,
    mut blk_size: u64,
    units: c_uint,
    buf: *mut u8,
    len: c_int,
) -> c_int {
    let units_base = (units & STRING_UNITS_MASK) as usize;
    let mut i: c_int = 0;
    let mut remainder: u32 = 0;
    let mut tmp = [0u8; 12];

    tmp[0] = 0;

    if blk_size == 0 {
        size = 0;
    }
    if size != 0 {
        let div = DIVISOR[units_base];

        while blk_size >> 32 != 0 {
            do_div(&mut blk_size, div);
            i = i.wrapping_add(1);
        }

        while size >> 32 != 0 {
            do_div(&mut size, div);
            i = i.wrapping_add(1);
        }

        size = size.wrapping_mul(blk_size);

        while size >= div as u64 {
            remainder = do_div(&mut size, div);
            i = i.wrapping_add(1);
        }

        let mut sf_cap: u32 = size as u32;
        let mut j: usize = 0;
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
            size = size.wrapping_add(1);
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

    let unit: *const u8 = if (i as usize) >= UNITS_2.len() {
        b"UNK\0".as_ptr()
    } else {
        UNITS_STR[units_base][i as usize].as_ptr()
    };

    let space: *const u8 = if units & STRING_UNITS_NO_SPACE != 0 {
        b"\0".as_ptr()
    } else {
        b" \0".as_ptr()
    };
    let bytes: *const u8 = if units & STRING_UNITS_NO_BYTES != 0 {
        b"\0".as_ptr()
    } else {
        b"B\0".as_ptr()
    };

    unsafe {
        snprintf(
            buf,
            len as usize,
            b"%u%s%s%s%s\0".as_ptr(),
            size as u32 as c_uint,
            tmp.as_ptr(),
            space,
            unit,
            bytes,
        )
    }
}

#[no_mangle]
pub extern "C" fn parse_int_array(buf: *const u8, _count: usize, array: *mut *mut c_int) -> c_int {
    let mut nints: c_int = 0;
    unsafe {
        get_options(buf, 0, &mut nints);
        if nints == 0 {
            return -ENOENT;
        }

        let ints = kcalloc(
            nints.wrapping_add(1) as usize,
            core::mem::size_of::<c_int>(),
            GFP_KERNEL,
        ) as *mut c_int;
        if ints.is_null() {
            return -ENOMEM;
        }

        get_options(buf, nints.wrapping_add(1), ints);
        *array = ints;
    }
    0
}

#[no_mangle]
pub extern "C" fn parse_int_array_user(
    from: *const u8,
    count: usize,
    array: *mut *mut c_int,
) -> c_int {
    unsafe {
        let buf = memdup_user_nul(from as *const c_void, count) as *mut u8;
        if is_err(buf) {
            return ptr_err(buf) as c_int;
        }

        let ret = parse_int_array(buf, count, array);
        kfree(buf as *const c_void);
        ret
    }
}

unsafe fn unescape_space(src: &mut *mut u8, dst: &mut *mut u8) -> bool {
    let p = *dst;
    let q = *src;
    *p = match *q {
        b'n' => b'\n',
        b'r' => b'\r',
        b't' => b'\t',
        b'v' => 0x0b,
        b'f' => 0x0c,
        _ => return false,
    };
    *dst = (*dst).wrapping_add(1);
    *src = (*src).wrapping_add(1);
    true
}

unsafe fn unescape_octal(src: &mut *mut u8, dst: &mut *mut u8) -> bool {
    let p = *dst;
    let mut q = *src;

    if !isodigit(*q) {
        return false;
    }

    let mut num: u8 = *q & 7;
    q = q.wrapping_add(1);
    while num < 32 && isodigit(*q) && ((q as isize).wrapping_sub(*src as isize) < 3) {
        num = ((num as u32) << 3) as u8;
        num = num.wrapping_add(*q & 7);
        q = q.wrapping_add(1);
    }
    *p = num;
    *dst = (*dst).wrapping_add(1);
    *src = q;
    true
}

unsafe fn unescape_hex(src: &mut *mut u8, dst: &mut *mut u8) -> bool {
    let p = *dst;
    let mut q = *src;

    let c = *q;
    q = q.wrapping_add(1);
    if c != b'x' {
        return false;
    }

    let mut digit = hex_to_bin(*q);
    q = q.wrapping_add(1);
    let mut num: u8 = digit as u8;
    if digit < 0 {
        return false;
    }

    digit = hex_to_bin(*q);
    if digit >= 0 {
        q = q.wrapping_add(1);
        num = (((num as c_int) << 4) | digit) as u8;
    }
    *p = num;
    *dst = (*dst).wrapping_add(1);
    *src = q;
    true
}

unsafe fn unescape_special(src: &mut *mut u8, dst: &mut *mut u8) -> bool {
    let p = *dst;
    let q = *src;
    *p = match *q {
        b'"' => b'"',
        b'\\' => b'\\',
        b'a' => 0x07,
        b'e' => 0x1b,
        _ => return false,
    };
    *dst = (*dst).wrapping_add(1);
    *src = (*src).wrapping_add(1);
    true
}

#[no_mangle]
pub extern "C" fn string_unescape(src: *mut u8, dst: *mut u8, size: usize, flags: c_uint) -> c_int {
    let mut src = src;
    let mut out = dst;
    let mut size = if size == 0 { usize::MAX } else { size };

    unsafe {
        loop {
            if *src == 0 {
                break;
            }
            size = size.wrapping_sub(1);
            if size == 0 {
                break;
            }
            if *src == b'\\' && *src.wrapping_add(1) != 0 && size > 1 {
                src = src.wrapping_add(1);
                size = size.wrapping_sub(1);

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
                out = out.wrapping_add(1);
            }
            *out = *src;
            out = out.wrapping_add(1);
            src = src.wrapping_add(1);
        }
        *out = 0;
    }

    (out as isize).wrapping_sub(dst as isize) as c_int
}

unsafe fn escape_passthrough(c: u8, dst: &mut *mut u8, end: *mut u8) -> bool {
    let out = *dst;
    if out < end {
        *out = c;
    }
    *dst = out.wrapping_add(1);
    true
}

#[inline]
unsafe fn put(out: &mut *mut u8, end: *mut u8, v: u8) {
    if *out < end {
        **out = v;
    }
    *out = (*out).wrapping_add(1);
}

unsafe fn escape_space(c: u8, dst: &mut *mut u8, end: *mut u8) -> bool {
    let mut out = *dst;
    let to = match c {
        b'\n' => b'n',
        b'\r' => b'r',
        b'\t' => b't',
        0x0b => b'v',
        0x0c => b'f',
        _ => return false,
    };
    put(&mut out, end, b'\\');
    put(&mut out, end, to);
    *dst = out;
    true
}

unsafe fn escape_special(c: u8, dst: &mut *mut u8, end: *mut u8) -> bool {
    let mut out = *dst;
    let to = match c {
        b'\\' => b'\\',
        0x07 => b'a',
        0x1b => b'e',
        b'"' => b'"',
        _ => return false,
    };
    put(&mut out, end, b'\\');
    put(&mut out, end, to);
    *dst = out;
    true
}

unsafe fn escape_null(c: u8, dst: &mut *mut u8, end: *mut u8) -> bool {
    let mut out = *dst;
    if c != 0 {
        return false;
    }
    put(&mut out, end, b'\\');
    put(&mut out, end, b'0');
    *dst = out;
    true
}

unsafe fn escape_octal(c: u8, dst: &mut *mut u8, end: *mut u8) -> bool {
    let mut out = *dst;
    put(&mut out, end, b'\\');
    put(&mut out, end, ((c >> 6) & 0x07) + b'0');
    put(&mut out, end, ((c >> 3) & 0x07) + b'0');
    put(&mut out, end, (c & 0x07) + b'0');
    *dst = out;
    true
}

unsafe fn escape_hex(c: u8, dst: &mut *mut u8, end: *mut u8) -> bool {
    let mut out = *dst;
    put(&mut out, end, b'\\');
    put(&mut out, end, b'x');
    put(&mut out, end, HEX_ASC[(c >> 4) as usize]);
    put(&mut out, end, HEX_ASC[(c & 0x0f) as usize]);
    *dst = out;
    true
}

/// Kernel strchr() semantics: the terminating NUL counts as part of the
/// string, so searching for 0 always succeeds.
unsafe fn strchr_found(mut s: *const u8, c: u8) -> bool {
    while *s != c {
        if *s == 0 {
            return false;
        }
        s = s.wrapping_add(1);
    }
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
    let mut src = src;
    let mut isz = isz;
    let mut p = dst;
    let end = p.wrapping_add(osz);

    unsafe {
        let is_dict = !only.is_null() && *only != 0;
        let is_append = flags & ESCAPE_APPEND != 0;

        while isz != 0 {
            isz -= 1;
            let c: u8 = *src;
            src = src.wrapping_add(1);
            let in_dict = is_dict && strchr_found(only, c);

            if !(is_append || in_dict) && is_dict && escape_passthrough(c, &mut p, end) {
                continue;
            }

            if !(is_append && in_dict)
                && isascii(c)
                && isprint(c)
                && flags & ESCAPE_NAP != 0
                && escape_passthrough(c, &mut p, end)
            {
                continue;
            }

            if !(is_append && in_dict)
                && isprint(c)
                && flags & ESCAPE_NP != 0
                && escape_passthrough(c, &mut p, end)
            {
                continue;
            }

            if !(is_append && in_dict)
                && isascii(c)
                && flags & ESCAPE_NA != 0
                && escape_passthrough(c, &mut p, end)
            {
                continue;
            }

            if flags & ESCAPE_SPACE != 0 && escape_space(c, &mut p, end) {
                continue;
            }

            if flags & ESCAPE_SPECIAL != 0 && escape_special(c, &mut p, end) {
                continue;
            }

            if flags & ESCAPE_NULL != 0 && escape_null(c, &mut p, end) {
                continue;
            }

            if flags & ESCAPE_OCTAL != 0 && escape_octal(c, &mut p, end) {
                continue;
            }

            if flags & ESCAPE_HEX != 0 && escape_hex(c, &mut p, end) {
                continue;
            }

            escape_passthrough(c, &mut p, end);
        }
    }

    (p as isize).wrapping_sub(dst as isize) as c_int
}

#[no_mangle]
pub extern "C" fn kstrdup_quotable(src: *const u8, gfp: gfp_t) -> *mut u8 {
    let flags: c_int = ESCAPE_HEX as c_int;
    let esc: [u8; 10] = *b"\x0c\n\r\t\x0b\x07\x1b\\\"\0";

    if src.is_null() {
        return core::ptr::null_mut();
    }
    unsafe {
        let slen = strlen(src);

        let dlen = string_escape_mem(
            src,
            slen,
            core::ptr::null_mut(),
            0,
            flags as c_uint,
            esc.as_ptr(),
        ) as isize as usize;
        let dst = kmalloc(dlen.wrapping_add(1), gfp) as *mut u8;
        if dst.is_null() {
            return core::ptr::null_mut();
        }

        // WARN_ON(): only the condition is evaluated; no other effect.
        let _warn = string_escape_mem(src, slen, dst, dlen, flags as c_uint, esc.as_ptr())
            as isize as usize
            != dlen;
        *dst.wrapping_add(dlen) = 0;

        dst
    }
}

#[no_mangle]
pub extern "C" fn kstrdup_quotable_cmdline(task: *mut task_struct, gfp: gfp_t) -> *mut u8 {
    unsafe {
        let buffer = kmalloc(PAGE_SIZE, GFP_KERNEL) as *mut u8;
        if buffer.is_null() {
            return core::ptr::null_mut();
        }

        let mut res = get_cmdline(task, buffer, (PAGE_SIZE - 1) as c_int);
        *buffer.wrapping_offset(res as isize) = 0;

        loop {
            res = res.wrapping_sub(1);
            if !(res >= 0 && *buffer.wrapping_offset(res as isize) == 0) {
                break;
            }
        }

        let mut i: c_int = 0;
        while i <= res {
            let b = buffer.wrapping_offset(i as isize);
            if *b == 0 {
                *b = b' ';
            }
            i = i.wrapping_add(1);
        }

        let quoted = kstrdup_quotable(buffer, gfp);
        kfree(buffer as *const c_void);
        quoted
    }
}

#[no_mangle]
pub extern "C" fn kstrdup_quotable_file(file: *mut file, gfp: gfp_t) -> *mut u8 {
    unsafe {
        if file.is_null() {
            return kstrdup(b"<unknown>\0".as_ptr(), gfp);
        }

        let temp = kmalloc(PATH_MAX + 11, GFP_KERNEL) as *mut u8;
        if temp.is_null() {
            return kstrdup(b"<no_memory>\0".as_ptr(), gfp);
        }

        let mut pathname = file_path(file, temp, (PATH_MAX + 11) as c_int);
        if is_err(pathname) {
            pathname = kstrdup(b"<too_long>\0".as_ptr(), gfp);
        } else {
            pathname = kstrdup_quotable(pathname, gfp);
        }

        kfree(temp as *const c_void);
        pathname
    }
}

#[no_mangle]
pub extern "C" fn kstrdup_and_replace(src: *const u8, old: u8, new: u8, gfp: gfp_t) -> *mut u8 {
    let dst = unsafe { kstrdup(src, gfp) };
    if dst.is_null() {
        return core::ptr::null_mut();
    }
    strreplace(dst, old, new)
}

#[no_mangle]
pub extern "C" fn kasprintf_strarray(gfp: gfp_t, prefix: *const u8, n: usize) -> *mut *mut u8 {
    unsafe {
        let names = kcalloc(n, core::mem::size_of::<*mut u8>(), gfp) as *mut *mut u8;
        if names.is_null() {
            return core::ptr::null_mut();
        }

        let mut i: usize = 0;
        while i < n {
            let s = kasprintf(gfp, b"%s-%zu\0".as_ptr(), prefix, i);
            *names.wrapping_add(i) = s;
            if (*names.wrapping_add(i)).is_null() {
                kfree_strarray(names, i);
                return core::ptr::null_mut();
            }
            i += 1;
        }

        names
    }
}

#[no_mangle]
pub extern "C" fn kfree_strarray(array: *mut *mut u8, n: usize) {
    if array.is_null() {
        return;
    }
    unsafe {
        let mut i: c_uint = 0;
        while (i as usize) < n {
            kfree(*array.wrapping_add(i as usize) as *const c_void);
            i = i.wrapping_add(1);
        }
        kfree(array as *const c_void);
    }
}

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
        let ptr = __devres_alloc_node(
            Some(devm_kfree_strarray as DrRelease),
            core::mem::size_of::<strarray>(),
            GFP_KERNEL,
            -1,
            b"devm_kfree_strarray\0".as_ptr(),
        ) as *mut strarray;
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

#[no_mangle]
pub extern "C" fn skip_spaces(str: *const u8) -> *mut u8 {
    let mut s = str;
    unsafe {
        while isspace(*s) {
            s = s.wrapping_add(1);
        }
    }
    s as *mut u8
}

#[no_mangle]
pub extern "C" fn strim(s: *mut u8) -> *mut u8 {
    unsafe {
        let size = strlen(s);
        if size == 0 {
            return s;
        }

        let mut end = s.wrapping_add(size).wrapping_sub(1);
        while end >= s && isspace(*end) {
            end = end.wrapping_sub(1);
        }
        *end.wrapping_add(1) = 0;
    }
    skip_spaces(s)
}

#[no_mangle]
pub extern "C" fn sysfs_streq(s1: *const u8, s2: *const u8) -> bool {
    let mut s1 = s1;
    let mut s2 = s2;
    unsafe {
        while *s1 != 0 && *s1 == *s2 {
            s1 = s1.wrapping_add(1);
            s2 = s2.wrapping_add(1);
        }

        if *s1 == *s2 {
            return true;
        }
        if *s1 == 0 && *s2 == b'\n' && *s2.wrapping_add(1) == 0 {
            return true;
        }
        if *s1 == b'\n' && *s1.wrapping_add(1) == 0 && *s2 == 0 {
            return true;
        }
    }
    false
}

#[no_mangle]
pub extern "C" fn match_string(array: *const *const u8, n: usize, string: *const u8) -> c_int {
    let mut index: c_int = 0;
    unsafe {
        while (index as usize) < n {
            let item = *array.wrapping_offset(index as isize);
            if item.is_null() {
                break;
            }
            if strcmp(item, string) == 0 {
                return index;
            }
            index = index.wrapping_add(1);
        }
    }
    -EINVAL
}

#[no_mangle]
pub extern "C" fn __sysfs_match_string(array: *const *const u8, n: usize, str: *const u8) -> c_int {
    let mut index: c_int = 0;
    unsafe {
        while (index as usize) < n {
            let item = *array.wrapping_offset(index as isize);
            if item.is_null() {
                break;
            }
            if sysfs_streq(item, str) {
                return index;
            }
            index = index.wrapping_add(1);
        }
    }
    -EINVAL
}

#[no_mangle]
pub extern "C" fn strreplace(str: *mut u8, old: u8, new: u8) -> *mut u8 {
    let mut s = str;
    unsafe {
        while *s != 0 {
            if *s == old {
                *s = new;
            }
            s = s.wrapping_add(1);
        }
    }
    str
}

#[no_mangle]
pub extern "C" fn memcpy_and_pad(
    dest: *mut c_void,
    dest_len: usize,
    src: *const c_void,
    count: usize,
    pad: c_int,
) {
    let d = dest as *mut u8;
    let s = src as *const u8;
    unsafe {
        if dest_len > count {
            if count != 0 {
                core::ptr::copy(s, d, count);
            }
            core::ptr::write_bytes(d.wrapping_add(count), pad as u8, dest_len - count);
        } else if dest_len != 0 {
            core::ptr::copy(s, d, dest_len);
        }
    }
}

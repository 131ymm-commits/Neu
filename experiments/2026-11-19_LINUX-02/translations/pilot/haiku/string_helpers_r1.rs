use core::ffi::{c_char, c_int, c_long, c_uint, c_void};
use core::mem::size_of;
use core::ptr::{copy_nonoverlapping, null_mut, write_bytes};

// ---------------------------------------------------------------------------
// Opaque kernel types (only ever used through pointers)
// ---------------------------------------------------------------------------

#[repr(C)]
pub struct Device {
    _private: [u8; 0],
}

#[repr(C)]
pub struct File {
    _private: [u8; 0],
}

#[repr(C)]
pub struct TaskStruct {
    _private: [u8; 0],
}

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const GFP_KERNEL: c_uint = 0xcc0;
const EINVAL: c_int = 22;
const ENOMEM: c_int = 12;
const ENOENT: c_int = 2;
const PAGE_SIZE: usize = 4096;
const PATH_MAX: usize = 4096;
const SIZE_MAX: usize = usize::MAX;
const NUMA_NO_NODE: c_int = -1;

const STRING_UNITS_10: c_uint = 0;
const STRING_UNITS_2: c_uint = 1;
const STRING_UNITS_MASK: c_uint = 1 << 0;
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

const DIVISOR: [u32; 2] = [1000, 1024];
const ROUNDING: [u32; 3] = [500, 50, 5];
const HEX_ASC: &[u8; 16] = b"0123456789abcdef";

static UNITS_10: [&[u8]; 9] = [
    b"\0", b"k\0", b"M\0", b"G\0", b"T\0", b"P\0", b"E\0", b"Z\0", b"Y\0",
];
static UNITS_2: [&[u8]; 9] = [
    b"\0", b"Ki\0", b"Mi\0", b"Gi\0", b"Ti\0", b"Pi\0", b"Ei\0", b"Zi\0", b"Yi\0",
];

const FMT_TMP: &[u8] = b".%03u\0";
const FMT_MAIN: &[u8] = b"%u%s%s%s%s\0";
const FMT_NUM_NAME: &[u8] = b"%s-%zu\0";
const DEVM_RELEASE_NAME: &[u8] = b"devm_kfree_strarray\0";

// ---------------------------------------------------------------------------
// External kernel functions
// ---------------------------------------------------------------------------

extern "C" {
    fn kmalloc(size: usize, flags: c_uint) -> *mut c_void;
    fn kcalloc(n: usize, size: usize, flags: c_uint) -> *mut c_void;
    fn kfree(p: *const c_void);
    fn kstrdup(s: *const c_char, gfp: c_uint) -> *mut c_char;
    fn kasprintf(gfp: c_uint, fmt: *const c_char, ...) -> *mut c_char;
    fn snprintf(buf: *mut c_char, size: usize, fmt: *const c_char, ...) -> c_int;
    fn get_options(s: *const c_char, nints: c_int, ints: *mut c_int) -> *mut c_char;
    fn hex_to_bin(ch: u8) -> c_int;
    fn memdup_user_nul(src: *const c_void, len: usize) -> *mut c_void;
    fn file_path(file: *mut File, buf: *mut c_char, buflen: c_int) -> *mut c_char;
    fn get_cmdline(task: *mut TaskStruct, buffer: *mut c_char, buflen: c_int) -> c_int;
    fn __devres_alloc_node(
        release: Option<unsafe extern "C" fn(*mut Device, *mut c_void)>,
        size: usize,
        gfp: c_uint,
        nid: c_int,
        name: *const c_char,
    ) -> *mut c_void;
    fn devres_add(dev: *mut Device, res: *mut c_void);
    fn devres_free(res: *mut c_void);
    fn strlen(s: *const c_char) -> usize;
    fn strcmp(a: *const c_char, b: *const c_char) -> c_int;
}

// ---------------------------------------------------------------------------
// Kernel macros / inline helpers reimplemented
// ---------------------------------------------------------------------------

#[inline]
fn isprint(c: u8) -> bool {
    (32..=126).contains(&c) || (160..=255).contains(&c)
}

#[inline]
fn isspace(c: u8) -> bool {
    matches!(c, 9..=13 | 32 | 160)
}

#[inline]
fn isascii(c: u8) -> bool {
    c <= 127
}

#[inline]
fn isodigit(c: u8) -> bool {
    (b'0'..=b'7').contains(&c)
}

/// do_div(n, base): divides *n in place, returns the remainder.
#[inline]
fn do_div(n: &mut u64, base: u32) -> u32 {
    let base = base as u64;
    let rem = *n % base;
    *n /= base;
    rem as u32
}

/// IS_ERR on an address given as an integer.
#[inline]
fn is_err(p: usize) -> bool {
    p >= (-4095isize) as usize
}

/// PTR_ERR on an address given as an integer.
#[inline]
fn ptr_err(p: usize) -> c_long {
    p as c_long
}

/// ERR_PTR.
#[inline]
fn err_ptr<T>(e: c_long) -> *mut T {
    e as usize as *mut T
}

/// WARN_ON: evaluates to its condition. Printing is not available without I/O.
#[inline]
fn warn_on(cond: bool) -> bool {
    cond
}

/// Equivalent of strchr(s, c) != NULL for a NUL-terminated string.
/// For c == 0 this is true, since strchr returns the terminator.
#[inline]
unsafe fn strchr_found(s: *const c_char, c: u8) -> bool {
    let mut p = s;
    loop {
        let b = *p as u8;
        if b == c {
            return true;
        }
        if b == 0 {
            return false;
        }
        p = p.add(1);
    }
}

#[repr(C)]
struct StrArray {
    array: *mut *mut c_char,
    n: usize,
}

// ---------------------------------------------------------------------------
// string_get_size
// ---------------------------------------------------------------------------

#[no_mangle]
pub extern "C" fn string_get_size(
    size: u64,
    blk_size: u64,
    units: c_uint,
    buf: *mut c_char,
    len: c_int,
) -> c_int {
    let units_base = units & STRING_UNITS_MASK;
    let table: &[&[u8]] = if units_base == STRING_UNITS_2 {
        &UNITS_2
    } else {
        &UNITS_10
    };
    let div = DIVISOR[units_base as usize];

    let mut size = size;
    let mut blk_size = blk_size;
    let mut i: c_int = 0;
    let mut j: usize = 0;
    let mut remainder: u32 = 0;
    let mut tmp = [0 as c_char; 12];

    if blk_size == 0 {
        size = 0;
    }

    if size != 0 {
        while (blk_size >> 32) != 0 {
            do_div(&mut blk_size, div);
            i += 1;
        }

        while (size >> 32) != 0 {
            do_div(&mut size, div);
            i += 1;
        }

        size = size.wrapping_mul(blk_size);

        while size >= div as u64 {
            remainder = do_div(&mut size, div);
            i += 1;
        }

        let mut sf_cap = size as u32;
        while sf_cap.wrapping_mul(10) < 1000 {
            sf_cap = sf_cap.wrapping_mul(10);
            j += 1;
        }

        if units_base == STRING_UNITS_2 {
            remainder = remainder.wrapping_mul(1000) >> 10;
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
                    FMT_TMP.as_ptr() as *const c_char,
                    remainder as c_uint,
                );
            }
            tmp[j + 1] = 0;
        }
    }

    let unit: &[u8] = if (i as usize) >= UNITS_2.len() {
        b"UNK\0"
    } else {
        table[i as usize]
    };
    let sp: &[u8] = if (units & STRING_UNITS_NO_SPACE) != 0 {
        b"\0"
    } else {
        b" \0"
    };
    let by: &[u8] = if (units & STRING_UNITS_NO_BYTES) != 0 {
        b"\0"
    } else {
        b"B\0"
    };

    unsafe {
        snprintf(
            buf,
            len as usize,
            FMT_MAIN.as_ptr() as *const c_char,
            size as c_uint,
            tmp.as_ptr(),
            sp.as_ptr() as *const c_char,
            unit.as_ptr() as *const c_char,
            by.as_ptr() as *const c_char,
        )
    }
}

// ---------------------------------------------------------------------------
// parse_int_array / parse_int_array_user
// ---------------------------------------------------------------------------

#[no_mangle]
pub extern "C" fn parse_int_array(
    buf: *const c_char,
    _count: usize,
    array: *mut *mut c_int,
) -> c_int {
    unsafe {
        let mut nints: c_int = 0;
        get_options(buf, 0, &mut nints);
        if nints == 0 {
            return -ENOENT;
        }

        let ints = kcalloc((nints + 1) as usize, size_of::<c_int>(), GFP_KERNEL) as *mut c_int;
        if ints.is_null() {
            return -ENOMEM;
        }

        get_options(buf, nints + 1, ints);
        *array = ints;

        0
    }
}

#[no_mangle]
pub extern "C" fn parse_int_array_user(
    from: *const c_char,
    count: usize,
    array: *mut *mut c_int,
) -> c_int {
    unsafe {
        let buf = memdup_user_nul(from as *const c_void, count) as *mut c_char;
        if is_err(buf as usize) {
            return ptr_err(buf as usize) as c_int;
        }

        let ret = parse_int_array(buf, count, array);
        kfree(buf as *const c_void);
        ret
    }
}

// ---------------------------------------------------------------------------
// string_unescape
// ---------------------------------------------------------------------------

unsafe fn unescape_space(src: &mut *mut c_char, dst: &mut *mut c_char) -> bool {
    let p = *dst;
    let q = *src;

    let v = match *q as u8 {
        b'n' => b'\n',
        b'r' => b'\r',
        b't' => b'\t',
        b'v' => 0x0b,
        b'f' => 0x0c,
        _ => return false,
    };

    *p = v as c_char;
    *dst = p.add(1);
    *src = q.add(1);
    true
}

unsafe fn unescape_octal(src: &mut *mut c_char, dst: &mut *mut c_char) -> bool {
    let p = *dst;
    let start = *src;
    let mut q = start;

    if !isodigit(*q as u8) {
        return false;
    }

    let mut num: u8 = (*q as u8) & 7;
    q = q.add(1);
    while num < 32 && isodigit(*q as u8) && (q as usize).wrapping_sub(start as usize) < 3 {
        num = (num << 3).wrapping_add((*q as u8) & 7);
        q = q.add(1);
    }

    *p = num as c_char;
    *dst = p.add(1);
    *src = q;
    true
}

unsafe fn unescape_hex(src: &mut *mut c_char, dst: &mut *mut c_char) -> bool {
    let p = *dst;
    let mut q = *src;

    if *q as u8 != b'x' {
        return false;
    }
    q = q.add(1);

    let mut digit = hex_to_bin(*q as u8);
    let mut num = digit as u8;
    q = q.add(1);
    if digit < 0 {
        return false;
    }

    digit = hex_to_bin(*q as u8);
    if digit >= 0 {
        q = q.add(1);
        num = (num << 4) | (digit as u8);
    }

    *p = num as c_char;
    *dst = p.add(1);
    *src = q;
    true
}

unsafe fn unescape_special(src: &mut *mut c_char, dst: &mut *mut c_char) -> bool {
    let p = *dst;
    let q = *src;

    let v = match *q as u8 {
        b'"' => b'"',
        b'\\' => b'\\',
        b'a' => 0x07,
        b'e' => 0x1b,
        _ => return false,
    };

    *p = v as c_char;
    *dst = p.add(1);
    *src = q.add(1);
    true
}

#[no_mangle]
pub extern "C" fn string_unescape(
    src: *mut c_char,
    dst: *mut c_char,
    size: usize,
    flags: c_uint,
) -> c_int {
    unsafe {
        let mut src = src;
        let mut out = dst;
        let mut size = if size == 0 { SIZE_MAX } else { size };

        while *src != 0 {
            size -= 1;
            if size == 0 {
                break;
            }

            if *src == b'\\' as c_char && *src.add(1) != 0 && size > 1 {
                src = src.add(1);
                size -= 1;

                if (flags & UNESCAPE_SPACE) != 0 && unescape_space(&mut src, &mut out) {
                    continue;
                }
                if (flags & UNESCAPE_OCTAL) != 0 && unescape_octal(&mut src, &mut out) {
                    continue;
                }
                if (flags & UNESCAPE_HEX) != 0 && unescape_hex(&mut src, &mut out) {
                    continue;
                }
                if (flags & UNESCAPE_SPECIAL) != 0 && unescape_special(&mut src, &mut out) {
                    continue;
                }

                *out = b'\\' as c_char;
                out = out.add(1);
            }

            *out = *src;
            out = out.add(1);
            src = src.add(1);
        }

        *out = 0;
        (out as usize).wrapping_sub(dst as usize) as c_int
    }
}

// ---------------------------------------------------------------------------
// string_escape_mem
// ---------------------------------------------------------------------------

/// Writes one byte if there is room; always advances the output cursor.
#[inline]
unsafe fn emit(out: &mut *mut c_char, end: *mut c_char, v: u8) {
    if *out < end {
        **out = v as c_char;
    }
    *out = (*out).wrapping_add(1);
}

unsafe fn escape_passthrough(c: u8, dst: &mut *mut c_char, end: *mut c_char) -> bool {
    emit(dst, end, c);
    true
}

unsafe fn escape_space(c: u8, dst: &mut *mut c_char, end: *mut c_char) -> bool {
    let to = match c {
        b'\n' => b'n',
        b'\r' => b'r',
        b'\t' => b't',
        0x0b => b'v',
        0x0c => b'f',
        _ => return false,
    };
    emit(dst, end, b'\\');
    emit(dst, end, to);
    true
}

unsafe fn escape_special(c: u8, dst: &mut *mut c_char, end: *mut c_char) -> bool {
    let to = match c {
        b'\\' => b'\\',
        0x07 => b'a',
        0x1b => b'e',
        b'"' => b'"',
        _ => return false,
    };
    emit(dst, end, b'\\');
    emit(dst, end, to);
    true
}

unsafe fn escape_null(c: u8, dst: &mut *mut c_char, end: *mut c_char) -> bool {
    if c != 0 {
        return false;
    }
    emit(dst, end, b'\\');
    emit(dst, end, b'0');
    true
}

unsafe fn escape_octal(c: u8, dst: &mut *mut c_char, end: *mut c_char) -> bool {
    emit(dst, end, b'\\');
    emit(dst, end, ((c >> 6) & 0x07) + b'0');
    emit(dst, end, ((c >> 3) & 0x07) + b'0');
    emit(dst, end, (c & 0x07) + b'0');
    true
}

unsafe fn escape_hex(c: u8, dst: &mut *mut c_char, end: *mut c_char) -> bool {
    emit(dst, end, b'\\');
    emit(dst, end, b'x');
    emit(dst, end, HEX_ASC[((c & 0xf0) >> 4) as usize]);
    emit(dst, end, HEX_ASC[(c & 0x0f) as usize]);
    true
}

#[no_mangle]
pub extern "C" fn string_escape_mem(
    src: *const c_char,
    isz: usize,
    dst: *mut c_char,
    osz: usize,
    flags: c_uint,
    only: *const c_char,
) -> c_int {
    unsafe {
        let mut src = src;
        let mut isz = isz;
        let mut p = dst;
        let end = dst.wrapping_add(osz);
        let is_dict = !only.is_null() && *only != 0;
        let is_append = (flags & ESCAPE_APPEND) != 0;

        while isz != 0 {
            isz -= 1;
            let c = *src as u8;
            src = src.add(1);

            let in_dict = is_dict && strchr_found(only, c);

            if !(is_append || in_dict) && is_dict && escape_passthrough(c, &mut p, end) {
                continue;
            }

            if !(is_append && in_dict)
                && isascii(c)
                && isprint(c)
                && (flags & ESCAPE_NAP) != 0
                && escape_passthrough(c, &mut p, end)
            {
                continue;
            }

            if !(is_append && in_dict)
                && isprint(c)
                && (flags & ESCAPE_NP) != 0
                && escape_passthrough(c, &mut p, end)
            {
                continue;
            }

            if !(is_append && in_dict)
                && isascii(c)
                && (flags & ESCAPE_NA) != 0
                && escape_passthrough(c, &mut p, end)
            {
                continue;
            }

            if (flags & ESCAPE_SPACE) != 0 && escape_space(c, &mut p, end) {
                continue;
            }

            if (flags & ESCAPE_SPECIAL) != 0 && escape_special(c, &mut p, end) {
                continue;
            }

            if (flags & ESCAPE_NULL) != 0 && escape_null(c, &mut p, end) {
                continue;
            }

            if (flags & ESCAPE_OCTAL) != 0 && escape_octal(c, &mut p, end) {
                continue;
            }

            if (flags & ESCAPE_HEX) != 0 && escape_hex(c, &mut p, end) {
                continue;
            }

            escape_passthrough(c, &mut p, end);
        }

        (p as usize).wrapping_sub(dst as usize) as c_int
    }
}

// ---------------------------------------------------------------------------
// kstrdup_quotable family
// ---------------------------------------------------------------------------

#[no_mangle]
pub extern "C" fn kstrdup_quotable(src: *const c_char, gfp: c_uint) -> *mut c_char {
    unsafe {
        if src.is_null() {
            return null_mut();
        }
        let slen = strlen(src);

        let flags = ESCAPE_HEX;
        // "\f\n\r\t\v\a\e\\\""
        let esc_arr: [u8; 10] = [0x0c, b'\n', b'\r', b'\t', 0x0b, 0x07, 0x1b, b'\\', b'"', 0];
        let esc = esc_arr.as_ptr() as *const c_char;

        let dlen = string_escape_mem(src, slen, null_mut(), 0, flags, esc) as usize;
        let dst = kmalloc(dlen + 1, gfp) as *mut c_char;
        if dst.is_null() {
            return null_mut();
        }

        warn_on(string_escape_mem(src, slen, dst, dlen, flags, esc) as usize != dlen);
        *dst.add(dlen) = 0;

        dst
    }
}

#[no_mangle]
pub extern "C" fn kstrdup_quotable_cmdline(task: *mut TaskStruct, gfp: c_uint) -> *mut c_char {
    unsafe {
        let buffer = kmalloc(PAGE_SIZE, GFP_KERNEL) as *mut c_char;
        if buffer.is_null() {
            return null_mut();
        }

        let mut res = get_cmdline(task, buffer, (PAGE_SIZE - 1) as c_int);
        *buffer.offset(res as isize) = 0;

        // Collapse trailing NULs; res ends up at the last non-NUL index (or -1).
        res -= 1;
        while res >= 0 && *buffer.offset(res as isize) == 0 {
            res -= 1;
        }

        // Replace inter-argument NULs with spaces.
        for i in 0..=res {
            if *buffer.offset(i as isize) == 0 {
                *buffer.offset(i as isize) = b' ' as c_char;
            }
        }

        let quoted = kstrdup_quotable(buffer, gfp);
        kfree(buffer as *const c_void);
        quoted
    }
}

#[no_mangle]
pub extern "C" fn kstrdup_quotable_file(file: *mut File, gfp: c_uint) -> *mut c_char {
    unsafe {
        if file.is_null() {
            return kstrdup(b"<unknown>\0".as_ptr() as *const c_char, gfp);
        }

        // Room for ' (deleted)' suffix.
        let temp = kmalloc(PATH_MAX + 11, GFP_KERNEL) as *mut c_char;
        if temp.is_null() {
            return kstrdup(b"<no_memory>\0".as_ptr() as *const c_char, gfp);
        }

        let mut pathname = file_path(file, temp, (PATH_MAX + 11) as c_int);
        if is_err(pathname as usize) {
            pathname = kstrdup(b"<too_long>\0".as_ptr() as *const c_char, gfp);
        } else {
            pathname = kstrdup_quotable(pathname, gfp);
        }

        kfree(temp as *const c_void);
        pathname
    }
}

#[no_mangle]
pub extern "C" fn kstrdup_and_replace(
    src: *const c_char,
    old: c_char,
    new: c_char,
    gfp: c_uint,
) -> *mut c_char {
    unsafe {
        let dst = kstrdup(src, gfp);
        if dst.is_null() {
            return null_mut();
        }
        strreplace(dst, old, new)
    }
}

// ---------------------------------------------------------------------------
// String arrays
// ---------------------------------------------------------------------------

#[no_mangle]
pub extern "C" fn kasprintf_strarray(gfp: c_uint, prefix: *const c_char, n: usize) -> *mut *mut c_char {
    unsafe {
        let names = kcalloc(n, size_of::<*mut c_char>(), gfp) as *mut *mut c_char;
        if names.is_null() {
            return null_mut();
        }

        for i in 0..n {
            let s = kasprintf(gfp, FMT_NUM_NAME.as_ptr() as *const c_char, prefix, i);
            *names.add(i) = s;
            if s.is_null() {
                kfree_strarray(names, i);
                return null_mut();
            }
        }

        names
    }
}

#[no_mangle]
pub extern "C" fn kfree_strarray(array: *mut *mut c_char, n: usize) {
    unsafe {
        if array.is_null() {
            return;
        }

        // Matches the C loop, which uses an unsigned int index.
        let mut i: c_uint = 0;
        while (i as usize) < n {
            kfree(*array.add(i as usize) as *const c_void);
            i = i.wrapping_add(1);
        }

        kfree(array as *const c_void);
    }
}

unsafe extern "C" fn devm_kfree_strarray(_dev: *mut Device, res: *mut c_void) {
    let array = res as *mut StrArray;
    kfree_strarray((*array).array, (*array).n);
}

#[no_mangle]
pub extern "C" fn devm_kasprintf_strarray(
    dev: *mut Device,
    prefix: *const c_char,
    n: usize,
) -> *mut *mut c_char {
    unsafe {
        let release: unsafe extern "C" fn(*mut Device, *mut c_void) = devm_kfree_strarray;
        let ptr = __devres_alloc_node(
            Some(release),
            size_of::<StrArray>(),
            GFP_KERNEL,
            NUMA_NO_NODE,
            DEVM_RELEASE_NAME.as_ptr() as *const c_char,
        ) as *mut StrArray;
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
// skip_spaces / strim / sysfs_streq / match_string
// ---------------------------------------------------------------------------

#[no_mangle]
pub extern "C" fn skip_spaces(s: *const c_char) -> *mut c_char {
    unsafe {
        let mut p = s;
        while isspace(*p as u8) {
            p = p.add(1);
        }
        p as *mut c_char
    }
}

#[no_mangle]
pub extern "C" fn strim(s: *mut c_char) -> *mut c_char {
    unsafe {
        let size = strlen(s);
        if size == 0 {
            return s;
        }

        let mut len = size;
        while len > 0 && isspace(*s.add(len - 1) as u8) {
            len -= 1;
        }
        *s.add(len) = 0;

        skip_spaces(s)
    }
}

#[no_mangle]
pub extern "C" fn sysfs_streq(s1: *const c_char, s2: *const c_char) -> bool {
    unsafe {
        let mut s1 = s1;
        let mut s2 = s2;

        while *s1 != 0 && *s1 == *s2 {
            s1 = s1.add(1);
            s2 = s2.add(1);
        }

        if *s1 == *s2 {
            return true;
        }
        if *s1 == 0 && *s2 == b'\n' as c_char && *s2.add(1) == 0 {
            return true;
        }
        if *s1 == b'\n' as c_char && *s1.add(1) == 0 && *s2 == 0 {
            return true;
        }
        false
    }
}

#[no_mangle]
pub extern "C" fn match_string(
    array: *const *const c_char,
    n: usize,
    string: *const c_char,
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
    array: *const *const c_char,
    n: usize,
    str_: *const c_char,
) -> c_int {
    unsafe {
        let mut index: usize = 0;
        while index < n {
            let item = *array.add(index);
            if item.is_null() {
                break;
            }
            if sysfs_streq(item, str_) {
                return index as c_int;
            }
            index += 1;
        }
        -EINVAL
    }
}

// ---------------------------------------------------------------------------
// strreplace / memcpy_and_pad
// ---------------------------------------------------------------------------

#[no_mangle]
pub extern "C" fn strreplace(str_: *mut c_char, old: c_char, new: c_char) -> *mut c_char {
    unsafe {
        let mut s = str_;
        while *s != 0 {
            if *s == old {
                *s = new;
            }
            s = s.add(1);
        }
        str_
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
        if dest_len > count {
            copy_nonoverlapping(src as *const u8, dest as *mut u8, count);
            write_bytes((dest as *mut u8).add(count), pad as u8, dest_len - count);
        } else {
            copy_nonoverlapping(src as *const u8, dest as *mut u8, dest_len);
        }
    }
}

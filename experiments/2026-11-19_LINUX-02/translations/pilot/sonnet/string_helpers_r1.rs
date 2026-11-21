use core::ffi::{c_char, c_int, c_long, c_uint, c_ulong, c_void};
use core::ptr;

#[repr(C)]
pub struct Device {
    _p: [u8; 0],
}
#[repr(C)]
pub struct File {
    _p: [u8; 0],
}
#[repr(C)]
pub struct TaskStruct {
    _p: [u8; 0],
}

type GfpT = c_uint;
const GFP_KERNEL: GfpT = 0xcc0;
const EINVAL: c_int = 22;
const ENOMEM: c_long = 12;
const ENOENT: c_int = 2;
const PAGE_SIZE: usize = 4096;
const PATH_MAX: usize = 4096;

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

const STRING_UNITS_MASK: c_uint = 1;
const STRING_UNITS_NO_SPACE: c_uint = 1 << 30;
const STRING_UNITS_NO_BYTES: c_uint = 1 << 31;

extern "C" {
    fn kmalloc(size: usize, flags: GfpT) -> *mut c_void;
    fn kcalloc(n: usize, size: usize, flags: GfpT) -> *mut c_void;
    fn kfree(p: *const c_void);
    fn kstrdup(s: *const c_char, gfp: GfpT) -> *mut c_char;
    fn kasprintf(gfp: GfpT, fmt: *const c_char, ...) -> *mut c_char;
    fn snprintf(buf: *mut c_char, size: usize, fmt: *const c_char, ...) -> c_int;
    fn get_options(str: *const c_char, nints: c_int, ints: *mut c_int) -> *mut c_char;
    fn hex_to_bin(ch: u8) -> c_int;
    fn memdup_user_nul(src: *const c_void, len: usize) -> *mut c_void;
    fn file_path(file: *mut File, buf: *mut c_char, buflen: c_int) -> *mut c_char;
    fn get_cmdline(task: *mut TaskStruct, buffer: *mut c_char, buflen: c_int) -> c_int;
    fn __devres_alloc_node(
        release: Option<unsafe extern "C" fn(*mut Device, *mut c_void)>,
        size: usize,
        gfp: GfpT,
        nid: c_int,
        name: *const c_char,
    ) -> *mut c_void;
    fn devres_add(dev: *mut Device, res: *mut c_void);
    fn devres_free(res: *mut c_void);
    fn strlen(s: *const c_char) -> usize;
    fn strcmp(a: *const c_char, b: *const c_char) -> c_int;
}

#[inline]
fn is_err<T>(p: *const T) -> bool {
    (p as usize) >= (-4095isize) as usize
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
    c < 128
}
#[inline]
fn isodigit(c: u8) -> bool {
    (b'0'..=b'7').contains(&c)
}

static UNITS_10: [&[u8]; 9] = [
    b"\0", b"k\0", b"M\0", b"G\0", b"T\0", b"P\0", b"E\0", b"Z\0", b"Y\0",
];
static UNITS_2: [&[u8]; 9] = [
    b"\0", b"Ki\0", b"Mi\0", b"Gi\0", b"Ti\0", b"Pi\0", b"Ei\0", b"Zi\0", b"Yi\0",
];
static DIVISOR: [u32; 2] = [1000, 1024];
static ROUNDING: [u32; 3] = [500, 50, 5];

#[no_mangle]
pub extern "C" fn string_get_size(
    size: u64,
    blk_size: u64,
    units: c_uint,
    buf: *mut c_char,
    len: c_int,
) -> c_int {
    let units_base = (units & STRING_UNITS_MASK) as usize;
    let mut size = size;
    let mut blk_size = blk_size;
    let mut i: c_int = 0;
    let mut remainder: u32 = 0;
    let mut tmp = [0 as c_char; 12];

    if blk_size == 0 {
        size = 0;
    }
    if size != 0 {
        let div = DIVISOR[units_base];
        while (blk_size >> 32) != 0 {
            blk_size /= div as u64;
            i += 1;
        }
        while (size >> 32) != 0 {
            size /= div as u64;
            i += 1;
        }
        size = size.wrapping_mul(blk_size);
        while size >= div as u64 {
            remainder = (size % div as u64) as u32;
            size /= div as u64;
            i += 1;
        }
        let mut sf_cap = size as u32;
        let mut j: usize = 0;
        while sf_cap.wrapping_mul(10) < 1000 {
            sf_cap *= 10;
            j += 1;
        }
        if units_base == 1 {
            remainder *= 1000;
            remainder >>= 10;
        }
        remainder += ROUNDING[j];
        if remainder >= 1000 {
            remainder -= 1000;
            size += 1;
        }
        if j != 0 {
            unsafe {
                snprintf(
                    tmp.as_mut_ptr(),
                    12,
                    b".%03u\0".as_ptr() as *const c_char,
                    remainder as c_uint,
                );
            }
            tmp[j + 1] = 0;
        }
    }

    let unit: *const c_char = if i >= 9 {
        b"UNK\0".as_ptr() as *const c_char
    } else if units_base == 0 {
        UNITS_10[i as usize].as_ptr() as *const c_char
    } else {
        UNITS_2[i as usize].as_ptr() as *const c_char
    };
    let space: *const c_char = if units & STRING_UNITS_NO_SPACE != 0 {
        b"\0".as_ptr() as *const c_char
    } else {
        b" \0".as_ptr() as *const c_char
    };
    let bytes: *const c_char = if units & STRING_UNITS_NO_BYTES != 0 {
        b"\0".as_ptr() as *const c_char
    } else {
        b"B\0".as_ptr() as *const c_char
    };
    unsafe {
        snprintf(
            buf,
            len as usize,
            b"%u%s%s%s%s\0".as_ptr() as *const c_char,
            size as u32 as c_uint,
            tmp.as_ptr(),
            space,
            unit,
            bytes,
        )
    }
}

#[no_mangle]
pub extern "C" fn parse_int_array(buf: *const c_char, _count: usize, array: *mut *mut c_int) -> c_int {
    unsafe {
        let mut nints: c_int = 0;
        get_options(buf, 0, &mut nints);
        if nints == 0 {
            return -ENOENT;
        }
        let n1 = nints.wrapping_add(1);
        let ints = kcalloc(n1 as usize, 4, GFP_KERNEL) as *mut c_int;
        if ints.is_null() {
            return -(ENOMEM as c_int);
        }
        get_options(buf, n1, ints);
        *array = ints;
        0
    }
}

#[no_mangle]
pub extern "C" fn parse_int_array_user(from: *const c_char, count: usize, array: *mut *mut c_int) -> c_int {
    unsafe {
        let buf = memdup_user_nul(from as *const c_void, count) as *mut c_char;
        if is_err(buf) {
            return (buf as usize as c_long) as c_int;
        }
        let ret = parse_int_array(buf, count, array);
        kfree(buf as *const c_void);
        ret
    }
}

unsafe fn unescape_space(src: &mut *mut c_char, dst: &mut *mut c_char) -> bool {
    let p = *dst;
    let q = *src;
    let to = match *q as u8 {
        b'n' => b'\n',
        b'r' => b'\r',
        b't' => b'\t',
        0x0b if false => 0,
        b'v' => 0x0b,
        b'f' => 0x0c,
        _ => return false,
    };
    *p = to as c_char;
    *dst = (*dst).add(1);
    *src = (*src).add(1);
    true
}

unsafe fn unescape_octal(src: &mut *mut c_char, dst: &mut *mut c_char) -> bool {
    let p = *dst;
    let mut q = *src;
    if !isodigit(*q as u8) {
        return false;
    }
    let mut num: u8 = (*q as u8) & 7;
    q = q.add(1);
    while num < 32 && isodigit(*q as u8) && q.offset_from(*src) < 3 {
        num <<= 3;
        num += (*q as u8) & 7;
        q = q.add(1);
    }
    *p = num as c_char;
    *dst = (*dst).add(1);
    *src = q;
    true
}

unsafe fn unescape_hex(src: &mut *mut c_char, dst: &mut *mut c_char) -> bool {
    let p = *dst;
    let mut q = *src;
    let c = *q as u8;
    q = q.add(1);
    if c != b'x' {
        return false;
    }
    let mut digit = hex_to_bin(*q as u8);
    q = q.add(1);
    let mut num = digit as u8;
    if digit < 0 {
        return false;
    }
    digit = hex_to_bin(*q as u8);
    if digit >= 0 {
        q = q.add(1);
        num = (num << 4) | (digit as u8);
    }
    *p = num as c_char;
    *dst = (*dst).add(1);
    *src = q;
    true
}

unsafe fn unescape_special(src: &mut *mut c_char, dst: &mut *mut c_char) -> bool {
    let p = *dst;
    let q = *src;
    let to = match *q as u8 {
        b'"' => b'"',
        b'\\' => b'\\',
        b'a' => 0x07,
        b'e' => 0x1b,
        _ => return false,
    };
    *p = to as c_char;
    *dst = (*dst).add(1);
    *src = (*src).add(1);
    true
}

#[no_mangle]
pub extern "C" fn string_unescape(src: *mut c_char, dst: *mut c_char, size: usize, flags: c_uint) -> c_int {
    unsafe {
        let mut src = src;
        let mut out = dst;
        let mut size = if size == 0 { usize::MAX } else { size };

        while *src != 0 {
            size -= 1;
            if size == 0 {
                break;
            }
            if *src as u8 == b'\\' && *src.add(1) != 0 && size > 1 {
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
                *out = b'\\' as c_char;
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

#[inline]
unsafe fn put(out: &mut *mut c_char, end: *mut c_char, ch: u8) {
    if *out < end {
        **out = ch as c_char;
    }
    *out = (*out).wrapping_add(1);
}

unsafe fn escape_passthrough(c: u8, dst: &mut *mut c_char, end: *mut c_char) -> bool {
    put(dst, end, c);
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
    let mut out = *dst;
    put(&mut out, end, b'\\');
    put(&mut out, end, to);
    *dst = out;
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
    let mut out = *dst;
    put(&mut out, end, b'\\');
    put(&mut out, end, to);
    *dst = out;
    true
}

unsafe fn escape_null(c: u8, dst: &mut *mut c_char, end: *mut c_char) -> bool {
    if c != 0 {
        return false;
    }
    let mut out = *dst;
    put(&mut out, end, b'\\');
    put(&mut out, end, b'0');
    *dst = out;
    true
}

unsafe fn escape_octal(c: u8, dst: &mut *mut c_char, end: *mut c_char) -> bool {
    let mut out = *dst;
    put(&mut out, end, b'\\');
    put(&mut out, end, ((c >> 6) & 7) + b'0');
    put(&mut out, end, ((c >> 3) & 7) + b'0');
    put(&mut out, end, (c & 7) + b'0');
    *dst = out;
    true
}

const HEX_ASC: &[u8; 16] = b"0123456789abcdef";

unsafe fn escape_hex(c: u8, dst: &mut *mut c_char, end: *mut c_char) -> bool {
    let mut out = *dst;
    put(&mut out, end, b'\\');
    put(&mut out, end, b'x');
    put(&mut out, end, HEX_ASC[((c & 0xf0) >> 4) as usize]);
    put(&mut out, end, HEX_ASC[(c & 0x0f) as usize]);
    *dst = out;
    true
}

unsafe fn str_has_char(s: *const c_char, c: u8) -> bool {
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
        let mut p = dst;
        let end = p.wrapping_add(osz);
        let is_dict = !only.is_null() && *only != 0;
        let is_append = flags & ESCAPE_APPEND != 0;
        let mut src = src;
        let mut isz = isz;

        while isz != 0 {
            isz -= 1;
            let c = *src as u8;
            src = src.add(1);
            let in_dict = is_dict && str_has_char(only, c);

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
            if !(is_append && in_dict) && isprint(c) && flags & ESCAPE_NP != 0 && escape_passthrough(c, &mut p, end) {
                continue;
            }
            if !(is_append && in_dict) && isascii(c) && flags & ESCAPE_NA != 0 && escape_passthrough(c, &mut p, end) {
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

        (p as usize).wrapping_sub(dst as usize) as c_int
    }
}

#[no_mangle]
pub extern "C" fn kstrdup_quotable(src: *const c_char, gfp: GfpT) -> *mut c_char {
    unsafe {
        if src.is_null() {
            return ptr::null_mut();
        }
        let slen = strlen(src);
        let flags: c_uint = ESCAPE_HEX;
        let esc: &[u8] = b"\x0c\n\r\t\x0b\x07\x1b\\\"\0";
        let esc = esc.as_ptr() as *const c_char;

        let dlen = string_escape_mem(src, slen, ptr::null_mut(), 0, flags, esc) as isize as usize;
        let dst = kmalloc(dlen.wrapping_add(1), gfp) as *mut c_char;
        if dst.is_null() {
            return ptr::null_mut();
        }
        // WARN_ON(... != dlen): result intentionally only evaluated
        let _ = (string_escape_mem(src, slen, dst, dlen, flags, esc) as isize as usize) != dlen;
        *dst.wrapping_add(dlen) = 0;
        dst
    }
}

#[no_mangle]
pub extern "C" fn kstrdup_quotable_cmdline(task: *mut TaskStruct, gfp: GfpT) -> *mut c_char {
    unsafe {
        let buffer = kmalloc(PAGE_SIZE, GFP_KERNEL) as *mut c_char;
        if buffer.is_null() {
            return ptr::null_mut();
        }
        let mut res = get_cmdline(task, buffer, (PAGE_SIZE - 1) as c_int);
        *buffer.offset(res as isize) = 0;

        loop {
            res = res.wrapping_sub(1);
            if !(res >= 0 && *buffer.offset(res as isize) == 0) {
                break;
            }
        }

        let mut i: c_int = 0;
        while i <= res {
            if *buffer.offset(i as isize) == 0 {
                *buffer.offset(i as isize) = b' ' as c_char;
            }
            i += 1;
        }

        let quoted = kstrdup_quotable(buffer, gfp);
        kfree(buffer as *const c_void);
        quoted
    }
}

#[no_mangle]
pub extern "C" fn kstrdup_quotable_file(file: *mut File, gfp: GfpT) -> *mut c_char {
    unsafe {
        if file.is_null() {
            return kstrdup(b"<unknown>\0".as_ptr() as *const c_char, gfp);
        }
        let temp = kmalloc(PATH_MAX + 11, GFP_KERNEL) as *mut c_char;
        if temp.is_null() {
            return kstrdup(b"<no_memory>\0".as_ptr() as *const c_char, gfp);
        }
        let mut pathname = file_path(file, temp, (PATH_MAX + 11) as c_int);
        if is_err(pathname) {
            pathname = kstrdup(b"<too_long>\0".as_ptr() as *const c_char, gfp);
        } else {
            pathname = kstrdup_quotable(pathname, gfp);
        }
        kfree(temp as *const c_void);
        pathname
    }
}

#[no_mangle]
pub extern "C" fn kstrdup_and_replace(src: *const c_char, old: c_char, new: c_char, gfp: GfpT) -> *mut c_char {
    unsafe {
        let dst = kstrdup(src, gfp);
        if dst.is_null() {
            return ptr::null_mut();
        }
        strreplace(dst, old, new)
    }
}

#[no_mangle]
pub extern "C" fn kasprintf_strarray(gfp: GfpT, prefix: *const c_char, n: usize) -> *mut *mut c_char {
    unsafe {
        let names = kcalloc(n, core::mem::size_of::<*mut c_char>(), gfp) as *mut *mut c_char;
        if names.is_null() {
            return ptr::null_mut();
        }
        let mut i: usize = 0;
        while i < n {
            let s = kasprintf(gfp, b"%s-%zu\0".as_ptr() as *const c_char, prefix, i);
            *names.add(i) = s;
            if s.is_null() {
                kfree_strarray(names, i);
                return ptr::null_mut();
            }
            i += 1;
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
        let mut i: c_uint = 0;
        while (i as usize) < n {
            kfree(*array.add(i as usize) as *const c_void);
            i = i.wrapping_add(1);
        }
        kfree(array as *const c_void);
    }
}

#[repr(C)]
struct StrArray {
    array: *mut *mut c_char,
    n: usize,
}

unsafe extern "C" fn devm_kfree_strarray(_dev: *mut Device, res: *mut c_void) {
    let array = res as *mut StrArray;
    kfree_strarray((*array).array, (*array).n);
}

#[no_mangle]
pub extern "C" fn devm_kasprintf_strarray(dev: *mut Device, prefix: *const c_char, n: usize) -> *mut *mut c_char {
    unsafe {
        let p = __devres_alloc_node(
            Some(devm_kfree_strarray),
            core::mem::size_of::<StrArray>(),
            GFP_KERNEL,
            -1,
            b"devm_kfree_strarray\0".as_ptr() as *const c_char,
        ) as *mut StrArray;
        if p.is_null() {
            return (-ENOMEM) as usize as *mut *mut c_char;
        }
        (*p).n = n;
        (*p).array = kasprintf_strarray(GFP_KERNEL, prefix, n);
        if (*p).array.is_null() {
            devres_free(p as *mut c_void);
            return (-ENOMEM) as usize as *mut *mut c_char;
        }
        devres_add(dev, p as *mut c_void);
        (*p).array
    }
}

#[no_mangle]
pub extern "C" fn skip_spaces(str: *const c_char) -> *mut c_char {
    unsafe {
        let mut s = str;
        while isspace(*s as u8) {
            s = s.add(1);
        }
        s as *mut c_char
    }
}

#[no_mangle]
pub extern "C" fn strim(s: *mut c_char) -> *mut c_char {
    unsafe {
        let size = strlen(s);
        if size == 0 {
            return s;
        }
        let mut end = s.add(size - 1);
        while end >= s && isspace(*end as u8) {
            end = end.wrapping_sub(1);
        }
        *end.wrapping_add(1) = 0;
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
        if *s1 == 0 && *s2 as u8 == b'\n' && *s2.add(1) == 0 {
            return true;
        }
        if *s1 as u8 == b'\n' && *s1.add(1) == 0 && *s2 == 0 {
            return true;
        }
        false
    }
}

#[no_mangle]
pub extern "C" fn match_string(array: *const *const c_char, n: usize, string: *const c_char) -> c_int {
    unsafe {
        let mut index: c_int = 0;
        while (index as isize as usize) < n {
            let item = *array.offset(index as isize);
            if item.is_null() {
                break;
            }
            if strcmp(item, string) == 0 {
                return index;
            }
            index = index.wrapping_add(1);
        }
        -EINVAL
    }
}

#[no_mangle]
pub extern "C" fn __sysfs_match_string(array: *const *const c_char, n: usize, str: *const c_char) -> c_int {
    unsafe {
        let mut index: c_int = 0;
        while (index as isize as usize) < n {
            let item = *array.offset(index as isize);
            if item.is_null() {
                break;
            }
            if sysfs_streq(item, str) {
                return index;
            }
            index = index.wrapping_add(1);
        }
        -EINVAL
    }
}

#[no_mangle]
pub extern "C" fn strreplace(str: *mut c_char, old: c_char, new: c_char) -> *mut c_char {
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
pub extern "C" fn memcpy_and_pad(dest: *mut c_void, dest_len: usize, src: *const c_void, count: usize, pad: c_int) {
    unsafe {
        let d = dest as *mut u8;
        if dest_len > count {
            ptr::copy_nonoverlapping(src as *const u8, d, count);
            ptr::write_bytes(d.add(count), pad as u8, dest_len - count);
        } else {
            ptr::copy_nonoverlapping(src as *const u8, d, dest_len);
        }
    }
}

#[allow(dead_code)]
type _Unused = c_ulong;

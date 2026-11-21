use core::ffi::{c_int, c_long, c_uint, c_ulong, c_void};

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

extern "C" {
    fn kmalloc(size: usize, flags: c_uint) -> *mut c_void;
    fn kcalloc(n: usize, size: usize, flags: c_uint) -> *mut c_void;
    fn kfree(p: *const c_void);
    fn kstrdup(s: *const u8, gfp: c_uint) -> *mut u8;
    fn kasprintf(gfp: c_uint, fmt: *const u8, ...) -> *mut u8;
    fn snprintf(buf: *mut u8, size: usize, fmt: *const u8, ...) -> c_int;
    fn get_options(str: *const u8, nints: c_int, ints: *mut c_int) -> *mut u8;
    fn hex_to_bin(ch: u8) -> c_int;
    fn memdup_user_nul(src: *const c_void, len: usize) -> *mut c_void;
    fn file_path(file: *mut File, buf: *mut u8, buflen: c_int) -> *mut u8;
    fn get_cmdline(task: *mut TaskStruct, buffer: *mut u8, buflen: c_int) -> c_int;
    fn __devres_alloc_node(
        release: unsafe extern "C" fn(*mut Device, *mut c_void),
        size: usize,
        gfp: c_uint,
        nid: c_int,
        name: *const u8,
    ) -> *mut c_void;
    fn devres_add(dev: *mut Device, res: *mut c_void);
    fn devres_free(res: *mut c_void);
    fn strlen(s: *const u8) -> usize;
    fn strcmp(a: *const u8, b: *const u8) -> c_int;
}

const GFP_KERNEL: c_uint = 0xcc0;
const PAGE_SIZE: usize = 4096;
const PATH_MAX: usize = 4096;
const EINVAL: c_int = 22;
const ENOMEM: c_long = 12;
const ENOENT: c_int = 2;

const STRING_UNITS_MASK: c_uint = 1;
const STRING_UNITS_NO_SPACE: c_uint = 1 << 30;
const STRING_UNITS_NO_BYTES: c_uint = 1 << 31;

const UNESCAPE_SPACE: c_uint = 1;
const UNESCAPE_OCTAL: c_uint = 2;
const UNESCAPE_HEX: c_uint = 4;
const UNESCAPE_SPECIAL: c_uint = 8;

const ESCAPE_SPACE: c_uint = 1;
const ESCAPE_SPECIAL: c_uint = 2;
const ESCAPE_NULL: c_uint = 4;
const ESCAPE_OCTAL: c_uint = 8;
const ESCAPE_NP: c_uint = 16;
const ESCAPE_HEX: c_uint = 32;
const ESCAPE_NA: c_uint = 64;
const ESCAPE_NAP: c_uint = 128;
const ESCAPE_APPEND: c_uint = 256;

fn isprint(c: u8) -> bool {
    (32..=126).contains(&c) || c >= 160
}
fn isspace(c: u8) -> bool {
    (9..=13).contains(&c) || c == 32 || c == 160
}
fn isascii(c: u8) -> bool {
    c < 128
}
fn isodigit(c: u8) -> bool {
    (b'0'..=b'7').contains(&c)
}
fn is_err(p: *const c_void) -> bool {
    (p as usize) >= 0usize.wrapping_sub(4095)
}
fn err_ptr(e: c_long) -> *mut c_void {
    e as usize as *mut c_void
}
fn ptr_err(p: *const c_void) -> c_long {
    p as usize as c_long
}
const HEX: &[u8; 16] = b"0123456789abcdef";

#[no_mangle]
pub extern "C" fn string_get_size(
    size: u64,
    blk_size: u64,
    units: c_uint,
    buf: *mut u8,
    len: c_int,
) -> c_int {
    let units_base = (units & STRING_UNITS_MASK) as usize;
    const UNITS_10: [&[u8]; 9] = [
        b"\0", b"k\0", b"M\0", b"G\0", b"T\0", b"P\0", b"E\0", b"Z\0", b"Y\0",
    ];
    const UNITS_2: [&[u8]; 9] = [
        b"\0", b"Ki\0", b"Mi\0", b"Gi\0", b"Ti\0", b"Pi\0", b"Ei\0", b"Zi\0", b"Yi\0",
    ];
    let units_str: [[&[u8]; 9]; 2] = [UNITS_10, UNITS_2];
    const DIVISOR: [u32; 2] = [1000, 1024];
    const ROUNDING: [u32; 3] = [500, 50, 5];
    let mut size = size;
    let mut blk_size = blk_size;
    let mut i: c_int = 0;
    let mut remainder: u32 = 0;
    let mut tmp = [0u8; 12];
    tmp[0] = 0;

    if blk_size == 0 {
        size = 0;
    }
    if size != 0 {
        let d = DIVISOR[units_base];
        while (blk_size >> 32) != 0 {
            blk_size /= d as u64;
            i += 1;
        }
        while (size >> 32) != 0 {
            size /= d as u64;
            i += 1;
        }
        size = size.wrapping_mul(blk_size);
        while size >= d as u64 {
            remainder = (size % d as u64) as u32;
            size /= d as u64;
            i += 1;
        }
        let mut sf_cap = size as u32;
        let mut j: usize = 0;
        while sf_cap.wrapping_mul(10) < 1000 {
            sf_cap = sf_cap.wrapping_mul(10);
            j += 1;
        }
        if units_base == 1 {
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
                snprintf(tmp.as_mut_ptr(), 12, b".%03u\0".as_ptr(), remainder);
            }
            tmp[j + 1] = 0;
        }
    }
    let unit: *const u8 = if (i as c_uint as usize) >= 9 {
        b"UNK\0".as_ptr()
    } else {
        units_str[units_base][i as usize].as_ptr()
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
            len as isize as usize,
            b"%u%s%s%s%s\0".as_ptr(),
            size as u32,
            tmp.as_ptr(),
            space,
            unit,
            bytes,
        )
    }
}

#[no_mangle]
pub extern "C" fn parse_int_array(buf: *const u8, _count: usize, array: *mut *mut c_int) -> c_int {
    unsafe {
        let mut nints: c_int = 0;
        get_options(buf, 0, &mut nints);
        if nints == 0 {
            return -ENOENT;
        }
        let n1 = nints.wrapping_add(1);
        let ints = kcalloc(n1 as isize as usize, 4, GFP_KERNEL) as *mut c_int;
        if ints.is_null() {
            return -(ENOMEM as c_int);
        }
        get_options(buf, n1, ints);
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
        let buf = memdup_user_nul(from as *const c_void, count);
        if is_err(buf) {
            return ptr_err(buf) as c_int;
        }
        let ret = parse_int_array(buf as *const u8, count, array);
        kfree(buf);
        ret
    }
}

unsafe fn unescape_space(src: &mut *mut u8, dst: &mut *mut u8) -> bool {
    let p = *dst;
    let q = *src;
    match *q {
        b'n' => *p = b'\n',
        b'r' => *p = b'\r',
        b't' => *p = b'\t',
        0x0b => unreachable_guard(),
        b'v' => *p = 0x0b,
        b'f' => *p = 0x0c,
        _ => return false,
    }
    *dst = (*dst).add(1);
    *src = (*src).add(1);
    true
}

#[inline(always)]
fn unreachable_guard() {}

unsafe fn unescape_octal(src: &mut *mut u8, dst: &mut *mut u8) -> bool {
    let p = *dst;
    let mut q = *src;
    if !isodigit(*q) {
        return false;
    }
    let mut num: u8 = *q & 7;
    q = q.add(1);
    while num < 32 && isodigit(*q) && (q.offset_from(*src) < 3) {
        num <<= 3;
        num += *q & 7;
        q = q.add(1);
    }
    *p = num;
    *dst = (*dst).add(1);
    *src = q;
    true
}

unsafe fn unescape_hex(src: &mut *mut u8, dst: &mut *mut u8) -> bool {
    let p = *dst;
    let mut q = *src;
    let c0 = *q;
    q = q.add(1);
    if c0 != b'x' {
        return false;
    }
    let mut digit = hex_to_bin(*q);
    q = q.add(1);
    let mut num = digit as u8;
    if digit < 0 {
        return false;
    }
    digit = hex_to_bin(*q);
    if digit >= 0 {
        q = q.add(1);
        num = (num << 4) | (digit as u8);
    }
    *p = num;
    *dst = (*dst).add(1);
    *src = q;
    true
}

unsafe fn unescape_special(src: &mut *mut u8, dst: &mut *mut u8) -> bool {
    let p = *dst;
    let q = *src;
    match *q {
        b'"' => *p = b'"',
        b'\\' => *p = b'\\',
        b'a' => *p = 0x07,
        b'e' => *p = 0x1b,
        _ => return false,
    }
    *dst = (*dst).add(1);
    *src = (*src).add(1);
    true
}

#[no_mangle]
pub extern "C" fn string_unescape(
    src: *mut u8,
    dst: *mut u8,
    size: usize,
    flags: c_uint,
) -> c_int {
    unsafe {
        let mut src = src;
        let mut out = dst;
        let mut size = size;
        if size == 0 {
            size = usize::MAX;
        }
        while *src != 0 {
            size -= 1;
            if size == 0 {
                break;
            }
            if *src == b'\\' && *src.add(1) != 0 && size > 1 {
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

#[inline(always)]
unsafe fn put(out: *mut u8, end: *mut u8, ch: u8) {
    if out < end {
        *out = ch;
    }
}

unsafe fn escape_passthrough(c: u8, dst: &mut *mut u8, end: *mut u8) -> bool {
    let out = *dst;
    put(out, end, c);
    *dst = out.wrapping_add(1);
    true
}

unsafe fn escape_two(to: u8, dst: &mut *mut u8, end: *mut u8) {
    let mut out = *dst;
    put(out, end, b'\\');
    out = out.wrapping_add(1);
    put(out, end, to);
    out = out.wrapping_add(1);
    *dst = out;
}

unsafe fn escape_space(c: u8, dst: &mut *mut u8, end: *mut u8) -> bool {
    let to = match c {
        b'\n' => b'n',
        b'\r' => b'r',
        b'\t' => b't',
        0x0b => b'v',
        0x0c => b'f',
        _ => return false,
    };
    escape_two(to, dst, end);
    true
}

unsafe fn escape_special(c: u8, dst: &mut *mut u8, end: *mut u8) -> bool {
    let to = match c {
        b'\\' => b'\\',
        0x07 => b'a',
        0x1b => b'e',
        b'"' => b'"',
        _ => return false,
    };
    escape_two(to, dst, end);
    true
}

unsafe fn escape_null(c: u8, dst: &mut *mut u8, end: *mut u8) -> bool {
    if c != 0 {
        return false;
    }
    escape_two(b'0', dst, end);
    true
}

unsafe fn escape_octal(c: u8, dst: &mut *mut u8, end: *mut u8) -> bool {
    let mut out = *dst;
    put(out, end, b'\\');
    out = out.wrapping_add(1);
    put(out, end, ((c >> 6) & 7) + b'0');
    out = out.wrapping_add(1);
    put(out, end, ((c >> 3) & 7) + b'0');
    out = out.wrapping_add(1);
    put(out, end, (c & 7) + b'0');
    out = out.wrapping_add(1);
    *dst = out;
    true
}

unsafe fn escape_hex(c: u8, dst: &mut *mut u8, end: *mut u8) -> bool {
    let mut out = *dst;
    put(out, end, b'\\');
    out = out.wrapping_add(1);
    put(out, end, b'x');
    out = out.wrapping_add(1);
    put(out, end, HEX[(c >> 4) as usize]);
    out = out.wrapping_add(1);
    put(out, end, HEX[(c & 15) as usize]);
    out = out.wrapping_add(1);
    *dst = out;
    true
}

unsafe fn in_set(only: *const u8, c: u8) -> bool {
    let mut s = only;
    while *s != c {
        if *s == 0 {
            return false;
        }
        s = s.add(1);
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
    unsafe {
        let mut p = dst;
        let end = p.wrapping_add(osz);
        let is_dict = !only.is_null() && *only != 0;
        let is_append = (flags & ESCAPE_APPEND) != 0;
        let mut src = src;
        let mut isz = isz;

        while isz != 0 {
            isz -= 1;
            let c = *src;
            src = src.add(1);
            let in_dict = is_dict && in_set(only, c);

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

#[no_mangle]
pub extern "C" fn kstrdup_quotable(src: *const u8, gfp: c_uint) -> *mut u8 {
    unsafe {
        if src.is_null() {
            return core::ptr::null_mut();
        }
        let slen = strlen(src);
        let esc: &[u8] = b"\x0c\n\r\t\x0b\x07\x1b\\\"\0";
        let flags = ESCAPE_HEX;

        let dlen = string_escape_mem(src, slen, core::ptr::null_mut(), 0, flags, esc.as_ptr())
            as isize as usize;
        let dst = kmalloc(dlen.wrapping_add(1), gfp) as *mut u8;
        if dst.is_null() {
            return core::ptr::null_mut();
        }
        // WARN_ON(...)
        let _ = string_escape_mem(src, slen, dst, dlen, flags, esc.as_ptr()) as isize as usize
            != dlen;
        *dst.add(dlen) = 0;
        dst
    }
}

#[no_mangle]
pub extern "C" fn kstrdup_quotable_cmdline(task: *mut TaskStruct, gfp: c_uint) -> *mut u8 {
    unsafe {
        let buffer = kmalloc(PAGE_SIZE, GFP_KERNEL) as *mut u8;
        if buffer.is_null() {
            return core::ptr::null_mut();
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
                *buffer.offset(i as isize) = b' ';
            }
            i += 1;
        }

        let quoted = kstrdup_quotable(buffer, gfp);
        kfree(buffer as *const c_void);
        quoted
    }
}

#[no_mangle]
pub extern "C" fn kstrdup_quotable_file(file: *mut File, gfp: c_uint) -> *mut u8 {
    unsafe {
        if file.is_null() {
            return kstrdup(b"<unknown>\0".as_ptr(), gfp);
        }
        let temp = kmalloc(PATH_MAX + 11, GFP_KERNEL) as *mut u8;
        if temp.is_null() {
            return kstrdup(b"<no_memory>\0".as_ptr(), gfp);
        }
        let mut pathname = file_path(file, temp, (PATH_MAX + 11) as c_int);
        if is_err(pathname as *const c_void) {
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
            return core::ptr::null_mut();
        }
        strreplace(dst, old, new)
    }
}

#[no_mangle]
pub extern "C" fn kasprintf_strarray(gfp: c_uint, prefix: *const u8, n: usize) -> *mut *mut u8 {
    unsafe {
        let names = kcalloc(n, core::mem::size_of::<*mut u8>(), gfp) as *mut *mut u8;
        if names.is_null() {
            return core::ptr::null_mut();
        }
        let mut i: usize = 0;
        while i < n {
            let s = kasprintf(gfp, b"%s-%zu\0".as_ptr(), prefix, i);
            *names.add(i) = s;
            if s.is_null() {
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
    array: *mut *mut u8,
    n: usize,
}

unsafe extern "C" fn devm_kfree_strarray(_dev: *mut Device, res: *mut c_void) {
    let array = res as *mut StrArray;
    kfree_strarray((*array).array, (*array).n);
}

#[no_mangle]
pub extern "C" fn devm_kasprintf_strarray(
    dev: *mut Device,
    prefix: *const u8,
    n: usize,
) -> *mut *mut u8 {
    unsafe {
        let ptr = __devres_alloc_node(
            devm_kfree_strarray,
            core::mem::size_of::<StrArray>(),
            GFP_KERNEL,
            -1,
            b"devm_kfree_strarray\0".as_ptr(),
        ) as *mut StrArray;
        if ptr.is_null() {
            return err_ptr(-ENOMEM) as *mut *mut u8;
        }
        (*ptr).n = n;
        (*ptr).array = kasprintf_strarray(GFP_KERNEL, prefix, n);
        if (*ptr).array.is_null() {
            devres_free(ptr as *mut c_void);
            return err_ptr(-ENOMEM) as *mut *mut u8;
        }
        devres_add(dev, ptr as *mut c_void);
        (*ptr).array
    }
}

#[no_mangle]
pub extern "C" fn skip_spaces(str: *const u8) -> *mut u8 {
    unsafe {
        let mut s = str;
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
        let mut end = s.add(size - 1);
        while end >= s && isspace(*end) {
            end = end.wrapping_sub(1);
        }
        *end.wrapping_add(1) = 0;
        skip_spaces(s)
    }
}

#[no_mangle]
pub extern "C" fn sysfs_streq(s1: *const u8, s2: *const u8) -> bool {
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
pub extern "C" fn match_string(array: *const *const u8, n: usize, string: *const u8) -> c_int {
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
pub extern "C" fn __sysfs_match_string(
    array: *const *const u8,
    n: usize,
    str: *const u8,
) -> c_int {
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
        let d = dest as *mut u8;
        if dest_len > count {
            if count != 0 {
                core::ptr::copy_nonoverlapping(src as *const u8, d, count);
            }
            let rest = dest_len - count;
            if rest != 0 {
                core::ptr::write_bytes(d.wrapping_add(count), pad as u8, rest);
            }
        } else if dest_len != 0 {
            core::ptr::copy_nonoverlapping(src as *const u8, d, dest_len);
        }
    }
}

#[allow(dead_code)]
const _UNUSED: c_ulong = 0;

// SPDX-License-Identifier: GPL-2.0-only
//! linux/lib/cmdline.c — перевод на Rust (x86_64, BITS_PER_LONG = 64).
//! Helper functions generally used for parsing kernel command line
//! and module options.

use core::ffi::{c_char, c_int, c_long, c_uint, c_ulonglong};
use core::ptr;

extern "C" {
    fn simple_strtoull(cp: *const c_char, endp: *mut *mut c_char, base: c_uint) -> c_ulonglong;
    fn simple_strtol(cp: *const c_char, endp: *mut *mut c_char, base: c_uint) -> c_long;
    fn skip_spaces(s: *const c_char) -> *mut c_char;
    fn strlen(s: *const c_char) -> usize;
    fn strncmp(a: *const c_char, b: *const c_char, n: usize) -> c_int;
}

const INT_MAX: c_int = c_int::MAX;
const ULLONG_MAX: c_ulonglong = c_ulonglong::MAX;

/// isspace() ядра: _S для 9–13, 32 и 160 (индекс — (unsigned char)c).
#[inline(always)]
fn isspace(c: c_char) -> bool {
    matches!(c as u8, 9..=13 | 32 | 160)
}

/// check_sub_overflow() для int: d = a - b с заворачиванием, истина при переполнении.
#[inline(always)]
fn check_sub_overflow(a: c_int, b: c_int, d: &mut c_int) -> bool {
    let (r, o) = a.overflowing_sub(b);
    *d = r;
    o
}

/// check_shl_overflow() для unsigned long long.
#[inline(always)]
fn check_shl_overflow(a: c_ulonglong, s: c_uint, d: &mut c_ulonglong) -> bool {
    let too_far = s >= 64;
    let sh = if too_far { 0 } else { s };
    *d = a << sh;
    too_far || (*d >> sh) != a
}

/*
 *	If a hyphen was found in get_option, this will handle the
 *	range of numbers, M-N.  This will expand the range and insert
 *	the values[M, M+1, ..., N] into the ints array in get_options.
 */
fn get_range(str: *mut *mut c_char, mut pint: *mut c_int, mut n: c_int) -> c_int {
    let mut inc_counter: c_int = 0;
    unsafe {
        *str = (*str).add(1);
        let upper_range = simple_strtol(*str, ptr::null_mut(), 0) as c_int;
        /* Keep the sign of the result when the difference doesn't fit */
        if check_sub_overflow(upper_range, *pint, &mut inc_counter) {
            inc_counter = if upper_range < *pint { -1 } else { INT_MAX };
        }
        let mut x = *pint;
        while n != 0 && x < upper_range {
            *pint = x;
            pint = pint.add(1);
            x = x.wrapping_add(1);
            n = n.wrapping_sub(1);
        }
    }
    inc_counter
}

/// get_option - Parse integer from an option string
///
/// Return: 0 - no int in string, 1 - int found, no subsequent comma,
/// 2 - int found including a subsequent comma, 3 - hyphen found to denote a range.
#[no_mangle]
pub extern "C" fn get_option(str: *mut *mut c_char, pint: *mut c_int) -> c_int {
    unsafe {
        let mut cur = *str;
        let value: c_int;

        if cur.is_null() || *cur == 0 {
            return 0;
        }
        if *cur == b'-' as c_char {
            cur = cur.add(1);
            value = simple_strtoull(cur, str, 0).wrapping_neg() as c_int;
        } else {
            value = simple_strtoull(cur, str, 0) as c_int;
        }
        if !pint.is_null() {
            *pint = value;
        }
        if cur == *str {
            return 0;
        }
        if **str == b',' as c_char {
            *str = (*str).add(1);
            return 2;
        }
        if **str == b'-' as c_char {
            return 3;
        }
        1
    }
}

/// get_options - Parse a string into a list of integers
#[no_mangle]
pub extern "C" fn get_options(str: *const c_char, nints: c_int, ints: *mut c_int) -> *mut c_char {
    let validate = nints == 0;
    let mut s = str as *mut c_char;
    let mut i: c_int = 1;

    unsafe {
        while i < nints || validate {
            let pint = if validate { ints } else { ints.offset(i as isize) };

            let res = get_option(&mut s, pint);
            if res == 0 {
                break;
            }
            if res == 3 {
                let n = if validate { 0 } else { nints.wrapping_sub(i) };

                let range_nums = get_range(&mut s, pint, n);
                if range_nums < 0 {
                    break;
                }
                /* The range didn't fit, so the array is full */
                if !validate && range_nums > n {
                    i = nints;
                    break;
                }
                /* Leave room for the upper number of the range */
                if range_nums >= INT_MAX.wrapping_sub(i) {
                    break;
                }
                /*
                 * Decrement the result by one to leave out the
                 * last number in the range.  The next iteration
                 * will handle the upper number in the range
                 */
                i = i.wrapping_add(range_nums.wrapping_sub(1));
            }
            i = i.wrapping_add(1);
            if res == 1 {
                break;
            }
        }
        *ints = i.wrapping_sub(1);
    }
    s
}

/// memparse - parse a string with mem suffixes into a number
#[no_mangle]
pub extern "C" fn memparse(ptr: *const c_char, retptr: *mut *mut c_char) -> c_ulonglong {
    unsafe {
        let mut endptr: *mut c_char = ptr::null_mut(); /* local pointer to end of parsed string */
        let mut ret = simple_strtoull(ptr, &mut endptr, 0);

        /* Consume valid suffix even in case of overflow. */
        let shl: c_uint = match *endptr as u8 {
            b'E' | b'e' => 60,
            b'P' | b'p' => 50,
            b'T' | b't' => 40,
            b'G' | b'g' => 30,
            b'M' | b'm' => 20,
            b'K' | b'k' => 10,
            _ => 0,
        };

        if shl != 0 && ptr != endptr as *const c_char {
            /* Have valid suffix with preceding number. */
            let mut d: c_ulonglong = 0;
            if check_shl_overflow(ret, shl, &mut d) {
                d = ULLONG_MAX;
            }
            ret = d;
            endptr = endptr.add(1);
        }

        if !retptr.is_null() {
            *retptr = endptr;
        }

        ret
    }
}

/// parse_option_str - Parse a string and check an option is set or not
/// (в C — глобальная функция без EXPORT_SYMBOL; символ сохранён для линковки).
#[no_mangle]
pub extern "C" fn parse_option_str(str: *const c_char, option: *const c_char) -> bool {
    let mut s = str;
    unsafe {
        while *s != 0 {
            if strncmp(s, option, strlen(option)) == 0 {
                s = s.add(strlen(option));
                if *s == 0 || *s == b',' as c_char {
                    return true;
                }
            }

            while *s != 0 && *s != b',' as c_char {
                s = s.add(1);
            }

            if *s == b',' as c_char {
                s = s.add(1);
            }
        }
    }
    false
}

/*
 * Parse a string to get a param value pair.
 * You can use " around spaces, but can't escape ".
 * Hyphens and underscores equivalent in parameter names.
 */
#[no_mangle]
pub extern "C" fn next_arg(
    mut args: *mut c_char,
    param: *mut *mut c_char,
    val: *mut *mut c_char,
) -> *mut c_char {
    let mut i: c_uint;
    let mut equals: c_uint = 0;
    let mut in_quote: c_int = 0;
    let mut quoted: c_int = 0;
    const QUOTE: c_char = b'"' as c_char;

    unsafe {
        if *args == QUOTE {
            args = args.add(1);
            in_quote = 1;
            quoted = 1;
        }

        i = 0;
        while *args.add(i as usize) != 0 {
            let c = *args.add(i as usize);
            if isspace(c) && in_quote == 0 {
                break;
            }
            if equals == 0 && c == b'=' as c_char {
                equals = i;
            }
            if c == QUOTE {
                in_quote = (in_quote == 0) as c_int;
            }
            i = i.wrapping_add(1);
        }

        let im1 = i.wrapping_sub(1) as usize;

        *param = args;
        if equals == 0 {
            *val = ptr::null_mut();
        } else {
            *args.add(equals as usize) = 0;
            *val = args.add(equals as usize).add(1);

            /* Don't include quotes in value. */
            if **val == QUOTE {
                *val = (*val).add(1);
                if *args.add(im1) == QUOTE {
                    *args.add(im1) = 0;
                }
            }
        }
        if quoted != 0 && i > 0 && *args.add(im1) == QUOTE {
            *args.add(im1) = 0;
        }

        if *args.add(i as usize) != 0 {
            *args.add(i as usize) = 0;
            args = args.add(i.wrapping_add(1) as usize);
        } else {
            args = args.add(i as usize);
        }

        /* Chew up trailing spaces. */
        skip_spaces(args)
    }
}

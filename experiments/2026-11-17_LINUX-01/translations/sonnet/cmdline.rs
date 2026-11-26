use core::ffi::{c_char, c_int, c_long, c_uint, c_ulong, c_ulonglong};

extern "C" {
    fn simple_strtoull(cp: *const c_char, endp: *mut *mut c_char, base: c_uint) -> c_ulonglong;
    fn simple_strtol(cp: *const c_char, endp: *mut *mut c_char, base: c_uint) -> c_long;
    fn skip_spaces(str: *const c_char) -> *mut c_char;
    fn strlen(s: *const c_char) -> usize;
    fn strncmp(a: *const c_char, b: *const c_char, n: usize) -> c_int;
}

#[allow(dead_code)]
type KernelUlong = c_ulong;

const INT_MAX: c_int = c_int::MAX;
const ULLONG_MAX: c_ulonglong = c_ulonglong::MAX;

#[inline]
fn isspace(c: c_char) -> bool {
    let b = c as u8;
    (9..=13).contains(&b) || b == 32 || b == 160
}

fn get_range(str: *mut *mut c_char, pint: *mut c_int, n: c_int) -> c_int {
    unsafe {
        let mut pint = pint;
        let mut n = n;

        *str = (*str).wrapping_add(1);
        let upper_range: c_int = simple_strtol(*str, core::ptr::null_mut(), 0) as c_int;

        let (diff, overflow) = upper_range.overflowing_sub(*pint);
        let mut inc_counter: c_int = diff;
        if overflow {
            inc_counter = if upper_range < *pint { -1 } else { INT_MAX };
        }

        let mut x: c_int = *pint;
        while n != 0 && x < upper_range {
            *pint = x;
            pint = pint.wrapping_add(1);
            x += 1;
            n = n.wrapping_sub(1);
        }
        inc_counter
    }
}

#[no_mangle]
pub extern "C" fn get_option(str: *mut *mut c_char, pint: *mut c_int) -> c_int {
    unsafe {
        let mut cur: *mut c_char = *str;

        if cur.is_null() || *cur == 0 {
            return 0;
        }
        let value: c_int;
        if *cur == b'-' as c_char {
            cur = cur.add(1);
            let v = simple_strtoull(cur, str, 0);
            value = v.wrapping_neg() as c_int;
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

#[no_mangle]
pub extern "C" fn get_options(str: *const c_char, nints: c_int, ints: *mut c_int) -> *mut c_char {
    unsafe {
        let mut str: *const c_char = str;
        let validate = nints == 0;
        let mut i: c_int = 1;

        while i < nints || validate {
            let pint: *mut c_int = if validate {
                ints
            } else {
                ints.wrapping_offset(i as isize)
            };
            let strp = &mut str as *mut *const c_char as *mut *mut c_char;

            let res = get_option(strp, pint);
            if res == 0 {
                break;
            }
            if res == 3 {
                let n: c_int = if validate { 0 } else { nints - i };

                let range_nums = get_range(strp, pint, n);
                if range_nums < 0 {
                    break;
                }
                // The range didn't fit, so the array is full
                if !validate && range_nums > n {
                    i = nints;
                    break;
                }
                // Leave room for the upper number of the range
                if range_nums >= INT_MAX - i {
                    break;
                }
                i += range_nums - 1;
            }
            i += 1;
            if res == 1 {
                break;
            }
        }
        *ints = i - 1;
        str as *mut c_char
    }
}

#[no_mangle]
pub extern "C" fn memparse(ptr: *const c_char, retptr: *mut *mut c_char) -> c_ulonglong {
    unsafe {
        let mut endptr: *mut c_char = core::ptr::null_mut();
        let mut ret: c_ulonglong = simple_strtoull(ptr, &mut endptr, 0);
        let mut shl: c_uint = 0;

        shl += match *endptr as u8 {
            b'E' | b'e' => 60,
            b'P' | b'p' => 50,
            b'T' | b't' => 40,
            b'G' | b'g' => 30,
            b'M' | b'm' => 20,
            b'K' | b'k' => 10,
            _ => 0,
        };

        if shl != 0 && ptr != endptr as *const c_char {
            // check_shl_overflow(ret, shl, &ret)
            let (s, big) = if shl >= 64 { (0u32, true) } else { (shl, false) };
            let d: c_ulonglong = ret.wrapping_shl(s);
            let overflow = big || (d >> s) != ret;
            ret = d;
            if overflow {
                ret = ULLONG_MAX;
            }
            endptr = endptr.add(1);
        }

        if !retptr.is_null() {
            *retptr = endptr;
        }

        ret
    }
}

#[no_mangle]
pub extern "C" fn parse_option_str(str: *const c_char, option: *const c_char) -> bool {
    unsafe {
        let mut str = str;
        while *str != 0 {
            if strncmp(str, option, strlen(option)) == 0 {
                str = str.add(strlen(option));
                if *str == 0 || *str == b',' as c_char {
                    return true;
                }
            }

            while *str != 0 && *str != b',' as c_char {
                str = str.add(1);
            }

            if *str == b',' as c_char {
                str = str.add(1);
            }
        }

        false
    }
}

#[no_mangle]
pub extern "C" fn next_arg(
    args: *mut c_char,
    param: *mut *mut c_char,
    val: *mut *mut c_char,
) -> *mut c_char {
    unsafe {
        let mut args = args;
        let mut equals: c_uint = 0;
        let mut in_quote: c_int = 0;
        let mut quoted: c_int = 0;

        if *args == b'"' as c_char {
            args = args.add(1);
            in_quote = 1;
            quoted = 1;
        }

        let mut i: c_uint = 0;
        while *args.add(i as usize) != 0 {
            let c = *args.add(i as usize);
            if isspace(c) && in_quote == 0 {
                break;
            }
            if equals == 0 && c == b'=' as c_char {
                equals = i;
            }
            if c == b'"' as c_char {
                in_quote = (in_quote == 0) as c_int;
            }
            i = i.wrapping_add(1);
        }

        *param = args;
        if equals == 0 {
            *val = core::ptr::null_mut();
        } else {
            *args.add(equals as usize) = 0;
            *val = args.add(equals as usize).add(1);

            // Don't include quotes in value.
            if **val == b'"' as c_char {
                *val = (*val).add(1);
                if *args.add(i.wrapping_sub(1) as usize) == b'"' as c_char {
                    *args.add(i.wrapping_sub(1) as usize) = 0;
                }
            }
        }
        if quoted != 0 && i > 0 && *args.add(i.wrapping_sub(1) as usize) == b'"' as c_char {
            *args.add(i.wrapping_sub(1) as usize) = 0;
        }

        if *args.add(i as usize) != 0 {
            *args.add(i as usize) = 0;
            args = args.add(i.wrapping_add(1) as usize);
        } else {
            args = args.add(i as usize);
        }

        // Chew up trailing spaces.
        skip_spaces(args)
    }
}

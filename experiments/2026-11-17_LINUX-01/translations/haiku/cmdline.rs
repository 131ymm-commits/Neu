// Перевод lib/cmdline.c (Linux kernel, GPL-2.0-only) на Rust.
// Конфигурация: x86_64, BITS_PER_LONG = 64, CONFIG_CPU_NO_EFFICIENT_FFS не задан.

use core::ffi::{c_char, c_int, c_long, c_uint, c_ulonglong};
use core::ptr;

extern "C" {
    fn simple_strtoull(cp: *const c_char, endp: *mut *mut c_char, base: c_uint) -> c_ulonglong;
    fn simple_strtol(cp: *const c_char, endp: *mut *mut c_char, base: c_uint) -> c_long;
    fn skip_spaces(str: *const c_char) -> *mut c_char;
    fn strlen(s: *const c_char) -> usize;
    fn strncmp(a: *const c_char, b: *const c_char, n: usize) -> c_int;
}

/// Эквивалент isspace() из ядра: байты 9..=13, 32 и 160.
#[inline]
fn is_space(c: u8) -> bool {
    matches!(c, 9..=13 | 32 | 160)
}

/// Разворачивает диапазон M-N в массив значений (static в C, не экспортируется).
fn get_range(str: *mut *mut c_char, pint: *mut c_int, mut n: c_int) -> c_int {
    unsafe {
        *str = (*str).add(1);
        let upper_range: c_int =
            simple_strtol(*str as *const c_char, ptr::null_mut(), 0) as c_int;

        // check_sub_overflow(upper_range, *pint, &inc_counter)
        let (diff, ov) = upper_range.overflowing_sub(*pint);
        let inc_counter: c_int = if ov {
            if upper_range < *pint {
                -1
            } else {
                c_int::MAX
            }
        } else {
            diff
        };

        // for (x = *pint; n && x < upper_range; x++, n--) *pint++ = x;
        let mut p = pint;
        let mut x = *pint;
        while n != 0 && x < upper_range {
            *p = x;
            p = p.add(1);
            x += 1;
            n -= 1;
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

        let value: c_int = if *cur as u8 == b'-' {
            cur = cur.add(1);
            // -simple_strtoull(...): беззнаковое отрицание, затем усечение до int
            (simple_strtoull(cur as *const c_char, str, 0).wrapping_neg()) as c_int
        } else {
            simple_strtoull(cur as *const c_char, str, 0) as c_int
        };

        if !pint.is_null() {
            *pint = value;
        }
        if cur == *str {
            return 0;
        }
        if *(*str) as u8 == b',' {
            *str = (*str).add(1);
            return 2;
        }
        if *(*str) as u8 == b'-' {
            return 3;
        }
        1
    }
}

#[no_mangle]
pub extern "C" fn get_options(str: *const c_char, nints: c_int, ints: *mut c_int) -> *mut c_char {
    unsafe {
        let validate = nints == 0;
        let mut i: c_int = 1;
        let mut s: *mut c_char = str as *mut c_char;

        while i < nints || validate {
            let pint: *mut c_int = if validate {
                ints
            } else {
                ints.add(i as usize)
            };

            let res = get_option(&mut s as *mut *mut c_char, pint);
            if res == 0 {
                break;
            }
            if res == 3 {
                let n: c_int = if validate { 0 } else { nints - i };

                let range_nums = get_range(&mut s as *mut *mut c_char, pint, n);
                if range_nums < 0 {
                    break;
                }
                // Диапазон не поместился, массив заполнен
                if !validate && range_nums > n {
                    i = nints;
                    break;
                }
                // Оставляем место для верхней границы диапазона
                if range_nums >= c_int::MAX - i {
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
        s
    }
}

#[no_mangle]
pub extern "C" fn memparse(ptr: *const c_char, retptr: *mut *mut c_char) -> c_ulonglong {
    unsafe {
        let mut endptr: *mut c_char = ptr::null_mut();
        let mut ret: u64 = simple_strtoull(ptr, &mut endptr as *mut *mut c_char, 0);

        // Суммарный сдвиг от цепочки fallthrough: E=60, P=50, T=40, G=30, M=20, K=10
        let shl: u32 = match *endptr as u8 {
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
            let (d, ov) = if shl >= 64 {
                (ret, true)
            } else {
                let d = ret << shl;
                (d, (d >> shl) != ret)
            };
            ret = d;
            if ov {
                ret = u64::MAX;
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
pub extern "C" fn parse_option_str(mut str: *const c_char, option: *const c_char) -> bool {
    unsafe {
        while *str != 0 {
            if strncmp(str, option, strlen(option)) == 0 {
                str = str.add(strlen(option));
                if *str == 0 || *str as u8 == b',' {
                    return true;
                }
            }

            while *str != 0 && *str as u8 != b',' {
                str = str.add(1);
            }
            if *str as u8 == b',' {
                str = str.add(1);
            }
        }
        false
    }
}

#[no_mangle]
pub extern "C" fn next_arg(
    mut args: *mut c_char,
    param: *mut *mut c_char,
    val: *mut *mut c_char,
) -> *mut c_char {
    unsafe {
        let mut i: c_uint = 0;
        let mut equals: c_uint = 0;
        let mut in_quote = false;
        let mut quoted = false;

        if *args as u8 == b'"' {
            args = args.add(1);
            in_quote = true;
            quoted = true;
        }

        while *args.add(i as usize) != 0 {
            let c = *args.add(i as usize) as u8;
            if is_space(c) && !in_quote {
                break;
            }
            if equals == 0 && c == b'=' {
                equals = i;
            }
            if c == b'"' {
                in_quote = !in_quote;
            }
            i = i.wrapping_add(1);
        }

        *param = args;
        if equals == 0 {
            *val = ptr::null_mut();
        } else {
            *args.add(equals as usize) = 0;
            *val = args.add(equals as usize + 1);

            // Кавычки в значении не включаем
            if **val as u8 == b'"' {
                *val = (*val).add(1);
                if *args.add(i.wrapping_sub(1) as usize) as u8 == b'"' {
                    *args.add(i.wrapping_sub(1) as usize) = 0;
                }
            }
        }

        if quoted && i > 0 && *args.add(i.wrapping_sub(1) as usize) as u8 == b'"' {
            *args.add(i.wrapping_sub(1) as usize) = 0;
        }

        if *args.add(i as usize) != 0 {
            *args.add(i as usize) = 0;
            args = args.add(i as usize + 1);
        } else {
            args = args.add(i as usize);
        }

        // Отбрасываем пробелы в хвосте
        skip_spaces(args)
    }
}

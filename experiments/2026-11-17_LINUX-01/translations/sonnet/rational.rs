use core::ffi::c_ulong;

#[no_mangle]
pub extern "C" fn rational_best_approximation(
    given_numerator: c_ulong,
    given_denominator: c_ulong,
    max_numerator: c_ulong,
    max_denominator: c_ulong,
    best_numerator: *mut c_ulong,
    best_denominator: *mut c_ulong,
) {
    let mut n: c_ulong = given_numerator;
    let mut d: c_ulong = given_denominator;
    let mut n0: c_ulong = 0;
    let mut d1: c_ulong = 0;
    let mut n1: c_ulong = 1;
    let mut d0: c_ulong = 1;

    loop {
        if d == 0 {
            break;
        }
        let dp: c_ulong = d;
        let a: c_ulong = n / d;
        d = n % d;
        n = dp;

        let n2: c_ulong = n0.wrapping_add(a.wrapping_mul(n1));
        let d2: c_ulong = d0.wrapping_add(a.wrapping_mul(d1));

        if n2 > max_numerator || d2 > max_denominator {
            let mut t: c_ulong = c_ulong::MAX;

            if d1 != 0 {
                t = max_denominator.wrapping_sub(d0) / d1;
            }
            if n1 != 0 {
                t = t.min(max_numerator.wrapping_sub(n0) / n1);
            }

            // `2u * t`: unsigned int promoted to unsigned long, wraps in 64 bits.
            let two_t: c_ulong = t.wrapping_mul(2);
            if d1 == 0
                || two_t > a
                || (two_t == a && d0.wrapping_mul(dp) > d1.wrapping_mul(d))
            {
                n1 = n0.wrapping_add(t.wrapping_mul(n1));
                d1 = d0.wrapping_add(t.wrapping_mul(d1));
            }
            break;
        }
        n0 = n1;
        n1 = n2;
        d0 = d1;
        d1 = d2;
    }
    unsafe {
        *best_numerator = n1;
        *best_denominator = d1;
    }
}

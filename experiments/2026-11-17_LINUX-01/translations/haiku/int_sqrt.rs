use core::ffi::c_ulong;

/// Computes floor(sqrt(x)).
#[no_mangle]
pub extern "C" fn int_sqrt(mut x: c_ulong) -> c_ulong {
    let mut y: c_ulong = 0;

    if x <= 1 {
        return x;
    }

    // __fls(x): index of the most significant set bit, x != 0 here.
    let fls: c_ulong = (63 - x.leading_zeros()) as c_ulong;
    let mut m: c_ulong = 1 << (fls & !1);

    while m != 0 {
        let b: c_ulong = y + m;
        y >>= 1;

        if x >= b {
            x -= b;
            y += m;
        }
        m >>= 2;
    }

    y
}

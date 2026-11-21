use core::ffi::c_ulong;

#[inline]
fn fls_index(x: c_ulong) -> c_ulong {
    // __fls: index of the most significant set bit, counting from 0 (x != 0)
    (63 - x.leading_zeros()) as c_ulong
}

#[no_mangle]
pub extern "C" fn int_sqrt(x: c_ulong) -> c_ulong {
    let mut x = x;
    let mut y: c_ulong = 0;

    if x <= 1 {
        return x;
    }

    let mut m: c_ulong = (1 as c_ulong) << (fls_index(x) & !1);
    while m != 0 {
        let b = y.wrapping_add(m);
        y >>= 1;

        if x >= b {
            x = x.wrapping_sub(b);
            y = y.wrapping_add(m);
        }
        m >>= 2;
    }

    y
}

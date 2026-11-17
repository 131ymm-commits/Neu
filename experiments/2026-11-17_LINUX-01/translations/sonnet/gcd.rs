use core::ffi::c_ulong;

#[inline(always)]
fn ffs(x: c_ulong) -> u32 {
    // __ffs(x): index of the lowest set bit, x != 0
    x.trailing_zeros()
}

fn binary_gcd(mut a: c_ulong, mut b: c_ulong) -> c_ulong {
    let r: c_ulong = a | b;

    b >>= ffs(b);
    if b == 1 {
        return r & r.wrapping_neg();
    }

    loop {
        a >>= ffs(a);
        if a == 1 {
            return r & r.wrapping_neg();
        }
        if a == b {
            return a << ffs(r);
        }

        if a < b {
            core::mem::swap(&mut a, &mut b);
        }
        a = a.wrapping_sub(b);
    }
}

#[no_mangle]
pub extern "C" fn gcd(a: c_ulong, b: c_ulong) -> c_ulong {
    let r: c_ulong = a | b;

    if a == 0 || b == 0 {
        return r;
    }

    // efficient_ffs_key is enabled in this configuration, so the
    // static-branch condition is always true and the generic
    // loop-based fallback after it is unreachable.
    binary_gcd(a, b)
}

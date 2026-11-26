use core::ffi::c_int;
use core::sync::atomic::{AtomicU32, Ordering};

#[allow(non_camel_case_types)]
pub type errseq_t = u32;

const MAX_ERRNO: u32 = 4095;

/* ilog2(MAX_ERRNO) + 1 = 11 + 1 = 12 */
const ERRSEQ_SHIFT: u32 = (31 - MAX_ERRNO.leading_zeros()) + 1;
const ERRSEQ_SEEN: u32 = 1 << ERRSEQ_SHIFT;
const ERRNO_MASK: u32 = ERRSEQ_SEEN - 1;
const ERRSEQ_CTR_INC: u32 = 1 << (ERRSEQ_SHIFT + 1);

#[inline(always)]
unsafe fn read_once(p: *mut errseq_t) -> errseq_t {
    AtomicU32::from_ptr(p).load(Ordering::Relaxed)
}

#[inline(always)]
unsafe fn cmpxchg(p: *mut errseq_t, old: errseq_t, new: errseq_t) -> errseq_t {
    match AtomicU32::from_ptr(p).compare_exchange(old, new, Ordering::SeqCst, Ordering::SeqCst) {
        Ok(v) => v,
        Err(v) => v,
    }
}

#[no_mangle]
pub extern "C" fn errseq_set(eseq: *mut errseq_t, err: c_int) -> errseq_t {
    unsafe {
        let mut old = read_once(eseq);
        let cur: errseq_t;

        let neg = err.wrapping_neg() as u32;
        if err == 0 || neg > MAX_ERRNO {
            // WARN("err = %d\n", err): no logging available
            return old;
        }

        loop {
            let mut new = (old & !(ERRNO_MASK | ERRSEQ_SEEN)) | neg;

            if old & ERRSEQ_SEEN != 0 {
                new = new.wrapping_add(ERRSEQ_CTR_INC);
            }

            if new == old {
                cur = new;
                break;
            }

            let c = cmpxchg(eseq, old, new);
            if c == old || c == new {
                cur = c;
                break;
            }

            old = c;
        }
        cur
    }
}

#[no_mangle]
pub extern "C" fn errseq_sample(eseq: *mut errseq_t) -> errseq_t {
    unsafe {
        let mut old = read_once(eseq);
        if old & ERRSEQ_SEEN == 0 {
            old = 0;
        }
        old
    }
}

#[no_mangle]
pub extern "C" fn errseq_check(eseq: *mut errseq_t, since: errseq_t) -> c_int {
    unsafe {
        let cur = read_once(eseq);
        if cur == since {
            return 0;
        }
        -((cur & ERRNO_MASK) as c_int)
    }
}

#[no_mangle]
pub extern "C" fn errseq_check_and_advance(eseq: *mut errseq_t, since: *mut errseq_t) -> c_int {
    unsafe {
        let mut err: c_int = 0;
        let mut old = read_once(eseq);
        while old != core::ptr::read_volatile(since) {
            let new = old | ERRSEQ_SEEN;
            if new != old {
                let cur = cmpxchg(eseq, old, new);
                if cur != old {
                    old = cur;
                    continue;
                }
            }
            core::ptr::write_volatile(since, new);
            err = -((new & ERRNO_MASK) as c_int);
            break;
        }
        err
    }
}

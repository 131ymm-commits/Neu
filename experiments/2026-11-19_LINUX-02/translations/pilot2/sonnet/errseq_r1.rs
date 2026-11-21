use core::sync::atomic::{AtomicU32, Ordering};
use core::ffi::{c_int, c_uint};

#[allow(non_camel_case_types)]
pub type errseq_t = u32;

const MAX_ERRNO: c_uint = 4095;
/// ilog2(MAX_ERRNO) + 1
const ERRSEQ_SHIFT: u32 = 11 + 1;
const ERRSEQ_SEEN: u32 = 1 << ERRSEQ_SHIFT;
const ERRNO_MASK: u32 = ERRSEQ_SEEN - 1;
const ERRSEQ_CTR_INC: u32 = 1 << (ERRSEQ_SHIFT + 1);

#[inline(always)]
unsafe fn cmpxchg(p: *mut errseq_t, old: u32, new: u32) -> u32 {
    let a = AtomicU32::from_ptr(p);
    match a.compare_exchange(old, new, Ordering::SeqCst, Ordering::SeqCst) {
        Ok(v) => v,
        Err(v) => v,
    }
}

#[inline(always)]
unsafe fn read_once(p: *mut errseq_t) -> u32 {
    AtomicU32::from_ptr(p).load(Ordering::Relaxed)
}

#[no_mangle]
pub extern "C" fn errseq_set(eseq: *mut errseq_t, err: c_int) -> errseq_t {
    unsafe {
        let mut old: errseq_t = read_once(eseq);
        let cur: errseq_t;

        if err == 0 || (err.wrapping_neg() as c_uint) > MAX_ERRNO {
            return old;
        }

        loop {
            let mut new: errseq_t =
                (old & !(ERRNO_MASK | ERRSEQ_SEEN)) | (err.wrapping_neg() as u32);

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
        ((cur & ERRNO_MASK) as c_int).wrapping_neg()
    }
}

#[no_mangle]
pub extern "C" fn errseq_check_and_advance(eseq: *mut errseq_t, since: *mut errseq_t) -> c_int {
    unsafe {
        let mut err: c_int = 0;
        let mut old: errseq_t = read_once(eseq);
        while old != *since {
            let new = old | ERRSEQ_SEEN;
            if new != old {
                let cur = cmpxchg(eseq, old, new);
                if cur != old {
                    old = cur;
                    continue;
                }
            }
            *since = new;
            err = ((new & ERRNO_MASK) as c_int).wrapping_neg();
            break;
        }
        err
    }
}

use core::ffi::{c_int, c_uint};
use core::sync::atomic::{AtomicU32, Ordering};

#[allow(non_camel_case_types)]
pub type errseq_t = u32;

/// include/linux/err.h
const MAX_ERRNO: c_uint = 4095;

/// ilog2(n): номер старшего установленного бита (n > 0).
const fn ilog2(n: u32) -> u32 {
    31 - n.leading_zeros()
}

/* The low bits are designated for error code (max of MAX_ERRNO) */
const ERRSEQ_SHIFT: u32 = ilog2(MAX_ERRNO) + 1;

/* This bit is used as a flag to indicate whether the value has been seen */
const ERRSEQ_SEEN: u32 = 1u32 << ERRSEQ_SHIFT;

/* Leverage macro ERRSEQ_SEEN to define errno mask macro here */
const ERRNO_MASK: u32 = ERRSEQ_SEEN - 1;

/* The lowest bit of the counter */
const ERRSEQ_CTR_INC: u32 = 1u32 << (ERRSEQ_SHIFT + 1);

#[inline(always)]
fn atomic_of<'a>(p: *mut errseq_t) -> &'a AtomicU32 {
    // SAFETY: вызывающий код на C передаёт валидный выровненный указатель на errseq_t,
    // к которому все конкурентные обращения идут атомарно (READ_ONCE/cmpxchg).
    unsafe { AtomicU32::from_ptr(p) }
}

/// READ_ONCE(*p)
#[inline(always)]
fn read_once(p: *mut errseq_t) -> errseq_t {
    atomic_of(p).load(Ordering::Relaxed)
}

/// cmpxchg(p, old, new): полностью упорядоченная операция, возвращает прежнее значение.
#[inline(always)]
fn cmpxchg(p: *mut errseq_t, old: errseq_t, new: errseq_t) -> errseq_t {
    match atomic_of(p).compare_exchange(old, new, Ordering::SeqCst, Ordering::SeqCst) {
        Ok(v) => v,
        Err(v) => v,
    }
}

/// WARN(cond, ...): возвращает cond (вывода в журнал здесь нет — только core).
#[inline(always)]
fn warn(cond: bool, _err: c_int) -> bool {
    cond
}

#[no_mangle]
pub extern "C" fn errseq_set(eseq: *mut errseq_t, err: c_int) -> errseq_t {
    let mut cur: errseq_t;
    let mut old: errseq_t;

    old = read_once(eseq);

    let neg_err: u32 = err.wrapping_neg() as c_uint;
    if warn(err == 0 || neg_err > MAX_ERRNO, err) {
        return old;
    }

    loop {
        /* Clear out error bits and set new error */
        let mut new: errseq_t = (old & !(ERRNO_MASK | ERRSEQ_SEEN)) | neg_err;

        /* Only increment if someone has looked at it */
        if old & ERRSEQ_SEEN != 0 {
            new = new.wrapping_add(ERRSEQ_CTR_INC);
        }

        /* If there would be no change, then call it done */
        if new == old {
            cur = new;
            break;
        }

        /* Try to swap the new value into place */
        cur = cmpxchg(eseq, old, new);

        /*
         * Call it success if we did the swap or someone else beat us
         * to it for the same value.
         */
        if cur == old || cur == new {
            break;
        }

        /* Raced with an update, try again */
        old = cur;
    }
    cur
}

#[no_mangle]
pub extern "C" fn errseq_sample(eseq: *mut errseq_t) -> errseq_t {
    let mut old = read_once(eseq);

    /* If nobody has seen this error yet, then we can be the first. */
    if old & ERRSEQ_SEEN == 0 {
        old = 0;
    }
    old
}

#[no_mangle]
pub extern "C" fn errseq_check(eseq: *mut errseq_t, since: errseq_t) -> c_int {
    let cur = read_once(eseq);

    if cur == since {
        return 0;
    }
    (cur & ERRNO_MASK).wrapping_neg() as c_int
}

#[no_mangle]
pub extern "C" fn errseq_check_and_advance(eseq: *mut errseq_t, since: *mut errseq_t) -> c_int {
    let mut err: c_int = 0;
    let mut old: errseq_t;
    let mut new: errseq_t;

    old = read_once(eseq);
    // SAFETY: since — валидный указатель от вызывающего кода; обычное чтение, как в C.
    while old != unsafe { *since } {
        new = old | ERRSEQ_SEEN;
        if new != old {
            let cur = cmpxchg(eseq, old, new);

            if cur != old {
                old = cur;
                continue;
            }
        }
        // SAFETY: since — валидный указатель от вызывающего кода; обычная запись, как в C.
        unsafe {
            *since = new;
        }
        err = (new & ERRNO_MASK).wrapping_neg() as c_int;
        break;
    }
    err
}

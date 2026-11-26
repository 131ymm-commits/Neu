//! Translation of Linux `lib/errseq.c` into Rust.
//!
//! An errseq_t is a way of recording errors in one place, and allowing any
//! number of "subscribers" to tell whether it has changed since a previous
//! point where it was sampled.
//!
//! It is a u32: the low 12 bits hold an error code (between 0 and
//! -MAX_ERRNO), bit 12 is the SEEN flag, and the upper bits are a counter.

#![allow(non_camel_case_types)]

use core::ffi::{c_int, c_uint};
use core::sync::atomic::{AtomicU32, Ordering};

/// `typedef u32 errseq_t;`
pub type errseq_t = u32;

/// include/linux/err.h
const MAX_ERRNO: c_uint = 4095;

/// ilog2(n) for n > 0: index of the most significant set bit.
const fn ilog2(n: u32) -> u32 {
    31 - n.leading_zeros()
}

/// The low bits are designated for error code (max of MAX_ERRNO).
const ERRSEQ_SHIFT: u32 = ilog2(MAX_ERRNO) + 1; // 12

/// This bit is used as a flag to indicate whether the value has been seen.
const ERRSEQ_SEEN: u32 = 1u32 << ERRSEQ_SHIFT; // 0x1000

/// Errno mask.
const ERRNO_MASK: u32 = ERRSEQ_SEEN - 1; // 0x0fff

/// The lowest bit of the counter.
const ERRSEQ_CTR_INC: u32 = 1u32 << (ERRSEQ_SHIFT + 1); // 0x2000

/// READ_ONCE(*p): a single atomic load.
#[inline(always)]
unsafe fn read_once(p: *mut errseq_t) -> errseq_t {
    // SAFETY: caller passes a valid, suitably aligned pointer to an errseq_t.
    unsafe { AtomicU32::from_ptr(p) }.load(Ordering::Relaxed)
}

/// cmpxchg(p, old, new): atomically replace *p with `new` if it equals
/// `old`; return the value of *p prior to the operation. Fully ordered.
#[inline(always)]
unsafe fn cmpxchg(p: *mut errseq_t, old: errseq_t, new: errseq_t) -> errseq_t {
    // SAFETY: caller passes a valid, suitably aligned pointer to an errseq_t.
    let a = unsafe { AtomicU32::from_ptr(p) };
    match a.compare_exchange(old, new, Ordering::SeqCst, Ordering::SeqCst) {
        Ok(v) => v,
        Err(v) => v,
    }
}

/// WARN(cond, ...): emit a warning (no logging facility is available here)
/// and return the condition.
#[inline(always)]
fn warn(cond: bool, _err: c_int) -> bool {
    cond
}

/// errseq_set - set a errseq_t for later reporting
///
/// Return: The previous value, primarily for debugging purposes.
#[no_mangle]
pub extern "C" fn errseq_set(eseq: *mut errseq_t, err: c_int) -> errseq_t {
    // SAFETY: eseq is a valid pointer supplied by the C caller.
    let mut old: errseq_t = unsafe { read_once(eseq) };

    // (unsigned int)-err, with kernel wrapping semantics for INT_MIN.
    let neg_err: c_uint = err.wrapping_neg() as c_uint;

    if warn(err == 0 || neg_err > MAX_ERRNO, err) {
        return old;
    }

    let cur: errseq_t;
    loop {
        // Clear out error bits and set new error.
        let mut new: errseq_t = (old & !(ERRNO_MASK | ERRSEQ_SEEN)) | neg_err;

        // Only increment if someone has looked at it.
        if old & ERRSEQ_SEEN != 0 {
            new = new.wrapping_add(ERRSEQ_CTR_INC);
        }

        // If there would be no change, then call it done.
        if new == old {
            cur = new;
            break;
        }

        // Try to swap the new value into place.
        // SAFETY: eseq is a valid pointer supplied by the C caller.
        let c = unsafe { cmpxchg(eseq, old, new) };

        // Success if we did the swap or someone else beat us to it
        // for the same value.
        if c == old || c == new {
            cur = c;
            break;
        }

        // Raced with an update, try again.
        old = c;
    }
    cur
}

/// errseq_sample() - Grab current errseq_t value.
#[no_mangle]
pub extern "C" fn errseq_sample(eseq: *mut errseq_t) -> errseq_t {
    // SAFETY: eseq is a valid pointer supplied by the C caller.
    let mut old: errseq_t = unsafe { read_once(eseq) };

    // If nobody has seen this error yet, then we can be the first.
    if old & ERRSEQ_SEEN == 0 {
        old = 0;
    }
    old
}

/// errseq_check() - Has an error occurred since a particular sample point?
///
/// Return: The latest error set in the errseq_t or 0 if it hasn't changed.
#[no_mangle]
pub extern "C" fn errseq_check(eseq: *mut errseq_t, since: errseq_t) -> c_int {
    // SAFETY: eseq is a valid pointer supplied by the C caller.
    let cur: errseq_t = unsafe { read_once(eseq) };

    if cur == since {
        return 0;
    }
    (cur & ERRNO_MASK).wrapping_neg() as c_int
}

/// errseq_check_and_advance() - Check an errseq_t and advance to current value.
///
/// Return: Negative errno if one has been stored, or 0 if no new error has
/// occurred.
#[no_mangle]
pub extern "C" fn errseq_check_and_advance(eseq: *mut errseq_t, since: *mut errseq_t) -> c_int {
    let mut err: c_int = 0;

    // SAFETY: eseq is a valid pointer supplied by the C caller.
    let mut old: errseq_t = unsafe { read_once(eseq) };

    // SAFETY: since is a valid pointer supplied by the C caller; the caller
    // is responsible for serializing updates to it.
    while old != unsafe { *since } {
        // Set the flag and try to swap it into place if it has changed.
        let new: errseq_t = old | ERRSEQ_SEEN;
        if new != old {
            // SAFETY: eseq is a valid pointer supplied by the C caller.
            let cur = unsafe { cmpxchg(eseq, old, new) };
            if cur != old {
                old = cur;
                continue;
            }
        }
        // SAFETY: since is a valid pointer supplied by the C caller.
        unsafe { *since = new };
        err = (new & ERRNO_MASK).wrapping_neg() as c_int;
        break;
    }
    err
}

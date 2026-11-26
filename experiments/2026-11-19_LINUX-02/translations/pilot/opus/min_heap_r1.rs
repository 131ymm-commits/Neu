// SPDX-License-Identifier: GPL-2.0
//! Rust translation of lib/min_heap.c (with the inline helpers from
//! include/linux/min_heap.h).

#![allow(non_camel_case_types)]
#![allow(clippy::missing_safety_doc)]

use core::ffi::{c_char, c_uint, c_ulong, c_void};
use core::ptr;
use core::sync::atomic::{AtomicBool, Ordering};

/* ------------------------------------------------------------------------ */
/* Types                                                                    */
/* ------------------------------------------------------------------------ */

/// `DEFINE_MIN_HEAP(char, min_heap_char)`
#[repr(C)]
pub struct min_heap_char {
    pub nr: usize,
    pub size: usize,
    pub data: *mut c_char,
    pub preallocated: [c_char; 0],
}

pub type LessFn = unsafe extern "C" fn(lhs: *const c_void, rhs: *const c_void, args: *mut c_void) -> bool;
pub type SwpFn = unsafe extern "C" fn(lhs: *mut c_void, rhs: *mut c_void, args: *mut c_void);

/// `struct min_heap_callbacks`
#[repr(C)]
pub struct min_heap_callbacks {
    pub less: Option<LessFn>,
    pub swp: Option<SwpFn>,
}

/* ------------------------------------------------------------------------ */
/* WARN_ONCE                                                                */
/* ------------------------------------------------------------------------ */

static WARN_POP: AtomicBool = AtomicBool::new(false);
static WARN_PUSH: AtomicBool = AtomicBool::new(false);
static WARN_DEL: AtomicBool = AtomicBool::new(false);

/// WARN_ONCE(cond, ...): emits a warning (once) and returns `cond`.
/// No logging facility is available here, so only the "once" state is kept.
#[inline(always)]
fn warn_once(cond: bool, flag: &AtomicBool) -> bool {
    if cond && !flag.load(Ordering::Relaxed) {
        flag.store(true, Ordering::Relaxed);
    }
    cond
}

/* ------------------------------------------------------------------------ */
/* Swap helpers                                                             */
/* ------------------------------------------------------------------------ */

#[derive(Clone, Copy)]
enum Swap {
    Words64,
    Words32,
    Bytes,
    Func(SwpFn),
}

/// is_aligned(): CONFIG_HAVE_EFFICIENT_UNALIGNED_ACCESS is set on x86_64,
/// so the base address is ignored.
#[inline(always)]
fn is_aligned(_base: *const c_void, size: usize, align: u8) -> bool {
    let lsbits: u8 = size as u8;
    (lsbits & align.wrapping_sub(1)) == 0
}

#[inline(always)]
fn select_swap_func(base: *const c_void, size: usize) -> Swap {
    if is_aligned(base, size, 8) {
        Swap::Words64
    } else if is_aligned(base, size, 4) {
        Swap::Words32
    } else {
        Swap::Bytes
    }
}

/// Mirrors `swp = func->swp; if (!swp) swp = select_swap_func(...)` followed
/// by the pointer-value comparisons done in do_swap().
#[inline(always)]
fn resolve_swap(swp: Option<SwpFn>, data: *const c_void, size: usize) -> Swap {
    match swp {
        None => select_swap_func(data, size),
        Some(f) => match f as usize {
            0 => Swap::Words64,
            1 => Swap::Words32,
            2 => Swap::Bytes,
            _ => Swap::Func(f),
        },
    }
}

#[inline(always)]
unsafe fn swap_words_32(a: *mut u8, b: *mut u8, mut n: usize) {
    loop {
        n = n.wrapping_sub(4);
        let pa = a.wrapping_add(n) as *mut u32;
        let pb = b.wrapping_add(n) as *mut u32;
        let t = pa.read_unaligned();
        pa.write_unaligned(pb.read_unaligned());
        pb.write_unaligned(t);
        if n == 0 {
            break;
        }
    }
}

#[inline(always)]
unsafe fn swap_words_64(a: *mut u8, b: *mut u8, mut n: usize) {
    loop {
        n = n.wrapping_sub(8);
        let pa = a.wrapping_add(n) as *mut u64;
        let pb = b.wrapping_add(n) as *mut u64;
        let t = pa.read_unaligned();
        pa.write_unaligned(pb.read_unaligned());
        pb.write_unaligned(t);
        if n == 0 {
            break;
        }
    }
}

#[inline(always)]
unsafe fn swap_bytes(a: *mut u8, b: *mut u8, mut n: usize) {
    loop {
        n = n.wrapping_sub(1);
        let pa = a.wrapping_add(n) as *mut c_char;
        let pb = b.wrapping_add(n) as *mut c_char;
        let t = pa.read();
        pa.write(pb.read());
        pb.write(t);
        if n == 0 {
            break;
        }
    }
}

#[inline(always)]
unsafe fn do_swap(a: *mut u8, b: *mut u8, size: usize, swap: Swap, priv_: *mut c_void) {
    match swap {
        Swap::Words64 => swap_words_64(a, b, size),
        Swap::Words32 => swap_words_32(a, b, size),
        Swap::Bytes => swap_bytes(a, b, size),
        Swap::Func(f) => f(a as *mut c_void, b as *mut c_void, priv_),
    }
}

/* ------------------------------------------------------------------------ */
/* Heap helpers                                                             */
/* ------------------------------------------------------------------------ */

#[inline(always)]
fn parent(i: usize, lsbit: c_uint, size: usize) -> usize {
    let mut i = i.wrapping_sub(size);
    i = i.wrapping_sub(size & (i & (lsbit as usize)).wrapping_neg());
    i / 2
}

#[inline(always)]
unsafe fn call_less(
    func: *const min_heap_callbacks,
    lhs: *mut u8,
    rhs: *mut u8,
    args: *mut c_void,
) -> bool {
    let f = (*func).less.expect("min_heap: NULL less callback");
    f(lhs as *const c_void, rhs as *const c_void, args)
}

#[inline(always)]
unsafe fn min_heap_init_inline(heap: *mut min_heap_char, data: *mut c_void, size: usize) {
    (*heap).nr = 0;
    (*heap).size = size;
    if !data.is_null() {
        (*heap).data = data as *mut c_char;
    } else {
        (*heap).data = ptr::addr_of_mut!((*heap).preallocated) as *mut c_char;
    }
}

#[inline(always)]
unsafe fn min_heap_peek_inline(heap: *mut min_heap_char) -> *mut c_void {
    if (*heap).nr != 0 {
        (*heap).data as *mut c_void
    } else {
        ptr::null_mut()
    }
}

#[inline(always)]
unsafe fn min_heap_full_inline(heap: *mut min_heap_char) -> bool {
    (*heap).nr == (*heap).size
}

#[inline(always)]
unsafe fn min_heap_sift_down_inline(
    heap: *mut min_heap_char,
    pos: usize,
    elem_size: usize,
    func: *const min_heap_callbacks,
    args: *mut c_void,
) {
    let lsbit: c_ulong = (elem_size & elem_size.wrapping_neg()) as c_ulong;
    let lsbit_u: c_uint = lsbit as c_uint;
    let data = (*heap).data as *mut u8;
    let swp_raw = (*func).swp;
    let a = pos.wrapping_mul(elem_size);
    let mut b: usize;
    let mut c: usize;
    let mut d: usize;
    let n = (*heap).nr.wrapping_mul(elem_size);

    let swp = resolve_swap(swp_raw, data as *const c_void, elem_size);

    /* Find the sift-down path all the way to the leaves. */
    b = a;
    loop {
        c = b.wrapping_mul(2).wrapping_add(elem_size);
        d = c.wrapping_add(elem_size);
        if d >= n {
            break;
        }
        b = if call_less(func, data.wrapping_add(c), data.wrapping_add(d), args) {
            c
        } else {
            d
        };
    }

    /* Special case for the last leaf with no sibling. */
    if d == n {
        b = c;
    }

    /* Backtrack to the correct location. */
    while b != a && call_less(func, data.wrapping_add(a), data.wrapping_add(b), args) {
        b = parent(b, lsbit_u, elem_size);
    }

    /* Shift the element into its correct place. */
    c = b;
    while b != a {
        b = parent(b, lsbit_u, elem_size);
        do_swap(data.wrapping_add(b), data.wrapping_add(c), elem_size, swp, args);
    }
}

#[inline(always)]
unsafe fn min_heap_sift_up_inline(
    heap: *mut min_heap_char,
    elem_size: usize,
    idx: usize,
    func: *const min_heap_callbacks,
    args: *mut c_void,
) {
    let lsbit: c_ulong = (elem_size & elem_size.wrapping_neg()) as c_ulong;
    let lsbit_u: c_uint = lsbit as c_uint;
    let data = (*heap).data as *mut u8;
    let swp_raw = (*func).swp;
    let mut a = idx.wrapping_mul(elem_size);

    let swp = resolve_swap(swp_raw, data as *const c_void, elem_size);

    while a != 0 {
        let b = parent(a, lsbit_u, elem_size);
        if call_less(func, data.wrapping_add(b), data.wrapping_add(a), args) {
            break;
        }
        do_swap(data.wrapping_add(a), data.wrapping_add(b), elem_size, swp, args);
        a = b;
    }
}

#[inline(always)]
unsafe fn min_heapify_all_inline(
    heap: *mut min_heap_char,
    elem_size: usize,
    func: *const min_heap_callbacks,
    args: *mut c_void,
) {
    let mut i: isize = ((*heap).nr / 2).wrapping_sub(1) as isize;
    while i >= 0 {
        min_heap_sift_down_inline(heap, i as usize, elem_size, func, args);
        i -= 1;
    }
}

#[inline(always)]
unsafe fn min_heap_pop_inline(
    heap: *mut min_heap_char,
    elem_size: usize,
    func: *const min_heap_callbacks,
    args: *mut c_void,
) -> bool {
    let data = (*heap).data as *mut u8;

    if warn_once((*heap).nr == 0, &WARN_POP) {
        return false;
    }

    /* Place last element at the root (position 0) and then sift down. */
    (*heap).nr = (*heap).nr.wrapping_sub(1);
    let src = data.wrapping_add((*heap).nr.wrapping_mul(elem_size));
    ptr::copy(src as *const u8, data, elem_size);
    min_heap_sift_down_inline(heap, 0, elem_size, func, args);

    true
}

#[inline(always)]
unsafe fn min_heap_pop_push_inline(
    heap: *mut min_heap_char,
    element: *const c_void,
    elem_size: usize,
    func: *const min_heap_callbacks,
    args: *mut c_void,
) {
    ptr::copy(element as *const u8, (*heap).data as *mut u8, elem_size);
    min_heap_sift_down_inline(heap, 0, elem_size, func, args);
}

#[inline(always)]
unsafe fn min_heap_push_inline(
    heap: *mut min_heap_char,
    element: *const c_void,
    elem_size: usize,
    func: *const min_heap_callbacks,
    args: *mut c_void,
) -> bool {
    let data = (*heap).data as *mut u8;

    if warn_once((*heap).nr >= (*heap).size, &WARN_PUSH) {
        return false;
    }

    /* Place at the end of data. */
    let pos = (*heap).nr;
    ptr::copy(
        element as *const u8,
        data.wrapping_add(pos.wrapping_mul(elem_size)),
        elem_size,
    );
    (*heap).nr = (*heap).nr.wrapping_add(1);

    /* Sift child at pos up. */
    min_heap_sift_up_inline(heap, elem_size, pos, func, args);

    true
}

#[inline(always)]
unsafe fn min_heap_del_inline(
    heap: *mut min_heap_char,
    elem_size: usize,
    idx: usize,
    func: *const min_heap_callbacks,
    args: *mut c_void,
) -> bool {
    let data = (*heap).data as *mut u8;
    let swp_raw = (*func).swp;

    if warn_once((*heap).nr == 0, &WARN_DEL) {
        return false;
    }

    let swp = resolve_swap(swp_raw, data as *const c_void, elem_size);

    /* Place last element at the root (position 0) and then sift down. */
    (*heap).nr = (*heap).nr.wrapping_sub(1);
    if idx == (*heap).nr {
        return true;
    }
    do_swap(
        data.wrapping_add(idx.wrapping_mul(elem_size)),
        data.wrapping_add((*heap).nr.wrapping_mul(elem_size)),
        elem_size,
        swp,
        args,
    );
    min_heap_sift_up_inline(heap, elem_size, idx, func, args);
    min_heap_sift_down_inline(heap, idx, elem_size, func, args);

    true
}

/* ------------------------------------------------------------------------ */
/* Exported functions                                                       */
/* ------------------------------------------------------------------------ */

#[no_mangle]
pub extern "C" fn __min_heap_init(heap: *mut min_heap_char, data: *mut c_void, size: usize) {
    unsafe { min_heap_init_inline(heap, data, size) }
}

#[no_mangle]
pub extern "C" fn __min_heap_peek(heap: *mut min_heap_char) -> *mut c_void {
    unsafe { min_heap_peek_inline(heap) }
}

#[no_mangle]
pub extern "C" fn __min_heap_full(heap: *mut min_heap_char) -> bool {
    unsafe { min_heap_full_inline(heap) }
}

#[no_mangle]
pub extern "C" fn __min_heap_sift_down(
    heap: *mut min_heap_char,
    pos: usize,
    elem_size: usize,
    func: *const min_heap_callbacks,
    args: *mut c_void,
) {
    unsafe { min_heap_sift_down_inline(heap, pos, elem_size, func, args) }
}

#[no_mangle]
pub extern "C" fn __min_heap_sift_up(
    heap: *mut min_heap_char,
    elem_size: usize,
    idx: usize,
    func: *const min_heap_callbacks,
    args: *mut c_void,
) {
    unsafe { min_heap_sift_up_inline(heap, elem_size, idx, func, args) }
}

#[no_mangle]
pub extern "C" fn __min_heapify_all(
    heap: *mut min_heap_char,
    elem_size: usize,
    func: *const min_heap_callbacks,
    args: *mut c_void,
) {
    unsafe { min_heapify_all_inline(heap, elem_size, func, args) }
}

#[no_mangle]
pub extern "C" fn __min_heap_pop(
    heap: *mut min_heap_char,
    elem_size: usize,
    func: *const min_heap_callbacks,
    args: *mut c_void,
) -> bool {
    unsafe { min_heap_pop_inline(heap, elem_size, func, args) }
}

#[no_mangle]
pub extern "C" fn __min_heap_pop_push(
    heap: *mut min_heap_char,
    element: *const c_void,
    elem_size: usize,
    func: *const min_heap_callbacks,
    args: *mut c_void,
) {
    unsafe { min_heap_pop_push_inline(heap, element, elem_size, func, args) }
}

#[no_mangle]
pub extern "C" fn __min_heap_push(
    heap: *mut min_heap_char,
    element: *const c_void,
    elem_size: usize,
    func: *const min_heap_callbacks,
    args: *mut c_void,
) -> bool {
    unsafe { min_heap_push_inline(heap, element, elem_size, func, args) }
}

#[no_mangle]
pub extern "C" fn __min_heap_del(
    heap: *mut min_heap_char,
    elem_size: usize,
    idx: usize,
    func: *const min_heap_callbacks,
    args: *mut c_void,
) -> bool {
    unsafe { min_heap_del_inline(heap, elem_size, idx, func, args) }
}

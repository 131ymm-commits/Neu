// SPDX-License-Identifier: GPL-2.0
//! Rust translation of lib/min_heap.c (with the inline helpers of
//! include/linux/min_heap.h).

use core::ffi::{c_ulong, c_void};
use core::sync::atomic::{AtomicBool, Ordering};

type LessFn = unsafe extern "C" fn(lhs: *const c_void, rhs: *const c_void, args: *mut c_void) -> bool;
type SwapFn = unsafe extern "C" fn(lhs: *mut c_void, rhs: *mut c_void, args: *mut c_void);

/// `DEFINE_MIN_HEAP(char, min_heap_char)`
#[repr(C)]
pub struct min_heap_char {
    pub nr: usize,
    pub size: usize,
    pub data: *mut u8,
    pub preallocated: [u8; 0],
}

/// `struct min_heap_callbacks`
#[repr(C)]
pub struct min_heap_callbacks {
    pub less: Option<LessFn>,
    pub swp: Option<SwapFn>,
}

/* Sentinel "swap function" values, as in the C header. */
const SWAP_WORDS_64: usize = 0;
const SWAP_WORDS_32: usize = 1;
const SWAP_BYTES: usize = 2;

static WARN_POP: AtomicBool = AtomicBool::new(false);
static WARN_PUSH: AtomicBool = AtomicBool::new(false);
static WARN_DEL: AtomicBool = AtomicBool::new(false);

/// WARN_ONCE(cond, ...): emits a warning once per call site, returns `cond`.
/// No logging facility is available here, so only the once-semantics are kept.
#[inline(always)]
fn warn_once(flag: &AtomicBool, cond: bool) -> bool {
    if cond && !flag.swap(true, Ordering::Relaxed) {
        /* warning would be printed here */
    }
    cond
}

#[inline(always)]
fn is_aligned(base: *const u8, size: usize, align: u8) -> bool {
    let lsbits = size as u8;
    let _ = base;
    /* CONFIG_HAVE_EFFICIENT_UNALIGNED_ACCESS: base is not taken into account */
    (lsbits & align.wrapping_sub(1)) == 0
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
        let pa = a.wrapping_add(n);
        let pb = b.wrapping_add(n);
        let t = *pa;
        *pa = *pb;
        *pb = t;
        if n == 0 {
            break;
        }
    }
}

#[inline(always)]
fn select_swap_func(base: *const u8, size: usize) -> usize {
    if is_aligned(base, size, 8) {
        SWAP_WORDS_64
    } else if is_aligned(base, size, 4) {
        SWAP_WORDS_32
    } else {
        SWAP_BYTES
    }
}

#[inline(always)]
unsafe fn do_swap(a: *mut u8, b: *mut u8, size: usize, swap_func: usize, priv_: *mut c_void) {
    if swap_func == SWAP_WORDS_64 {
        swap_words_64(a, b, size);
    } else if swap_func == SWAP_WORDS_32 {
        swap_words_32(a, b, size);
    } else if swap_func == SWAP_BYTES {
        swap_bytes(a, b, size);
    } else {
        // swap_func is a non-null function pointer value supplied by the caller.
        let f: SwapFn = core::mem::transmute::<usize, SwapFn>(swap_func);
        f(a as *mut c_void, b as *mut c_void, priv_);
    }
}

#[inline(always)]
fn parent(i: usize, lsbit: u32, size: usize) -> usize {
    let i = i.wrapping_sub(size);
    let i = i.wrapping_sub(size & (i & lsbit as usize).wrapping_neg());
    i / 2
}

#[inline(always)]
unsafe fn call_less(func: *const min_heap_callbacks, a: *const u8, b: *const u8, args: *mut c_void) -> bool {
    let less = (*func).less.unwrap();
    less(a as *const c_void, b as *const c_void, args)
}

#[inline(always)]
unsafe fn swp_value(func: *const min_heap_callbacks) -> usize {
    match (*func).swp {
        Some(f) => f as usize,
        None => 0,
    }
}

#[inline(always)]
unsafe fn min_heap_init_inline(heap: *mut min_heap_char, data: *mut c_void, size: usize) {
    (*heap).nr = 0;
    (*heap).size = size;
    if !data.is_null() {
        (*heap).data = data as *mut u8;
    } else {
        (*heap).data = core::ptr::addr_of_mut!((*heap).preallocated) as *mut u8;
    }
}

#[inline(always)]
unsafe fn min_heap_peek_inline(heap: *mut min_heap_char) -> *mut c_void {
    if (*heap).nr != 0 {
        (*heap).data as *mut c_void
    } else {
        core::ptr::null_mut()
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
    let data = (*heap).data;
    let mut swp = swp_value(func);
    let a = pos.wrapping_mul(elem_size);
    let mut b: usize;
    let mut c: usize;
    let mut d: usize;
    let n = (*heap).nr.wrapping_mul(elem_size);

    if swp == 0 {
        swp = select_swap_func(data, elem_size);
    }

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
        b = parent(b, lsbit as u32, elem_size);
    }

    /* Shift the element into its correct place. */
    c = b;
    while b != a {
        b = parent(b, lsbit as u32, elem_size);
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
    let data = (*heap).data;
    let mut swp = swp_value(func);
    let mut a = idx.wrapping_mul(elem_size);
    let mut b: usize;

    if swp == 0 {
        swp = select_swap_func(data, elem_size);
    }

    while a != 0 {
        b = parent(a, lsbit as u32, elem_size);
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
    let data = (*heap).data;

    if warn_once(&WARN_POP, (*heap).nr == 0) {
        return false;
    }

    /* Place last element at the root (position 0) and then sift down. */
    (*heap).nr = (*heap).nr.wrapping_sub(1);
    core::ptr::copy(
        data.wrapping_add((*heap).nr.wrapping_mul(elem_size)) as *const u8,
        data,
        elem_size,
    );
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
    core::ptr::copy(element as *const u8, (*heap).data, elem_size);
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
    let data = (*heap).data;

    if warn_once(&WARN_PUSH, (*heap).nr >= (*heap).size) {
        return false;
    }

    /* Place at the end of data. */
    let pos = (*heap).nr;
    core::ptr::copy(
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
    let data = (*heap).data;
    let mut swp = swp_value(func);

    if warn_once(&WARN_DEL, (*heap).nr == 0) {
        return false;
    }

    if swp == 0 {
        swp = select_swap_func(data, elem_size);
    }

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

/* ---------------- exported functions ---------------- */

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
